# # app/services/sumo_service.py
# import traci
# import sumolib
# import threading
# import time
# import json
# import os
# from typing import Dict, List, Optional, Tuple
# import logging

# logger = logging.getLogger(__name__)

# class SUMOService:
#     """Service class to handle SUMO simulation integration"""
    
#     def __init__(self):
#         self.sumo_running = False
#         self.sumo_thread = None
#         self.simulation_data = {
#             'vehicles': {},
#             'traffic_lights': {},
#             'detectors': {},
#             'current_time': 0,
#             'total_vehicles': 0,
#             'average_speed': 0
#         }
#         self._lock = threading.Lock()
#         self.listeners = []  # For real-time updates
        
#     def add_listener(self, callback):
#         """Add a callback function to receive simulation updates"""
#         self.listeners.append(callback)
        
#     def remove_listener(self, callback):
#         """Remove a callback function"""
#         if callback in self.listeners:
#             self.listeners.remove(callback)
    
#     def _notify_listeners(self, data):
#         """Notify all registered listeners of simulation updates"""
#         for callback in self.listeners:
#             try:
#                 callback(data)
#             except Exception as e:
#                 logger.error(f"Error notifying listener: {e}")
    
#     def start_simulation(self, config_file: str = "Traci.sumocfg", gui: bool = True) -> bool:
#         """Start SUMO simulation using routing link approach"""
#         try:
#             if self.sumo_running:
#                 logger.warning("SUMO simulation already running")
#                 return True

#             # Check if SUMO_HOME is set
#             if 'SUMO_HOME' not in os.environ:
#                 logger.error("SUMO_HOME environment variable not set")
#                 return False

#             # Define SUMO configuration similar to the first approach
#             if gui:
#                 # Use full path to sumo-gui executable
#                 sumo_binary = os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo-gui')
#                 # Check if executable exists
#                 if not os.path.exists(sumo_binary):
#                     logger.error(f"SUMO-GUI executable not found: {sumo_binary}")
#                     # Try alternative path (Linux/Mac)
#                     sumo_binary = os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo-gui.exe')
#                     if not os.path.exists(sumo_binary):
#                         logger.error("SUMO-GUI executable not found in SUMO_HOME/bin")
#                         return False
#             else:
#                 sumo_binary = os.path.join(os.environ['SUMO_HOME'], 'bin', 'sumo')

#             # Build SUMO command configuration list
#             sumo_config = [
#                 sumo_binary,
#                 '-c', "sumo_configs/Traci.sumocfg",
#                 '--step-length', '0.05',
#                 '--delay', '1000',
#                 '--lateral-resolution', '0.1'
#                 '-start'
#             ]

#             # Add GUI-specific options if needed
#             if gui:
#                 # Remove --start for GUI to allow manual control
#                 # sumo_config.extend(['--start'])  # Start simulation immediately in GUI
#                 pass
#             else:
#                 sumo_config.extend(['--start', '--quit-on-end'])

#             logger.info(f"Starting SUMO with config: {' '.join(sumo_config)}")

#             # Start SUMO with TraCI using the configuration list
#             traci.start(sumo_config)

#             with self._lock:
#                 self.sumo_running = True

#             logger.info(f"SUMO simulation started successfully - Config: {config_file}, GUI: {gui}")
#             return True

#         except Exception as e:
#             logger.error(f"Error starting SUMO: {e}")
#             logger.exception("Full traceback:")
#             return False
    
#     def stop_simulation(self):
#         """Stop SUMO simulation"""
#         try:
#             if self.sumo_running:
#                 traci.close()
#                 with self._lock:
#                     self.sumo_running = False
#                     self.simulation_data = {
#                         'vehicles': {},
#                         'traffic_lights': {},
#                         'detectors': {},
#                         'current_time': 0,
#                         'total_vehicles': 0,
#                         'average_speed': 0
#                     }
#                 logger.info("SUMO simulation stopped")
#         except Exception as e:
#             logger.error(f"Error stopping SUMO: {e}")
    
#     def step_simulation(self) -> bool:
#         """Advance simulation by one step and update data"""
#         if not self.sumo_running:
#             return False
            
#         try:
#             traci.simulationStep()
#             self._update_simulation_data()
#             return True
#         except Exception as e:
#             logger.error(f"Error stepping simulation: {e}")
#             with self._lock:
#                 self.sumo_running = False
#             return False
    
#     def _update_simulation_data(self):
#         """Update internal simulation data"""
#         try:
#             current_time = traci.simulation.getTime()
            
#             # Get vehicle information
#             vehicles = {}
#             vehicle_ids = traci.vehicle.getIDList()
#             speeds = []
            
#             for veh_id in vehicle_ids:
#                 try:
#                     position = traci.vehicle.getPosition(veh_id)
#                     speed = traci.vehicle.getSpeed(veh_id)
#                     road_id = traci.vehicle.getRoadID(veh_id)
                    
#                     vehicles[veh_id] = {
#                         'id': veh_id,
#                         'position': position,
#                         'speed': speed,
#                         'road_id': road_id,
#                         'lane_id': traci.vehicle.getLaneID(veh_id),
#                         'waiting_time': traci.vehicle.getWaitingTime(veh_id)
#                     }
#                     speeds.append(speed)
#                 except Exception as e:
#                     logger.warning(f"Error getting data for vehicle {veh_id}: {e}")
            
#             # Get traffic light information
#             traffic_lights = {}
#             for tl_id in traci.trafficlight.getIDList():
#                 try:
#                     traffic_lights[tl_id] = {
#                         'id': tl_id,
#                         'state': traci.trafficlight.getRedYellowGreenState(tl_id),
#                         'phase': traci.trafficlight.getPhase(tl_id),
#                         'next_switch': traci.trafficlight.getNextSwitch(tl_id)
#                     }
#                 except Exception as e:
#                     logger.warning(f"Error getting data for traffic light {tl_id}: {e}")
            
#             # Calculate statistics
#             avg_speed = sum(speeds) / len(speeds) if speeds else 0
            
#             with self._lock:
#                 self.simulation_data = {
#                     'vehicles': vehicles,
#                     'traffic_lights': traffic_lights,
#                     'detectors': {},  # Can be extended for induction loops
#                     'current_time': current_time,
#                     'total_vehicles': len(vehicles),
#                     'average_speed': avg_speed,
#                     'simulation_ended': traci.simulation.getMinExpectedNumber() == 0
#                 }
            
#             # Notify listeners
#             self._notify_listeners(self.simulation_data.copy())
            
#         except Exception as e:
#             logger.error(f"Error updating simulation data: {e}")
    
#     def get_simulation_data(self) -> Dict:
#         """Get current simulation data"""
#         with self._lock:
#             return self.simulation_data.copy()
    
#     def is_running(self) -> bool:
#         """Check if simulation is running"""
#         return self.sumo_running
    
#     def get_vehicle_info(self, vehicle_id: str) -> Optional[Dict]:
#         """Get information for a specific vehicle"""
#         with self._lock:
#             return self.simulation_data['vehicles'].get(vehicle_id)
    
#     def get_traffic_light_info(self, tl_id: str) -> Optional[Dict]:
#         """Get information for a specific traffic light"""
#         with self._lock:
#             return self.simulation_data['traffic_lights'].get(tl_id)
    
#     def set_traffic_light_phase(self, tl_id: str, phase: int) -> bool:
#         """Set traffic light phase"""
#         if not self.sumo_running:
#             return False
        
#         try:
#             traci.trafficlight.setPhase(tl_id, phase)
#             return True
#         except Exception as e:
#             logger.error(f"Error setting traffic light phase: {e}")
#             return False
    
#     def add_vehicle(self, route_id: str, vehicle_id: str = None, depart_time: int = None) -> bool:
#         """Add a vehicle to the simulation"""
#         if not self.sumo_running:
#             return False
        
#         try:
#             if vehicle_id is None:
#                 vehicle_id = f"vehicle_{int(time.time())}"
            
#             if depart_time is None:
#                 depart_time = int(traci.simulation.getTime())
            
#             traci.vehicle.add(vehicle_id, route_id, departTime=depart_time)
#             return True
#         except Exception as e:
#             logger.error(f"Error adding vehicle: {e}")
#             return False
    
#     def run_continuous_simulation(self, max_steps: int = 3600):
#         """Run simulation continuously in a separate thread"""
#         def simulation_loop():
#             step_count = 0
#             while self.sumo_running and step_count < max_steps:
#                 if not self.step_simulation():
#                     break
                    
#                 # Check if simulation has ended
#                 with self._lock:
#                     if self.simulation_data.get('simulation_ended', False):
#                         break
                
#                 step_count += 1
#                 time.sleep(0.1)  # Control simulation speed
            
#             # Clean up
#             self.stop_simulation()
        
#         if not self.sumo_running:
#             return False
        
#         self.sumo_thread = threading.Thread(target=simulation_loop)
#         self.sumo_thread.daemon = True
#         self.sumo_thread.start()
#         return True
    
#     def get_network_info(self) -> Dict:
#         """Get network information"""
#         if not self.sumo_running:
#             return {}
        
#         try:
#             return {
#                 'edges': list(traci.edge.getIDList()),
#                 'junctions': list(traci.junction.getIDList()),
#                 'routes': list(traci.route.getIDList()),
#                 'vehicle_types': list(traci.vehicletype.getIDList())
#             }
#         except Exception as e:
#             logger.error(f"Error getting network info: {e}")
#             return {}

# # Global SUMO service instance
# sumo_service = SUMOService()

import subprocess
import os
import signal
import threading
import time
from typing import Optional, Dict, Any

class SumoService:
    def __init__(self):
        self.simulation_process: Optional[subprocess.Popen] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.current_config = None
        
        # SUMO configurations directory
        self.sumo_configs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'sumo_configs'
        )
        
        # Available scenarios
        self.available_scenarios = {
            'simple': {
                'config': 'complex.sumocfg',
                'name': 'Simple Intersection',
                'description': 'A basic 4-way intersection scenario'
            },
            # Add more scenarios as needed
        }
    
    def get_available_scenarios(self) -> Dict[str, Any]:
        """Return available SUMO scenarios"""
        return self.available_scenarios
    
    def start_simulation(self, scenario: str = 'simple', gui: bool = True) -> Dict[str, Any]:
        """Start SUMO simulation with the specified scenario"""
        if self.is_running:
            return {"success": False, "error": "Simulation is already running"}
        
        if scenario not in self.available_scenarios:
            return {"success": False, "error": f"Scenario '{scenario}' not found"}
        
        try:
            config_file = self.available_scenarios[scenario]['config']
            config_path = os.path.join(self.sumo_configs_dir, config_file)
            
            if not os.path.exists(config_path):
                return {"success": False, "error": f"Config file not found: {config_path}"}
            
            # Build SUMO command
            sumo_binary = 'sumo-gui' if gui else 'sumo'
            sumo_cmd = [
                sumo_binary,
                '-c', config_path,
                '--step-length', '0.1',
                '--delay', '100'
            ]
            
            # Start simulation in a separate thread to avoid blocking
            self.simulation_thread = threading.Thread(
                target=self._run_simulation,
                args=(sumo_cmd, scenario)
            )
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
            
            # Wait a moment for the process to start
            time.sleep(2)
            
            if self.is_running:
                self.current_config = scenario
                return {
                    "success": True,
                    "message": f"SUMO simulation started successfully with {scenario} scenario",
                    "scenario": scenario,
                    "pid": self.simulation_process.pid if self.simulation_process else None
                }
            else:
                return {"success": False, "error": "Failed to start simulation"}
                
        except Exception as e:
            return {"success": False, "error": f"Failed to start simulation: {str(e)}"}
    
    def _run_simulation(self, sumo_cmd: list, scenario: str):
        """Run SUMO simulation in a separate thread"""
        try:
            self.is_running = True
            self.simulation_process = subprocess.Popen(
                sumo_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.simulation_process.wait()
        except Exception as e:
            print(f"Simulation error: {e}")
        finally:
            self.is_running = False
            self.simulation_process = None
            self.current_config = None
    
    def stop_simulation(self) -> Dict[str, Any]:
        """Stop the running SUMO simulation"""
        if not self.is_running or not self.simulation_process:
            return {"success": False, "error": "No simulation is currently running"}
        
        try:
            # Terminate the process
            self.simulation_process.terminate()
            
            # Wait for process to terminate
            try:
                self.simulation_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.simulation_process.kill()
                self.simulation_process.wait()
            
            self.is_running = False
            self.simulation_process = None
            self.current_config = None
            
            return {"success": True, "message": "SUMO simulation stopped successfully"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to stop simulation: {str(e)}"}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status"""
        return {
            "is_running": self.is_running,
            "current_scenario": self.current_config,
            "available_scenarios": list(self.available_scenarios.keys())
        }
    
    def check_sumo_availability(self) -> Dict[str, Any]:
        """Check if SUMO is properly installed and available"""
        try:
            result = subprocess.run(['sumo', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return {"available": True, "version": result.stdout.strip()}
            else:
                return {"available": False, "error": result.stderr}
        except FileNotFoundError:
            return {"available": False, "error": "SUMO not found in PATH"}
        except Exception as e:
            return {"available": False, "error": str(e)}

# Global instance
sumo_service = SumoService()