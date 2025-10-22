import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import statistics
import uuid

from app.extensions import db
from app.models.traffic_light import TrafficLightLog

from app.services.db_queue import db_queue_service
from app.services.tls_config_service import tls_config_service

class TLSDataService:
    """Comprehensive Traffic Light System data collection and analysis service"""
    
    def __init__(self, app=None):
        self.app = app
        self.real_time_data = {}
        self.historical_stats = {}
        self.performance_metrics = defaultdict(lambda: deque(maxlen=1000))
        
        # Track last logged data for change detection
        self.last_logged_data = {}  # {tl_id: {state, phase, vehicle_count, efficiency_score, last_log_time}}
        self.MIN_LOG_INTERVAL = 30  # Minimum 30 simulation seconds between logs
        self.CHANGE_THRESHOLDS = {
            'vehicle_count': 3,      # ±3 vehicles
            'efficiency_score': 5,   # ±5 points
            'waiting_vehicles': 2    # ±2 waiting vehicles
        }
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def collect_tls_snapshot(self, traci, scenario: str) -> Dict[str, Any]:
        """
        Collect comprehensive TLS data from SUMO simulation
        """
        if not traci:
            return {}
        
        try:
            tl_ids = traci.trafficlight.getIDList()
            current_time = traci.simulation.getTime()
            snapshot = {
                'timestamp': current_time,
                'scenario': scenario,
                'traffic_lights': {},
                'summary': {
                    'total_tls': len(tl_ids),
                    'timestamp': current_time,
                    'scenario': scenario
                }
            }
            
            successful_collections = 0
            logged_count = 0
            
            for tl_id in tl_ids:
                try:
                    tl_data = self._get_comprehensive_tl_data(traci, tl_id, current_time, scenario)
                    if tl_data:  # Only add if data collection was successful
                        snapshot['traffic_lights'][tl_id] = tl_data
                        successful_collections += 1
                        
                        # Update real-time data store
                        self.real_time_data[tl_id] = tl_data
                        
                        # Queue for database storage - USING COMBINED APPROACH
                        if self._should_log_tls_data(tl_id, tl_data, current_time):
                            self._queue_tls_log(tl_data, scenario)
                            logged_count += 1
                    
                except Exception as e:
                    print(f"⚠️ Error collecting data for TLS {tl_id}: {e}")
                    continue
            
            # Update summary with successful count
            snapshot['summary']['successful_collections'] = successful_collections
            snapshot['summary']['collection_errors'] = len(tl_ids) - successful_collections
            snapshot['summary']['logged_instances'] = logged_count
            
            # Calculate summary statistics only if we have data
            if successful_collections > 0:
                snapshot['summary'].update(self._calculate_summary_stats(snapshot['traffic_lights']))
            
            print(f"📊 TLS Data: Collected {successful_collections} traffic lights, Logged {logged_count} instances")
            return snapshot
            
        except Exception as e:
            print(f"❌ Error in TLS data collection: {e}")
            return {}
    
    def _should_log_tls_data(self, tl_id: str, current_data: Dict, current_time: float) -> bool:
        """
        Determine if TLS data should be logged based on combined time-based + change-based approach
        """
        # Initialize if first time seeing this TLS
        if tl_id not in self.last_logged_data:
            self.last_logged_data[tl_id] = {
                'state': current_data['state'],
                'phase': current_data['phase'],
                'vehicle_count': current_data.get('performance', {}).get('total_vehicles', 0),
                'waiting_vehicles': current_data.get('performance', {}).get('waiting_vehicles', 0),
                'efficiency_score': current_data.get('performance', {}).get('efficiency_score', 0),
                'last_log_time': current_time
            }
            return True  # Always log first occurrence
        
        last_data = self.last_logged_data[tl_id]
        
        # Check time-based condition (minimum interval)
        time_since_last_log = current_time - last_data['last_log_time']
        if time_since_last_log < self.MIN_LOG_INTERVAL:
            return False
        
        # Check change-based conditions
        # significant_changes = self._detect_significant_changes(last_data, current_data)
        
        # Always log on state or phase changes (critical events)
        if current_data['state'] != last_data['state'] or current_data['phase'] != last_data['phase']:
            return True
        
        # Log if significant performance changes detected
        # if significant_changes:
        #     return True
        
        # Log if minimum time interval reached (even without significant changes)
        # This ensures we capture baseline data periodically
        if time_since_last_log >= self.MIN_LOG_INTERVAL * 2:  # Double the minimum interval
            return True
        
        return False
    
    def _detect_significant_changes(self, last_data: Dict, current_data: Dict) -> bool:
        """
        Detect significant changes in performance metrics
        """
        current_perf = current_data.get('performance', {})
        last_perf = last_data
        
        changes_detected = False
        
        # Check vehicle count change
        vehicle_diff = abs(current_perf.get('total_vehicles', 0) - last_perf.get('vehicle_count', 0))
        if vehicle_diff >= self.CHANGE_THRESHOLDS['vehicle_count']:
            changes_detected = True
        
        # Check efficiency score change
        efficiency_diff = abs(current_perf.get('efficiency_score', 0) - last_perf.get('efficiency_score', 0))
        if efficiency_diff >= self.CHANGE_THRESHOLDS['efficiency_score']:
            changes_detected = True
        
        # Check waiting vehicles change
        waiting_diff = abs(current_perf.get('waiting_vehicles', 0) - last_perf.get('waiting_vehicles', 0))
        if waiting_diff >= self.CHANGE_THRESHOLDS['waiting_vehicles']:
            changes_detected = True
        
        return changes_detected
    
    def _update_last_logged_data(self, tl_id: str, current_data: Dict, current_time: float):
        """
        Update the last logged data for a traffic light
        """
        self.last_logged_data[tl_id] = {
            'state': current_data['state'],
            'phase': current_data['phase'],
            'vehicle_count': current_data.get('performance', {}).get('total_vehicles', 0),
            'waiting_vehicles': current_data.get('performance', {}).get('waiting_vehicles', 0),
            'efficiency_score': current_data.get('performance', {}).get('efficiency_score', 0),
            'last_log_time': current_time
        }
    
    def _estimate_phase_count(self, state: str) -> int:
        """Estimate phase count based on state pattern"""
        if not state:
            return 4  # Default assumption
        
        # Common phase patterns
        if len(state) <= 4:
            return 4
        elif len(state) <= 8:
            return 4
        else:
            return 8  # For complex intersections
    
    def _get_comprehensive_tl_data(self, traci, tl_id: str, current_time: float, scenario: str) -> Dict[str, Any]:
        """Get comprehensive data for a single traffic light"""
        
        try:
            # Basic TLS information - using correct TraCI method names
            state = traci.trafficlight.getRedYellowGreenState(tl_id)
            phase = traci.trafficlight.getPhase(tl_id)
            phase_duration = traci.trafficlight.getPhaseDuration(tl_id)
            program_id = traci.trafficlight.getProgram(tl_id)
            next_switch = traci.trafficlight.getNextSwitch(tl_id) - current_time
            
            # Get phase count safely - this method might not exist in all SUMO versions
            try:
                phase_count = traci.trafficlight.getPhaseNumber(tl_id)
            except Exception:
                # Fallback: estimate phase count based on common patterns
                phase_count = self._estimate_phase_count(state)
            
            # Controlled lanes and traffic data
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            lane_data = self._get_lane_traffic_data(traci, controlled_lanes)
            
            current_phase_name = self._get_phase_name(state)
            
            # Calculate performance metrics
            performance = self._calculate_tl_performance(traci, tl_id, controlled_lanes, state)
            
            # Build comprehensive data structure
            tl_data = {
                'id': tl_id,
                'state': state,
                'phase': phase,
                'phase_name': current_phase_name,
                'phase_duration': phase_duration,
                'phase_count': phase_count,
                'program_id': program_id,
                'next_switch': next_switch,
                'controlled_lanes': controlled_lanes,
                'lane_data': lane_data,
                'performance': performance,
                'timestamp': current_time,
                'scenario': scenario,
                'signal_groups': self._analyze_signal_groups(state),
                'optimization_metrics': self._calculate_optimization_metrics(performance, lane_data)
            }
            
            return tl_data
            
        except Exception as e:
            print(f"❌ Error in _get_comprehensive_tl_data for {tl_id}: {e}")
            # Return basic data even if some methods fail
            return self._get_basic_tl_data(traci, tl_id, current_time, scenario)
    
    def _get_basic_tl_data(self, traci, tl_id: str, current_time: float, scenario: str) -> Dict[str, Any]:
        """Get basic TLS data when comprehensive collection fails"""
        try:
            state = traci.trafficlight.getRedYellowGreenState(tl_id)
            phase = traci.trafficlight.getPhase(tl_id)
            
            return {
                'id': tl_id,
                'state': state,
                'phase': phase,
                'phase_name': self._get_phase_name(state),
                'timestamp': current_time,
                'scenario': scenario,
                'basic_data': True  # Flag to indicate this is basic data
            }
        except Exception as e:
            print(f"❌ Even basic data collection failed for {tl_id}: {e}")
            return None
    
    def _get_lane_traffic_data(self, traci, lane_ids: List[str]) -> Dict[str, Any]:
        """Get traffic data for controlled lanes"""
        lane_data = {}
        total_vehicles = 0
        total_waiting = 0
        total_speed = 0
        lane_count = 0
        
        for lane_id in lane_ids:
            try:
                vehicles = traci.lane.getLastStepVehicleNumber(lane_id)
                waiting = traci.lane.getLastStepHaltingNumber(lane_id)
                speed = traci.lane.getLastStepMeanSpeed(lane_id)
                occupancy = traci.lane.getLastStepOccupancy(lane_id)
                
                lane_data[lane_id] = {
                    'vehicle_count': vehicles,
                    'waiting_vehicles': waiting,
                    'average_speed': speed * 3.6,  # Convert to km/h
                    'occupancy': occupancy,
                    'length': traci.lane.getLength(lane_id),
                    'max_speed': traci.lane.getMaxSpeed(lane_id) * 3.6
                }
                
                total_vehicles += vehicles
                total_waiting += waiting
                total_speed += speed
                lane_count += 1
                
            except Exception as e:
                continue
        
        avg_speed = (total_speed / lane_count * 3.6) if lane_count > 0 else 0
        
        return {
            'lanes': lane_data,
            'summary': {
                'total_vehicles': total_vehicles,
                'total_waiting': total_waiting,
                'average_speed': round(avg_speed, 2),
                'total_lanes': len(lane_ids),
                'successful_lanes': lane_count
            }
        }
    
    def _calculate_tl_performance(self, traci, tl_id: str, controlled_lanes: List[str], state: str) -> Dict[str, Any]:
        """Calculate performance metrics for traffic light"""
        
        # Get lane data for performance calculation
        total_vehicles = 0
        total_waiting = 0
        
        for lane_id in controlled_lanes:
            try:
                total_vehicles += traci.lane.getLastStepVehicleNumber(lane_id)
                total_waiting += traci.lane.getLastStepHaltingNumber(lane_id)
            except:
                continue
        
        # Calculate efficiency metrics
        green_ratio = state.count('G') / len(state) if state else 0
        efficiency_score = green_ratio * 100
        
        # Determine congestion level
        if total_waiting > 10:
            congestion_level = 'HIGH'
        elif total_waiting > 5:
            congestion_level = 'MEDIUM'
        else:
            congestion_level = 'LOW'
        
        return {
            'efficiency_score': round(efficiency_score, 2),
            'congestion_level': congestion_level,
            'total_vehicles': total_vehicles,
            'waiting_vehicles': total_waiting,
            'green_ratio': round(green_ratio, 2),
            'throughput': total_vehicles,
            'performance_grade': self._calculate_performance_grade(efficiency_score, total_waiting)
        }
    
    def _calculate_optimization_metrics(self, performance: Dict, lane_data: Dict) -> Dict[str, Any]:
        """Calculate optimization metrics and recommendations"""
        recommendations = []
        optimization_score = 0
        
        # Analyze for optimization opportunities
        if performance['waiting_vehicles'] > 8 and performance['green_ratio'] < 0.3:
            recommendations.append("High congestion detected - consider increasing green time")
            optimization_score -= 20
        
        if performance['efficiency_score'] > 80:
            optimization_score += 10
            recommendations.append("Good efficiency - current configuration is working well")
        
        lane_summary = lane_data.get('summary', {})
        if lane_summary.get('average_speed', 0) < 10:  # Less than 10 km/h
            recommendations.append("Low average speed - check for bottlenecks")
            optimization_score -= 15
        
        # Calculate overall optimization score (0-100)
        optimization_score = max(0, min(100, 70 + optimization_score))
        
        return {
            'optimization_score': optimization_score,
            'recommendations': recommendations,
            'priority_level': 'HIGH' if optimization_score < 60 else 'MEDIUM' if optimization_score < 80 else 'LOW'
        }
    
    def _analyze_signal_groups(self, state: str) -> List[Dict[str, Any]]:
        """Analyze signal groups from state string"""
        signal_groups = []
        
        if not state:
            return signal_groups
        
        # Simple analysis - in real implementation, this would be more sophisticated
        groups = []
        current_char = state[0]
        current_count = 1
        
        for i in range(1, len(state)):
            if state[i] == current_char:
                current_count += 1
            else:
                groups.append({'signal': current_char, 'count': current_count})
                current_char = state[i]
                current_count = 1
        
        groups.append({'signal': current_char, 'count': current_count})
        
        # Convert to signal groups with meanings
        for group in groups:
            signal_type = self._get_signal_type(group['signal'])
            signal_groups.append({
                'signal': group['signal'],
                'count': group['count'],
                'type': signal_type,
                'meaning': self._get_signal_meaning(group['signal'])
            })
        
        return signal_groups
    
    def _get_signal_type(self, signal: str) -> str:
        """Get signal type from character"""
        signal_types = {
            'G': 'GREEN',
            'g': 'GREEN_PEDESTRIAN', 
            'y': 'YELLOW',
            'r': 'RED',
            'u': 'RED_YELLOW',
            ' ': 'OFF',
            'O': 'OFF',
            'o': 'OFF'
        }
        return signal_types.get(signal, 'UNKNOWN')
    
    def _get_signal_meaning(self, signal: str) -> str:
        """Get human-readable meaning of signal"""
        meanings = {
            'G': 'Green for vehicles',
            'g': 'Green for pedestrians',
            'y': 'Yellow (prepare to stop)',
            'r': 'Red (stop)',
            'u': 'Red + Yellow (prepare to go)',
            ' ': 'Signal off',
            'O': 'Signal off',
            'o': 'Signal off'
        }
        return meanings.get(signal, f'Unknown signal: {signal}')
    
    def _get_phase_name(self, state: str) -> str:
        """Get phase name from state"""
        if not state:
            return 'UNKNOWN'
        
        if 'G' in state and 'r' in state:
            return 'MAIN_GREEN'
        elif 'y' in state and 'r' in state:
            return 'YELLOW'
        elif 'r' in state and 'G' in state:
            return 'SIDE_GREEN'
        elif 'r' in state and 'y' in state:
            return 'SIDE_YELLOW'
        elif 'g' in state and 'r' in state:
            return 'PEDESTRIAN_GREEN'
        else:
            return 'COMPLEX'
    
    def _calculate_performance_grade(self, efficiency: float, waiting: int) -> str:
        """Calculate performance grade"""
        if efficiency > 85 and waiting < 3:
            return 'A'
        elif efficiency > 70 and waiting < 6:
            return 'B'
        elif efficiency > 60 and waiting < 10:
            return 'C'
        else:
            return 'D'
    
    def _calculate_summary_stats(self, traffic_lights: Dict) -> Dict[str, Any]:
        """Calculate summary statistics for all traffic lights"""
        if not traffic_lights:
            return {}
        
        total_tls = len(traffic_lights)
        avg_efficiency = 0
        total_waiting = 0
        total_vehicles = 0
        grade_distribution = defaultdict(int)
        
        valid_tls = 0
        
        for tl_id, tl_data in traffic_lights.items():
            # Skip TLS with only basic data
            if tl_data.get('basic_data'):
                continue
                
            perf = tl_data.get('performance', {})
            efficiency = perf.get('efficiency_score', 0)
            waiting = perf.get('waiting_vehicles', 0)
            vehicles = perf.get('total_vehicles', 0)
            
            if efficiency > 0:  # Only count valid data
                avg_efficiency += efficiency
                total_waiting += waiting
                total_vehicles += vehicles
                grade = perf.get('performance_grade', 'D')
                grade_distribution[grade] += 1
                valid_tls += 1
        
        if valid_tls > 0:
            avg_efficiency = avg_efficiency / valid_tls
            avg_waiting = total_waiting / valid_tls
        else:
            avg_efficiency = 0
            avg_waiting = 0
        
        return {
            'average_efficiency': round(avg_efficiency, 2),
            'average_waiting_vehicles': round(avg_waiting, 2),
            'total_vehicles_observed': total_vehicles,
            'performance_grade_distribution': dict(grade_distribution),
            'overall_performance_grade': self._calculate_overall_grade(avg_efficiency, avg_waiting),
            'valid_tls_count': valid_tls,
            'basic_data_tls': total_tls - valid_tls
        }
    
    def _calculate_overall_grade(self, efficiency: float, avg_waiting: float) -> str:
        """Calculate overall performance grade"""
        if efficiency > 80 and avg_waiting < 2:
            return 'A'
        elif efficiency > 65 and avg_waiting < 4:
            return 'B'
        elif efficiency > 50 and avg_waiting < 6:
            return 'C'
        else:
            return 'D'
    
    def _queue_tls_log(self, tl_data: Dict, scenario: str):
        """Queue TLS data for database storage using queue service"""
        if not db_queue_service:
            print("❌ DB Queue Service not available")
            return

        try:
            log_data = {
                'id': str(uuid.uuid4()),
                'traffic_light_id': tl_data['id'],
                'scenario': scenario,
                'simulation_time': tl_data['timestamp'],
                'state': tl_data['state'],
                'phase': tl_data['phase'],
                'phase_name': tl_data['phase_name'],
                'duration': tl_data.get('phase_duration', 0),
                'next_switch': tl_data.get('next_switch', 0),
                'vehicle_count': tl_data.get('performance', {}).get('total_vehicles', 0),
                'waiting_vehicles': tl_data.get('performance', {}).get('waiting_vehicles', 0),
                'efficiency_score': tl_data.get('performance', {}).get('efficiency_score', 0),
                'performance_grade': tl_data.get('performance', {}).get('performance_grade', 'D'),
                'created_at': datetime.utcnow()
            }

            print(f"📤 Queueing TLS log for {tl_data['id']}")

            if self.app:
                with self.app.app_context():
                    db_queue_service.add_traffic_light_log(log_data)
                    # MANUALLY TRIGGER FLUSH TO SEE WHAT HAPPENS
                    print(f"🔍 Queue size: {len(db_queue_service.queue)}")
                    if len(db_queue_service.queue) >= 1:  # Flush even with 1 item for testing
                        print("🔍 Manually triggering flush...")
                        db_queue_service.flush_queue()
            else:
                print("❌ No app context available")
                return

            self._update_last_logged_data(tl_data['id'], tl_data, tl_data['timestamp'])

        except Exception as e:
            print(f"❌ Error queuing TLS log: {e}")
            import traceback
            traceback.print_exc()
    
    def store_traffic_pattern(self, pattern_data: Dict):
        """Store traffic pattern using queue service"""
        if not db_queue_service:
            print("❌ DB Queue Service not available for pattern storage")
            return
        
        try:
            db_queue_service.add_traffic_pattern(pattern_data)
            print(f"📊 Queued traffic pattern for {pattern_data.get('traffic_light_id', 'unknown')}")
        except Exception as e:
            print(f"❌ Error queuing traffic pattern: {e}")
    
    # Analysis Methods
    def get_tls_analysis(self, tl_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive analysis for a specific TLS"""
        if not self.app:
            return {"error": "Service not initialized with app context"}
            
        with self.app.app_context():
            try:
                # Get recent logs
                since_time = datetime.utcnow() - timedelta(hours=hours)
                logs = TrafficLightLog.query.filter(
                    TrafficLightLog.traffic_light_id == tl_id,
                    TrafficLightLog.created_at >= since_time
                ).order_by(TrafficLightLog.simulation_time).all()
                
                if not logs:
                    return {"error": f"No data available for traffic light {tl_id}"}
                
                return self._analyze_tls_logs(logs, tl_id)
                
            except Exception as e:
                return {"error": f"Analysis failed: {str(e)}"}
    
    def _analyze_tls_logs(self, logs: List[TrafficLightLog], tl_id: str) -> Dict[str, Any]:
        """Analyze TLS logs for patterns and insights"""
        try:
            analysis = {
                'traffic_light_id': tl_id,
                'analysis_period': {
                    'start': logs[0].created_at.isoformat(),
                    'end': logs[-1].created_at.isoformat(),
                    'total_logs': len(logs)
                },
                'performance_metrics': {},
                'phase_analysis': {},
                'recommendations': []
            }
            
            # Calculate performance metrics
            total_efficiency = sum(log.efficiency_score or 0 for log in logs)
            total_waiting = sum(log.waiting_vehicles or 0 for log in logs)
            total_vehicles = sum(log.vehicle_count or 0 for log in logs)
            
            analysis['performance_metrics'] = {
                'average_efficiency': round(total_efficiency / len(logs), 2),
                'average_waiting_vehicles': round(total_waiting / len(logs), 2),
                'total_vehicles_observed': total_vehicles,
                'efficiency_trend': self._calculate_efficiency_trend(logs)
            }
            
            # Phase analysis
            analysis['phase_analysis'] = self._analyze_phase_patterns(logs)
            
            # Generate recommendations
            analysis['recommendations'] = self._generate_data_driven_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            return {"error": f"Log analysis failed: {str(e)}"}
    
    def _calculate_efficiency_trend(self, logs: List[TrafficLightLog]) -> str:
        """Calculate efficiency trend over time"""
        if len(logs) < 10:
            return "INSUFFICIENT_DATA"
        
        # Simple trend analysis - compare first and last quarters
        quarter = len(logs) // 4
        early_avg = sum(log.efficiency_score or 0 for log in logs[:quarter]) / quarter
        late_avg = sum(log.efficiency_score or 0 for log in logs[-quarter:]) / quarter
        
        if late_avg > early_avg + 5:
            return "IMPROVING"
        elif late_avg < early_avg - 5:
            return "DECLINING"
        else:
            return "STABLE"
    
    def _analyze_phase_patterns(self, logs: List[TrafficLightLog]) -> Dict[str, Any]:
        """Analyze phase patterns and durations"""
        phase_data = defaultdict(list)
        
        for log in logs:
            if log.phase_name:
                phase_data[log.phase_name].append({
                    'duration': log.duration or 0,
                    'waiting_vehicles': log.waiting_vehicles or 0,
                    'efficiency': log.efficiency_score or 0
                })
        
        analysis = {}
        for phase_name, data in phase_data.items():
            if data:
                avg_duration = sum(d['duration'] for d in data) / len(data)
                avg_waiting = sum(d['waiting_vehicles'] for d in data) / len(data)
                avg_efficiency = sum(d['efficiency'] for d in data) / len(data)
                
                analysis[phase_name] = {
                    'average_duration': round(avg_duration, 2),
                    'average_waiting': round(avg_waiting, 2),
                    'average_efficiency': round(avg_efficiency, 2),
                    'occurrence_count': len(data)
                }
        
        return analysis
    
    def _generate_data_driven_recommendations(self, analysis: Dict) -> List[str]:
        """Generate recommendations based on data analysis"""
        recommendations = []
        metrics = analysis.get('performance_metrics', {})
        phase_analysis = analysis.get('phase_analysis', {})
        
        if metrics.get('average_efficiency', 0) < 60:
            recommendations.append("Consider optimizing traffic light timing - current efficiency is low")
        
        if metrics.get('average_waiting_vehicles', 0) > 5:
            recommendations.append("High vehicle wait times detected - review phase durations")
        
        # Analyze specific phases
        for phase_name, data in phase_analysis.items():
            if data['average_waiting'] > 3 and data['average_duration'] < 20:
                recommendations.append(f"Consider increasing duration for {phase_name} phase")
            elif data['average_waiting'] < 1 and data['average_duration'] > 40:
                recommendations.append(f"Consider reducing duration for {phase_name} phase - underutilized")
        
        if not recommendations:
            recommendations.append("Current configuration appears optimal - continue monitoring")
        
        return recommendations

# Global instance
tls_data_service = TLSDataService()

def init_tls_data_service(app):
    """Initialize TLS data service"""
    tls_data_service.init_app(app)