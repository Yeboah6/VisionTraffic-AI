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

class SumoService:
    def __init__(self):
        self.simulation_process: Optional[subprocess.Popen] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.monitoring_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.current_config = None
        self.traci = None
        self.simulation_step = 0
        self.traffic_light_history = {}
        self.last_tl_update = 0
        self.tl_update_interval = 5  # seconds
        
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
            
            # Update traffic light data less frequently to avoid DB overload
            if current_time - self.last_tl_update >= self.tl_update_interval:
                self._update_traffic_light_data(current_time)
                self.last_tl_update = current_time
                
            
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
    
    # Update traffic light data and store in DB
    def _update_traffic_light_data(self, current_time: float):
        """Update comprehensive traffic light data and store in DB"""
        try:
            tl_ids = self.traci.trafficlight.getIDList()
            
            for tl_id in tl_ids:
                try:
                    # Get basic traffic light state
                    state = self.traci.trafficlight.getRedYellowGreenState(tl_id)
                    phase = self.traci.trafficlight.getPhase(tl_id)
                    phase_duration = self.traci.trafficlight.getPhaseDuration(tl_id)
                    
                    # Get program information
                    program_id = self.traci.trafficlight.getProgram(tl_id)
                    next_switch = self.traci.trafficlight.getNextSwitch(tl_id) - current_time
                    
                    # Get vehicle counts for each lane controlled by this traffic light
                    controlled_lanes = self.traci.trafficlight.getControlledLanes(tl_id)
                    total_vehicles = 0
                    waiting_vehicles = 0
                    
                    for lane_id in controlled_lanes:
                        lane_vehicles = self.traci.lane.getLastStepVehicleNumber(lane_id)
                        lane_waiting = self.traci.lane.getLastStepHaltingNumber(lane_id)
                        total_vehicles += lane_vehicles
                        waiting_vehicles += lane_waiting
                    
                    # Get phase name if available
                    phase_name = self._get_phase_name(state)
                    
                    # Store in database with proper application context
                    self._store_traffic_light_log(
                        tl_id=tl_id,
                        scenario=self.current_config,
                        simulation_time=current_time,
                        state=state,
                        phase=phase,
                        phase_name=phase_name,
                        duration=phase_duration,
                        next_switch=next_switch,
                        vehicle_count=total_vehicles,
                        waiting_vehicles=waiting_vehicles
                    )
                    
                    # Update traffic light configuration if not exists
                    self._update_traffic_light_config(tl_id, program_id, phase)
                    
                    # Update monitoring data for API
                    self.monitoring_data['traffic_lights'].append({
                        'id': tl_id,
                        'state': state,
                        'phase': phase,
                        'phase_name': phase_name,
                        'duration': phase_duration,
                        'next_switch': next_switch,
                        'program_id': program_id,
                        'controlled_lanes': controlled_lanes,
                        'vehicle_count': total_vehicles,
                        'waiting_vehicles': waiting_vehicles,
                        'current_state_analysis': self._analyze_traffic_light_state(state, waiting_vehicles)
                    })
                    
                except Exception as e:
                    print(f"Error processing traffic light {tl_id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error updating traffic light data: {e}")
    
    # Store traffic light data in database
    def _store_traffic_light_log(self, **kwargs):
        """Store traffic light data in database with proper context"""
        try:
            # Use application context for database operations
            # from flask import current_app
            with current_app.app_context():
                # Map parameters to correct column names
                log_data = {
                    'traffic_light_id': kwargs.get('tl_id'),  # Map to correct column name
                    'scenario': kwargs.get('scenario'),
                    'simulation_time': kwargs.get('simulation_time'),
                    'state': kwargs.get('state'),
                    'phase': kwargs.get('phase'),
                    'phase_name': kwargs.get('phase_name'),
                    'duration': kwargs.get('duration'),
                    'next_switch': kwargs.get('next_switch'),
                    'vehicle_count': kwargs.get('vehicle_count'),
                    'waiting_vehicles': kwargs.get('waiting_vehicles')
                }

                log = TrafficLightLog(**log_data)
                db.session.add(log)
                db.session.commit()
                print(f"✓ Stored traffic light log for {kwargs.get('tl_id')}")

        except Exception as e:
            print(f"Error storing traffic light log: {e}")
            db.session.rollback()
    
    # Update traffic light configuration
    def _update_traffic_light_config(self, tl_id: str, program_id: str, current_phase: int):
        """Update or create traffic light configuration with proper context"""
        try:
            # from flask import current_app
            with current_app.app_context():
                config = TrafficLightConfig.query.filter_by(
                    traffic_light_id=tl_id, 
                    scenario=self.current_config
                ).first()
                
                if not config:
                    # Get complete phase information
                    phases = self._get_traffic_light_phases(tl_id, program_id)
                    
                    config = TrafficLightConfig(
                        traffic_light_id=tl_id,
                        scenario=self.current_config,
                        program_id=program_id,
                        phases=json.dumps(phases) if phases else None,
                        current_phase_index=current_phase,
                        cycle_time=self._calculate_cycle_time(phases),
                        is_adaptive=False
                    )
                    db.session.add(config)
                else:
                    config.current_phase_index = current_phase
                    config.updated_at = datetime.utcnow()
                
                db.session.commit()
                print(f"✓ Updated traffic light config for {tl_id}")
                
        except Exception as e:
            print(f"Error updating traffic light config: {e}")
            
    # Get complete phase information for a traffic light
    def _get_traffic_light_phases(self, tl_id: str, program_id: str) -> List[Dict]:
        """Get complete phase information for a traffic light"""
        try:
            # Get the number of phases
            phase_count = self.traci.trafficlight.getPhaseNumber(tl_id)
            phases = []
            
            for phase_index in range(phase_count):
                try:
                    duration = self.traci.trafficlight.getPhaseDuration(tl_id)
                    state = self.traci.trafficlight.getRedYellowGreenState(tl_id)
                    
                    phases.append({
                        'index': phase_index,
                        'duration': duration,
                        'state': state,
                        'name': self._get_phase_name(state),
                        'min_duration': self._get_phase_min_duration(tl_id, phase_index),
                        'max_duration': self._get_phase_max_duration(tl_id, phase_index)
                    })
                    
                    # Move to next phase to get its data
                    if phase_index < phase_count - 1:
                        self.traci.trafficlight.setPhase(tl_id, phase_index + 1)
                        
                except Exception as e:
                    print(f"Error getting phase {phase_index} for {tl_id}: {e}")
                    continue
            
            # Return to original phase
            self.traci.trafficlight.setPhase(tl_id, 0)
            return phases
            
        except Exception as e:
            print(f"Error getting phases for {tl_id}: {e}")
            return []
    
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
    def _analyze_traffic_light_state(self, state: str, waiting_vehicles: int) -> Dict:
        """Analyze traffic light state for optimization opportunities"""
        analysis = {
            'efficiency_score': 0,
            'recommendations': [],
            'congestion_level': 'LOW'
        }
        
        # Calculate efficiency based on green time vs waiting vehicles
        green_ratio = state.count('G') + state.count('g') / len(state) if state else 0
        analysis['efficiency_score'] = green_ratio * 100
        
        # Add recommendations
        if waiting_vehicles > 10 and green_ratio < 0.3:
            analysis['recommendations'].append('Consider increasing green time for congested direction')
            analysis['congestion_level'] = 'HIGH'
        elif waiting_vehicles > 5:
            analysis['congestion_level'] = 'MEDIUM'
        
        if 'rrrr' in state:  # All red phase
            analysis['recommendations'].append('All-red phase detected, check if necessary')
        
        return analysis
    
    # Calculate total cycle time from phases
    def _calculate_cycle_time(self, phases: List[Dict]) -> float:
        """Calculate total cycle time from phases"""
        if not phases:
            return 0
        return sum(phase.get('duration', 0) for phase in phases)
    
    # Get maximum duration for a phase (if available)
    def _get_phase_min_duration(self, tl_id: str, phase_index: int) -> float:
        """Get minimum duration for a phase (if available)"""
        try:
            # This might require accessing TLS program details
            return 5.0  # Default minimum
        except:
            return 5.0
    
    # Get maximum duration for a phase (if available)
    def _get_phase_max_duration(self, tl_id: str, phase_index: int) -> float:
        """Get maximum duration for a phase (if available)"""
        try:
            # This might require accessing TLS program details
            return 60.0  # Default maximum
        except:
            return 60.0
    
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
        green_phases = [log for log in logs if 'GREEN' in log['phase_name']]
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

# Global instance
sumo_service = SumoService()