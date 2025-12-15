"""
Traffic Pattern Analyzer - FIXED VERSION
Analyzes traffic logs and stores patterns in database using simulation time intervals (0-100)
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
import statistics
import json
import uuid

from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficPattern
from app.services.db_queue import db_queue_service


class TrafficPatternAnalyzer:
    """
    Analyzes traffic logs and identifies patterns using simulation time intervals (0-100)
    """
    
    def __init__(self, app=None):
        self.app = app
        # FIXED: Use 500-second intervals to capture more logs per interval
        # With logging every 30-60 seconds, 500s interval will have ~8-16 logs
        self.simulation_interval_size = 150  # 150-second intervals (0-150, 150-300, etc.)
        self.min_samples_for_pattern = 3
        self.pattern_cache = {}
        self.auto_analysis_enabled = False
        self.verbose_logging = True  # Set to False to reduce console output
        
        # Real-time scheduling for automatic analysis
        self.analysis_thread = None
        self.analysis_running = False
        self.last_analysis_time = 0
        self.real_time_analysis_interval = 900  # 15 minutes in real-time seconds
        
        # Track analysis history
        self.analysis_history = deque(maxlen=100)
        
        # Add deferred analysis mode
        self.deferred_mode = False
        self.pending_analysis_queue = []
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self.start_auto_analysis()
        
    def start_auto_analysis(self):
        """Start the automatic analysis thread"""
        if self.analysis_running:
            return
            
        self.analysis_running = True
        self.analysis_thread = threading.Thread(
            target=self._auto_analysis_loop,
            daemon=True,
            name="PatternAnalyzer-Auto"
        )
        self.analysis_thread.start()
        print("✅ Automatic pattern analysis STARTED - running every 15 real-time minutes")
    
    def stop_auto_analysis(self):
        """Stop the automatic analysis thread"""
        self.analysis_running = False
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=5.0)
        print("✅ Automatic pattern analysis STOPPED")
    
    def _auto_analysis_loop(self):
        """Main loop for automatic pattern analysis"""
        while self.analysis_running:
            try:
                current_time = time.time()
                
                # Check if it's time for analysis (every 15 real-time minutes)
                if current_time - self.last_analysis_time >= self.real_time_analysis_interval:
                    if self.auto_analysis_enabled:
                        self._perform_auto_analysis()
                    self.last_analysis_time = current_time
                
                # Sleep for 30 seconds before checking again
                time.sleep(30)
                
            except Exception as e:
                print(f"❌ Auto-analysis loop error: {e}")
                time.sleep(60)
    
    def _perform_auto_analysis(self):
        """Perform automatic pattern analysis on all traffic logs"""
        try:
            print(f"🕒 AUTO-PATTERN: Starting automatic analysis at {datetime.now().strftime('%H:%M:%S')}")
            
            with self.app.app_context():
                # Get ALL traffic logs from database
                all_logs = TrafficLightLog.query.order_by(
                    TrafficLightLog.scenario, 
                    TrafficLightLog.traffic_light_id,
                    TrafficLightLog.simulation_time
                ).all()
                
                if not all_logs:
                    print("🕒 AUTO-PATTERN: No traffic logs found")
                    return
                
                print(f"🕒 AUTO-PATTERN: Found {len(all_logs)} total logs in database")
                
                # Group logs by scenario
                logs_by_scenario = self._group_logs_by_scenario(all_logs)
                
                total_patterns = 0
                analysis_results = []
                
                for scenario, scenario_logs in logs_by_scenario.items():
                    print(f"🕒 AUTO-PATTERN: Analyzing scenario '{scenario}' with {len(scenario_logs)} logs")
                    
                    # Analyze this scenario using simulation time intervals
                    scenario_patterns = self._analyze_scenario_by_intervals(scenario, scenario_logs)
                    total_patterns += scenario_patterns
                    
                    analysis_results.append({
                        'scenario': scenario,
                        'logs_analyzed': len(scenario_logs),
                        'patterns_found': scenario_patterns
                    })
                
                result = {
                    "analysis_time": datetime.utcnow().isoformat(),
                    "total_logs_analyzed": len(all_logs),
                    "total_patterns_found": total_patterns,
                    "scenarios_analyzed": len(logs_by_scenario),
                    "scenario_results": analysis_results,
                    "analysis_type": "AUTO_ALL_LOGS"
                }
                
                self.analysis_history.append(result)
                print(f"✅ AUTO-PATTERN: Analysis complete - {total_patterns} patterns found/updated from {len(all_logs)} logs")
                
        except Exception as e:
            print(f"❌ Auto-analysis error: {e}")
            import traceback
            traceback.print_exc()
    
    def _analyze_scenario_by_intervals(self, scenario: str, logs: List[TrafficLightLog]) -> int:
        """
        FIXED: Analyze logs for a scenario using simulation time intervals (0-500, 500-1000, etc.)
        """
        if not logs:
            return 0
        
        # Group logs by traffic light
        logs_by_tl = self._group_logs_by_traffic_light(logs)
        if self.verbose_logging:
            print(f"   📍 Found {len(logs_by_tl)} traffic lights in scenario '{scenario}'")
        
        patterns_created_or_updated = 0
        
        for tl_id, tl_logs in logs_by_tl.items():
            # FIXED: Group logs by simulation time intervals
            interval_groups = self._group_logs_by_simulation_intervals(tl_logs)
            
            if self.verbose_logging:
                print(f"   📍 TL '{tl_id}': {len(tl_logs)} logs grouped into {len(interval_groups)} intervals")
            
            for interval_start, interval_logs in interval_groups.items():
                if self.verbose_logging:
                    print(f"      ⏱️  Interval {interval_start}-{interval_start + self.simulation_interval_size}: {len(interval_logs)} logs (min required: {self.min_samples_for_pattern})")
                
                if len(interval_logs) >= self.min_samples_for_pattern:
                    interval_end = interval_start + self.simulation_interval_size
                    
                    # FIXED: Create or update pattern (no duplicates)
                    pattern = self._create_or_update_pattern(
                        tl_id, interval_logs, interval_start, interval_end, scenario
                    )
                    if pattern:
                        patterns_created_or_updated += 1
                elif self.verbose_logging:
                    print(f"      ⚠️  Skipping interval {interval_start}: insufficient samples ({len(interval_logs)} < {self.min_samples_for_pattern})")
        
        return patterns_created_or_updated
    
    def _group_logs_by_simulation_intervals(self, logs: List[TrafficLightLog]) -> Dict[float, List[TrafficLightLog]]:
        """
        FIXED: Group logs by simulation time intervals
        """
        interval_groups = defaultdict(list)
        
        # Debug: Check simulation times
        sim_times = []
        null_count = 0
        
        for log in logs:
            if log.simulation_time is not None:
                sim_times.append(log.simulation_time)
                # Calculate interval start (0, 500, 1000, etc.)
                interval_start = (int(log.simulation_time) // self.simulation_interval_size) * self.simulation_interval_size
                interval_groups[interval_start].append(log)
            else:
                null_count += 1
        
        if self.verbose_logging and sim_times:
            print(f"      📊 Simulation time range: {min(sim_times):.1f} - {max(sim_times):.1f}")
            if null_count > 0:
                print(f"      ⚠️  {null_count} logs with null simulation_time")
        elif self.verbose_logging:
            print(f"      ❌ ALL logs have null simulation_time!")
        
        return interval_groups
    
    def _create_or_update_pattern(self, tl_id: str, logs: List[TrafficLightLog], 
                                   interval_start: float, interval_end: float, 
                                   scenario: str) -> Optional[TrafficPattern]:
        """
        FIXED: Create new pattern or update existing pattern (avoid duplicates)
        """
        try:
            # Check if pattern already exists for this TL, scenario, and interval
            existing_pattern = TrafficPattern.query.filter_by(
                traffic_light_id=tl_id,
                scenario=scenario,
                interval_start=interval_start,
                interval_end=interval_end
            ).first()
            
            # Calculate metrics
            metrics = self._calculate_metrics(logs)
            pattern_type = self._identify_pattern_type(metrics)
            best_action = self._determine_best_action(logs)
            confidence = self._calculate_confidence(metrics, len(logs))
            recommendations = self._generate_recommendations(metrics, pattern_type)
            
            if existing_pattern:
                # UPDATE existing pattern
                print(f"🔄 Updating existing pattern for {tl_id} interval {interval_start}-{interval_end}")
                existing_pattern.pattern_type = pattern_type
                existing_pattern.pattern_metrics = metrics
                existing_pattern.best_action = best_action
                existing_pattern.action_success_rate = self._calculate_success_rate(logs, best_action)
                existing_pattern.confidence_score = confidence
                existing_pattern.sample_size = len(logs)
                existing_pattern.recommendations = recommendations
                existing_pattern.updated_at = datetime.utcnow()
                
                db.session.commit()
                print(f"✅ Pattern updated for {tl_id}: {pattern_type} (confidence: {confidence:.2f})")
                return existing_pattern
            else:
                # CREATE new pattern
                print(f"➕ Creating new pattern for {tl_id} interval {interval_start}-{interval_end}")
                pattern = TrafficPattern(
                    id=str(uuid.uuid4()),
                    traffic_light_id=tl_id,
                    scenario=scenario,
                    interval_start=interval_start,  # FIXED: Store as integer
                    interval_end=interval_end,      # FIXED: Store as integer
                    pattern_type=pattern_type,
                    pattern_metrics=metrics,
                    best_action=best_action,
                    action_success_rate=self._calculate_success_rate(logs, best_action),
                    confidence_score=confidence,
                    sample_size=len(logs),
                    recommendations=recommendations
                )
                
                db.session.add(pattern)
                db.session.commit()
                print(f"📊 Pattern created for {tl_id}: {pattern_type} (confidence: {confidence:.2f})")
                return pattern
            
        except Exception as e:
            print(f"❌ Error creating/updating pattern for {tl_id}: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return None
    
    def _group_logs_by_scenario(self, logs: List[TrafficLightLog]) -> Dict[str, List[TrafficLightLog]]:
        """Group logs by scenario"""
        grouped = defaultdict(list)
        for log in logs:
            grouped[log.scenario].append(log)
        return grouped
    
    def _group_logs_by_traffic_light(self, logs: List[TrafficLightLog]) -> Dict[str, List[TrafficLightLog]]:
        """Group logs by traffic light ID"""
        grouped = defaultdict(list)
        for log in logs:
            grouped[log.traffic_light_id].append(log)
        return grouped
    
    def analyze_recent_traffic_patterns(self, minutes: int = 15, scenario: str = None) -> Dict[str, Any]:
        """
        Manually analyze recent traffic patterns (by created_at timestamp)
        """
        if not self.app:
            return {"error": "Service not initialized with app context"}
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=minutes)
            
            print(f"🔍 Analyzing recent traffic patterns from {start_time} to {end_time}")
            
            with self.app.app_context():
                query = TrafficLightLog.query.filter(
                    TrafficLightLog.created_at >= start_time,
                    TrafficLightLog.created_at <= end_time
                )
                
                if scenario:
                    query = query.filter(TrafficLightLog.scenario == scenario)
                
                logs = query.order_by(TrafficLightLog.simulation_time).all()
                
                if not logs:
                    return {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "patterns_found": 0,
                        "message": f"No traffic logs found for the last {minutes} minutes",
                        "analysis_type": "MANUAL"
                    }
                
                # Group by scenario and analyze
                logs_by_scenario = self._group_logs_by_scenario(logs)
                total_patterns = 0
                scenario_results = {}
                
                for scenario_name, scenario_logs in logs_by_scenario.items():
                    patterns = self._analyze_scenario_by_intervals(scenario_name, scenario_logs)
                    total_patterns += patterns
                    scenario_results[scenario_name] = {
                        'patterns_found': patterns,
                        'logs_analyzed': len(scenario_logs)
                    }
                
                result = {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "time_window_minutes": minutes,
                    "patterns_found": total_patterns,
                    "total_logs_analyzed": len(logs),
                    "scenario_results": scenario_results,
                    "analysis_type": "MANUAL",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                print(f"✅ Manual Analysis: {total_patterns} patterns found/updated from {len(logs)} logs")
                return result
                
        except Exception as e:
            print(f"❌ Error analyzing recent traffic patterns: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Pattern analysis failed: {str(e)}"}
    
    def force_immediate_analysis(self, scenario: str = None) -> Dict[str, Any]:
        """Force an immediate pattern analysis on all logs"""
        print("🚀 Forcing immediate pattern analysis...")
        
        if self.deferred_mode:
            # Queue for later instead of running now
            self.pending_analysis_queue.append({
                'scenario': scenario,
                'timestamp': time.time()
            })
            return {"status": "deferred", "queued": True}
        
        try:
            with self.app.app_context():
                query = TrafficLightLog.query.order_by(
                    TrafficLightLog.scenario,
                    TrafficLightLog.traffic_light_id,
                    TrafficLightLog.simulation_time
                )
                
                if scenario:
                    query = query.filter(TrafficLightLog.scenario == scenario)
                
                all_logs = query.all()
                
                if not all_logs:
                    return {"error": "No logs found", "patterns_found": 0}
                
                logs_by_scenario = self._group_logs_by_scenario(all_logs)
                total_patterns = 0
                
                for scenario_name, scenario_logs in logs_by_scenario.items():
                    patterns = self._analyze_scenario_by_intervals(scenario_name, scenario_logs)
                    total_patterns += patterns
                
                return {
                    "total_logs_analyzed": len(all_logs),
                    "patterns_found": total_patterns,
                    "analysis_type": "FORCED_IMMEDIATE",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            print(f"❌ Forced analysis error: {e}")
            return {"error": str(e)}
    
    def process_deferred_analysis(self):
        """Run all deferred analysis after simulation"""
        print(f"🔄 Processing {len(self.pending_analysis_queue)} deferred analyses")
        results = []
        
        for queued_item in self.pending_analysis_queue:
            result = self._perform_auto_analysis()
            results.append(result)
        
        self.pending_analysis_queue.clear()
        return results
    
    def get_patterns_for_interval(self, scenario: str, interval_start: int, interval_end: int) -> Dict[str, Any]:
        """Get all patterns for a specific simulation time interval"""
        with self.app.app_context():
            patterns = TrafficPattern.query.filter(
                TrafficPattern.scenario == scenario,
                TrafficPattern.interval_start == interval_start,
                TrafficPattern.interval_end == interval_end
            ).all()
            
            return {
                'interval_start': interval_start,
                'interval_end': interval_end,
                'scenario': scenario,
                'patterns': [
                    {
                        'id': pattern.id,
                        'traffic_light_id': pattern.traffic_light_id,
                        'pattern_type': pattern.pattern_type,
                        'best_action': pattern.best_action,
                        'confidence': pattern.confidence_score,
                        'sample_size': pattern.sample_size,
                        'created_at': pattern.created_at.isoformat(),
                        'updated_at': pattern.updated_at.isoformat()
                    }
                    for pattern in patterns
                ],
                'total_patterns': len(patterns)
            }
    
    def get_traffic_light_patterns(self, tl_id: str, scenario: str) -> Dict[str, Any]:
        """Get all patterns for a specific traffic light"""
        with self.app.app_context():
            patterns = TrafficPattern.query.filter(
                TrafficPattern.traffic_light_id == tl_id,
                TrafficPattern.scenario == scenario
            ).order_by(TrafficPattern.interval_start).all()
            
            return {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'patterns': [
                    {
                        'interval_start': pattern.interval_start,
                        'interval_end': pattern.interval_end,
                        'pattern_type': pattern.pattern_type,
                        'best_action': pattern.best_action,
                        'confidence': pattern.confidence_score,
                        'sample_size': pattern.sample_size,
                        'recommendations': pattern.recommendations
                    }
                    for pattern in patterns
                ],
                'total_patterns': len(patterns)
            }
    
    def set_interval_size(self, size: int):
        """
        Set the simulation interval size dynamically
        Recommended sizes based on logging frequency:
        - 100s: if logging every 5-10 seconds (dense logging)
        - 300s: if logging every 20-30 seconds (medium logging)  
        - 500s: if logging every 30-60 seconds (sparse logging)
        - 1000s: if logging every 60+ seconds (very sparse)
        """
        old_size = self.simulation_interval_size
        self.simulation_interval_size = max(100, size)
        print(f"✅ Simulation interval size changed from {old_size}s to {self.simulation_interval_size}s")
        return {
            "old_interval_size": old_size,
            "new_interval_size": self.simulation_interval_size,
            "recommendation": f"With current logging frequency, expect ~{self._estimate_logs_per_interval()} logs per interval"
        }
    
    def _estimate_logs_per_interval(self) -> str:
        """Estimate logs per interval based on typical logging patterns"""
        # Assuming 30-60 second logging frequency
        avg_logging_freq = 45  # seconds
        logs_per_interval = self.simulation_interval_size / avg_logging_freq
        return f"{int(logs_per_interval)}-{int(logs_per_interval * 1.5)}"
    
    def analyze_data_density(self, scenario: str = None) -> Dict[str, Any]:
        """
        Analyze the density of logged data to recommend optimal interval size
        """
        if not self.app:
            return {"error": "Service not initialized"}
        
        try:
            with self.app.app_context():
                query = TrafficLightLog.query
                if scenario:
                    query = query.filter(TrafficLightLog.scenario == scenario)
                
                logs = query.order_by(TrafficLightLog.simulation_time).all()
                
                if len(logs) < 2:
                    return {"error": "Insufficient data for analysis"}
                
                # Calculate time gaps between consecutive logs
                time_gaps = []
                for i in range(1, len(logs)):
                    if logs[i].simulation_time and logs[i-1].simulation_time:
                        gap = logs[i].simulation_time - logs[i-1].simulation_time
                        if gap > 0:  # Only positive gaps
                            time_gaps.append(gap)
                
                if not time_gaps:
                    return {"error": "No valid time gaps found"}
                
                avg_gap = statistics.mean(time_gaps)
                median_gap = statistics.median(time_gaps)
                min_gap = min(time_gaps)
                max_gap = max(time_gaps)
                
                # Recommend interval size (should be 10-20x the average gap)
                recommended_interval = int(avg_gap * 15)
                # Round to nearest 100
                recommended_interval = round(recommended_interval / 100) * 100
                recommended_interval = max(100, min(1000, recommended_interval))
                
                # Calculate expected logs per interval
                expected_logs = recommended_interval / avg_gap
                
                return {
                    "total_logs": len(logs),
                    "logging_frequency": {
                        "average_gap_seconds": round(avg_gap, 1),
                        "median_gap_seconds": round(median_gap, 1),
                        "min_gap_seconds": round(min_gap, 1),
                        "max_gap_seconds": round(max_gap, 1)
                    },
                    "current_settings": {
                        "interval_size": self.simulation_interval_size,
                        "min_samples": self.min_samples_for_pattern,
                        "expected_logs_per_interval": round(self.simulation_interval_size / avg_gap, 1)
                    },
                    "recommendation": {
                        "recommended_interval_size": recommended_interval,
                        "expected_logs_per_interval": round(expected_logs, 1),
                        "reasoning": f"Based on avg logging every {round(avg_gap, 1)}s, {recommended_interval}s intervals will capture ~{round(expected_logs, 1)} logs"
                    }
                }
                
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
        """Enable automatic pattern analysis"""
        self.auto_analysis_enabled = True
        if not self.analysis_running:
            self.start_auto_analysis()
        print("✅ Automatic pattern analysis ENABLED")
    
    def disable_auto_analysis(self):
        """Disable automatic pattern analysis"""
        self.auto_analysis_enabled = False
        print("⏸️ Automatic pattern analysis DISABLED")
    
    def get_analysis_status(self) -> Dict[str, Any]:
        """Get current analysis status"""
        return {
            "auto_analysis_enabled": self.auto_analysis_enabled,
            "analysis_running": self.analysis_running,
            "simulation_interval_size": self.simulation_interval_size,
            "min_samples_for_pattern": self.min_samples_for_pattern,
            "real_time_interval_minutes": self.real_time_analysis_interval / 60,
            "analysis_history_count": len(self.analysis_history),
            "last_analysis_time": datetime.fromtimestamp(self.last_analysis_time).isoformat() if self.last_analysis_time > 0 else "Never"
        }
    
    # ==================== CALCULATION METHODS ====================
    
    def _calculate_metrics(self, logs: List[TrafficLightLog]) -> Dict[str, Any]:
        """Calculate comprehensive metrics from logs"""
        efficiencies = [log.efficiency_score for log in logs if log.efficiency_score is not None]
        waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
        vehicle_counts = [log.vehicle_count for log in logs if log.vehicle_count is not None]
        
        # Phase analysis
        phases = defaultdict(list)
        for log in logs:
            if log.phase_name and log.waiting_vehicles is not None:
                phases[log.phase_name].append(log.waiting_vehicles)
        
        phase_efficiency = {}
        for phase_name, waiting_list in phases.items():
            if waiting_list:
                phase_efficiency[phase_name] = {
                    'avg_waiting': statistics.mean(waiting_list),
                    'max_waiting': max(waiting_list),
                    'min_waiting': min(waiting_list),
                    'sample_count': len(waiting_list)
                }
        
        return {
            'efficiency': {
                'average': statistics.mean(efficiencies) if efficiencies else 0,
                'std_dev': statistics.stdev(efficiencies) if len(efficiencies) > 1 else 0,
                'min': min(efficiencies) if efficiencies else 0,
                'max': max(efficiencies) if efficiencies else 0,
                'trend': self._calculate_trend(efficiencies)
            },
            'congestion': {
                'average_waiting': statistics.mean(waiting_vehicles) if waiting_vehicles else 0,
                'peak_waiting': max(waiting_vehicles) if waiting_vehicles else 0,
                'congestion_frequency': len([w for w in waiting_vehicles if w > 5]) / len(waiting_vehicles) if waiting_vehicles else 0
            },
            'volume': {
                'average_volume': statistics.mean(vehicle_counts) if vehicle_counts else 0,
                'peak_volume': max(vehicle_counts) if vehicle_counts else 0
            },
            'phases': phase_efficiency,
            'stability': {
                'efficiency_consistency': 1 - (statistics.stdev(efficiencies) / statistics.mean(efficiencies)) if efficiencies and statistics.mean(efficiencies) > 0 else 1,
                'waiting_consistency': 1 - (statistics.stdev(waiting_vehicles) / statistics.mean(waiting_vehicles)) if waiting_vehicles and statistics.mean(waiting_vehicles) > 0 else 1
            }
        }
    
    def _identify_pattern_type(self, metrics: Dict[str, Any]) -> str:
        """Identify the type of traffic pattern"""
        avg_efficiency = metrics['efficiency']['average']
        avg_waiting = metrics['congestion']['average_waiting']
        congestion_freq = metrics['congestion']['congestion_frequency']
        
        if avg_efficiency > 80 and avg_waiting < 3:
            return 'OPTIMAL_FLOW'
        elif avg_efficiency > 65 and avg_waiting < 6:
            return 'STABLE_FLOW'
        elif congestion_freq > 0.3 or avg_waiting > 8:
            return 'CONGESTED'
        elif metrics['efficiency']['trend'] == 'IMPROVING':
            return 'IMPROVING_FLOW'
        elif metrics['efficiency']['trend'] == 'DECLINING':
            return 'DEGRADING_FLOW'
        else:
            return 'VARIABLE_FLOW'
    
    def _determine_best_action(self, logs: List[TrafficLightLog]) -> str:
        """Determine the best action based on historical performance"""
        waiting_values = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
        efficiency_values = [log.efficiency_score for log in logs if log.efficiency_score is not None]
        
        if not waiting_values or not efficiency_values:
            return 'MAINTAIN'
        
        avg_waiting = statistics.mean(waiting_values)
        avg_efficiency = statistics.mean(efficiency_values)
        
        if avg_waiting > 8 and avg_efficiency < 60:
            return 'EXTEND_GREEN'
        elif avg_waiting < 2 and avg_efficiency > 80:
            return 'REDUCE_GREEN'
        else:
            return 'MAINTAIN'
    
    def _calculate_success_rate(self, logs: List[TrafficLightLog], action: str) -> float:
        """Calculate success rate for the recommended action"""
        waiting_values = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
        if not waiting_values:
            return 0.5
        
        avg_waiting = statistics.mean(waiting_values)
        
        if action == 'EXTEND_GREEN' and avg_waiting > 5:
            return 0.8
        elif action == 'REDUCE_GREEN' and avg_waiting < 3:
            return 0.7
        elif action == 'MAINTAIN':
            return 0.9
        else:
            return 0.5
    
    def _calculate_confidence(self, metrics: Dict[str, Any], sample_size: int) -> float:
        """Calculate confidence score for the pattern"""
        base_confidence = min(1.0, sample_size / 20)
        stability = metrics['stability']['efficiency_consistency']
        confidence = (base_confidence * 0.6) + (stability * 0.4)
        return round(confidence, 2)
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend of values"""
        if len(values) < 2:
            return 'STABLE'
        
        first_quarter = values[:len(values)//4] if len(values) >= 4 else values[:1]
        last_quarter = values[-len(values)//4:] if len(values) >= 4 else values[-1:]
        
        if not first_quarter or not last_quarter:
            return 'STABLE'
        
        first_avg = statistics.mean(first_quarter)
        last_avg = statistics.mean(last_quarter)
        
        if last_avg > first_avg + 5:
            return 'IMPROVING'
        elif last_avg < first_avg - 5:
            return 'DECLINING'
        else:
            return 'STABLE'
    
    def _generate_recommendations(self, metrics: Dict[str, Any], pattern_type: str) -> List[str]:
        """Generate recommendations based on pattern analysis"""
        recommendations = []
        avg_waiting = metrics['congestion']['average_waiting']
        avg_efficiency = metrics['efficiency']['average']
        
        if pattern_type == 'CONGESTED':
            recommendations.append("High congestion detected - consider optimizing phase timing")
            if avg_efficiency < 60:
                recommendations.append("Low efficiency - review traffic light program")
        elif pattern_type == 'OPTIMAL_FLOW':
            recommendations.append("Traffic flow is optimal - maintain current configuration")
        elif pattern_type == 'DEGRADING_FLOW':
            recommendations.append("Traffic flow is degrading - investigate potential issues")
        
        # Phase-specific recommendations
        for phase_name, phase_data in metrics.get('phases', {}).items():
            if phase_data['avg_waiting'] > 5:
                recommendations.append(f"High waiting time in {phase_name} phase - consider adjustments")
        
        if not recommendations:
            recommendations.append("Continue monitoring traffic patterns")
        
        return recommendations

def stop_simulation(self) -> Dict[str, Any]:
    """Stop simulation and run deferred analysis"""
    if not self.is_running:
        return {"success": False, "error": "No simulation running"}
    
    print("🛑 Stopping simulation...")
    self.is_running = False
    
    # Wait for thread to finish
    if self.simulation_thread and self.simulation_thread.is_alive():
        self.simulation_thread.join(timeout=5.0)
    
    # NOW run pattern analysis on all collected data
    print("📊 Running pattern analysis on collected data...")
    analysis_results = traffic_pattern_analyzer.process_deferred_analysis()
    
    return {
        "success": True,
        "message": "Simulation stopped successfully",
        "analysis_results": analysis_results
    }

# Global instance
traffic_pattern_analyzer = TrafficPatternAnalyzer()