import threading
import time
import os
import sys
import traci
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.services.db_queue import db_queue_service
from app.services.performance_monitor import performance_monitor

class SumoService:
    """
    High-performance SUMO simulation service
    Optimized for smooth real-time operation with async database writes
    """
    
    def __init__(self, app=None):
        self.app = app
        self.simulation_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.current_config = None
        self.traci = None
        self.simulation_step = 0
        
        # Performance optimization settings
        self.performance_config = {
            'data_update_interval': 5,           # Update monitoring data every 5 steps
            'traffic_light_update_interval': 10, # Update TL data every 10 steps  
            'min_sleep_time': 0.001,            # Minimum sleep for headless
            'gui_sleep_time': 0.01,             # Reduced sleep for GUI
            'max_vehicles_to_track': 50,        # Limit vehicle tracking for performance
            'max_traffic_lights': 5,            # Limit TL processing
            'adaptive_sleep_enabled': True      # Dynamic sleep based on performance
        }
        
        # Monitoring data (minimal for performance)
        self.monitoring_data = {
            'vehicle_count': 0,
            'average_speed': 0.0,
            'current_time': 0,
            'traffic_lights': [],
            'performance_stats': {},
            'simulation_step': 0
        }
        
        # Performance tracking
        self.last_data_update = 0
        self.last_tl_update = 0
        self.actual_step_times = []
        
        # SUMO paths
        self.sumo_configs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'sumo_configs'
        )
        
        self.available_scenarios = {
            'intersection': {
                'config': 'intersection.sumocfg',
                'name': 'Intersection',
                'description': 'Optimized performance test'
            },
            'simple': {
                'config': 'simple.sumocfg', 
                'name': 'Simple Network',
                'description': 'Basic network for testing'
            }
        }
        
        self._set_sumo_path()
        
        # If app is provided during initialization, set it up
        if app:
            self.init_app(app)
            
        
    def init_app(self, app):
        """Initialize with Flask app instance"""
        self.app = app
        print("✅ SumoService initialized with Flask app")
        
        # Initialize database queue if available
        try:
            from app.services.db_queue import db_queue_service, init_db_queue
            if db_queue_service is None:
                init_db_queue(app)
                print("✅ Database queue service initialized")
            else:
                print("✅ Database queue service already initialized")
        except Exception as e:
            print(f"⚠️ Database queue initialization warning: {e}")
    
    def _set_sumo_path(self):
        """Set up SUMO environment variables"""
        try:
            possible_paths = [
                os.environ.get('SUMO_HOME', ''),
                'C:/Program Files (x86)/Eclipse/Sumo',
                'C:/Program Files/Eclipse/Sumo',
            ]
            
            for sumo_path in possible_paths:
                if sumo_path and os.path.exists(sumo_path):
                    os.environ['SUMO_HOME'] = sumo_path
                    tools_dir = os.path.join(sumo_path, 'tools')
                    if tools_dir not in sys.path:
                        sys.path.append(tools_dir)
                    print(f"✅ SUMO_HOME set to: {sumo_path}")
                    break
            else:
                print("⚠️ SUMO_HOME not found")
                
        except Exception as e:
            print(f"❌ Error setting SUMO path: {e}")
    
    def start_simulation(self, scenario: str, gui: bool = True) -> Dict[str, Any]:
        """Start high-performance SUMO simulation"""
        if self.is_running:
            return {"success": False, "error": "Simulation already running"}
        
        if scenario not in self.available_scenarios:
            return {"success": False, "error": f"Scenario '{scenario}' not found"}
        
        try:
            config_file = self.available_scenarios[scenario]['config']
            config_path = os.path.join(self.sumo_configs_dir, config_file)
            
            if not os.path.exists(config_path):
                return {"success": False, "error": f"Config file not found: {config_path}"}
            
            # Reset state
            self._reset_monitoring_data()
            self.current_config = scenario
            
            # Start simulation in separate thread
            self.simulation_thread = threading.Thread(
                target=self._run_high_performance_simulation,
                args=(config_path, scenario, gui),
                name=f"SUMO-HP-{scenario}"
            )
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
            
            # Wait for startup with shorter timeout
            for _ in range(15):  # 1.5 second timeout
                if self.is_running:
                    break
                time.sleep(0.1)
            else:
                return {"success": False, "error": "Simulation failed to start"}
            
            return {
                "success": True,
                "message": f"High-performance simulation started",
                "scenario": scenario,
                "performance_mode": "Optimized"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to start simulation: {str(e)}"}
    
    def _run_high_performance_simulation(self, config_path: str, scenario: str, gui: bool):
        """High-performance simulation loop optimized for smooth operation"""
        try:
            # Build optimized SUMO command
            sumo_binary = 'sumo-gui' if gui else 'sumo'
            sumo_cmd = [
                sumo_binary,
                '-c', config_path,
                '--step-length', '0.1',
                '--delay', '500'
                '--start',
                '--quit-on-end'
            ]
            
            print(f"🚀 Starting high-performance SUMO: {' '.join(sumo_cmd)}")
            
            # Start TraCI connection
            traci.start(sumo_cmd)
            self.traci = traci
            self.is_running = True
            
            print("✅ High-performance simulation running...")
            
            # Performance tracking
            step_count = 0
            last_perf_log = time.time()
            last_db_flush = time.time()
            
            # Main optimized simulation loop
            while self.is_running and step_count < 20000:  # Increased limit
                step_start = time.time()
                
                try:
                    # 1. CRITICAL: Simulation step (fastest possible)
                    traci.simulationStep()
                    step_count += 1
                    self.simulation_step = step_count
                    
                    # 2. Performance monitoring (minimal overhead)
                    performance_monitor.record_step()
                    
                    current_time = traci.simulation.getTime()
                    self.monitoring_data['current_time'] = current_time
                    self.monitoring_data['simulation_step'] = step_count
                    
                    # 3. Optimized data collection (strategic intervals)
                    if step_count % self.performance_config['data_update_interval'] == 0:
                        self._collect_minimal_data(traci)
                    
                    # 4. Traffic light updates (less frequent)
                    if step_count % self.performance_config['traffic_light_update_interval'] == 0:
                        self._update_traffic_lights_optimized(traci, current_time, scenario)
                    
                    # 5. Performance logging (infrequent)
                    if time.time() - last_perf_log > 3.0:  # Every 3 seconds
                        perf_stats = performance_monitor.get_current_performance()
                        vehicle_count = len(traci.vehicle.getIDList())
                        print(f"🎯 Step {step_count}: {vehicle_count} vehicles, {perf_stats['steps_per_second']['current']:.1f} steps/sec")
                        last_perf_log = time.time()
                    
                    # 6. Database queue maintenance
                    if time.time() - last_db_flush > 2.0 and db_queue_service:
                        if db_queue_service.get_stats()['current_queue_size'] > 20:
                            db_queue_service.flush_queue()
                        last_db_flush = time.time()
                    
                    # 7. Adaptive sleep calculation for optimal performance
                    step_duration = time.time() - step_start
                    sleep_time = self._calculate_optimized_sleep(step_duration, gui, step_count)
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                except Exception as step_error:
                    print(f"⚠️ Step error: {step_error}")
                    continue
                    
        except Exception as e:
            print(f"❌ Simulation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup_simulation()
    
    def _collect_minimal_data(self, traci):
        """Collect only essential data with minimal performance impact"""
        try:
            # Get vehicle count (single fast call)
            vehicle_ids = traci.vehicle.getIDList()
            vehicle_count = len(vehicle_ids)
            self.monitoring_data['vehicle_count'] = vehicle_count
            
            # Calculate average speed (limited sampling for performance)
            if vehicle_count > 0:
                sampled_vehicles = min(vehicle_count, self.performance_config['max_vehicles_to_track'])
                speeds = []
                for i in range(0, sampled_vehicles, max(1, vehicle_count // sampled_vehicles)):
                    try:
                        speed = traci.vehicle.getSpeed(vehicle_ids[i])
                        speeds.append(speed)
                    except:
                        continue
                
                if speeds:
                    avg_speed = sum(speeds) / len(speeds) * 3.6  # km/h
                    self.monitoring_data['average_speed'] = avg_speed
            
            # Update performance stats
            self.monitoring_data['performance_stats'] = performance_monitor.get_current_performance()
            
        except Exception as e:
            print(f"⚠️ Minimal data collection error: {e}")
            
            
    def _update_traffic_light_data(self, current_time: float):
        """Update comprehensive traffic light data and store in DB via queue"""
        try:
            print("🔍 Looking for traffic lights...")
            tl_ids = self.traci.trafficlight.getIDList()
            print(f"🚥 Found {len(tl_ids)} traffic lights: {tl_ids}")

            if not tl_ids:
                print("❌ No traffic lights found in the simulation!")
                return

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

                    # Get vehicle counts (simplified for performance)
                    controlled_lanes = self.traci.trafficlight.getControlledLanes(tl_id)
                    total_vehicles = 0
                    waiting_vehicles = 0

                    # Sample a few lanes instead of all for performance
                    for lane_id in controlled_lanes[:3]:  # Limit to 3 lanes
                        try:
                            lane_vehicles = self.traci.lane.getLastStepVehicleNumber(lane_id)
                            lane_waiting = self.traci.lane.getLastStepHaltingNumber(lane_id)
                            total_vehicles += lane_vehicles
                            waiting_vehicles += lane_waiting
                        except Exception as e:
                            continue
                        
                    phase_name = self._get_phase_name(state)

                    # ✅ USE QUEUE FOR DATABASE STORAGE
                    storage_success = self._store_traffic_light_log(
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

                    if storage_success:
                        print(f"   ✅ Queued for DB: {tl_id}")
                    else:
                        print(f"   ❌ Failed to queue: {tl_id}")

                    # Update monitoring data for API
                    tl_data = {
                        'id': tl_id,
                        'state': state,
                        'phase': phase,
                        'phase_name': phase_name,
                        'duration': phase_duration,
                        'next_switch': next_switch,
                        'program_id': program_id,
                        'vehicle_count': total_vehicles,
                        'waiting_vehicles': waiting_vehicles
                    }

                    self.monitoring_data['traffic_lights'].append(tl_data)

                except Exception as e:
                    print(f"❌ Error processing traffic light {tl_id}: {e}")
                    continue
                
            print(f"🎉 Traffic light update complete: {len(self.monitoring_data['traffic_lights'])} traffic lights processed")

        except Exception as e:
            print(f"❌ Error updating traffic light data: {e}")
    
    def _update_traffic_lights_optimized(self, traci, current_time: float, scenario: str):
        """Optimized traffic light data collection with async DB storage"""
        try:
            tl_ids = traci.trafficlight.getIDList()
            processed_tls = []
            
            # Limit processing for performance
            max_tls = min(len(tl_ids), self.performance_config['max_traffic_lights'])
            
            for tl_id in tl_ids[:max_tls]:
                try:
                    # Get minimal TL data
                    state = traci.trafficlight.getRedYellowGreenState(tl_id)
                    phase = traci.trafficlight.getPhase(tl_id)
                    
                    tl_data = {
                        'id': tl_id,
                        'state': state,
                        'phase': phase,
                        'phase_name': self._get_phase_name(state)
                    }
                    processed_tls.append(tl_data)
                    
                    # Async database storage via queue
                    if db_queue_service:
                        log_data = {
                            'traffic_light_id': tl_id,
                            'scenario': scenario,
                            'simulation_time': current_time,
                            'state': state,
                            'phase': phase,
                            'phase_name': self._get_phase_name(state),
                            'duration': traci.trafficlight.getPhaseDuration(tl_id),
                            'next_switch': traci.trafficlight.getNextSwitch(tl_id) - current_time,
                            'vehicle_count': 0,  # Skip expensive counting
                            'waiting_vehicles': 0,
                            'created_at': datetime.utcnow()
                        }
                        db_queue_service.add_traffic_light_log(log_data)
                        
                except Exception as e:
                    continue  # Skip failed TLs
            
            self.monitoring_data['traffic_lights'] = processed_tls
            
        except Exception as e:
            print(f"⚠️ Optimized TL update error: {e}")
    
    def _calculate_optimized_sleep(self, step_duration: float, gui: bool, step_count: int) -> float:
        """Calculate optimal sleep time for target performance"""
        # Track recent step times for adaptive calculation
        self.actual_step_times.append(step_duration)
        if len(self.actual_step_times) > 10:
            self.actual_step_times.pop(0)
        
        if gui:
            # Target ~15 FPS for GUI smoothness
            target_step_time = 0.066  # ~15 FPS
            avg_step_time = sum(self.actual_step_times) / len(self.actual_step_times)
            sleep_time = max(0.001, target_step_time - avg_step_time)
            return min(sleep_time, self.performance_config['gui_sleep_time'])
        else:
            # Headless - minimal sleep, focus on max speed
            return self.performance_config['min_sleep_time']
    
    def _get_phase_name(self, state: str) -> str:
        """Get phase name from state (optimized)"""
        if 'G' in state and 'r' in state:
            return 'GREEN'
        elif 'y' in state:
            return 'YELLOW' 
        elif 'g' in state:
            return 'PEDESTRIAN'
        else:
            return 'RED'
    
    def _cleanup_simulation(self):
        """Cleanup simulation resources"""
        try:
            if self.traci:
                self.traci.close()
        except:
            pass
        
        # Final database flush
        if db_queue_service:
            db_queue_service.flush_queue()
        
        self.is_running = False
        self.traci = None
        self.current_config = None
        print("✅ Simulation cleanup completed")
    
    def _reset_monitoring_data(self):
        """Reset monitoring data"""
        self.monitoring_data = {
            'vehicle_count': 0,
            'average_speed': 0.0,
            'current_time': 0,
            'traffic_lights': [],
            'performance_stats': {},
            'simulation_step': 0
        }
        self.simulation_step = 0
        self.actual_step_times = []
    
    def stop_simulation(self) -> Dict[str, Any]:
        """Stop the running SUMO simulation and flush queue"""
        if not self.is_running:
            return {"success": False, "error": "No simulation is currently running"}

        try:
            self.is_running = False

            # Give it a moment to stop gracefully
            time.sleep(1)

            # Force close TraCI if still connected
            if self.traci and hasattr(self.traci, 'close'):
                try:
                    self.traci.close()
                except:
                    pass
                
            # ✅ FLUSH DATABASE QUEUE ON STOP
            from app.services.db_queue import db_queue_service
            if db_queue_service:
                print("🔄 Flushing database queue before shutdown...")
                db_queue_service.flush_queue()
                queue_stats = db_queue_service.get_stats()
                print(f"📊 Final queue stats: {queue_stats}")

            self.current_config = None
            self.traci = None

            return {"success": True, "message": "SUMO simulation stopped successfully"}

        except Exception as e:
            return {"success": False, "error": f"Failed to stop simulation: {str(e)}"}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status"""
        perf_stats = performance_monitor.get_current_performance()
        return {
            "is_running": self.is_running,
            "current_scenario": self.current_config,
            "simulation_step": self.simulation_step,
            "performance": {
                "steps_per_second": perf_stats.get('steps_per_second', {}).get('current', 0),
                "mode": "High-Performance Optimized"
            }
        }
    
    def get_simulation_data(self) -> Dict[str, Any]:
        """Get current simulation data for API"""
        return {
            "monitoring": self.monitoring_data,
            "performance": performance_monitor.get_current_performance(),
            "db_queue": db_queue_service.get_stats() if db_queue_service else {},
            "is_running": self.is_running,
            "config": self.performance_config
        }

    # Keep your existing methods for compatibility
    def get_available_scenarios(self) -> Dict[str, Any]:
        return self.available_scenarios
        
    def get_traffic_lights(self) -> List[Dict[str, Any]]:
        return self.monitoring_data.get('traffic_lights', [])
        
    def get_vehicle_list(self) -> List[Dict[str, Any]]:
        return []  # Simplified for performance

# Replace global instance with high-performance version
sumo_service = SumoService()

def init_sumo_service(app):
    """Initialize SUMO service with app context"""
    sumo_service.app = app