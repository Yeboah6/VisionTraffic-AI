import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

from app.extensions import db
from app.models.traffic_light import TrafficLightConfig

class TLSConfigService:
    """
    Service to manage Traffic Light System configurations
    Handles storage and retrieval of TLS static configurations
    """
    
    def __init__(self, app=None):
        self.app = app
        self.config_cache = {}  # Cache for frequently accessed configs
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def store_tls_configuration(self, traci, tl_id: str, scenario: str) -> Dict[str, Any]:
        """
        Store comprehensive TLS configuration from SUMO simulation
        """
        if not traci:
            return {"success": False, "error": "No TraCI connection"}
        
        try:
            print(f"🔄 Storing TLS configuration for {tl_id} in scenario {scenario}")
            
            # Get basic TLS information
            program_id = traci.trafficlight.getProgram(tl_id)
            current_phase = traci.trafficlight.getPhase(tl_id)
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            
            # Get complete phase information
            phases = self._get_complete_phase_info(traci, tl_id, program_id)
            
            # Calculate cycle time
            cycle_time = sum(phase.get('duration', 0) for phase in phases)
            
            # Create or update configuration
            config_data = {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'program_id': program_id,
                'phases': phases,
                'current_phase_index': current_phase,
                'cycle_time': cycle_time,
                'controlled_lanes': controlled_lanes,
                'is_adaptive': False,  # Default to static
                'config_type': 'STATIC'
            }
            
            # Store in database
            success = self._save_config_to_db(config_data)
            
            if success:
                print(f"✅ TLS configuration stored for {tl_id}")
                return {
                    "success": True,
                    "message": f"TLS configuration stored for {tl_id}",
                    "config": config_data
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to save TLS configuration for {tl_id}"
                }
                
        except Exception as e:
            print(f"❌ Error storing TLS configuration for {tl_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to store TLS configuration: {str(e)}"
            }
    
    def _get_complete_phase_info(self, traci, tl_id: str, program_id: str) -> List[Dict[str, Any]]:
        """
        Get complete phase information for a traffic light
        Uses safe methods to avoid TraCI method issues
        """
        phases = []
        
        try:
            # Try to get phase count - this might fail in some SUMO versions
            try:
                phase_count = traci.trafficlight.getPhaseNumber(tl_id)
            except Exception:
                # Fallback: use current phase and common patterns
                phase_count = 4  # Default assumption
            
            current_phase = traci.trafficlight.getPhase(tl_id)
            current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
            
            # Get complete logic information if available
            try:
                logic = traci.trafficlight.getCompleteRedYellowGreenDefinition(tl_id)
                if logic:
                    return self._parse_tls_logic(logic)
            except Exception:
                # Fall back to phase-by-phase collection
                pass
            
            # Collect phase information
            for phase_index in range(phase_count):
                phase_info = self._get_phase_info_safe(traci, tl_id, phase_index, current_phase, current_state)
                if phase_info:
                    phases.append(phase_info)
            
            # If we couldn't collect real phases, create synthetic ones
            if not phases:
                phases = self._create_synthetic_phases(current_state, phase_count)
            
            return phases
            
        except Exception as e:
            print(f"⚠️ Error getting phase info for {tl_id}: {e}")
            return self._create_synthetic_phases(current_state, 4)  # Fallback
    
    def _get_phase_info_safe(self, traci, tl_id: str, phase_index: int, 
                           current_phase: int, current_state: str) -> Optional[Dict[str, Any]]:
        """
        Safely get information for a specific phase
        """
        try:
            # For current phase, we can get real data
            if phase_index == current_phase:
                duration = traci.trafficlight.getPhaseDuration(tl_id)
                state = current_state
            else:
                # For other phases, use estimates
                duration = self._estimate_phase_duration(phase_index, current_phase)
                state = self._estimate_phase_state(phase_index, current_state)
            
            phase_info = {
                'index': phase_index,
                'duration': duration,
                'state': state,
                'name': self._get_phase_name(state),
                'min_duration': max(5.0, duration * 0.5),  # Conservative estimates
                'max_duration': min(120.0, duration * 2.0),
                'type': self._get_phase_type(state)
            }
            
            return phase_info
            
        except Exception as e:
            print(f"⚠️ Error getting phase {phase_index} for {tl_id}: {e}")
            return None
    
    # WORK HERE
    
    def _parse_tls_logic(self, logic) -> List[Dict[str, Any]]:
        """Parse TLS logic definition into phase information"""
        phases = []
        
        try:
            # This is a simplified parser - real implementation would depend on SUMO version
            for i, phase in enumerate(logic):
                phase_info = {
                    'index': i,
                    'duration': getattr(phase, 'duration', 30.0),
                    'state': getattr(phase, 'state', ''),
                    'name': self._get_phase_name(getattr(phase, 'state', '')),
                    'min_duration': getattr(phase, 'minDur', 5.0),
                    'max_duration': getattr(phase, 'maxDur', 60.0),
                    'type': 'DEFINED'
                }
                phases.append(phase_info)
            
            return phases
            
        except Exception as e:
            print(f"⚠️ Error parsing TLS logic: {e}")
            return []
    
    def _estimate_phase_duration(self, phase_index: int, current_phase: int) -> float:
        """Estimate phase duration based on common patterns"""
        # Common phase durations in seconds
        base_durations = {
            0: 30.0,  # Main green
            1: 5.0,   # Yellow
            2: 30.0,  # Side green  
            3: 5.0,   # Side yellow
        }
        return base_durations.get(phase_index % 4, 30.0)
    
    def _estimate_phase_state(self, phase_index: int, current_state: str) -> str:
        """Estimate phase state based on common patterns"""
        if not current_state:
            return 'r' * 6  # Default to all red
        
        # Simple state rotation pattern
        if phase_index % 4 == 0:
            return 'G' * 3 + 'r' * 3  # Main green
        elif phase_index % 4 == 1:
            return 'y' * 3 + 'r' * 3  # Yellow
        elif phase_index % 4 == 2:
            return 'r' * 3 + 'G' * 3  # Side green
        else:
            return 'r' * 3 + 'y' * 3  # Side yellow
    
    def _create_synthetic_phases(self, current_state: str, phase_count: int) -> List[Dict[str, Any]]:
        """Create synthetic phase data when real data isn't available"""
        phases = []
        
        for i in range(phase_count):
            if i % 4 == 0:
                state = 'GGGrrr'
                name = 'MAIN_GREEN'
                duration = 30.0
            elif i % 4 == 1:
                state = 'yyyrrr' 
                name = 'YELLOW'
                duration = 5.0
            elif i % 4 == 2:
                state = 'rrrGGG'
                name = 'SIDE_GREEN'
                duration = 30.0
            else:
                state = 'rrryyy'
                name = 'SIDE_YELLOW'
                duration = 5.0
            
            phases.append({
                'index': i,
                'duration': duration,
                'state': state,
                'name': name,
                'min_duration': 5.0,
                'max_duration': 60.0,
                'type': 'SYNTHETIC'
            })
        
        return phases
    
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
    
    def _get_phase_type(self, state: str) -> str:
        """Get phase type from state"""
        if 'G' in state:
            return 'GREEN'
        elif 'y' in state:
            return 'YELLOW'
        elif 'r' in state:
            return 'RED'
        else:
            return 'UNKNOWN'
    
    def _save_config_to_db(self, config_data: Dict) -> bool:
        """Save TLS configuration to database"""
        if not self.app:
            print("⚠️ No app context for database operations")
            return False
            
        try:
            with self.app.app_context():
                # Check if config already exists
                existing_config = TrafficLightConfig.query.filter_by(
                    traffic_light_id=config_data['traffic_light_id'],
                    scenario=config_data['scenario']
                ).first()
                
                if existing_config:
                    # Update existing config
                    existing_config.program_id = config_data['program_id']
                    existing_config.phases = config_data['phases']
                    existing_config.current_phase_index = config_data['current_phase_index']
                    existing_config.cycle_time = config_data['cycle_time']
                    existing_config.controlled_lanes = config_data['controlled_lanes']
                    existing_config.is_adaptive = config_data['is_adaptive']
                    existing_config.config_type = config_data['config_type']
                    existing_config.updated_at = datetime.utcnow()
                    action = "updated"
                else:
                    # Create new config
                    new_config = TrafficLightConfig(
                        traffic_light_id=config_data['traffic_light_id'],
                        scenario=config_data['scenario'],
                        program_id=config_data['program_id'],
                        phases=config_data['phases'],
                        current_phase_index=config_data['current_phase_index'],
                        cycle_time=config_data['cycle_time'],
                        controlled_lanes=config_data['controlled_lanes'],
                        is_adaptive=config_data['is_adaptive'],
                        config_type=config_data['config_type']
                    )
                    db.session.add(new_config)
                    action = "created"
                
                db.session.commit()
                print(f"✅ TLS config {action} for {config_data['traffic_light_id']}")
                return True
                
        except Exception as e:
            print(f"❌ Error saving TLS config to database: {e}")
            db.session.rollback()
            return False
    
    # Configuration Retrieval Methods
    def get_tls_config(self, tl_id: str, scenario: str) -> Optional[Dict[str, Any]]:
        """Get TLS configuration from database"""
        if not self.app:
            return None
            
        try:
            with self.app.app_context():
                config = TrafficLightConfig.query.filter_by(
                    traffic_light_id=tl_id,
                    scenario=scenario
                ).first()
                
                return config.to_dict() if config else None
                
        except Exception as e:
            print(f"❌ Error retrieving TLS config: {e}")
            return None
    
    def get_all_configs_for_scenario(self, scenario: str) -> List[Dict[str, Any]]:
        """Get all TLS configurations for a scenario"""
        if not self.app:
            return []
            
        try:
            with self.app.app_context():
                configs = TrafficLightConfig.query.filter_by(scenario=scenario).all()
                return [config.to_dict() for config in configs]
                
        except Exception as e:
            print(f"❌ Error retrieving TLS configs for scenario: {e}")
            return []
    
    def update_tls_phase(self, tl_id: str, scenario: str, phase_index: int) -> bool:
        """Update current phase index for TLS"""
        if not self.app:
            return False
            
        try:
            with self.app.app_context():
                config = TrafficLightConfig.query.filter_by(
                    traffic_light_id=tl_id,
                    scenario=scenario
                ).first()
                
                if config:
                    config.current_phase_index = phase_index
                    config.updated_at = datetime.utcnow()
                    db.session.commit()
                    return True
                return False
                
        except Exception as e:
            print(f"❌ Error updating TLS phase: {e}")
            db.session.rollback()
            return False
    
    def store_bulk_tls_configs(self, traci, scenario: str) -> Dict[str, Any]:
        """
        Store configurations for all TLS in current simulation
        """
        if not traci:
            return {"success": False, "error": "No TraCI connection"}
        
        try:
            tl_ids = traci.trafficlight.getIDList()
            results = {
                "success_count": 0,
                "error_count": 0,
                "details": []
            }
            
            for tl_id in tl_ids:
                result = self.store_tls_configuration(traci, tl_id, scenario)
                if result["success"]:
                    results["success_count"] += 1
                else:
                    results["error_count"] += 1
                
                results["details"].append({
                    "traffic_light_id": tl_id,
                    "success": result["success"],
                    "message": result.get("message", result.get("error", "Unknown error"))
                })
            
            print(f"📊 Bulk TLS config storage: {results['success_count']} successful, {results['error_count']} failed")
            return results
            
        except Exception as e:
            print(f"❌ Error in bulk TLS config storage: {e}")
            return {"success": False, "error": str(e)}

# Global instance
tls_config_service = TLSConfigService()

def init_tls_config_service(app):
    """Initialize TLS config service"""
    tls_config_service.init_app(app)