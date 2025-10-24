from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict
import statistics
import uuid

from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficPattern
from app.services.db_queue import db_queue_service
from app.services.tls_data_service import tls_data_service

class TrafficPatternAnalyzer:
    """Analyzes traffic logs to extract patterns every 15 minutes"""
    
    def __init__(self, app=None):
        self.app = app
        self.analysis_interval = 15  # minutes
        self.batch_size = 1000  # Process logs in batches to avoid memory issues
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def analyze_traffic_patterns(self, scenario: str = None) -> Dict[str, Any]:
        """
        Analyze traffic patterns by looping through traffic logs in the database
        """
        if not self.app:
            return {"error": "Service not initialized with app context"}
            
        with self.app.app_context():
            try:
                # Get analysis time window
                analysis_start = datetime.utcnow() - timedelta(minutes=self.analysis_interval)
                
                print(f"🔍 Analyzing traffic patterns from {analysis_start} to now")
                
                # Get all unique traffic lights that have logs in the analysis period
                tl_query = db.session.query(TrafficLightLog.traffic_light_id).distinct()
                if scenario:
                    tl_query = tl_query.filter(TrafficLightLog.scenario == scenario)
                
                traffic_light_ids = [result[0] for result in tl_query.all()]
                
                if not traffic_light_ids:
                    print("📭 No traffic lights found in database")
                    return {"message": "No traffic lights found for analysis"}
                
                print(f"📊 Found {len(traffic_light_ids)} traffic lights to analyze")
                
                patterns = []
                total_logs_analyzed = 0
                
                # Loop through each traffic light and analyze its patterns
                for tl_id in traffic_light_ids:
                    try:
                        tl_patterns = self._analyze_single_traffic_light(tl_id, analysis_start, scenario)
                        if tl_patterns:
                            patterns.extend(tl_patterns)
                            total_logs_analyzed += len(tl_patterns)
                            print(f"✅ Analyzed {len(tl_patterns)} patterns for {tl_id}")
                    except Exception as e:
                        print(f"❌ Error analyzing traffic light {tl_id}: {e}")
                        continue
                
                # Store patterns via queue service
                stored_count = self._store_patterns_via_queue(patterns)
                
                return {
                    "status": "success",
                    "patterns_generated": len(patterns),
                    "patterns_stored": stored_count,
                    "traffic_lights_analyzed": len(traffic_light_ids),
                    "total_logs_analyzed": total_logs_analyzed,
                    "analysis_period": {
                        "start": analysis_start.isoformat(),
                        "end": datetime.utcnow().isoformat()
                    },
                    "scenario": scenario
                }
                
            except Exception as e:
                print(f"❌ Error analyzing traffic patterns: {e}")
                import traceback
                traceback.print_exc()
                return {"error": f"Analysis failed: {str(e)}"}
    
    # Analyze patterns for a single traffic light
    def _analyze_single_traffic_light(self, tl_id: str, analysis_start: datetime, scenario: str = None) -> List[Dict[str, Any]]:
        """Analyze patterns for a single traffic light"""

        print(f"🔍 Analyzing traffic light: {tl_id}")

        # Get ALL logs for this traffic light (not just recent)
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.traffic_light_id == tl_id
        ).order_by(TrafficLightLog.created_at).all()

        print(f"📋 Found {len(logs)} total logs for {tl_id}")

        if len(logs) < 3:
            print(f"⚠️ Skipping {tl_id}: only {len(logs)} logs (minimum 3 required)")
            return []

        patterns = []

        try:
            # Create a basic pattern from all available logs
            pattern = self._create_basic_pattern(logs, tl_id, scenario)
            if pattern:
                patterns.append(pattern)
                print(f"✅ Created basic pattern for {tl_id}")

            # Also try time-based patterns
            time_patterns = self._analyze_time_based_patterns(logs, tl_id, analysis_start, scenario)
            patterns.extend(time_patterns)

        except Exception as e:
            print(f"❌ Error analyzing {tl_id}: {e}")
            import traceback
            traceback.print_exc()

        return patterns
    
    def _create_basic_pattern(self, logs: List[TrafficLightLog], tl_id: str, scenario: str = None) -> Dict[str, Any]:
        """Create a basic pattern from all available logs"""

        try:
            # Get basic metrics
            efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
            waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
            vehicle_counts = [log.vehicle_count for log in logs if log.vehicle_count is not None]

            if not efficiency_scores:
                print(f"⚠️ No efficiency scores for {tl_id}")
                return None

            print(f"📊 {tl_id}: {len(efficiency_scores)} efficiency scores, {len(waiting_vehicles)} waiting counts")

            # Calculate basic metrics
            pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, vehicle_counts)
            pattern_type = self._determine_pattern_type(efficiency_scores, waiting_vehicles, {})
            confidence_score = self._calculate_confidence_score(logs)
            recommendations = self._generate_pattern_recommendations(efficiency_scores, waiting_vehicles, {})

            # Get time range from logs
            log_times = [log.created_at for log in logs]

            return {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'interval_start': min(log_times),
                'interval_end': max(log_times),
                'pattern_metrics': pattern_metrics,
                'phase_patterns': self._analyze_phase_patterns(logs),
                'pattern_type': pattern_type,
                'confidence_score': confidence_score,
                'recommendations': recommendations
            }

        except Exception as e:
            print(f"❌ Error creating basic pattern for {tl_id}: {e}")
            return None
    
    # Analyze time-based patterns
    def _analyze_time_based_patterns(self, logs: List[TrafficLightLog], tl_id: str, 
                                   analysis_start: datetime, scenario: str) -> List[Dict[str, Any]]:
        """Analyze patterns based on time windows (hourly, peak hours, etc.)"""
        
        if not logs:
            return []
        
        patterns = []
        
        # Group logs by hour of day
        hourly_logs = defaultdict(list)
        for log in logs:
            hour = log.created_at.hour
            hourly_logs[hour].append(log)
        
        # Analyze each hour's pattern
        for hour, hour_logs in hourly_logs.items():
            if len(hour_logs) >= 3:  # Minimum logs for pattern analysis
                pattern = self._create_time_pattern(hour_logs, tl_id, hour, analysis_start, scenario)
                if pattern:
                    patterns.append(pattern)
        
        # Analyze peak vs off-peak patterns
        peak_patterns = self._analyze_peak_hours(logs, tl_id, analysis_start, scenario)
        patterns.extend(peak_patterns)
        
        return patterns
    
    def _analyze_phase_based_patterns(self, logs: List[TrafficLightLog], tl_id: str,
                                    analysis_start: datetime, scenario: str) -> List[Dict[str, Any]]:
        """Analyze patterns based on traffic light phases"""
        
        if not logs:
            return []
        
        patterns = []
        
        # Group logs by phase
        phase_logs = defaultdict(list)
        for log in logs:
            if log.phase_name and log.phase_name != 'UNKNOWN':
                phase_logs[log.phase_name].append(log)
        
        # Analyze each phase's pattern
        for phase_name, phase_log_list in phase_logs.items():
            if len(phase_log_list) >= 3:
                pattern = self._create_phase_pattern(phase_log_list, tl_id, phase_name, analysis_start, scenario)
                if pattern:
                    patterns.append(pattern)
        
        # Analyze phase sequence patterns
        sequence_pattern = self._analyze_phase_sequence_pattern(logs, tl_id, analysis_start, scenario)
        if sequence_pattern:
            patterns.append(sequence_pattern)
        
        return patterns
    
    def _create_phase_pattern(self, logs: List[TrafficLightLog], tl_id: str, phase_name: str,
                            analysis_start: datetime, scenario: str) -> Dict[str, Any]:
        """Create a phase-based pattern"""
        
        try:
            efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
            waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
            
            if not efficiency_scores:
                return None
            
            pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, [])
            pattern_type = self._determine_phase_pattern_type(phase_name, efficiency_scores, waiting_vehicles)
            confidence_score = self._calculate_confidence_score(logs)
            recommendations = self._generate_phase_recommendations(phase_name, efficiency_scores, waiting_vehicles)
            
            # Create time window for this pattern
            log_times = [log.created_at for log in logs]
            interval_start = min(log_times)
            interval_end = max(log_times)
            
            # Analyze phase-specific metrics
            phase_durations = [log.duration for log in logs if log.duration and log.duration > 0]
            phase_stats = {}
            if phase_durations:
                phase_stats = {
                    'average_duration': round(statistics.mean(phase_durations), 2),
                    'min_duration': min(phase_durations),
                    'max_duration': max(phase_durations),
                    'occurrences': len(logs)
                }
            
            phase_patterns = {
                'phase_statistics': {phase_name: phase_stats},
                'dominant_phase': phase_name,
                'total_phases_analyzed': len(logs)
            }
            
            return {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'interval_start': interval_start,
                'interval_end': interval_end,
                'pattern_metrics': pattern_metrics,
                'phase_patterns': phase_patterns,
                'pattern_type': pattern_type,
                'confidence_score': confidence_score,
                'recommendations': recommendations,
                'pattern_subtype': f'PHASE_{phase_name}'
            }
            
        except Exception as e:
            print(f"❌ Error creating phase pattern for {tl_id} phase {phase_name}: {e}")
            return None
    
    def _create_time_pattern(self, logs: List[TrafficLightLog], tl_id: str, hour: int,
                           analysis_start: datetime, scenario: str) -> Dict[str, Any]:
        """Create a time-based pattern for a specific hour"""
        
        try:
            efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
            waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
            vehicle_counts = [log.vehicle_count for log in logs if log.vehicle_count is not None]
            
            if not efficiency_scores:
                return None
            
            pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, vehicle_counts)
            pattern_type = self._determine_time_pattern_type(hour, efficiency_scores, waiting_vehicles)
            confidence_score = self._calculate_confidence_score(logs)
            recommendations = self._generate_time_recommendations(hour, efficiency_scores, waiting_vehicles)
            
            # Create time window for this pattern
            log_times = [log.created_at for log in logs]
            interval_start = min(log_times)
            interval_end = max(log_times)
            
            return {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'interval_start': interval_start,
                'interval_end': interval_end,
                'pattern_metrics': pattern_metrics,
                'phase_patterns': self._analyze_phase_patterns(logs),
                'pattern_type': pattern_type,
                'confidence_score': confidence_score,
                'recommendations': recommendations,
                'pattern_subtype': f'HOUR_{hour:02d}'
            }
            
        except Exception as e:
            print(f"❌ Error creating time pattern for {tl_id} hour {hour}: {e}")
            return None
    
    def _analyze_peak_hours(self, logs: List[TrafficLightLog], tl_id: str,
                          analysis_start: datetime, scenario: str) -> List[Dict[str, Any]]:
        """Analyze peak hour patterns"""
        
        if len(logs) < 10:
            return []
        
        # Define peak hours (7-9 AM, 4-7 PM)
        morning_peak = [7, 8, 9]
        evening_peak = [16, 17, 18, 19]
        
        peak_logs = [log for log in logs if log.created_at.hour in morning_peak + evening_peak]
        off_peak_logs = [log for log in logs if log.created_at.hour not in morning_peak + evening_peak]
        
        patterns = []
        
        # Analyze peak hours pattern
        if len(peak_logs) >= 5:
            peak_pattern = self._create_peak_pattern(peak_logs, tl_id, "PEAK_HOURS", analysis_start, scenario)
            if peak_pattern:
                patterns.append(peak_pattern)
        
        # Analyze off-peak hours pattern
        if len(off_peak_logs) >= 5:
            off_peak_pattern = self._create_peak_pattern(off_peak_logs, tl_id, "OFF_PEAK", analysis_start, scenario)
            if off_peak_pattern:
                patterns.append(off_peak_pattern)
        
        return patterns
    
    def _create_peak_pattern(self, logs: List[TrafficLightLog], tl_id: str, pattern_type: str,
                           analysis_start: datetime, scenario: str) -> Dict[str, Any]:
        """Create peak/off-peak pattern"""
        
        try:
            efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
            waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
            
            if not efficiency_scores:
                return None
            
            pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, [])
            confidence_score = self._calculate_confidence_score(logs)
            recommendations = self._generate_peak_recommendations(pattern_type, efficiency_scores, waiting_vehicles)
            
            log_times = [log.created_at for log in logs]
            interval_start = min(log_times)
            interval_end = max(log_times)
            
            return {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'interval_start': interval_start,
                'interval_end': interval_end,
                'pattern_metrics': pattern_metrics,
                'phase_patterns': self._analyze_phase_patterns(logs),
                'pattern_type': pattern_type,
                'confidence_score': confidence_score,
                'recommendations': recommendations,
                'pattern_subtype': pattern_type
            }
            
        except Exception as e:
            print(f"❌ Error creating {pattern_type} pattern for {tl_id}: {e}")
            return None
    
    def _analyze_phase_sequence_pattern(self, logs: List[TrafficLightLog], tl_id: str,
                                      analysis_start: datetime, scenario: str) -> Dict[str, Any]:
        """Analyze phase sequence patterns across all logs"""
        
        if len(logs) < 10:
            return None
        
        try:
            # Extract phase sequence
            phase_sequence = []
            for log in sorted(logs, key=lambda x: x.created_at):
                if log.phase_name and log.phase_name != 'UNKNOWN':
                    phase_sequence.append(log.phase_name)
            
            if len(phase_sequence) < 5:
                return None
            
            sequence_analysis = self._analyze_phase_sequence(phase_sequence)
            
            efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
            waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
            
            pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, [])
            confidence_score = self._calculate_confidence_score(logs)
            
            log_times = [log.created_at for log in logs]
            interval_start = min(log_times)
            interval_end = max(log_times)
            
            return {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'interval_start': interval_start,
                'interval_end': interval_end,
                'pattern_metrics': pattern_metrics,
                'phase_patterns': {'sequence_pattern': sequence_analysis},
                'pattern_type': f"SEQUENCE_{sequence_analysis.get('pattern', 'UNKNOWN')}",
                'confidence_score': confidence_score,
                'recommendations': self._generate_sequence_recommendations(sequence_analysis),
                'pattern_subtype': 'PHASE_SEQUENCE'
            }
            
        except Exception as e:
            print(f"❌ Error analyzing phase sequence for {tl_id}: {e}")
            return None
    
    def _determine_time_pattern_type(self, hour: int, efficiencies: List[float], waiting_vehicles: List[int]) -> str:
        """Determine pattern type for time-based analysis"""
        if not efficiencies:
            return "INSUFFICIENT_DATA"
        
        avg_efficiency = statistics.mean(efficiencies)
        avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
        
        # Peak hour detection
        if hour in [7, 8, 9, 16, 17, 18, 19]:
            if avg_waiting > 10:
                return "PEAK_CONGESTION"
            elif avg_efficiency < 70:
                return "PEAK_MODERATE"
            else:
                return "PEAK_EFFICIENT"
        else:
            if avg_efficiency > 80:
                return "OFF_PEAK_OPTIMAL"
            else:
                return "OFF_PEAK_SUBOPTIMAL"
    
    def _determine_phase_pattern_type(self, phase_name: str, efficiencies: List[float], waiting_vehicles: List[int]) -> str:
        """Determine pattern type for phase-based analysis"""
        if not efficiencies:
            return "INSUFFICIENT_DATA"
        
        avg_efficiency = statistics.mean(efficiencies)
        avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
        
        if 'GREEN' in phase_name:
            if avg_efficiency > 85:
                return "GREEN_EFFICIENT"
            elif avg_waiting > 5:
                return "GREEN_CONGESTED"
            else:
                return "GREEN_NORMAL"
        elif 'YELLOW' in phase_name:
            return "TRANSITION_PHASE"
        elif 'RED' in phase_name:
            if avg_waiting > 8:
                return "RED_CONGESTED"
            else:
                return "RED_NORMAL"
        else:
            return "UNKNOWN_PHASE"
    
    def _generate_time_recommendations(self, hour: int, efficiencies: List[float], waiting_vehicles: List[int]) -> List[str]:
        """Generate time-specific recommendations"""
        recommendations = []
        
        if not efficiencies:
            return ["Insufficient data for time-based recommendations"]
        
        avg_efficiency = statistics.mean(efficiencies)
        avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
        
        # Peak hour recommendations
        if hour in [7, 8, 9]:
            if avg_waiting > 8:
                recommendations.append(f"Morning peak hour {hour}:00 - consider increasing green time for main routes")
        elif hour in [16, 17, 18, 19]:
            if avg_waiting > 8:
                recommendations.append(f"Evening peak hour {hour}:00 - optimize for commuter traffic patterns")
        
        if avg_efficiency < 60:
            recommendations.append(f"Low efficiency during hour {hour}:00 - review timing parameters")
        
        return recommendations if recommendations else [f"Hour {hour}:00 patterns appear normal"]
    
    def _generate_phase_recommendations(self, phase_name: str, efficiencies: List[float], waiting_vehicles: List[int]) -> List[str]:
        """Generate phase-specific recommendations"""
        recommendations = []
        
        if not efficiencies:
            return ["Insufficient data for phase-specific recommendations"]
        
        avg_efficiency = statistics.mean(efficiencies)
        avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
        
        if 'GREEN' in phase_name and avg_waiting > 5:
            recommendations.append(f"High waiting during {phase_name} - consider extending duration")
        elif 'RED' in phase_name and avg_waiting > 8:
            recommendations.append(f"Excessive waiting during {phase_name} - review cycle length")
        
        if avg_efficiency < 60:
            recommendations.append(f"Low efficiency during {phase_name} - optimize timing")
        
        return recommendations if recommendations else [f"{phase_name} performance appears adequate"]
    
    def _generate_peak_recommendations(self, pattern_type: str, efficiencies: List[float], waiting_vehicles: List[int]) -> List[str]:
        """Generate peak/off-peak specific recommendations"""
        recommendations = []
        
        if not efficiencies:
            return ["Insufficient data for peak hour recommendations"]
        
        avg_efficiency = statistics.mean(efficiencies)
        avg_waiting = statistics.mean(waiting_vehicles) if waiting_vehicles else 0
        
        if pattern_type == "PEAK_HOURS":
            if avg_waiting > 10:
                recommendations.append("High congestion during peak hours - implement peak-specific timing plans")
            elif avg_efficiency < 70:
                recommendations.append("Suboptimal performance during peak hours - optimize for high traffic volume")
        else:  # OFF_PEAK
            if avg_efficiency < 75:
                recommendations.append("Low efficiency during off-peak hours - review base timing parameters")
        
        return recommendations if recommendations else [f"{pattern_type} performance meets expectations"]
    
    def _generate_sequence_recommendations(self, sequence_analysis: Dict) -> List[str]:
        """Generate sequence-specific recommendations"""
        pattern = sequence_analysis.get('pattern', 'UNKNOWN')
        
        if pattern == "STATIC":
            return ["Static phase sequence detected - consider implementing variable timing"]
        elif pattern == "CYCLIC":
            cycle_length = sequence_analysis.get('cycle_length', 0)
            return [f"Cyclic pattern with {cycle_length} phases detected - optimize cycle timing"]
        elif pattern == "VARIABLE":
            return ["Variable phase sequence - ensure adequate phase transitions"]
        else:
            return ["Review phase sequencing for optimization opportunities"]
    
    # def _analyze_time_period_logs(self, logs: List[TrafficLightLog], start_time: datetime, 
    #                             end_time: datetime, scenario: str) -> List[Dict[str, Any]]:
    #     """Analyze logs for a specific time period and extract patterns"""
        
    #     # Group logs by traffic light ID
    #     tl_logs = defaultdict(list)
    #     for log in logs:
    #         tl_logs[log.traffic_light_id].append(log)
        
    #     patterns = []
        
    #     for tl_id, tl_log_list in tl_logs.items():
    #         if len(tl_log_list) < 3:  # Need minimum data points for pattern analysis
    #             print(f"⚠️ Skipping {tl_id}: only {len(tl_log_list)} logs (minimum 3 required)")
    #             continue
                
    #         pattern = self._analyze_single_tl_pattern(tl_log_list, tl_id, start_time, end_time, scenario)
    #         if pattern:
    #             patterns.append(pattern)
    #             print(f"✅ Analyzed pattern for {tl_id}: {pattern['pattern_type']}")
    #         else:
    #             print(f"❌ Failed to analyze pattern for {tl_id}")
        
    #     print(f"📈 Generated {len(patterns)} patterns from {len(tl_logs)} traffic lights")
    #     return patterns
    
    # def _analyze_single_tl_pattern(self, logs: List[TrafficLightLog], tl_id: str, 
    #                              start_time: datetime, end_time: datetime, scenario: str) -> Dict[str, Any]:
    #     """Analyze pattern for a single traffic light"""
        
    #     try:
    #         # Sort logs by time
    #         logs.sort(key=lambda x: x.created_at)
            
    #         # Extract key metrics over time with proper filtering
    #         efficiency_scores = [log.efficiency_score for log in logs if log.efficiency_score is not None]
    #         waiting_vehicles = [log.waiting_vehicles for log in logs if log.waiting_vehicles is not None]
    #         vehicle_counts = [log.vehicle_count for log in logs if log.vehicle_count is not None]
            
    #         print(f"📋 {tl_id}: {len(efficiency_scores)} efficiency scores, {len(waiting_vehicles)} waiting counts")
            
    #         # Phase analysis
    #         phase_patterns = self._analyze_phase_patterns(logs)
            
    #         # Calculate statistical patterns with proper defaults
    #         pattern_metrics = self._calculate_pattern_metrics(efficiency_scores, waiting_vehicles, vehicle_counts)
            
    #         pattern_type = self._determine_pattern_type(efficiency_scores, waiting_vehicles, phase_patterns)
    #         confidence_score = self._calculate_confidence_score(logs)
    #         recommendations = self._generate_pattern_recommendations(efficiency_scores, waiting_vehicles, phase_patterns)
            
    #         pattern_data = {
    #             'traffic_light_id': tl_id,
    #             'scenario': scenario,
    #             'interval_start': start_time,
    #             'interval_end': end_time,
    #             'pattern_metrics': pattern_metrics,
    #             'phase_patterns': phase_patterns,
    #             'pattern_type': pattern_type,
    #             'confidence_score': confidence_score,
    #             'recommendations': recommendations
    #         }
            
    #         print(f"📊 Pattern data for {tl_id}:")
    #         print(f"   - Type: {pattern_type}")
    #         print(f"   - Confidence: {confidence_score}")
    #         print(f"   - Recommendations: {len(recommendations)}")
    #         print(f"   - Metrics: {pattern_metrics.keys()}")
            
    #         return pattern_data
            
    #     except Exception as e:
    #         print(f"❌ Error analyzing pattern for {tl_id}: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         return None
    
    # Keep
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
    
    # Keep
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
    
    # Keep
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
    
    # Keep
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
    
    # keep
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
    
    # Keep
    def _calculate_congestion_frequency(self, waiting_vehicles: List[int]) -> float:
        """Calculate frequency of congestion events"""
        if not waiting_vehicles:
            return 0.0
        
        congestion_count = sum(1 for w in waiting_vehicles if w > 5)  # Threshold for congestion
        return round(congestion_count / len(waiting_vehicles), 3)
    
    # Keep
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
    
    # Keep
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
    
    # Keep
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
    
    # Keep
    def _store_patterns_via_queue(self, patterns: List[Dict[str, Any]]) -> int:
        """Store analyzed patterns directly to database with conflict handling"""
        if not patterns:
            print("📭 No patterns to store")
            return 0
        
        stored_count = 0
        updated_count = 0
        print(f"💾 Attempting to store {len(patterns)} patterns directly to database...")
        
        try:
            for i, pattern in enumerate(patterns):
                try:
                    print(f"🔍 Processing pattern {i+1}/{len(patterns)} for {pattern['traffic_light_id']}")
                    
                    # Check if pattern already exists for this traffic light and interval
                    existing_pattern = TrafficPattern.query.filter_by(
                        traffic_light_id=pattern['traffic_light_id'],
                        interval_start=pattern['interval_start']
                    ).first()
                    
                    if existing_pattern:
                        # Update existing pattern
                        existing_pattern.interval_end = pattern['interval_end']
                        existing_pattern.pattern_type = pattern['pattern_type']
                        existing_pattern.pattern_metrics = pattern.get('pattern_metrics', {})
                        existing_pattern.phase_patterns = pattern.get('phase_patterns', {})
                        existing_pattern.confidence_score = pattern.get('confidence_score', 0.5)
                        existing_pattern.recommendations = pattern.get('recommendations', [])
                        existing_pattern.created_at = datetime.utcnow()
                        
                        updated_count += 1
                        print(f"🔄 Updated existing pattern for {pattern['traffic_light_id']}")
                        
                    else:
                        # Create new pattern
                        pattern_entry = TrafficPattern(
                            id=str(uuid.uuid4()),
                            traffic_light_id=pattern['traffic_light_id'],
                            scenario=pattern.get('scenario') or 'default',
                            interval_start=pattern['interval_start'],
                            interval_end=pattern['interval_end'],
                            pattern_type=pattern['pattern_type'],
                            pattern_metrics=pattern.get('pattern_metrics', {}),
                            phase_patterns=pattern.get('phase_patterns', {}),
                            confidence_score=pattern.get('confidence_score', 0.5),
                            recommendations=pattern.get('recommendations', []),
                            created_at=datetime.utcnow()
                        )
                        
                        db.session.add(pattern_entry)
                        stored_count += 1
                        print(f"✅ Added new pattern for {pattern['traffic_light_id']} - Type: {pattern['pattern_type']}")
                    
                except Exception as e:
                    print(f"❌ Error storing pattern {i+1} for {pattern['traffic_light_id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                
            # Commit all changes
            print("🔍 Committing transaction...")
            db.session.commit()
            print(f"✅ Successfully stored {stored_count} new patterns and updated {updated_count} existing patterns")
            
        except Exception as e:
            print(f"❌ Error committing patterns: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            print("🔄 Transaction rolled back")
            stored_count = 0
            updated_count = 0
        
        return stored_count + updated_count
    
    def store_patterns_directly(self, patterns: List[Dict[str, Any]]) -> int:
        """Direct pattern storage for testing"""
        if not patterns:
            return 0

        stored_count = 0

        try:
            for pattern in patterns:
                # Simple pattern storage without complex processing
                try:
                    pattern_entry = TrafficPattern(
                        traffic_light_id=pattern['traffic_light_id'],
                        scenario=pattern.get('scenario', 'test'),
                        interval_start=datetime.utcnow() - timedelta(hours=1),
                        interval_end=datetime.utcnow(),
                        pattern_type=pattern.get('pattern_type', 'TEST_PATTERN'),
                        pattern_metrics={},
                        phase_patterns={},
                        confidence_score=0.5,
                        recommendations=['Test pattern'],
                        created_at=datetime.utcnow()
                    )

                    db.session.add(pattern_entry)
                    stored_count += 1
                    print(f"💾 Stored test pattern for {pattern['traffic_light_id']}")

                except Exception as e:
                    print(f"❌ Failed to store test pattern: {e}")
                    continue
                
            db.session.commit()
            print(f"✅ Stored {stored_count} test patterns")

        except Exception as e:
            print(f"❌ Commit failed: {e}")
            db.session.rollback()

        return stored_count
    
    # Keep
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
    try:
        traffic_pattern_analyzer.schedule_automatic_analysis()
        print("✅ Traffic pattern analyzer scheduler STARTED")
    except Exception as e:
        print(f"❌ Scheduler failed to start: {e}")