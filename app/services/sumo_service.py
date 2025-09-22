# app/services/sumo_service.py
import traci
import sumolib
import threading
import time
import json
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SUMOService:
    """Service class to handle SUMO simulation integration"""
    
    def __init__(self):
        self.sumo_running = False
        self.sumo_thread = None
        self.simulation_data = {
            'vehicles': {},
            'traffic_lights': {},
            'detectors': {},
            'current_time': 0,
            'total_vehicles': 0,
            'average_speed': 0
        }
        self._lock = threading.Lock()
        self.listeners = []  # For real-time updates
        
    def add_listener(self, callback):
        """Add a callback function to receive simulation updates"""
        self.listeners.append(callback)
        
    def remove_listener(self, callback):
        """Remove a callback function"""
        if callback in self.listeners:
            self.listeners.remove(callback)
    
    def _notify_listeners(self, data):
        """Notify all registered listeners of simulation updates"""
        for callback in self.listeners:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")
    
    def start_simulation(self, config_file: str = "complex.sumocfg", gui: bool = False) -> bool:
        """Start SUMO simulation"""
        try:
            if self.sumo_running:
                logger.warning("SUMO simulation already running")
                return True
                
            # Determine SUMO binary
            if gui:
                sumo_binary = sumolib.checkBinary('sumo-gui')
            else:
                sumo_binary = sumolib.checkBinary('sumo')
            
            # Full path to config file
            config_path = f"sumo_configs/{config_file}"
            
            # Start SUMO with TraCI
            traci.start([sumo_binary, "-c", config_path, "--start", "--quit-on-end"])
            
            with self._lock:
                self.sumo_running = True
                
            logger.info(f"SUMO simulation started with config: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting SUMO: {e}")
            return False
    
    def stop_simulation(self):
        """Stop SUMO simulation"""
        try:
            if self.sumo_running:
                traci.close()
                with self._lock:
                    self.sumo_running = False
                    self.simulation_data = {
                        'vehicles': {},
                        'traffic_lights': {},
                        'detectors': {},
                        'current_time': 0,
                        'total_vehicles': 0,
                        'average_speed': 0
                    }
                logger.info("SUMO simulation stopped")
        except Exception as e:
            logger.error(f"Error stopping SUMO: {e}")
    
    def step_simulation(self) -> bool:
        """Advance simulation by one step and update data"""
        if not self.sumo_running:
            return False
            
        try:
            traci.simulationStep()
            self._update_simulation_data()
            return True
        except Exception as e:
            logger.error(f"Error stepping simulation: {e}")
            with self._lock:
                self.sumo_running = False
            return False
    
    def _update_simulation_data(self):
        """Update internal simulation data"""
        try:
            current_time = traci.simulation.getTime()
            
            # Get vehicle information
            vehicles = {}
            vehicle_ids = traci.vehicle.getIDList()
            speeds = []
            
            for veh_id in vehicle_ids:
                try:
                    position = traci.vehicle.getPosition(veh_id)
                    speed = traci.vehicle.getSpeed(veh_id)
                    road_id = traci.vehicle.getRoadID(veh_id)
                    
                    vehicles[veh_id] = {
                        'id': veh_id,
                        'position': position,
                        'speed': speed,
                        'road_id': road_id,
                        'lane_id': traci.vehicle.getLaneID(veh_id),
                        'waiting_time': traci.vehicle.getWaitingTime(veh_id)
                    }
                    speeds.append(speed)
                except Exception as e:
                    logger.warning(f"Error getting data for vehicle {veh_id}: {e}")
            
            # Get traffic light information
            traffic_lights = {}
            for tl_id in traci.trafficlight.getIDList():
                try:
                    traffic_lights[tl_id] = {
                        'id': tl_id,
                        'state': traci.trafficlight.getRedYellowGreenState(tl_id),
                        'phase': traci.trafficlight.getPhase(tl_id),
                        'next_switch': traci.trafficlight.getNextSwitch(tl_id)
                    }
                except Exception as e:
                    logger.warning(f"Error getting data for traffic light {tl_id}: {e}")
            
            # Calculate statistics
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            
            with self._lock:
                self.simulation_data = {
                    'vehicles': vehicles,
                    'traffic_lights': traffic_lights,
                    'detectors': {},  # Can be extended for induction loops
                    'current_time': current_time,
                    'total_vehicles': len(vehicles),
                    'average_speed': avg_speed,
                    'simulation_ended': traci.simulation.getMinExpectedNumber() == 0
                }
            
            # Notify listeners
            self._notify_listeners(self.simulation_data.copy())
            
        except Exception as e:
            logger.error(f"Error updating simulation data: {e}")
    
    def get_simulation_data(self) -> Dict:
        """Get current simulation data"""
        with self._lock:
            return self.simulation_data.copy()
    
    def is_running(self) -> bool:
        """Check if simulation is running"""
        return self.sumo_running
    
    def get_vehicle_info(self, vehicle_id: str) -> Optional[Dict]:
        """Get information for a specific vehicle"""
        with self._lock:
            return self.simulation_data['vehicles'].get(vehicle_id)
    
    def get_traffic_light_info(self, tl_id: str) -> Optional[Dict]:
        """Get information for a specific traffic light"""
        with self._lock:
            return self.simulation_data['traffic_lights'].get(tl_id)
    
    def set_traffic_light_phase(self, tl_id: str, phase: int) -> bool:
        """Set traffic light phase"""
        if not self.sumo_running:
            return False
        
        try:
            traci.trafficlight.setPhase(tl_id, phase)
            return True
        except Exception as e:
            logger.error(f"Error setting traffic light phase: {e}")
            return False
    
    def add_vehicle(self, route_id: str, vehicle_id: str = None, depart_time: int = None) -> bool:
        """Add a vehicle to the simulation"""
        if not self.sumo_running:
            return False
        
        try:
            if vehicle_id is None:
                vehicle_id = f"vehicle_{int(time.time())}"
            
            if depart_time is None:
                depart_time = int(traci.simulation.getTime())
            
            traci.vehicle.add(vehicle_id, route_id, departTime=depart_time)
            return True
        except Exception as e:
            logger.error(f"Error adding vehicle: {e}")
            return False
    
    def run_continuous_simulation(self, max_steps: int = 3600):
        """Run simulation continuously in a separate thread"""
        def simulation_loop():
            step_count = 0
            while self.sumo_running and step_count < max_steps:
                if not self.step_simulation():
                    break
                    
                # Check if simulation has ended
                with self._lock:
                    if self.simulation_data.get('simulation_ended', False):
                        break
                
                step_count += 1
                time.sleep(0.1)  # Control simulation speed
            
            # Clean up
            self.stop_simulation()
        
        if not self.sumo_running:
            return False
        
        self.sumo_thread = threading.Thread(target=simulation_loop)
        self.sumo_thread.daemon = True
        self.sumo_thread.start()
        return True
    
    def get_network_info(self) -> Dict:
        """Get network information"""
        if not self.sumo_running:
            return {}
        
        try:
            return {
                'edges': list(traci.edge.getIDList()),
                'junctions': list(traci.junction.getIDList()),
                'routes': list(traci.route.getIDList()),
                'vehicle_types': list(traci.vehicletype.getIDList())
            }
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return {}

# Global SUMO service instance
sumo_service = SUMOService()