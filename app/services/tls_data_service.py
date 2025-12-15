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
# from app.services.ai_optimization_controller import ai_controller

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
        
        # Always log on state or phase changes (critical events)
        if current_data['state'] != last_data['state'] or current_data['phase'] != last_data['phase']:
            return True
        
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
        """Get comprehensive data for a single traffic light including vehicle types"""
        
        try:
            # Basic TLS information
            state = traci.trafficlight.getRedYellowGreenState(tl_id)
            phase = traci.trafficlight.getPhase(tl_id)
            phase_duration = traci.trafficlight.getPhaseDuration(tl_id)
            program_id = traci.trafficlight.getProgram(tl_id)
            next_switch = traci.trafficlight.getNextSwitch(tl_id) - current_time
            
            try:
                phase_count = traci.trafficlight.getPhaseNumber(tl_id)
            except Exception:
                phase_count = self._estimate_phase_count(state)
            
            # Controlled lanes and traffic data (NOW INCLUDES VEHICLE TYPES)
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            lane_data = self._get_lane_traffic_data(traci, controlled_lanes)
            
            current_phase_name = self._get_phase_name(state)
            
            # Calculate performance metrics (PASS lane_data to avoid duplicate calls)
            performance = self._calculate_tl_performance(traci, tl_id, controlled_lanes, state, lane_data)
            
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
                'optimization_metrics': self._calculate_optimization_metrics(performance, lane_data),
                'data_collection_mode': 'RAW_SUMO'
            }
            
            return tl_data
            
        except Exception as e:
            print(f"❌ Error in _get_comprehensive_tl_data for {tl_id}: {e}")
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
        """Get traffic data for controlled lanes including vehicle types"""
        lane_data = {}
        total_vehicles = 0
        total_waiting = 0
        total_speed = 0
        lane_count = 0

        # Vehicle type counters
        vehicle_type_counts = {
            'passenger': 0,
            'truck': 0,
            'bus': 0,
            'motorcycle': 0,
            'bicycle': 0,
            'emergency': 0,
            'other': 0
        }

        for lane_id in lane_ids:
            try:
                vehicles = traci.lane.getLastStepVehicleNumber(lane_id)
                waiting = traci.lane.getLastStepHaltingNumber(lane_id)
                speed = traci.lane.getLastStepMeanSpeed(lane_id)
                occupancy = traci.lane.getLastStepOccupancy(lane_id)

                # NEW: Get vehicle IDs on this lane and classify them
                vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
                lane_vehicle_types = self._classify_vehicles_on_lane(traci, vehicle_ids)

                # Aggregate vehicle types
                for vtype, count in lane_vehicle_types.items():
                    vehicle_type_counts[vtype] += count

                lane_data[lane_id] = {
                    'vehicle_count': vehicles,
                    'waiting_vehicles': waiting,
                    'average_speed': speed * 3.6,  # Convert to km/h
                    'occupancy': occupancy,
                    'length': traci.lane.getLength(lane_id),
                    'max_speed': traci.lane.getMaxSpeed(lane_id) * 3.6,
                    'vehicle_types': lane_vehicle_types  # NEW: vehicle types on this lane
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
            },
            'vehicle_type_distribution': vehicle_type_counts  # NEW: overall distribution
        }
    
    def _classify_vehicles_on_lane(self, traci, vehicle_ids: List[str]) -> Dict[str, int]:
        """
        Classify vehicles by type - CUSTOMIZED for carprice.rou.xml vehicle types
        
        Your vehicle types from the route file:
        - passenger_car (will be added)
        - DEFAULT_BIKETYPE (motorcycle class)
        - Police (authority class)
        - ambulance (emergency class)
        - bus (bus class)
        - truck (truck class)
        
        Plus flows without types (blue-car, green-car, etc.) default to passenger
        """
        type_counts = {
            'passenger': 0,
            'truck': 0,
            'bus': 0,
            'motorcycle': 0,
            'bicycle': 0,
            'emergency': 0,
            'other': 0
        }
        
        for veh_id in vehicle_ids:
            try:
                # Get SUMO vehicle type ID (exactly as defined in your .rou.xml)
                vtype = traci.vehicle.getTypeID(veh_id)
                
                # Also get vehicle class for better classification
                try:
                    vclass = traci.vehicle.getVehicleClass(veh_id).lower()
                except:
                    vclass = ""
                
                # EXACT MATCHING for your specific vehicle types
                if vtype == 'passenger_car':
                    type_counts['passenger'] += 1
                    
                elif vtype == 'truck':
                    type_counts['truck'] += 1
                    
                elif vtype == 'bus':
                    type_counts['bus'] += 1
                    
                elif vtype == 'DEFAULT_BIKETYPE':
                    type_counts['motorcycle'] += 1
                    
                elif vtype in ['ambulance', 'Police']:
                    type_counts['emergency'] += 1
                    
                # Fallback to vehicle class if type doesn't match
                elif 'passenger' in vclass:
                    type_counts['passenger'] += 1
                    
                elif 'truck' in vclass or 'trailer' in vclass:
                    type_counts['truck'] += 1
                    
                elif 'bus' in vclass:
                    type_counts['bus'] += 1
                    
                elif 'motorcycle' in vclass or 'moped' in vclass:
                    type_counts['motorcycle'] += 1
                    
                elif 'bicycle' in vclass:
                    type_counts['bicycle'] += 1
                    
                elif 'emergency' in vclass or 'authority' in vclass:
                    type_counts['emergency'] += 1
                    
                else:
                    # DEFAULT: If type is empty or unrecognized, assume passenger car
                    # This handles flows without type specification (blue-car, green-car, etc.)
                    type_counts['passenger'] += 1
                    
            except Exception as e:
                # If we can't get vehicle type, count as passenger (most common)
                type_counts['passenger'] += 1
                continue
            
        return type_counts
    
    def _get_lane_traffic_data_with_debug(self, traci, lane_ids: List[str]) -> Dict[str, Any]:
        """
        Enhanced version with debugging to see what's happening
        """
        lane_data = {}
        total_vehicles = 0
        total_waiting = 0
        total_speed = 0
        lane_count = 0
        
        # Vehicle type counters
        vehicle_type_counts = {
            'passenger': 0,
            'truck': 0,
            'bus': 0,
            'motorcycle': 0,
            'bicycle': 0,
            'emergency': 0,
            'other': 0
        }
        
        # DEBUG: Check if we're getting any vehicles at all
        total_vehicles_found = 0
        
        for lane_id in lane_ids:
            try:
                vehicles = traci.lane.getLastStepVehicleNumber(lane_id)
                waiting = traci.lane.getLastStepHaltingNumber(lane_id)
                speed = traci.lane.getLastStepMeanSpeed(lane_id)
                occupancy = traci.lane.getLastStepOccupancy(lane_id)
                
                # Get vehicle IDs on this lane
                vehicle_ids = traci.lane.getLastStepVehicleIDs(lane_id)
                total_vehicles_found += len(vehicle_ids)
                
                print(f"🚗 Lane {lane_id}: {len(vehicle_ids)} vehicles - IDs: {vehicle_ids[:3]}")  # Show first 3
                
                # Classify vehicles
                lane_vehicle_types = self._classify_vehicles_on_lane(traci, vehicle_ids)
                
                # Aggregate vehicle types
                for vtype, count in lane_vehicle_types.items():
                    vehicle_type_counts[vtype] += count
                
                lane_data[lane_id] = {
                    'vehicle_count': vehicles,
                    'waiting_vehicles': waiting,
                    'average_speed': speed * 3.6,
                    'occupancy': occupancy,
                    'length': traci.lane.getLength(lane_id),
                    'max_speed': traci.lane.getMaxSpeed(lane_id) * 3.6,
                    'vehicle_types': lane_vehicle_types
                }
                
                total_vehicles += vehicles
                total_waiting += waiting
                total_speed += speed
                lane_count += 1
                
            except Exception as e:
                print(f"❌ Error processing lane {lane_id}: {e}")
                continue
        
        avg_speed = (total_speed / lane_count * 3.6) if lane_count > 0 else 0
        
        print(f"📊 FINAL COUNTS: Total vehicles: {total_vehicles_found}, Distribution: {vehicle_type_counts}")
        
        return {
            'lanes': lane_data,
            'summary': {
                'total_vehicles': total_vehicles,
                'total_waiting': total_waiting,
                'average_speed': round(avg_speed, 2),
                'total_lanes': len(lane_ids),
                'successful_lanes': lane_count
            },
            'vehicle_type_distribution': vehicle_type_counts
        }
    
    
    def diagnose_vehicle_types(self, traci):
        """
        DIAGNOSTIC FUNCTION: Call this once to see what vehicle types exist in your simulation
        Add this to your simulation initialization to debug
        """
        print("\n" + "="*60)
        print("🔍 VEHICLE TYPE DIAGNOSTIC")
        print("="*60)
        
        try:
            # Get all vehicles in simulation
            all_vehicles = traci.vehicle.getIDList()
            print(f"✅ Total vehicles in simulation: {len(all_vehicles)}")
            
            if len(all_vehicles) == 0:
                print("⚠️  WARNING: No vehicles found in simulation!")
                print("   Check if simulation has started and vehicles are loaded")
                return
            
            # Sample first 20 vehicles
            sample_vehicles = all_vehicles[:min(20, len(all_vehicles))]
            
            type_distribution = {}
            class_distribution = {}
            
            print(f"\n📋 Sampling {len(sample_vehicles)} vehicles:\n")
            
            for veh_id in sample_vehicles:
                try:
                    vtype = traci.vehicle.getTypeID(veh_id)
                    
                    # Count types
                    type_distribution[vtype] = type_distribution.get(vtype, 0) + 1
                    
                    # Try to get vehicle class
                    try:
                        vclass = traci.vehicle.getVehicleClass(veh_id)
                        class_distribution[vclass] = class_distribution.get(vclass, 0) + 1
                        print(f"  {veh_id}: type='{vtype}', class='{vclass}'")
                    except:
                        print(f"  {veh_id}: type='{vtype}', class=N/A")
                        
                except Exception as e:
                    print(f"  {veh_id}: ERROR - {e}")
            
            print(f"\n📊 Type Distribution:")
            for vtype, count in sorted(type_distribution.items(), key=lambda x: x[1], reverse=True):
                print(f"  '{vtype}': {count} vehicles")
            
            print(f"\n📊 Vehicle Class Distribution:")
            for vclass, count in sorted(class_distribution.items(), key=lambda x: x[1], reverse=True):
                print(f"  '{vclass}': {count} vehicles")
            
            # Recommendations
            print(f"\n💡 RECOMMENDATIONS:")
            
            if len(type_distribution) == 1 and 'DEFAULT_VEHTYPE' in list(type_distribution.keys())[0].upper():
                print("  ⚠️  All vehicles have the same default type!")
                print("  ➡️  You need to define vehicle types in your .rou.xml file")
                print("  ➡️  Example:")
                print("      <vType id='passenger_car' vClass='passenger' length='4.5'/>")
                print("      <vType id='truck' vClass='truck' length='7.5'/>")
                print("      <vehicle id='veh_1' type='passenger_car' depart='0'>")
            else:
                print("  ✅ Multiple vehicle types detected!")
                print("  ➡️  Update classification logic to match these type names")
            
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"❌ Diagnostic failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_tl_performance(self, traci, tl_id: str, controlled_lanes: List[str], 
                              state: str, lane_data: Dict = None) -> Dict[str, Any]:
        """Calculate performance metrics for traffic light including vehicle types"""

        # Get lane data for performance calculation
        total_vehicles = 0
        total_waiting = 0
        vehicle_types = {
            'passenger': 0,
            'truck': 0,
            'bus': 0,
            'motorcycle': 0,
            'bicycle': 0,
            'emergency': 0
        }

        # If lane_data is provided, use it (to avoid duplicate TraCI calls)
        if lane_data and 'vehicle_type_distribution' in lane_data:
            vehicle_types = lane_data['vehicle_type_distribution']
            total_vehicles = lane_data['summary']['total_vehicles']
            total_waiting = lane_data['summary']['total_waiting']
        else:
            # Fallback: calculate from scratch
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
            'performance_grade': self._calculate_performance_grade(efficiency_score, total_waiting),
            'vehicle_types': vehicle_types  # NEW: Include vehicle type breakdown
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
        """Queue TLS data for database storage with vehicle type information"""

        if not db_queue_service:
            print("❌ DB Queue Service not available")
            return

        try:
            performance = tl_data.get('performance', {})
            vehicle_types = performance.get('vehicle_types', {})
            lane_data = tl_data.get('lane_data', {})
            vehicle_distribution = lane_data.get('vehicle_type_distribution', {})

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

                # Total counts
                'vehicle_count': performance.get('total_vehicles', 0),
                'waiting_vehicles': performance.get('waiting_vehicles', 0),

                # NEW: Vehicle type breakdown
                'passenger_count': vehicle_types.get('passenger', 0),
                'truck_count': vehicle_types.get('truck', 0),
                'bus_count': vehicle_types.get('bus', 0),
                'motorcycle_count': vehicle_types.get('motorcycle', 0),
                'bicycle_count': vehicle_types.get('bicycle', 0),
                'emergency_count': vehicle_types.get('emergency', 0),

                # NEW: Detailed distribution as JSON
                'vehicle_type_distribution': vehicle_distribution,

                # Performance metrics
                'efficiency_score': performance.get('efficiency_score', 0),
                'performance_grade': performance.get('performance_grade', 'D'),

                # Metadata
                'collection_mode': None,
                'ai_enabled_during_collection': False,
                'created_at': datetime.utcnow()
            }

            print(f"📤 Queueing TLS log for {tl_data['id']} with vehicle types: {vehicle_types}")

            if self.app:
                with self.app.app_context():
                    db_queue_service.add_traffic_light_log(log_data)
                    print(f"📊 Queue size: {len(db_queue_service.queue)}")
                    if len(db_queue_service.queue) >= 1:
                        print("🔄 Manually triggering flush...")
                        db_queue_service.flush_queue()
            else:
                print("❌ No app context available")
                return

            self._update_last_logged_data(tl_data['id'], tl_data, tl_data['timestamp'])

        except Exception as e:
            print(f"❌ Error queuing TLS log: {e}")
            import traceback
            traceback.print_exc()
    
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