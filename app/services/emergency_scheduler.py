# services/emergency_scheduler.py
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from app.extensions import db
from app.models.emergency_veh import GreenWaveSchedule, EmergencySchedule
from app.models.traffic_light import TrafficLightConfig

class EmergencySchedulerService:
    """
    Service for manual emergency vehicle scheduling and green wave management
    """
    
    def __init__(self, app=None):
        self.app = app
        self.active_emergencies = {}
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def schedule_emergency(self, emergency_data: Dict) -> Dict[str, Any]:
        """Schedule emergency vehicle via web form"""
        if not self.app:
            return {"success": False, "error": "No app context"}
            
        try:
            with self.app.app_context():
                # Generate unique ID
                emergency_id = f"emergency_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                
                # Create emergency schedule
                emergency_schedule = EmergencySchedule(
                    id=emergency_id,
                    scenario=emergency_data['scenario'],
                    emergency_type=emergency_data['emergency_type'],
                    priority=emergency_data['priority'],
                    vehicle_id=emergency_data['vehicle_id'],
                    description=emergency_data.get('description', ''),
                    departure_time=emergency_data['departure_time'],
                    estimated_duration=emergency_data.get('estimated_duration', 300.0),
                    from_location=emergency_data.get('from_location', ''),
                    to_location=emergency_data.get('to_location', ''),
                    route_edges=emergency_data['route_edges'],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                
                db.session.add(emergency_schedule)
                db.session.commit()
                
                # Add to active tracking
                self.active_emergencies[emergency_id] = {
                    'schedule': emergency_schedule.to_dict(),
                    'status': 'SCHEDULED'
                }
                
                print(f"✅ Emergency scheduled: {emergency_id} - {emergency_data['vehicle_id']}")
                
                return {
                    "success": True,
                    "emergency_id": emergency_id,
                    "message": "Emergency scheduled successfully. Please schedule green waves separately."
                }
                
        except Exception as e:
            print(f"❌ Error scheduling emergency: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}
    
    def schedule_green_wave(self, green_wave_data: Dict) -> Dict[str, Any]:
        """Schedule green wave manually via web form"""
        if not self.app:
            return {"success": False, "error": "No app context"}
            
        try:
            with self.app.app_context():
                # Generate unique ID
                green_wave_id = f"greenwave_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                
                # Verify traffic light exists in TLS config
                if not self._verify_traffic_light_config(green_wave_data['traffic_light_id']):
                    return {
                        "success": False, 
                        "error": f"Traffic light {green_wave_data['traffic_light_id']} not found in TLS configuration"
                    }
                
                # Create green wave schedule
                green_wave = GreenWaveSchedule(
                    id=green_wave_id,
                    emergency_id=green_wave_data.get('emergency_id'),
                    traffic_light_id=green_wave_data['traffic_light_id'],
                    edge=green_wave_data.get('edge', ''),
                    green_wave_type=green_wave_data.get('green_wave_type', 'EMERGENCY'),
                    description=green_wave_data.get('description', ''),
                    scheduled_start=green_wave_data['scheduled_start'],
                    duration=green_wave_data['duration']
                )
                
                db.session.add(green_wave)
                db.session.commit()
                
                print(f"✅ Green wave scheduled: {green_wave_id} - {green_wave_data['traffic_light_id']}")
                
                return {
                    "success": True,
                    "green_wave_id": green_wave_id,
                    "message": "Green wave scheduled successfully"
                }
                
        except Exception as e:
            print(f"❌ Error scheduling green wave: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}
    
    def _verify_traffic_light_config(self, tl_id: str) -> bool:
        """Verify traffic light exists in TLS configuration database"""
        try:
            config = TrafficLightConfig.query.filter_by(traffic_light_id=tl_id).first()
            return config is not None
        except Exception as e:
            print(f"⚠️ Error verifying traffic light config: {e}")
            return False
    
    def _calculate_green_waves(self, emergency_data: Dict) -> List[Dict]:
        """Calculate green wave timing along the route"""
        green_waves = []
        current_time = emergency_data['departure_time']
        route_edges = emergency_data['route_edges']
        
        # Edge travel time estimates (in seconds)
        edge_travel_times = {
            'E0': 10.0, '-E0': 10.0, 'E1': 12.0, '-E1': 12.0,
            'E2': 8.0, '-E2': 8.0, 'E0.55': 10.0, '-E0.55': 10.0
        }
        
        for i, edge in enumerate(route_edges):
            # Get traffic light for this edge
            tl_id = self._get_traffic_light_for_edge(edge)
            if tl_id:
                # Estimate travel time to this intersection
                travel_time = edge_travel_times.get(edge, 10.0)
                arrival_time = current_time + travel_time
                
                # Schedule green wave 15 seconds before arrival
                green_start = max(current_time, arrival_time - 15)
                
                green_waves.append({
                    'traffic_light_id': tl_id,
                    'edge': edge,
                    'scheduled_start': green_start,
                    'duration': 25.0,  # 25 seconds green
                    'arrival_time': arrival_time,
                    'position_in_route': i
                })
                
                current_time = arrival_time + 3.0  # Intersection crossing time
        
        return green_waves
    
    def _get_traffic_light_for_edge(self, edge: str) -> Optional[str]:
        """Get traffic light controlling an edge by checking TLS config DB"""
        try:
            tls_list = self.get_traffic_lights_for_edge(edge)
            if tls_list:
                return tls_list[0]['traffic_light_id']  # Return first matching TLS
            return None
        except Exception as e:
            print(f"⚠️ Error getting traffic light for edge {edge}: {e}")
            return None
    
    def get_traffic_lights_for_edge(self, edge: str) -> List[Dict]:
        """Get traffic lights that control a specific edge by checking TLS config"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                # Get all TLS configurations
                tls_configs = TrafficLightConfig.query.all()
                matching_tls = []
                
                for config in tls_configs:
                    # Check if this TLS controls the requested edge
                    controlled_lanes = config.controlled_lanes or []
                    for lane in controlled_lanes:
                        if lane.startswith(edge + '_'):
                            matching_tls.append({
                                'traffic_light_id': config.traffic_light_id,
                                'program_id': config.program_id,
                                'phases': config.phases,
                                'controlled_lanes': controlled_lanes,
                                'cycle_time': config.cycle_time
                            })
                            break  # Found this TLS, move to next
                
                return matching_tls
                
        except Exception as e:
            print(f"❌ Error getting traffic lights for edge: {e}")
            return []
    
    def get_traffic_lights_by_scenario(self, scenario: str) -> List[Dict]:
        """Get traffic lights for a specific scenario"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                tls_configs = TrafficLightConfig.query.filter_by(scenario=scenario).all()
                return [
                    {
                        'traffic_light_id': config.traffic_light_id,
                        'program_id': config.program_id,
                        'phases': config.phases,
                        'controlled_lanes': config.controlled_lanes,
                        'cycle_time': config.cycle_time,
                        'scenario': config.scenario
                    }
                    for config in tls_configs
                ]
                
        except Exception as e:
            print(f"❌ Error getting traffic lights for scenario {scenario}: {e}")
            return []
    
    def get_available_traffic_lights(self) -> List[Dict]:
        """Get all available traffic lights from TLS configuration"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                tls_configs = TrafficLightConfig.query.all()
                return [
                    {
                        'traffic_light_id': config.traffic_light_id,
                        'program_id': config.program_id,
                        'phases': config.phases,
                        'controlled_lanes': config.controlled_lanes,
                        'cycle_time': config.cycle_time,
                        'scenario': config.scenario
                    }
                    for config in tls_configs
                ]
                
        except Exception as e:
            print(f"❌ Error getting available traffic lights: {e}")
            return []
    
    def get_traffic_light_details(self, tl_id: str) -> Optional[Dict]:
        """Get detailed information about a specific traffic light"""
        if not self.app:
            return None
            
        try:
            with self.app.app_context():
                config = TrafficLightConfig.query.filter_by(traffic_light_id=tl_id).first()
                if config:
                    return {
                        'traffic_light_id': config.traffic_light_id,
                        'program_id': config.program_id,
                        'phases': config.phases,
                        'current_phase_index': config.current_phase_index,
                        'cycle_time': config.cycle_time,
                        'controlled_lanes': config.controlled_lanes,
                        'is_adaptive': config.is_adaptive,
                        'config_type': config.config_type,
                        'scenario': config.scenario
                    }
                return None
                
        except Exception as e:
            print(f"❌ Error getting traffic light details: {e}")
            return None
    
    def get_active_emergencies(self) -> List[Dict]:
        """Get all active emergency schedules"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                emergencies = EmergencySchedule.query.filter(
                    EmergencySchedule.status.in_(['SCHEDULED', 'ACTIVE'])
                ).all()
                return [emergency.to_dict() for emergency in emergencies]
                
        except Exception as e:
            print(f"❌ Error getting active emergencies: {e}")
            return []
    
    def get_active_green_waves(self) -> List[Dict]:
        """Get all active green wave schedules"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                green_waves = GreenWaveSchedule.query.filter(
                    GreenWaveSchedule.status.in_(['SCHEDULED', 'ACTIVE'])
                ).all()
                return [wave.to_dict() for wave in green_waves]
                
        except Exception as e:
            print(f"❌ Error getting active green waves: {e}")
            return []
    
    def cancel_emergency(self, emergency_id: str) -> Dict[str, Any]:
        """Cancel a scheduled emergency"""
        if not self.app:
            return {"success": False, "error": "No app context"}
            
        try:
            with self.app.app_context():
                emergency = EmergencySchedule.query.get(emergency_id)
                if emergency:
                    emergency.status = 'CANCELLED'
                    emergency.updated_at = datetime.utcnow()
                    
                    # Also cancel green waves
                    GreenWaveSchedule.query.filter_by(emergency_id=emergency_id).update(
                        {'status': 'CANCELLED'}
                    )
                    
                    db.session.commit()
                    
                    # Remove from active tracking
                    self.active_emergencies.pop(emergency_id, None)
                    
                    return {"success": True, "message": "Emergency cancelled"}
                else:
                    return {"success": False, "error": "Emergency not found"}
                    
        except Exception as e:
            print(f"❌ Error cancelling emergency: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}
    
    def cancel_green_wave(self, green_wave_id: str) -> Dict[str, Any]:
        """Cancel a scheduled green wave"""
        if not self.app:
            return {"success": False, "error": "No app context"}
            
        try:
            with self.app.app_context():
                green_wave = GreenWaveSchedule.query.get(green_wave_id)
                if green_wave:
                    green_wave.status = 'CANCELLED'
                    db.session.commit()
                    return {"success": True, "message": "Green wave cancelled"}
                else:
                    return {"success": False, "error": "Green wave not found"}
                    
        except Exception as e:
            print(f"❌ Error cancelling green wave: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}
    
    def get_pending_green_waves(self, current_time: float) -> List[Dict]:
        """Get green waves that should be activated now"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                pending_waves = GreenWaveSchedule.query.filter(
                    GreenWaveSchedule.status == 'SCHEDULED',
                    GreenWaveSchedule.scheduled_start <= current_time + 5.0,  # 5 second buffer
                    GreenWaveSchedule.scheduled_start >= current_time - 10.0  # Allow some past
                ).all()
                
                return [wave.to_dict() for wave in pending_waves]
                
        except Exception as e:
            print(f"❌ Error getting pending green waves: {e}")
            return []
    def get_network_topology(self) -> Dict[str, Any]:
        """Get complete network topology from TLS configurations"""
        if not self.app:
            return {}

        try:
            with self.app.app_context():
                tls_configs = TrafficLightConfig.query.all()
                topology = {
                    'edges': set(),
                    'edge_to_tls': {},
                    'tls_to_edges': {}
                }

                for config in tls_configs:
                    tl_id = config.traffic_light_id
                    topology['tls_to_edges'][tl_id] = set()

                    if config.controlled_lanes:
                        for lane in config.controlled_lanes:
                            edge = lane.split('_')[0]  # Extract edge from lane ID
                            topology['edges'].add(edge)

                            if edge not in topology['edge_to_tls']:
                                topology['edge_to_tls'][edge] = set()
                            topology['edge_to_tls'][edge].add(tl_id)
                            topology['tls_to_edges'][tl_id].add(edge)

                # Convert sets to lists for JSON serialization
                topology['edges'] = list(topology['edges'])
                for key in ['edge_to_tls', 'tls_to_edges']:
                    topology[key] = {k: list(v) for k, v in topology[key].items()}

                return topology

        except Exception as e:
            print(f"❌ Error getting network topology: {e}")
            return {}
        
# Global instance
emergency_scheduler = EmergencySchedulerService()