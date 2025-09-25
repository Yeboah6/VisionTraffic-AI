import subprocess
import os
import sys
import signal
import threading
import json
import time
from typing import Optional, Dict, Any, List

class SumoService:
    def __init__(self):
        self.simulation_process: Optional[subprocess.Popen] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.current_config = None
        self.traci = None
        self.simulation_step = 0
        
        # Initialize monitoring data with default values
        self.monitoring_data = {
            'vehicle_count': 0,
            'average_speed': 0.0,
            'current_time': 0,
            'vehicle_ids': [],
            'traffic_stats': {
                'total_vehicles': 0,
                'avg_speed_kmh': 0.0,
                'simulation_time': 0,
                'throughput': 0,
                'density': 0.0,
                'waiting_vehicles': 0,
                'co2_emission': 0.0,
                'fuel_consumption': 0.0
            },
            'vehicles': [],
            'traffic_lights': [],
            'edges': []
        }
        
        # SUMO configurations directory
        self.sumo_configs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'sumo_configs'
        )
        
        # Set SUMO_HOME path (adjust this to your SUMO installation)
        self.set_sumo_path()
        
        # Available scenarios - EXPANDED LIST
        self.available_scenarios = {
            'complex': {
                'config': 'complex.sumocfg',
                'name': 'Complex Intersection',
                'description': 'A basic 4-way intersection scenario',
                'complexity': 'Beginner'
            },
            'traci': {
                'config': 'Traci.sumocfg',
                'name': 'Complex Intersection',
                'description': 'Multiple lanes with traffic lights',
                'complexity': 'Intermediate'
            },
            'simple': {
                'config': 'simple.sumocfg',
                'name': 'Highway Simulation',
                'description': 'Multi-lane highway with merging',
                'complexity': 'Advanced'
            },
            'please': {
                'config': 'please.sumocfg',
                'name': 'Roundabout',
                'description': 'Single and multi-lane roundabout',
                'complexity': 'Intermediate'
            }
        }
        
        # Set SUMO_HOME path
        self.set_sumo_path()
        
        # Verify scenario files exist
        self._verify_scenario_files()
        
    def _verify_scenario_files(self):
        """Verify that all scenario configuration files exist"""
        missing_files = []
        for scenario_name, scenario_info in self.available_scenarios.items():
            config_file = scenario_info['config']
            config_path = os.path.join(self.sumo_configs_dir, config_file)
            if not os.path.exists(config_path):
                missing_files.append(config_path)
                print(f"Warning: Scenario file not found: {config_path}")
        
        if missing_files:
            print(f"Missing scenario files: {missing_files}")
        
    def set_sumo_path(self):
        """Set up SUMO environment variables"""
        try:
            # Common SUMO installation paths
            possible_paths = [
                os.environ.get('SUMO_HOME', ''),
                'C:/Program Files (x86)/Eclipse/Sumo',
                'C:/Program Files/Eclipse/Sumo',
                '/usr/share/sumo',
                '/opt/sumo'
            ]
            
            for sumo_path in possible_paths:
                if sumo_path and os.path.exists(sumo_path):
                    os.environ['SUMO_HOME'] = sumo_path
                    tools_dir = os.path.join(sumo_path, 'tools')
                    if tools_dir not in sys.path:
                        sys.path.append(tools_dir)
                    print(f"SUMO_HOME set to: {sumo_path}")
                    break
            else:
                print("Warning: SUMO_HOME not found. TraCI functionality will be limited.")
                
        except Exception as e:
            print(f"Error setting SUMO path: {e}")
    
    def get_available_scenarios(self) -> Dict[str, Any]:
        """Return available SUMO scenarios"""
        return self.available_scenarios
    
    def auto_discover_scenarios(self) -> Dict[str, Any]:
        """Auto-discover SUMO config files in the configs directory"""
        discovered = {}
        if os.path.exists(self.sumo_configs_dir):
            for file in os.listdir(self.sumo_configs_dir):
                if file.endswith('.sumocfg'):
                    scenario_name = file.replace('.sumocfg', '')
                    if scenario_name not in self.available_scenarios:
                        discovered[scenario_name] = {
                            'config': file,
                            'name': scenario_name.replace('_', ' ').title(),
                            'description': f'Auto-discovered {scenario_name} scenario',
                            'complexity': 'Unknown'
                        }
        return discovered
    # Start simulation with specified scenario  
    def start_simulation(self, scenario: str, gui: bool = True) -> Dict[str, Any]:
        """Start SUMO simulation with the specified scenario"""
        
        if not scenario:
            return {"success": False, "error": "No scenario provided"}
    
        if self.is_running:
            return {"success": False, "error": "Simulation is already running"}
        
        # Check both predefined and auto-discovered scenarios
        all_scenarios = {**self.available_scenarios, **self.auto_discover_scenarios()}
        
        if scenario not in all_scenarios:
            available = list(all_scenarios.keys())
            return {"success": False, "error": f"Scenario '{scenario}' not found. Available: {available}"}
        
        try:
            config_file = all_scenarios[scenario]['config']
            config_path = os.path.join(self.sumo_configs_dir, config_file)
            
            print(f"Attempting to start scenario: {scenario} with config: {config_path}")
            
            if not os.path.exists(config_path):
                return {"success": False, "error": f"Config file not found: {config_path}"}
            
            # Reset monitoring data when starting new simulation
            self._reset_monitoring_data()
            
            # Start simulation in a separate thread
            self.simulation_thread = threading.Thread(
                target=self._run_simulation_with_traci,
                args=(config_path, scenario, gui)
            )
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
            
            # Wait for simulation to start
            for _ in range(10):  # Wait up to 2 seconds
                if self.is_running:
                    break
                time.sleep(0.2)
            else:
                return {"success": False, "error": "Simulation failed to start within timeout period"}
            
            if self.is_running:
                self.current_config = scenario
                return {
                    "success": True,
                    "message": f"SUMO simulation started successfully with {scenario} scenario",
                    "scenario": scenario,
                    "config_file": config_file,
                    "pid": self.simulation_process.pid if self.simulation_process else None
                }
            else:
                return {"success": False, "error": "Failed to start simulation"}
                
        except Exception as e:
            return {"success": False, "error": f"Failed to start simulation: {str(e)}"}
    
    # Run simulation with TraCI
    def _run_simulation_with_traci(self, config_path: str, scenario: str, gui: bool):
        """Run SUMO simulation with TraCI connection"""
        try:
            # Import TraCI
            try:
                import traci
                self.traci = traci
            except ImportError as e:
                self.is_running = False
                return

            # Build SUMO command with proper GUI handling
            if gui:
                sumo_binary = 'sumo-gui'
                sumo_cmd = [
                    sumo_binary,
                    '-c', config_path,
                    '--step-length', '0.1',
                    '--delay', '100',
                    '--start',
                ]
            else:
                sumo_binary = 'sumo'
                sumo_cmd = [
                    sumo_binary,
                    '-c', config_path,
                    '--step-length', '0.1'
                ]

            print(f"SUMO command: {' '.join(sumo_cmd)}")

            # Start TraCI connection
            print("Starting TraCI connection...")
            try:
                self.traci.start(sumo_cmd)
                self.is_running = True
                self.simulation_step = 0

            except Exception as e:
                self.is_running = False
                return

            print(f"TraCI simulation started for scenario: {scenario}")

            # Main simulation loop
            max_steps = 10000
            while self.is_running and self.simulation_step < max_steps:
                try:
                    # Perform simulation step
                    self.traci.simulationStep()
                    self.simulation_step += 1

                    # Update monitoring data every 10 steps
                    if self.simulation_step % 10 == 0:
                        self._update_simulation_data()

                    # Small delay for GUI responsiveness
                    if gui:
                        time.sleep(0.1)
                    else:
                        time.sleep(0.05)

                except Exception as e:
                    break
                
            print(f"Simulation ended after {self.simulation_step} steps")

        except Exception as e:
            print(f"✗ Simulation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up
            if self.traci and hasattr(self.traci, 'close'):
                try:
                    self.traci.close()
                    print("✓ TraCI connection closed")
                except:
                    print("✗ Error closing TraCI connection")

            self.is_running = False
            self.traci = None
            self.current_config = None
            self.simulation_step = 0
            
    # Update monitoring data using TraCI
    def _update_simulation_data(self):
        """Update monitoring data using TraCI calls"""
        if not self.traci or not self.is_running:
            return
        
        try:
            # Get current simulation time
            current_time = self.traci.simulation.getTime()
            
            # Get vehicle information
            vehicle_ids = self.traci.vehicle.getIDList()
            vehicle_count = len(vehicle_ids)
            
            # Calculate average speed
            speeds = []
            vehicles_data = []
            
            for veh_id in vehicle_ids:
                try:
                    speed = self.traci.vehicle.getSpeed(veh_id)
                    speeds.append(speed)
                    
                    position = self.traci.vehicle.getPosition(veh_id)
                    road_id = self.traci.vehicle.getRoadID(veh_id)
                    lane_id = self.traci.vehicle.getLaneID(veh_id)
                    vehicle_type = self.traci.vehicle.getTypeID(veh_id)
                    
                    vehicles_data.append({
                        'id': veh_id,
                        'speed': speed * 3.6,  # Convert to km/h
                        'position': position,
                        'road_id': road_id,
                        'lane_id': lane_id,
                        'type': vehicle_type,
                        'waiting_time': self.traci.vehicle.getWaitingTime(veh_id)
                    })
                except Exception as e:
                    print(f"Error getting data for vehicle {veh_id}: {e}")
                    continue
            
            avg_speed = sum(speeds) / len(speeds) * 3.6 if speeds else 0  # km/h
            
            # Get traffic light information
            traffic_lights = []
            try:
                tl_ids = self.traci.trafficlight.getIDList()
                for tl_id in tl_ids:
                    try:
                        state = self.traci.trafficlight.getRedYellowGreenState(tl_id)
                        phase = self.traci.trafficlight.getPhase(tl_id)
                        traffic_lights.append({
                            'id': tl_id,
                            'state': state,
                            'phase': phase
                        })
                    except:
                        continue
            except:
                pass  # Traffic lights might not be available
            
            # Get edge/lane information
            edges_data = []
            try:
                lane_ids = self.traci.lane.getIDList()
                edge_stats = {}
                
                for lane_id in lane_ids:
                    try:
                        edge_id = lane_id[:-2]  # Remove lane index
                        if edge_id not in edge_stats:
                            edge_stats[edge_id] = {
                                'vehicle_count': 0,
                                'avg_speed': 0,
                                'lane_count': 0
                            }
                        
                        edge_stats[edge_id]['vehicle_count'] += self.traci.lane.getLastStepVehicleNumber(lane_id)
                        edge_stats[edge_id]['avg_speed'] += self.traci.lane.getLastStepMeanSpeed(lane_id)
                        edge_stats[edge_id]['lane_count'] += 1
                    except:
                        continue
                
                for edge_id, stats in edge_stats.items():
                    if stats['lane_count'] > 0:
                        edges_data.append({
                            'id': edge_id,
                            'vehicle_count': stats['vehicle_count'],
                            'avg_speed': (stats['avg_speed'] / stats['lane_count']) * 3.6,
                            'occupancy': stats['vehicle_count'] / (stats['lane_count'] * 20)  # Rough estimate
                        })
            except:
                pass
            
            # Get simulation-wide statistics
            try:
                co2_emission = self.traci.simulation.getCO2Emission()
                fuel_consumption = self.traci.simulation.getFuelConsumption()
                waiting_time = self.traci.simulation.getWaitingTime()
            except:
                co2_emission = 0
                fuel_consumption = 0
                waiting_time = 0
            
            # Update monitoring data
            self.monitoring_data.update({
                'vehicle_count': vehicle_count,
                'average_speed': avg_speed,
                'current_time': current_time,
                'vehicle_ids': vehicle_ids,
                'vehicles': vehicles_data,
                'traffic_lights': traffic_lights,
                'edges': edges_data,
                'traffic_stats': {
                    'total_vehicles': vehicle_count,
                    'avg_speed_kmh': avg_speed,
                    'simulation_time': current_time,
                    'throughput': vehicle_count * 2,  # Simplified metric
                    'density': vehicle_count / max(len(edges_data), 1),
                    'waiting_vehicles': sum(1 for v in vehicles_data if v['waiting_time'] > 10),
                    'co2_emission': co2_emission,
                    'fuel_consumption': fuel_consumption
                }
            })
            
        except Exception as e:
            print(f"Error updating simulation data: {e}")
            
    def _reset_monitoring_data(self):
        """Reset monitoring data for new simulation"""
        self.monitoring_data = {
            'vehicle_count': 0,
            'average_speed': 0.0,
            'current_time': 0,
            'vehicle_ids': [],
            'traffic_stats': {
                'total_vehicles': 0,
                'avg_speed_kmh': 0.0,
                'simulation_time': 0,
                'throughput': 0,
                'density': 0.0,
                'waiting_vehicles': 0,
                'co2_emission': 0.0,
                'fuel_consumption': 0.0
            },
            'vehicles': [],
            'traffic_lights': [],
            'edges': []
        }
        self.simulation_step = 0

    # Get current simulation status
    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status"""
        return {
            "is_running": self.is_running,
            "current_scenario": self.current_config,
            "simulation_step": self.simulation_step,
            "available_scenarios": list(self.available_scenarios.keys())
        }
        
    # Get current simulation statistics  
    def get_simulation_stats(self) -> Dict[str, Any]:
        """Get current simulation statistics"""
        if not hasattr(self, 'monitoring_data'):
            self._reset_monitoring_data()
            
        return {
            "monitoring": self.monitoring_data,
            "scenario_info": self.available_scenarios.get(self.current_config, {}),
            "simulation_step": self.simulation_step,
            "is_running": self.is_running
        }
        
    def get_vehicle_list(self) -> List[Dict[str, Any]]:
        """Get list of current vehicles in simulation"""
        if not hasattr(self, 'monitoring_data') or not self.monitoring_data['vehicles']:
            return []
        
        return self.monitoring_data['vehicles']
    
    def get_traffic_lights(self) -> List[Dict[str, Any]]:
        """Get current traffic light states"""
        if not hasattr(self, 'monitoring_data'):
            return []
        
        return self.monitoring_data['traffic_lights']
    
    def get_edges(self) -> List[Dict[str, Any]]:
        """Get current edge/lane statistics"""
        if not hasattr(self, 'monitoring_data'):
            return []
        
        return self.monitoring_data['edges']
    
    def stop_simulation(self) -> Dict[str, Any]:
        """Stop the running SUMO simulation"""
        if not self.is_running:
            return {"success": False, "error": "No simulation is currently running"}
        
        try:
            self.is_running = False  # This will break the simulation loop
            
            # Give it a moment to stop gracefully
            time.sleep(1)
            
            # Force close TraCI if still connected
            if self.traci and hasattr(self.traci, 'close'):
                try:
                    self.traci.close()
                except:
                    pass
            
            self.current_config = None
            self.traci = None
            
            return {"success": True, "message": "SUMO simulation stopped successfully"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to stop simulation: {str(e)}"}
        
    def check_sumo_availability(self) -> Dict[str, Any]:
        """Check if SUMO is properly installed and available"""
        try:
            result = subprocess.run(['sumo', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Also check if TraCI can be imported
                try:
                    import traci
                    traci_available = True
                except ImportError:
                    traci_available = False
                
                return {
                    "available": True, 
                    "version": result.stdout.strip(),
                    "traci_available": traci_available
                }
            else:
                return {"available": False, "error": result.stderr}
        except FileNotFoundError:
            return {"available": False, "error": "SUMO not found in PATH"}
        except Exception as e:
            return {"available": False, "error": str(e)}

# Global instance
sumo_service = SumoService()