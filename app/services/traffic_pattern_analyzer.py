from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict
import statistics

from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficPattern
from app.services.db_queue import db_queue_service
from app.services.tls_data_service import tls_data_service

class TrafficPatternAnalyzer:
    """Analyzes traffic logs to extract patterns every 15 minutes"""
    
    def __init__(self, app=None):
        self.app = app
        self.analysis_interval = 15  # minutes
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def analyze_traffic_patterns(self, scenario: str = None) -> Dict[str, Any]:
        """
        Analyze traffic patterns for the last 15 minutes of SUMO simulation time
        """
        if not self.app:
            return {"error": "Service not initialized with app context"}
            
        with self.app.app_context():
            try:
                # Get the most recent simulation time from any log
                latest_log = TrafficLightLog.query.order_by(
                    TrafficLightLog.simulation_time.desc()
                ).first()
                
                if not latest_log:
                    print("📭 No traffic logs found in database")
                    return {"message": "No traffic logs available for analysis"}
                
                current_sim_time = latest_log.simulation_time
                analysis_window = 900  # 15 minutes in SUMO seconds (15 * 60)
                start_sim_time = max(0, current_sim_time - analysis_window)
                
                print(f"🔍 Analyzing patterns from SUMO time {start_sim_time}s to {current_sim_time}s")
                
                # Get logs based on SIMULATION time
                query = TrafficLightLog.query.filter(
                    TrafficLightLog.simulation_time >= start_sim_time,
                    TrafficLightLog.simulation_time <= current_sim_time
                )
                
                if scenario:
                    query = query.filter(TrafficLightLog.scenario == scenario)
                
                logs = query.order_by(TrafficLightLog.simulation_time).all()
                
                if not logs:
                    print(f"📭 No logs found in SUMO time range {start_sim_time}-{current_sim_time}")
                    return {"message": f"No logs found in SUMO time range {start_sim_time}-{current_sim_time}", "logs_analyzed": 0}
                
                print(f"📊 Found {len(logs)} logs in SUMO time range {start_sim_time}-{current_sim_time}")
                
                # Convert simulation times to datetime for storage
                # Use the actual time range of the data we analyzed
                analysis_start = datetime.utcnow() - timedelta(minutes=15)
                analysis_end = datetime.utcnow()
                
                # Group logs by traffic light and analyze patterns
                patterns = self._analyze_time_period_logs(logs, analysis_start, analysis_end, scenario)
                
                # Store patterns via queue service
                stored_count = self._store_patterns_via_queue(patterns)
                
                return {
                    "status": "success",
                    "patterns_generated": len(patterns),
                    "patterns_stored": stored_count,
                    "logs_analyzed": len(logs),
                    "analysis_period": {
                        "sumo_start": start_sim_time,
                        "sumo_end": current_sim_time,
                        "real_start": analysis_start.isoformat(),
                        "real_end": analysis_end.isoformat()
                    },
                    "scenario": scenario
                }
                
            except Exception as e:
                print(f"❌ Error analyzing traffic patterns: {e}")
                import traceback
                traceback.print_exc()
                return {"error": f"Analysis failed: {str(e)}"}
    
    def _analyze_time_period_logs(self, logs: List[TrafficLightLog], start_time: datetime, 
                                end_time: datetime, scenario: str) -> List[Dict[str, Any]]:
        """Analyze logs for a specific time period and extract patterns"""
        
        # Group logs by traffic light ID
        tl_logs = defaultdict(list)
        for log in logs:
            tl_logs[log.traffic_light_id].append(log)
        
        patterns = []
        
        for tl_id, tl_log_list in tl_logs.items():
            if len(tl_log_list) < 3:  # Need minimum data points for pattern analysis
                print(f"⚠️ Skipping {tl_id}: only {len(tl_log_list)} logs (minimum 3 required)")
                continue
                
            pattern = self._analyze_single_tl_pattern(tl_log_list, tl_id, start_time, end_time, scenario)
            if pattern:
                patterns.append(pattern)
                print(f"✅ Analyzed pattern for {tl_id}: {pattern['pattern_type']}")
            else:
                print(f"❌ Failed to analyze pattern for {tl_id}")
        
        print(f"📈 Generated {len(patterns)} patterns from {len(tl_logs)} traffic lights")
        return patterns
    
    def _analyze_single_tl_pattern(self, logs: List[TrafficLightLog], tl_id: str, 
                                 start_time: datetime, end_time: datetime, scenario: str) -> Dict[str, Any]:
        """Analyze pattern for a single traffic light"""
        
        try:
            # Sort logs by time
            logs.sort(key=lambda x: x.created_at)
            
            # Extract key metrics over time with proper filtering
            efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
            waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
            vehicle_counts = [log.vehicle_count for log in logs if log.vehicle_count is not None]
            
            print(f"📋 {tl_id}: {len(efficiency_scores)} efficiency scores, {len(waiting_vehicles)} waiting counts")
            
            # Phase analysis
            phase_patterns = self._analyze_phase_patterns(logs)
            
            # Calculate statistical patterns with proper defaults
            pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, vehicle_counts)
            
            pattern_type = self._determine_pattern_type(efficiency_scores, waiting_vehicles, phase_patterns)
            confidence_score = self._calculate_confidence_score(logs)
            recommendations = self._generate_pattern_recommendations(efficiency_scores, waiting_vehicles, phase_patterns)
            
            pattern_data = {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'interval_start': start_time,
                'interval_end': end_time,
                'pattern_metrics': pattern_metrics,
                'phase_patterns': phase_patterns,
                'pattern_type': pattern_type,
                'confidence_score': confidence_score,
                'recommendations': recommendations
            }
            
            print(f"📊 Pattern data for {tl_id}:")
            print(f"   - Type: {pattern_type}")
            print(f"   - Confidence: {confidence_score}")
            print(f"   - Recommendations: {len(recommendations)}")
            print(f"   - Metrics: {pattern_metrics.keys()}")
            
            return pattern_data
            
        except Exception as e:
            print(f"❌ Error analyzing pattern for {tl_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_pattern_metrics(self, efficiency_scores: List[float], waiting_vehicles: List[int], 
                                 vehicle_counts: List[int]) -> Dict[str, Any]:
        """Calculate comprehensive pattern metrics with proper error handling"""
        
        # Efficiency metrics
        if efficiency_scores:
            avg_efficiency = statistics.mean(efficiency_scores)
            efficiency_trend = self._calculate_trend(efficiency_scores)
            efficiency_stability = self._calculate_stability(efficiency_scores)
        else:
            avg_efficiency = 0
            efficiency_trend = "INSUFFICIENT_DATA"
            efficiency_stability = 0
        
        # Congestion metrics
        if waiting_vehicles:
            avg_waiting = statistics.mean(waiting_vehicles)
            peak_waiting = max(waiting_vehicles)
            congestion_frequency = self._calculate_congestion_frequency(waiting_vehicles)
            congestion_trend = self._calculate_trend(waiting_vehicles)
        else:
            avg_waiting = 0
            peak_waiting = 0
            congestion_frequency = 0
            congestion_trend = "INSUFFICIENT_DATA"
        
        # Volume metrics
        if vehicle_counts:
            avg_volume = statistics.mean(vehicle_counts)
            peak_volume = max(vehicle_counts)
            volume_trend = self._calculate_trend(vehicle_counts)
        else:
            avg_volume = 0
            peak_volume = 0
            volume_trend = "INSUFFICIENT_DATA"
        
        return {
            'efficiency': {
                'average': round(avg_efficiency, 2),
                'trend': efficiency_trend,
                'stability': efficiency_stability,
                'min': min(efficiency_scores) if efficiency_scores else 0,
                'max': max(efficiency_scores) if efficiency_scores else 0
            },
            'congestion': {
                'average_waiting': round(avg_waiting, 2),
                'peak_waiting': peak_waiting,
                'congestion_frequency': congestion_frequency,
                'trend': congestion_trend
            },
            'volume': {
                'average_volume': round(avg_volume, 2),
                'peak_volume': peak_volume,
                'volume_trend': volume_trend
            }
        }
    
    def _analyze_phase_patterns(self, logs: List[TrafficLightLog]) -> Dict[str, Any]:
        """Analyze phase duration and sequence patterns"""
        phase_data = defaultdict(list)
        phase_sequence = []
        
        for log in logs:
            if log.phase_name and log.phase_name != 'UNKNOWN':
                phase_sequence.append(log.phase_name)
                if log.duration and log.duration > 0:
                    phase_data[log.phase_name].append(log.duration)
        
        print(f"🔧 Phase analysis: {len(phase_sequence)} phases, {len(phase_data)} unique phases")
        
        # Calculate phase statistics
        phase_stats = {}
        for phase_name, durations in phase_data.items():
            if durations:
                phase_stats[phase_name] = {
                    'average_duration': round(statistics.mean(durations), 2),
                    'duration_std': round(statistics.stdev(durations), 2) if len(durations) > 1 else 0,
                    'frequency': len(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations)
                }
        
        # Analyze phase sequence patterns
        sequence_pattern = self._analyze_phase_sequence(phase_sequence)
        
        return {
            'phase_statistics': phase_stats,
            'sequence_pattern': sequence_pattern,
            'dominant_phase': max(phase_stats.items(), key=lambda x: x[1]['frequency'])[0] if phase_stats else None,
            'total_phases_analyzed': len(phase_sequence)
        }
    
    def _analyze_phase_sequence(self, phase_sequence: List[str]) -> Dict[str, Any]:
        """Analyze phase sequence patterns"""
        if len(phase_sequence) < 3:
            return {"pattern": "INSUFFICIENT_DATA", "reason": f"Only {len(phase_sequence)} phases"}
        
        unique_phases = list(set(phase_sequence))
        
        if len(unique_phases) == 1:
            return {"pattern": "STATIC", "phase": unique_phases[0], "occurrences": len(phase_sequence)}
        
        # Check for cyclic patterns
        sequence_length = min(10, len(phase_sequence) // 2)
        for pattern_len in range(2, sequence_length + 1):
            if self._is_cyclic_pattern(phase_sequence, pattern_len):
                return {
                    "pattern": "CYCLIC",
                    "cycle_length": pattern_len,
                    "phases": phase_sequence[:pattern_len],
                    "cycles_detected": len(phase_sequence) // pattern_len
                }
        
        return {
            "pattern": "VARIABLE", 
            "unique_phases": len(unique_phases),
            "total_phases": len(phase_sequence)
        }
    
    def _is_cyclic_pattern(self, sequence: List[str], pattern_len: int) -> bool:
        """Check if sequence follows a cyclic pattern"""
        if len(sequence) < pattern_len * 2:
            return False
        
        for i in range(pattern_len, len(sequence)):
            if sequence[i] != sequence[i % pattern_len]:
                return False
        return True
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend of values over time"""
        if len(values) < 3:
            return "INSUFFICIENT_DATA"
        
        try:
            x = list(range(len(values)))
            slope = statistics.covariance(x, values) / statistics.variance(x)
            
            if slope > 0.1:
                return "INCREASING"
            elif slope < -0.1:
                return "DECLINING"
            else:
                return "STABLE"
        except:
            return "UNKNOWN"
    
    def _calculate_stability(self, values: List[float]) -> float:
        """Calculate stability score (0-1)"""
        if len(values) < 2:
            return 0.0
        
        try:
            cv = statistics.stdev(values) / statistics.mean(values)
            stability = 1.0 / (1.0 + abs(cv))  # Use abs to handle negative values
            return round(stability, 3)
        except:
            return 0.0
    
    def _calculate_congestion_frequency(self, waiting_vehicles: List[int]) -> float:
        """Calculate frequency of congestion events"""
        if not waiting_vehicles:
            return 0.0
        
        congestion_count = sum(1 for w in waiting_vehicles if w > 5)  # Threshold for congestion
        return round(congestion_count / len(waiting_vehicles), 3)
    
    def _determine_pattern_type(self, efficiencies: List[float], waiting_vehicles: List[int], 
                              phase_patterns: Dict) -> str:
        """Determine the overall traffic pattern type"""
        if not efficiencies:
            return "INSUFFICIENT_DATA"
        
        try:
            avg_efficiency = statistics.mean(efficiencies)
            avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
            
            if avg_efficiency > 80 and avg_waiting < 3:
                return "EFFICIENT_FLOW"
            elif avg_efficiency < 60 and avg_waiting > 8:
                return "CONGESTED"
            elif phase_patterns.get('sequence_pattern', {}).get('pattern') == "CYCLIC":
                return "PREDICTABLE_CYCLIC"
            elif self._calculate_stability(efficiencies) > 0.8:
                return "STABLE"
            else:
                return "VARIABLE"
        except:
            return "UNKNOWN"
    
    def _calculate_confidence_score(self, logs: List[TrafficLightLog]) -> float:
        """Calculate confidence score for the pattern (0-1)"""
        if len(logs) < 5:
            return round(len(logs) / 5.0, 3)  # Scale based on data points
        
        try:
            # Consider data consistency, sample size, and time coverage
            time_span = (logs[-1].created_at - logs[0].created_at).total_seconds()
            time_coverage = min(1.0, time_span / (self.analysis_interval * 60))
            
            sample_score = min(1.0, len(logs) / 20.0)  # More samples = higher confidence
            
            # Check data quality (how many logs have valid efficiency scores)
            valid_efficiency_logs = sum(1 for log in logs if log.efficiency_score is not None)
            data_quality = valid_efficiency_logs / len(logs)
            
            confidence = (time_coverage + sample_score + data_quality) / 3.0
            return round(confidence, 3)
        except:
            return 0.0
    
    def _generate_pattern_recommendations(self, efficiencies: List[float], waiting_vehicles: List[int],
                                       phase_patterns: Dict) -> List[str]:
        """Generate recommendations based on pattern analysis"""
        recommendations = []
        
        if not efficiencies:
            return ["Insufficient data for meaningful recommendations"]
        
        try:
            avg_efficiency = statistics.mean(efficiencies)
            avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
            
            if avg_efficiency < 60:
                recommendations.append("Optimize traffic light timing for better efficiency")
            
            if avg_waiting > 8:
                recommendations.append("High congestion detected - review phase durations and sequencing")
            
            sequence_pattern = phase_patterns.get('sequence_pattern', {})
            if sequence_pattern.get('pattern') == 'STATIC':
                recommendations.append("Static phase pattern detected - consider implementing adaptive timing")
            elif sequence_pattern.get('pattern') == 'CYCLIC':
                recommendations.append("Cyclic pattern detected - consider optimizing cycle length")
            
            stability = self._calculate_stability(efficiencies)
            if stability < 0.5:
                recommendations.append("High variability in performance - investigate inconsistent traffic patterns")
            
            # Add phase-specific recommendations
            phase_stats = phase_patterns.get('phase_statistics', {})
            for phase_name, stats in phase_stats.items():
                if stats.get('average_waiting', 0) > 3 and stats.get('average_duration', 0) < 20:
                    recommendations.append(f"Increase duration for {phase_name} phase (high waiting time)")
                elif stats.get('average_waiting', 0) < 1 and stats.get('average_duration', 0) > 40:
                    recommendations.append(f"Reduce duration for {phase_name} phase (underutilized)")
            
            if not recommendations:
                recommendations.append("Current configuration appears optimal - continue monitoring")
            
            return recommendations[:5]  # Limit to top 5 recommendations
            
        except Exception as e:
            return [f"Error generating recommendations: {str(e)}"]
    
    def _store_patterns_via_queue(self, patterns: List[Dict[str, Any]]) -> int:
        """Store analyzed patterns using the queue service"""
        if not db_queue_service:
            print("❌ DB Queue Service not available - cannot store patterns")
            return 0
        
        stored_count = 0
        for pattern in patterns:
            try:
                # Ensure all required fields are present and properly formatted
                pattern_data = {
                    'traffic_light_id': pattern['traffic_light_id'],
                    'scenario': pattern.get('scenario', 'default'),
                    'interval_start': pattern['interval_start'],
                    'interval_end': pattern['interval_end'],
                    'pattern_type': pattern['pattern_type'],
                    'pattern_metrics': pattern['pattern_metrics'],
                    'phase_patterns': pattern['phase_patterns'],
                    'confidence_score': pattern['confidence_score'],
                    'recommendations': pattern['recommendations']
                }
                
                db_queue_service.add_traffic_pattern(pattern_data)
                stored_count += 1
                print(f"📊 Queued pattern for {pattern['traffic_light_id']} - Type: {pattern['pattern_type']}")
                
            except Exception as e:
                print(f"❌ Error queuing pattern for {pattern['traffic_light_id']}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"💾 Successfully queued {stored_count} patterns for storage")
        return stored_count
    
    def schedule_automatic_analysis(self):
        """Schedule automatic pattern analysis every 15 minutes"""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            
            scheduler = BackgroundScheduler()
            scheduler.add_job(
                func=self.analyze_traffic_patterns,
                trigger='interval',
                minutes=self.analysis_interval,
                id='traffic_pattern_analysis',
                max_instances=1
            )
            scheduler.start()
            print(f"✅ Scheduled automatic traffic pattern analysis every {self.analysis_interval} minutes")
            
        except ImportError:
            print("⚠️ APScheduler not available - manual analysis only")
        except Exception as e:
            print(f"❌ Error scheduling automatic analysis: {e}")

# Global instance
traffic_pattern_analyzer = TrafficPatternAnalyzer()

def init_traffic_pattern_analyzer(app):
    """Initialize traffic pattern analyzer"""
    traffic_pattern_analyzer.init_app(app)
    # Enable automatic scheduling
    traffic_pattern_analyzer.schedule_automatic_analysis()