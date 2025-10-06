from flask import current_app
import subprocess
import os
import sys
import threading
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig
from app.services.camera_service import camera_service
from app.services.ai_traffic_service import ai_traffic_service

class SumoService:
    def __init__(self, app=None):
        self.simulation_process: Optional[subprocess.Popen] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.current_config = None
        self.traci = None
        self.simulation_step = 0
        self.traffic_light_history = {}
        self.last_tl_update = 0
        self.tl_update_interval = 1  # seconds
        self.app = app
        self.camera_data = {}
        self.ai_decisions = []
        
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
            'intersection': {
                'config': 'intersection.sumocfg',
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
        
    def init_app(self, app):
        """Initialize with Flask app instance"""
        self.app = app
        
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
            
            # ✅ FIX: Set current_config BEFORE starting the simulation thread
            self.current_config = scenario
            print(f"✅ Set current_config to: {self.current_config}")
        
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
                    # '--lateral-resolution', '0.1',
                    # '--delay', '500',
                    # '--start',
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
                    # if self.simulation_step % 10 == 0:
                    self._update_simulation_data()

                    # Print progress every 10 steps
                    if self.simulation_step % 10 == 0:
                        vehicle_count = len(self.traci.vehicle.getIDList())
                        print(f"Step {self.simulation_step}: {vehicle_count} vehicles")
                    
                    # Small delay for GUI responsiveness
                    if gui:
                        time.sleep(0.02)
                    else:
                        time.sleep(0.001)

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
            print("✓ Simulation resources cleaned up")
    
    def _update_simulation_data(self):
        """Update monitoring data using TraCI calls"""
        if not self.traci or not self.is_running:
            print("❌ Cannot update data: TraCI not connected or simulation not running")
            return

        try:
            current_time = self.traci.simulation.getTime()
            print(f"🔄 Updating simulation data at time: {current_time}")
            
            # Clear previous data
            self.monitoring_data['traffic_lights'] = []
            self.monitoring_data['vehicles'] = []
            self.monitoring_data['edges'] = []
            
            # Debug: Check if we should update traffic lights
            time_since_last_update = current_time - self.last_tl_update
            print(f"⏰ Time since last TL update: {time_since_last_update}s (interval: {self.tl_update_interval}s)")

             # Update traffic light data periodically
            if time_since_last_update >= self.tl_update_interval:
                print("🚦 Updating traffic light data...")
                self._update_traffic_light_data(current_time)
                self.last_tl_update = current_time
            else:
                print("⏭️ Skipping traffic light update (too soon)")

            # Update traffic light data periodically
            if current_time - self.last_tl_update >= self.tl_update_interval:
                self._update_traffic_light_data(current_time)
                self.last_tl_update = current_time

            # Update vehicle information
            print("🚗 Updating vehicle data...")
            vehicle_ids = self.traci.vehicle.getIDList()
            vehicle_count = len(vehicle_ids)
            speeds = []
            vehicles_data = []
            
            print(f"📊 Found {vehicle_count} vehicles")

            for veh_id in vehicle_ids:
                try:
                    speed = self.traci.vehicle.getSpeed(veh_id)
                    speeds.append(speed)

                    vehicles_data.append({
                        'id': veh_id,
                        'speed': speed * 3.6,  # Convert to km/h
                        'position': self.traci.vehicle.getPosition(veh_id),
                        'road_id': self.traci.vehicle.getRoadID(veh_id),
                        'lane_id': self.traci.vehicle.getLaneID(veh_id),
                        'type': self.traci.vehicle.getTypeID(veh_id),
                        'waiting_time': self.traci.vehicle.getWaitingTime(veh_id)
                    })
                except Exception as e:
                    print(f"Error getting data for vehicle {veh_id}: {e}")
                    continue
                
            avg_speed = sum(speeds) / len(speeds) * 3.6 if speeds else 0

            # Update edge/lane information
            edges_data = []
            try:
                lane_ids = self.traci.lane.getIDList()
                for lane_id in lane_ids:
                    try:
                        edge_id = lane_id[:-2]  # Remove lane index
                        edges_data.append({
                            'id': edge_id,
                            'lane_id': lane_id,
                            'vehicle_count': self.traci.lane.getLastStepVehicleNumber(lane_id),
                            'avg_speed': self.traci.lane.getLastStepMeanSpeed(lane_id) * 3.6,
                            'occupancy': self.traci.lane.getLastStepOccupancy(lane_id)
                        })
                    except:
                        continue
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
                'edges': edges_data,
                'traffic_stats': {
                    'total_vehicles': vehicle_count,
                    'avg_speed_kmh': avg_speed,
                    'simulation_time': current_time,
                    'throughput': vehicle_count * 2,
                    'density': vehicle_count / max(len(edges_data), 1),
                    'waiting_vehicles': sum(1 for v in vehicles_data if v.get('waiting_time', 0) > 10),
                    'co2_emission': co2_emission,
                    'fuel_consumption': fuel_consumption
                }
            })
            
            print(f"✅ Data update complete: {vehicle_count} vehicles, {len(self.monitoring_data['traffic_lights'])} traffic lights")

        except Exception as e:
            print(f"Error updating simulation data: {e}")
            print(f"❌ Error updating simulation data: {e}")
            import traceback
            traceback.print_exc()
    
    
    # Update traffic light data and store in DB
    def _update_traffic_light_data(self, current_time: float):
        """Update comprehensive traffic light data and store in DB"""
        try:
            print("🔍 Looking for traffic lights...")
            tl_ids = self.traci.trafficlight.getIDList()
            print(f"🚥 Found {len(tl_ids)} traffic lights: {tl_ids}")
            
            if not tl_ids:
                print("❌ No traffic lights found in the simulation!")
                return
            
            # ✅ FIX: Ensure scenario is not None
            scenario = self.current_config or "unknown_scenario"
            print(f"📋 Using scenario: {scenario}")
            
            for tl_id in tl_ids:
                try:
                    print(f"📡 Processing traffic light: {tl_id}")
                    
                    # Get basic traffic light state
                    state = self.traci.trafficlight.getRedYellowGreenState(tl_id)
                    phase = self.traci.trafficlight.getPhase(tl_id)
                    phase_duration = self.traci.trafficlight.getPhaseDuration(tl_id)
                    
                    print(f"   State: {state}, Phase: {phase}, Duration: {phase_duration}")
                    
                    # Get program information
                    program_id = self.traci.trafficlight.getProgram(tl_id)
                    next_switch = self.traci.trafficlight.getNextSwitch(tl_id) - current_time
                    
                    # Get vehicle counts for each lane controlled by this traffic light
                    controlled_lanes = self.traci.trafficlight.getControlledLanes(tl_id)
                    total_vehicles = 0
                    waiting_vehicles = 0
                    
                    print(f"   Controlled lanes: {controlled_lanes}")
                    
                    for lane_id in controlled_lanes:
                        try:
                            lane_vehicles = self.traci.lane.getLastStepVehicleNumber(lane_id)
                            lane_waiting = self.traci.lane.getLastStepHaltingNumber(lane_id)
                            total_vehicles += lane_vehicles
                            waiting_vehicles += lane_waiting
                            print(f"   Lane {lane_id}: {lane_vehicles} vehicles, {lane_waiting} waiting")
                        except Exception as e:
                            print(f"   ❌ Error processing lane {lane_id}: {e}")
                            continue
                    
                    # Get phase name if available
                    phase_name = self._get_phase_name(state)
                    print(f"   Phase name: {phase_name}")
                    
                    # Store in database with proper application context
                    if self.app:
                        try:
                            with self.app.app_context():
                                self._store_traffic_light_log(
                                    traffic_light_id=tl_id,
                                    scenario=scenario,
                                    simulation_time=current_time,
                                    state=state,
                                    phase=phase,
                                    phase_name=phase_name,
                                    duration=phase_duration,
                                    next_switch=next_switch,
                                    vehicle_count=total_vehicles,
                                    waiting_vehicles=waiting_vehicles
                                )
                            print(f"   💾 Stored in database")
                        except Exception as e:
                            print(f"   ❌ Database error: {e}")
                    else:
                        print("   ⚠️ No app context available, skipping database storage")
                    
                    # Update traffic light configuration if not exists
                    print("   ⚙️ Updating traffic light configuration...")
                    self._update_traffic_light_config(tl_id, program_id, phase)
                    
                    # Update monitoring data for API
                    tl_data = {
                        'id': tl_id,
                        'state': state,
                        'phase': phase,
                        'phase_name': phase_name,
                        'duration': phase_duration,
                        'next_switch': next_switch,
                        'program_id': program_id,
                        'controlled_lanes': controlled_lanes,
                        'vehicle_count': total_vehicles,
                        'waiting_vehicles': waiting_vehicles
                    }
                    
                    self.monitoring_data['traffic_lights'].append(tl_data)
                    print(f"   ✅ Added to monitoring data: {tl_data}")
                    
                except Exception as e:
                    print(f"❌ Error processing traffic light {tl_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                
            print(f"🎉 Traffic light update complete: {len(self.monitoring_data['traffic_lights'])} traffic lights processed")
            
        except Exception as e:
            print(f"❌ Error updating traffic light data: {e}")
            import traceback
            traceback.print_exc()
    
    # Store traffic light data in database
    def _store_traffic_light_log(self, **kwargs):
        """Store traffic light data in database - FIXED VERSION"""
        try:
            log = TrafficLightLog(
                traffic_light_id=kwargs.get('traffic_light_id'),
                scenario=kwargs.get('scenario'),
                simulation_time=kwargs.get('simulation_time'),
                state=kwargs.get('state'),
                phase=kwargs.get('phase'),
                phase_name=kwargs.get('phase_name'),
                duration=kwargs.get('duration'),
                next_switch=kwargs.get('next_switch'),
                vehicle_count=kwargs.get('vehicle_count'),
                waiting_vehicles=kwargs.get('waiting_vehicles')
            )
            
            db.session.add(log)
            db.session.commit()
            print(f"✓ Stored traffic light log for {kwargs.get('traffic_light_id')}")
            
        except Exception as e:
            print(f"Error storing traffic light log: {e}")
            db.session.rollback()
    
    # Update traffic light configuration
    def _update_traffic_light_config(self, tl_id: str, program_id: str, current_phase: int):
        """Update or create traffic light configuration with proper context"""
        try:
            # ✅ FIX: Ensure scenario is not None
            scenario = self.current_config or "unknown_scenario"
            
            print(f"🔄 Updating traffic light config for {tl_id}")
            print(f"   Scenario: {scenario}, Program: {program_id}, Phase: {current_phase}")
        
            # Use self.app instead of current_app
            if self.app:
                with self.app.app_context():
                    config = TrafficLightConfig.query.filter_by(
                        traffic_light_id=tl_id, 
                        scenario=scenario
                    ).first()
                    
                    if config:
                        print(f"   📝 Updating existing config (ID: {config.id})")
                    else:
                        print("   📄 Creating new config")

                    if not config:
                        # Get complete phase information
                        print("   🔍 Getting phase information...")
                        phases = self._get_traffic_light_phases_safe(tl_id, program_id)
                        print(f"   📊 Found {len(phases)} phases")
                        
                        # Ensure we have at least some phase data
                        if not phases:
                            print("   ⚠️ No phases collected, using defaults")
                            phases = self._get_default_phases()

                        print(f"   📊 Using {len(phases)} phases")

                        config = TrafficLightConfig(
                            traffic_light_id=tl_id,
                            scenario=scenario,
                            program_id=program_id,
                            phases=json.dumps(phases) if phases else json.dumps(self._get_default_phases()),  # Never null
                            current_phase_index=current_phase,
                            cycle_time=self._calculate_cycle_time(phases),
                            is_adaptive=False
                        )
                        db.session.add(config)
                        action = "created"
                    else:
                        config.current_phase_index = current_phase
                        config.updated_at = datetime.utcnow()
                        action = "updated"

                    db.session.commit()
                    print(f"   ✅ Traffic light config {action} for {tl_id}")
                    
                    # Debug: Check what was stored
                    if config.phases:
                        print(f"   📝 Phases stored: {len(json.loads(config.phases))} phases")
                    else:
                        print("   ❌ PHASES ARE STILL NULL!")
            else:
                print("⚠️ No app context available, skipping config update")

        except Exception as e:
            print(f"Error updating traffic light config: {e}")
            import traceback
            traceback.print_exc()
            
    
    def _get_traffic_light_phases_safe(self, tl_id: str, program_id: str) -> List[Dict]:
        """Get phase information without disrupting the simulation"""
        try:
            print(f"   🔧 Getting phases safely for {tl_id}")

            # Try to get phase count
            try:
                phase_count = self.traci.trafficlight.getPhaseNumber(tl_id)
                print(f"   📈 Traffic light has {phase_count} phases")
            except:
                print("   ❌ Could not get phase count, using default")
                return self._get_default_phases()

            phases = []
            current_phase = self.traci.trafficlight.getPhase(tl_id)
            print(f"   📍 Current phase: {current_phase}")

            # Only get info for the current phase to avoid disruption
            try:
                duration = self.traci.trafficlight.getPhaseDuration(tl_id)
                state = self.traci.trafficlight.getRedYellowGreenState(tl_id)

                phases.append({
                    'index': current_phase,
                    'duration': duration,
                    'state': state,
                    'name': self._get_phase_name(state),
                    'min_duration': 5.0,
                    'max_duration': 60.0
                })

                print(f"   ✅ Added current phase {current_phase}")

            except Exception as e:
                print(f"   ❌ Error getting current phase: {e}")

            # For other phases, use educated guesses based on common patterns
            for phase_index in range(phase_count):
                if phase_index != current_phase:
                    # Create synthetic phase data based on common patterns
                    synthetic_phase = self._create_synthetic_phase(phase_index, current_phase, state)
                    phases.append(synthetic_phase)
                    print(f"   📋 Added synthetic phase {phase_index}")

            print(f"   🎯 Collected {len(phases)} phases (mix of real and synthetic)")
            return phases

        except Exception as e:
            print(f"❌ Error in safe phase collection: {e}")
            return self._get_default_phases()

    def _create_synthetic_phase(self, phase_index: int, current_phase: int, current_state: str) -> Dict:
        """Create synthetic phase data based on common traffic light patterns"""
        # Common phase patterns for 4-phase traffic lights
        if phase_index == 0:
            return {'index': 0, 'duration': 30.0, 'state': 'GGGrrr', 'name': 'MAIN_GREEN', 'min_duration': 5.0, 'max_duration': 60.0}
        elif phase_index == 1:
            return {'index': 1, 'duration': 5.0, 'state': 'yyyrrr', 'name': 'YELLOW', 'min_duration': 3.0, 'max_duration': 10.0}
        elif phase_index == 2:
            return {'index': 2, 'duration': 30.0, 'state': 'rrrGGG', 'name': 'SIDE_GREEN', 'min_duration': 5.0, 'max_duration': 60.0}
        elif phase_index == 3:
            return {'index': 3, 'duration': 5.0, 'state': 'rrryyy', 'name': 'SIDE_YELLOW', 'min_duration': 3.0, 'max_duration': 10.0}
        else:
            return {'index': phase_index, 'duration': 30.0, 'state': 'G' * 6, 'name': f'PHASE_{phase_index}', 'min_duration': 5.0, 'max_duration': 60.0}

    def _get_default_phases(self) -> List[Dict]:
        """Return default phase structure when detailed info isn't available"""
        return [
            {'index': 0, 'duration': 30.0, 'state': 'GGGrrr', 'name': 'MAIN_GREEN', 'min_duration': 5.0, 'max_duration': 60.0},
            {'index': 1, 'duration': 5.0, 'state': 'yyyrrr', 'name': 'YELLOW', 'min_duration': 3.0, 'max_duration': 10.0},
            {'index': 2, 'duration': 30.0, 'state': 'rrrGGG', 'name': 'SIDE_GREEN', 'min_duration': 5.0, 'max_duration': 60.0},
            {'index': 3, 'duration': 5.0, 'state': 'rrryyy', 'name': 'SIDE_YELLOW', 'min_duration': 3.0, 'max_duration': 10.0}
        ]
            
    # Get complete phase information for a traffic light
    # def _get_traffic_light_phases(self, tl_id: str, program_id: str) -> List[Dict]:
    #     """Get complete phase information for a traffic light"""
    #     try:
    #         print(f"   🔧 Getting phases for {tl_id}, program {program_id}")
    #         # Get the number of phases
    #         phase_count = self.traci.trafficlight.getPhaseNumber(tl_id)
    #         print(f"   📈 Traffic light has {phase_count} phases")
            
    #         if phase_count == 0:
    #             print("   ❌ Phase count is 0, returning empty list")
    #             return []
            
    #         phases = []
    #         original_phase = self.traci.trafficlight.getPhase(tl_id)
    #         print(f"   📍 Original phase: {original_phase}")
            
    #         for phase_index in range(phase_count):
    #             try:
    #                 print(f"   🔄 Processing phase {phase_index}")
                    
    #                 # Switch to this phase to get its data
    #                 self.traci.trafficlight.setPhase(tl_id, phase_index)
    #                 time.sleep(0.1)  # Small delay for phase change

    #                 # Get phase data
    #                 duration = self.traci.trafficlight.getPhaseDuration(tl_id)
    #                 state = self.traci.trafficlight.getRedYellowGreenState(tl_id)
                    
    #                 phase_data = ({
    #                     'index': phase_index,
    #                     'duration': duration,
    #                     'state': state,
    #                     'name': self._get_phase_name(state),
    #                     'min_duration': 5.0,  # Default values
    #                     'max_duration': 60.0
    #                     # 'min_duration': self._get_phase_min_duration(tl_id, phase_index),
    #                     # 'max_duration': self._get_phase_max_duration(tl_id, phase_index)
    #                 })
                    
    #                 phases.append(phase_data)
    #                 print(f"   ✅ Phase {phase_index}: {state} for {duration}s")
                    
    #                 # Move to next phase to get its data
    #                 # if phase_index < phase_count - 1:
    #                 #     self.traci.trafficlight.setPhase(tl_id, phase_index + 1)
                        
    #             except Exception as e:
    #                 print(f"Error getting phase {phase_index}: {e}")
    #                 import traceback
    #                 traceback.print_exc()
    #                 continue
            
    #         # Return to original phase
    #         self.traci.trafficlight.setPhase(tl_id, original_phase)
    #         print(f"   🔙 Returned to original phase {original_phase}")
    #         # self.traci.trafficlight.setPhase(tl_id, 0)
    #         time.sleep(0.2)
    #         print(f"   🎯 Successfully collected {len(phases)} phases")
    #         return phases
            
    #     except Exception as e:
    #         print(f"Error getting phases for {tl_id}: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         return []
    
    # Get phase name from state string
    def _get_phase_name(self, state: str) -> str:
        """Convert traffic light state to phase name"""
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
            return 'UNKNOWN'
        
    # Analyze traffic light state for optimization opportunities
    # def _analyze_traffic_light_state(self, state: str, waiting_vehicles: int) -> Dict:
    #     """Analyze traffic light state for optimization opportunities"""
    #     analysis = {
    #         'efficiency_score': 0,
    #         'recommendations': [],
    #         'congestion_level': 'LOW'
    #     }
        
    #     # Calculate efficiency based on green time vs waiting vehicles
    #     green_ratio = state.count('G') + state.count('g') / len(state) if state else 0
    #     analysis['efficiency_score'] = green_ratio * 100
        
    #     # Add recommendations
    #     if waiting_vehicles > 10 and green_ratio < 0.3:
    #         analysis['recommendations'].append('Consider increasing green time for congested direction')
    #         analysis['congestion_level'] = 'HIGH'
    #     elif waiting_vehicles > 5:
    #         analysis['congestion_level'] = 'MEDIUM'
        
    #     if 'rrrr' in state:  # All red phase
    #         analysis['recommendations'].append('All-red phase detected, check if necessary')
        
    #     return analysis
    
    # Calculate total cycle time from phases
    def _calculate_cycle_time(self, phases: List[Dict]) -> float:
        """Calculate total cycle time from phases"""
        if not phases:
            return 0
        return sum(phase.get('duration', 0) for phase in phases)
    
    # Get maximum duration for a phase (if available)
    # def _get_phase_min_duration(self, tl_id: str, phase_index: int) -> float:
    #     """Get minimum duration for a phase (if available)"""
    #     try:
    #         # This might require accessing TLS program details
    #         return 5.0  # Default minimum
    #     except:
    #         return 5.0
    
    # Get maximum duration for a phase (if available)
    # def _get_phase_max_duration(self, tl_id: str, phase_index: int) -> float:
    #     """Get maximum duration for a phase (if available)"""
    #     try:
    #         # This might require accessing TLS program details
    #         return 60.0  # Default maximum
    #     except:
    #         return 60.0
    
    # New methods for traffic light control
    def set_traffic_light_phase(self, tl_id: str, phase: int) -> Dict[str, Any]:
        """Set traffic light to specific phase"""
        if not self.is_running or not self.traci:
            return {"success": False, "error": "Simulation not running"}
        
        try:
            self.traci.trafficlight.setPhase(tl_id, phase)
            return {"success": True, "message": f"Traffic light {tl_id} set to phase {phase}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to set phase: {str(e)}"}
    
    # Change traffic light program
    def set_traffic_light_program(self, tl_id: str, program_id: str) -> Dict[str, Any]:
        """Change traffic light program"""
        if not self.is_running or not self.traci:
            return {"success": False, "error": "Simulation not running"}
        
        try:
            self.traci.trafficlight.setProgram(tl_id, program_id)
            return {"success": True, "message": f"Traffic light {tl_id} set to program {program_id}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to set program: {str(e)}"}
    
    # Get historical data for a specific traffic light
    def get_traffic_light_history(self, tl_id: str, limit: int = 100) -> List[Dict]:
        """Get historical data for a specific traffic light"""
        logs = TrafficLightLog.query.filter_by(traffic_light_id=tl_id)\
                                  .order_by(TrafficLightLog.simulation_time.desc())\
                                  .limit(limit)\
                                  .all()
        return [log.to_dict() for log in logs]
    
    # Get comprehensive analysis for a traffic light
    def get_traffic_light_analysis(self, tl_id: str) -> Dict[str, Any]:
        """Get comprehensive analysis for a traffic light"""
        # Get recent logs
        recent_logs = self.get_traffic_light_history(tl_id, 50)
        
        if not recent_logs:
            return {"error": "No data available for this traffic light"}
        
        # Calculate statistics
        total_vehicles = sum(log['vehicle_count'] for log in recent_logs)
        avg_waiting = sum(log['waiting_vehicles'] for log in recent_logs) / len(recent_logs)
        
        # Phase distribution
        phase_times = {}
        for log in recent_logs:
            phase = log['phase_name']
            phase_times[phase] = phase_times.get(phase, 0) + (log['duration'] or 0)
        
        return {
            'traffic_light_id': tl_id,
            'analysis_period': f"{recent_logs[-1]['simulation_time']} to {recent_logs[0]['simulation_time']}",
            'total_vehicles_observed': total_vehicles,
            'average_waiting_vehicles': round(avg_waiting, 2),
            'phase_time_distribution': phase_times,
            'efficiency_recommendations': self._generate_efficiency_recommendations(recent_logs)
        }
    
    # Generate efficiency recommendations based on historical data
    def _generate_efficiency_recommendations(self, logs: List[Dict]) -> List[str]:
        """Generate efficiency recommendations based on historical data"""
        recommendations = []
        
        if len(logs) < 10:
            return ["Insufficient data for analysis"]
        
        # Analyze green time vs waiting vehicles
        green_phases = [log for log in logs if 'MAIN_GREEN' in log['phase_name']]
        if green_phases:
            avg_green_time = sum(log['duration'] or 0 for log in green_phases) / len(green_phases)
            avg_waiting_during_green = sum(log['waiting_vehicles'] for log in green_phases) / len(green_phases)
            
            if avg_waiting_during_green > 5 and avg_green_time < 20:
                recommendations.append("Consider increasing green phase duration")
        
        return recommendations
    
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
        
        
    def force_traffic_light_update(self) -> Dict[str, Any]:
        """Force an immediate update of traffic light data (for testing)"""
        if not self.is_running or not self.traci:
            return {"success": False, "error": "Simulation not running"}

        try:
            current_time = self.traci.simulation.getTime()
            print("🔄 FORCING traffic light update...")
            self._update_traffic_light_data(current_time)

            traffic_lights = self.monitoring_data['traffic_lights']
            return {
                "success": True,
                "message": f"Traffic light data updated",
                "traffic_light_count": len(traffic_lights),
                "traffic_lights": traffic_lights
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to update traffic lights: {str(e)}"}

    def add_virtual_cameras_to_simulation(self):
        """Add virtual cameras to SUMO network"""
        virtual_cameras = {
            'cam_north': {'detector': 'detector_north', 'lane': 'edge1_0'},
            'cam_south': {'detector': 'detector_south', 'lane': 'edge2_0'},
            'cam_east': {'detector': 'detector_east', 'lane': 'edge3_0'},
            'cam_west': {'detector': 'detector_west', 'lane': 'edge4_0'}
        }
        
        for cam_id, config in virtual_cameras.items():
            camera_service.add_virtual_camera(
                cam_id, 
                config['detector'],
                {'lane': config['lane']}
            )
            
    def _update_simulation_with_ai(self):
        """Update simulation based on AI decisions"""
        if not self.traci or not self.is_running:
            return
        
        # Get camera data from both sources
        camera_data = camera_service.get_combined_camera_data(self.traci)
        self.camera_data = camera_data
        
        # Get current SUMO state
        sumo_state = self._get_current_sumo_state()
        
        # Get AI decision
        ai_decision = ai_traffic_service.make_traffic_decision(camera_data, sumo_state)
        self.ai_decisions.append(ai_decision)
        
        # Apply AI decision to SUMO
        self._apply_ai_decision(ai_decision)
    
    def _apply_ai_decision(self, decision: Dict):
        """Apply AI decision to SUMO simulation"""
        if decision['action'] == 'extend_green':
            # Extend current green phase
            current_phase = self.traci.trafficlight.getPhase('tl_id')
            new_duration = self.traci.trafficlight.getPhaseDuration('tl_id') + decision['duration_increase']
            self.traci.trafficlight.setPhaseDuration('tl_id', new_duration)
            
        elif decision['action'] == 'reduce_cycle':
            # Reduce cycle time
            current_duration = self.traci.trafficlight.getPhaseDuration('tl_id')
            new_duration = max(10, current_duration - decision['duration_decrease'])
            self.traci.trafficlight.setPhaseDuration('tl_id', new_duration)
# Global instance
sumo_service = SumoService()