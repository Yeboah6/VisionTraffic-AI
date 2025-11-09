import threading
import time
import os
import sys
import subprocess
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.extensions import db
# from app.models.traffic_light import TrafficLightLog, TrafficLightConfig

# Services
from app.services.db_queue import db_queue_service
from app.services.performance_monitor import performance_monitor
from app.services.tls_data_service import tls_data_service
from app.services.tls_config_service import tls_config_service
from app.services.ai_traffic_service import ai_traffic_service

class OptimizedSumoService:
    """
    High-performance SUMO simulation service with integrated TLS data collection
    """
    
    def __init__(self, app=None):
        self.app = app
        self.simulation_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.current_config = None
        self.traci = None
        self.simulation_step = 0
        self.ai_optimization_enabled = True
        self.last_ai_decision = None
        self.ai_optimization_interval = 30  # Apply AI every 30 steps
        self._last_tls_update_step = 0  # Track last update
        
        # Performance optimization settings
        self.performance_config = {
            'data_update_interval': 5,           # Update data every 5 steps
            'tls_update_interval': 10, # Update TL every 10 steps  
            'min_sleep_time': 0.001,             # Minimum sleep for headless
            'gui_sleep_time': 0.02,              # Sleep for GUI mode
            'max_steps': 50000,                  # Safety limit
            'print_interval': 50                 # Print progress every 50 steps
        }
        
        # Monitoring data (with TLS data)
        self.monitoring_data = {
            'vehicle_count': 0,
            'average_speed': 0.0,
            'current_time': 0,
            'traffic_lights': [],
            'tls_snapshot': {},  # Added for TLS data
            'performance_stats': {}
        }
        
        # SUMO configurations directory
        self.sumo_configs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'sumo_configs'
        )
        
        # Available scenarios
        self.available_scenarios = {
            'intersection': {
                'config': 'intersection.sumocfg',
                'name': 'Complex Intersection',
                'description': 'A basic 4-way intersection scenario',
                'complexity': 'Beginner'
            },
            'accra': {
                'config': 'accra_37.sumocfg',
                'name': 'Highway Simulation',
                'description': 'Multi-lane highway with merging',
                'complexity': 'Advanced'
            },
            'test': {
                'config': 'test.sumocfg',
                'name': 'Test Scenario',
                'description': 'A scenario for testing purposes',
                'complexity': 'Advanced'
            }
        }
        
        self._set_sumo_path()
        self._verify_scenario_files()
        
    def init_app(self, app):
        """Initialize with Flask app instance"""
        self.app = app
        tls_data_service.init_app(app)
        
    def _set_sumo_path(self):
        """Set up SUMO environment variables"""
        try:
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
                    print(f"✅ SUMO_HOME set to: {sumo_path}")
                    break
            else:
                print("⚠️ SUMO_HOME not found. TraCI functionality will be limited.")
                
        except Exception as e:
            print(f"❌ Error setting SUMO path: {e}")
    
    def _verify_scenario_files(self):
        """Verify that all scenario configuration files exist"""
        for scenario_name, scenario_info in self.available_scenarios.items():
            config_file = scenario_info['config']
            config_path = os.path.join(self.sumo_configs_dir, config_file)
            if not os.path.exists(config_path):
                print(f"⚠️ Scenario file not found: {config_path}")
    
    def start_simulation(self, scenario: str, gui: bool = True) -> Dict[str, Any]:
        """Start high-performance SUMO simulation with TLS data collection"""
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
            
            print(f"🚀 Starting optimized simulation with TLS data and configs: {scenario}")
            
            # Start simulation in separate thread
            self.simulation_thread = threading.Thread(
                target=self._run_simulation_with_context,
                args=(config_path, scenario, gui, self.app),  # Pass app context
                name=f"SUMO-Simulation-{scenario}"
            )
            self.simulation_thread.daemon = True
            self.is_running = True
            self.simulation_thread.start()
            
            # Wait for startup
            # for _ in range(20):  # 2 second timeout
            #     if self.is_running:
            #         break
            #     time.sleep(0.1)
            # else:
            #     return {"success": False, "error": "Simulation failed to start"}
            
            return {
                "success": True,
                "message": f"High-performance simulation started with {scenario}",
                "scenario": scenario,
                "performance_config": self.performance_config,
                "starting": True
            }
            
        except Exception as e:
            self.is_running = False
            return {"success": False, "error": f"Failed to start simulation: {str(e)}"}
        
    def _run_simulation_with_context(self, config_path: str, scenario: str, gui: bool, app):
        """Run simulation with proper app context"""
        # Set app context for this thread
        self.app = app

        # Initialize services with app context
        from app.services.tls_data_service import tls_data_service
        from app.services.ai_traffic_service import ai_traffic_service
        from app.services.db_queue import db_queue_service

        if db_queue_service:
            db_queue_service.app = app
        if tls_data_service:
            tls_data_service.app = app  
        if ai_traffic_service:
            ai_traffic_service.app = app

        # Now run the simulation
        self._run_optimized_simulation(config_path, scenario, gui)    
    
    def _run_optimized_simulation(self, config_path: str, scenario: str, gui: bool):
        """Optimized simulation loop with TLS data and config collection and emergency vehicle registry"""
        
        try:
            import traci
            
            # Build optimized SUMO command
            sumo_binary = 'sumo-gui' if gui else 'sumo'
            sumo_cmd = [
                sumo_binary,
                '-c', config_path,
                '--step-length', '0.1',
                '--delay', '500',
            ]
            
            if not gui:
                sumo_cmd.extend([
                    '--no-warnings',
                    '--no-step-log',
                ])
            
            print(f"🚀 SUMO command: {' '.join(sumo_cmd)}")
            
            # Start TraCI connection
            try:
                traci.start(sumo_cmd)
                self.traci = traci
                print("✅ TraCI connection established")
            except Exception as traci_error:
                print(f"❌ TraCI connection failed: {traci_error}")
                self.is_running = False
                return
        
            # Set running flag - simulation is now fully started
            self.is_running = True
            
            # Initialize services
            from app.services.tls_data_service import tls_data_service
            from app.services.tls_config_service import tls_config_service
            from app.services.emergency import emergency_service

            # Ensure services have app context
            if self.app:
                with self.app.app_context():
                    tls_data_service.init_app(self.app)
                    tls_config_service.init_app(self.app)
                    ai_traffic_service.init_app(self.app)
                    emergency_service.init_app(self.app)

            print("✅ Optimized simulation running...")
            
            # STORE TLS CONFIGURATIONS AT STARTUP
            print("💾 Storing TLS configurations...")
            from app.services.tls_config_service import tls_config_service
            config_results = tls_config_service.store_bulk_tls_configs(traci, scenario)
            print(f"✅ TLS Configs: {config_results['success_count']} stored successfully")
            
            # CREATE EMERGENCY VEHICLE REGISTRY AT STARTUP
            print("🚨 Creating emergency vehicle registry...")
            emergency_service._preload_emergency_schedule_to_db(traci)
            
            # Performance tracking
            last_data_update = 0
            last_tls_update = 0
            last_perf_log = time.time()
            steps_since_print = 0
            
            print("✅ Optimized simulation with TLS data and configs running...")
            
            # AI optimization tracking
            last_ai_optimization = 0
            ai_decision_count = 0
            
            # Main optimized simulation loop
            while self.is_running and self.simulation_step < self.performance_config['max_steps']:
                step_start = time.time()
                
                try:
                    # 1. Simulation step
                    traci.simulationStep()
                    self.simulation_step += 1
                    performance_monitor.record_step()
                    
                    current_time = traci.simulation.getTime()
                    
                    # 2. Minimal basic data collection
                    if (self.simulation_step - last_data_update) >= self.performance_config['data_update_interval']:
                        self._collect_basic_data(traci, current_time)
                        last_data_update = self.simulation_step
                    
                    # 3. TLS DATA COLLECTION
                    if (self.simulation_step - last_tls_update) >= self.performance_config['tls_update_interval']:
                        tls_snapshot = tls_data_service.collect_tls_snapshot(traci, scenario)
                        if tls_snapshot:
                            self.monitoring_data['tls_snapshot'] = tls_snapshot
                            self.monitoring_data['traffic_lights'] = list(tls_snapshot.get('traffic_lights', {}).values())
                        last_tls_update = self.simulation_step
                    
                    # 4. Progress printing
                    steps_since_print += 1
                    if steps_since_print >= self.performance_config['print_interval']:
                        vehicle_count = len(traci.vehicle.getIDList())
                        tl_count = len(self.monitoring_data['tls_snapshot'].get('traffic_lights', {}))
                        print(f"📊 Step {self.simulation_step}: {vehicle_count} vehicles, {tl_count} TLS")
                        steps_since_print = 0
                    
                    # 5. Performance logging
                    current_time_real = time.time()
                    if current_time_real - last_perf_log > 2.0:
                        perf_stats = performance_monitor.get_current_performance()
                        if perf_stats:
                            current_steps_per_sec = perf_stats['steps_per_second']['current']
                            print(f"🎯 Performance: {current_steps_per_sec:.1f} steps/sec")
                        last_perf_log = current_time_real
                    
                    # 6. Adaptive sleep
                    step_duration = current_time_real - step_start
                    sleep_time = self._calculate_adaptive_sleep(step_duration, gui)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                    # 7. AI OPTIMIZATION
                    if (self.ai_optimization_enabled and 
                        (self.simulation_step - last_ai_optimization) >= self.ai_optimization_interval):

                        tls_snapshot = self.monitoring_data.get('tls_snapshot', {})
                        if tls_snapshot:
                            current_time = traci.simulation.getTime()
                            ai_decision = ai_traffic_service.make_traffic_decision(tls_snapshot, current_time)

                            if ai_decision:
                                self.last_ai_decision = ai_decision
                                ai_decision_count += 1

                                # Apply AI decisions to SUMO
                                self._apply_ai_decisions(traci, ai_decision)

                                print(f"🤖 AI Decision #{ai_decision_count}: "
                                      f"{ai_decision['system_decision']['system_action']} - "
                                      f"{ai_decision['total_tls_optimized']} TLS optimized")

                        last_ai_optimization = self.simulation_step
                        
                    # 8. Manage scheduled emergencies (ADD THIS)
                    self._manage_scheduled_emergencies(traci, current_time)
                        
                except Exception as step_error:
                    print(f"⚠️ Step error: {step_error}")
                    continue
                    
        except Exception as e:
            print(f"❌ Simulation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            self._cleanup_simulation()
    
    def get_data_collection_status(self) -> Dict[str, Any]:
        """Get status of data collection"""
        return {
            "is_running": self.is_running,
            "simulation_step": self.simulation_step,
            "tls_data_available": bool(self.monitoring_data.get('tls_snapshot', {})),
            "last_tls_update_step": getattr(self, '_last_tls_update_step', 0),
            "tls_update_interval": self.performance_config['tls_update_interval'],
            "next_tls_update_in": max(0, self.performance_config['tls_update_interval'] - 
                                     (self.simulation_step - getattr(self, '_last_tls_update_step', 0))),
            "traffic_light_count": len(self.monitoring_data.get('tls_snapshot', {}).get('traffic_lights', {})),
            "has_traci": self.traci is not None
        }
    
    # AI FUNCTIONS - START
    # Apply AI optimization decisions to SUMO simulation
    def _apply_ai_decisions(self, traci, ai_decision: Dict):
        """Apply AI decisions and ensure they're stored"""
        try:
            applied_count = 0
            
            # STORE THE DECISION FIRST - WITH PROPER ERROR HANDLING
            decision_stored = False
            try:
                from app.services.ai_traffic_service import ai_traffic_service
                if hasattr(ai_traffic_service, '_store_ai_decision'):
                    ai_traffic_service._store_ai_decision(ai_decision, self.current_config)
                    decision_stored = True
                    print("💾 AI decision stored successfully")
            except Exception as store_error:
                print(f"⚠️ Could not store AI decision: {store_error}")
            
            if not decision_stored:
                print("📝 Fallback: Logging AI decision locally")
                # Fallback storage - log to file or local variable
                self._fallback_store_decision(ai_decision)
            
            # Then apply safe actions
            for decision in ai_decision.get('decisions', []):
                tl_id = decision['traffic_light_id']
                action = decision['action']
                
                try:
                    if action == 'EXTEND_GREEN':
                        current_duration = traci.trafficlight.getPhaseDuration(tl_id)
                        new_duration = current_duration + 5
                        traci.trafficlight.setPhaseDuration(tl_id, new_duration)
                        applied_count += 1
                        print(f"🟢 Extended {tl_id} green phase to {new_duration}s")
                        
                    elif action == 'REDUCE_GREEN':
                        current_duration = traci.trafficlight.getPhaseDuration(tl_id)
                        new_duration = max(10, current_duration - 5)
                        traci.trafficlight.setPhaseDuration(tl_id, new_duration)
                        applied_count += 1
                        print(f"🟡 Reduced {tl_id} green phase to {new_duration}s")
                        
                    elif action == 'MAINTAIN':
                        # Do nothing - this is safe
                        print(f"⏸️  Maintaining {tl_id} current state")
                        applied_count += 1
                        
                    else:
                        print(f"⏭️ Skipped {action} on {tl_id} (unsafe)")
                        
                except Exception as tl_error:
                    print(f"❌ Failed to apply {action} to {tl_id}: {tl_error}")
                    continue
                
            print(f"✅ Applied {applied_count}/{len(ai_decision.get('decisions', []))} AI decisions")
            
        except Exception as e:
            print(f"❌ Error in AI decision application: {e}")

    def _fallback_store_decision(self, ai_decision: Dict):
        """Fallback method to store decisions when primary storage fails"""
        # Store in instance variable
        if not hasattr(self, '_fallback_decisions'):
            self._fallback_decisions = []
        self._fallback_decisions.append(ai_decision)

        # Also log to file for persistence
        try:
            with open('ai_decisions_fallback.log', 'a') as f:
                import json
                from datetime import datetime
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'decision': ai_decision
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"⚠️ Could not write to fallback log: {e}")
    
    def enable_ai_optimization(self):
        """Enable AI optimization"""
        self.ai_optimization_enabled = True
        print("✅ AI optimization enabled")
    
    def disable_ai_optimization(self):
        """Disable AI optimization"""
        self.ai_optimization_enabled = False
        print("✅ AI optimization disabled")
    
    def set_ai_optimization_interval(self, interval: int):
        """Set AI optimization interval (in simulation steps)"""
        self.ai_optimization_interval = max(5, interval)
        print(f"✅ AI optimization interval set to {self.ai_optimization_interval} steps")
        
    def get_ai_status(self) -> Dict[str, Any]:
        """Get AI optimization status"""
        ai_status = ai_traffic_service.get_ai_status()
        ai_status.update({
            'optimization_enabled': self.ai_optimization_enabled,
            'optimization_interval': self.ai_optimization_interval,
            'last_decision': self.last_ai_decision
        })
        return ai_status
    
    # AI FUNCTIONS - END
    
    def _collect_basic_data(self, traci, current_time: float):
        """Collect only essential basic data including emergency vehicles"""
        try:
            # Update basic simulation time
            self.monitoring_data['current_time'] = current_time
            
            # Get vehicle count
            vehicle_ids = traci.vehicle.getIDList()
            vehicle_count = len(vehicle_ids)
            self.monitoring_data['vehicle_count'] = vehicle_count
            
            # Calculate average speed
            if vehicle_count > 0:
                try:
                    speeds = [traci.vehicle.getSpeed(veh_id) for veh_id in vehicle_ids[:5]]
                    avg_speed = sum(speeds) / len(speeds) * 3.6 if speeds else 0
                    self.monitoring_data['average_speed'] = avg_speed
                except:
                    self.monitoring_data['average_speed'] = 0
            
            # SIMPLE EMERGENCY VEHICLE DETECTION AND MANAGEMENT
            self._manage_emergency_vehicles_simple(traci, current_time)
            
            # Update performance stats
            perf_stats = performance_monitor.get_current_performance()
            if perf_stats:
                self.monitoring_data['performance_stats'] = perf_stats
                
        except Exception as e:
            # Silent error for data collection
            pass
    
    def _manage_scheduled_green_waves(self, traci, current_time: float):
        """Manage manually scheduled green waves"""
        try:
            if not hasattr(self, 'emergency_scheduler'):
                from app.services.emergency_scheduler import emergency_scheduler
                self.emergency_scheduler = emergency_scheduler
                self.emergency_scheduler.init_app(self.app)

            # Get pending green waves
            pending_waves = self.emergency_scheduler.get_pending_green_waves(current_time)

            # Activate green waves
            activated_count = 0
            for wave in pending_waves:
                if self._activate_manual_green_wave(traci, wave, current_time):
                    activated_count += 1

            if activated_count > 0:
                print(f"🟢 Activated {activated_count} manual green waves")
                
            # Update monitoring data
            active_emergencies = self.emergency_scheduler.get_active_emergencies()
            active_green_waves = self.emergency_scheduler.get_active_green_waves()

            self.monitoring_data['manual_scheduling'] = {
                'active_emergencies': active_emergencies,
                'active_green_waves': active_green_waves,
                'pending_green_waves': pending_waves,
                'activated_count': activated_count,
                'timestamp': time.time()
            }

        except Exception as e:
            print(f"⚠️ Manual green wave management error: {e}")
    
    def _manage_scheduled_emergencies(self, traci, current_time: float):
        """Manage scheduled emergencies and green waves"""
        try:
            if not hasattr(self, 'emergency_scheduler'):
                from app.services.emergency_scheduler import emergency_scheduler
                self.emergency_scheduler = emergency_scheduler
                self.emergency_scheduler.init_app(self.app)

            # Get pending green waves
            pending_waves = self.emergency_scheduler.get_pending_green_waves(current_time)

            # Activate green waves
            activated_count = 0
            for wave in pending_waves:
                if self._activate_scheduled_green_wave(traci, wave, current_time):
                    activated_count += 1

            if activated_count > 0:
                print(f"🟢 Activated {activated_count} scheduled green waves")

            # Update monitoring data
            active_emergencies = self.emergency_scheduler.get_active_emergencies()
            self.monitoring_data['scheduled_emergencies'] = {
                'active_emergencies': active_emergencies,
                'pending_green_waves': pending_waves,
                'activated_count': activated_count,
                'timestamp': time.time()
            }

        except Exception as e:
            print(f"⚠️ Scheduled emergency management error: {e}")

    def _activate_manual_green_wave(self, traci, green_wave: Dict, current_time: float) -> bool:
        """Activate a manually scheduled green wave"""
        try:
            tl_id = green_wave['traffic_light_id']

            # Get current phase and duration
            current_phase = traci.trafficlight.getPhase(tl_id)
            current_duration = traci.trafficlight.getPhaseDuration(tl_id)

            # Set extended green phase
            new_duration = max(current_duration, green_wave['duration'])
            traci.trafficlight.setPhaseDuration(tl_id, new_duration)

            print(f"🟢 MANUAL GREEN WAVE: {tl_id} extended to {new_duration}s (scheduled)")

            # Update green wave status in database
            self._update_green_wave_status(green_wave['id'], 'ACTIVE', current_time)

            return True

        except Exception as e:
            print(f"❌ Failed to activate manual green wave: {e}")
            return False

    def _update_green_wave_status(self, wave_id: str, status: str, timestamp: float):
        """Update green wave status in database"""
        try:
            if hasattr(self, 'emergency_scheduler') and self.app:
                with self.app.app_context():
                    from app.models.emergency_veh import GreenWaveSchedule
                    wave = GreenWaveSchedule.query.get(wave_id)
                    if wave:
                        wave.status = status
                        if status == 'ACTIVE':
                            wave.activated_at = timestamp
                        db.session.commit()
        except Exception as e:
            print(f"⚠️ Error updating green wave status: {e}")
    
    def _manage_emergency_vehicles_simple(self, traci, current_time: float):
        """Simple emergency vehicle management"""
        try:
            # Initialize emergency service if not already done
            if not hasattr(self, 'emergency_service_initialized'):
                from app.services.emergency import emergency_service
                self.emergency_service = emergency_service
                self.emergency_service.init_app(self.app)

                # SIMPLE INITIALIZATION - just scan current vehicles
                self.emergency_service.initialize_emergency_registry(traci)
                self.emergency_service_initialized = True
                print("🚨 Emergency service initialized (simple approach)")

            # 1. Detect emergency vehicles in real-time
            detected_emergencies = self.emergency_service.detect_emergency_vehicles(traci)

            # 2. Get vehicles that need green waves
            green_wave_candidates = self.emergency_service.get_green_wave_candidates(traci, current_time)

            # 3. Apply green waves for approaching emergencies
            if green_wave_candidates:
                self._apply_simple_green_waves(traci, green_wave_candidates)

            # 4. Store emergency vehicle data
            if detected_emergencies:
                self.emergency_service.store_emergency_data(detected_emergencies, current_time, self.current_config)

            # 5. Update monitoring data
            self.monitoring_data['emergency_vehicles'] = {
                'detected_emergencies': detected_emergencies,
                'green_wave_candidates': green_wave_candidates,
                'active_count': len(detected_emergencies),
                'timestamp': time.time()
            }

        except Exception as e:
            print(f"⚠️ Simple emergency management error: {e}")

    def _apply_simple_green_waves(self, traci, candidates: List[Dict]):
        """Apply simple green waves for emergency vehicles"""
        applied_count = 0

        for candidate in candidates:
            vehicle_id = candidate['vehicle_id']
            tl_id = candidate['traffic_light_id']
            time_to_intersection = candidate['time_to_intersection']

            # Only apply if vehicle is close enough
            if time_to_intersection <= 10.0:  # 10 seconds or less
                try:
                    # Simple approach: extend current green phase
                    current_phase = traci.trafficlight.getPhase(tl_id)
                    current_duration = traci.trafficlight.getPhaseDuration(tl_id)

                    # Extend green phase for emergency
                    new_duration = max(current_duration, 15.0)  # At least 15 seconds
                    traci.trafficlight.setPhaseDuration(tl_id, new_duration)

                    applied_count += 1
                    print(f"🟢 GREEN WAVE: Extended {tl_id} to {new_duration}s for {vehicle_id}")

                except Exception as e:
                    print(f"❌ Failed to apply green wave for {vehicle_id}: {e}")

        if applied_count > 0:
            self.emergency_service.stats['green_waves_activated'] += applied_count
            print(f"✅ Applied {applied_count} green waves for emergencies")
    
    def _calculate_adaptive_sleep(self, step_duration: float, gui: bool) -> float:
        """Calculate optimal sleep time for target performance"""
        if gui:
            target_step_time = 0.1  # ~10 FPS for GUI
            sleep_time = max(0.001, target_step_time - step_duration)
            return min(sleep_time, self.performance_config['gui_sleep_time'])
        else:
            # Headless - minimal sleep, focus on max performance
            return self.performance_config['min_sleep_time']
    
    def _cleanup_simulation(self):
        """Cleanup simulation resources"""
        try:
            if self.traci and hasattr(self.traci, 'close'):
                self.traci.close()
                print("✅ TraCI connection closed")
        except:
            pass
        
        # Final database flush
        if db_queue_service:
            db_queue_service.flush_queue()
            print("✅ Final database flush completed")
        
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
            'tls_snapshot': {},  # Initialize empty TLS snapshot
            'performance_stats': {}
        }
        self.simulation_step = 0
    
    def stop_simulation(self) -> Dict[str, Any]:
        """Stop the simulation gracefully"""
        if not self.is_running:
            return {"success": False, "error": "No simulation running"}
        
        print("🛑 Stopping simulation...")
        self.is_running = False
        
        # Wait for thread to finish
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=5.0)
            print("✅ Simulation thread stopped")
        
        return {"success": True, "message": "Simulation stopped successfully"}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status"""
        return {
            "is_running": self.is_running,
            "current_scenario": self.current_config,
            "simulation_step": self.simulation_step,
            "performance_config": self.performance_config
        }
    
    def get_simulation_data(self) -> Dict[str, Any]:
        """Get current simulation data for API - INCLUDES TLS DATA"""
        return {
            "monitoring": self.monitoring_data,
            "performance": performance_monitor.get_current_performance(),
            "db_queue": db_queue_service.get_stats() if db_queue_service else {},
            "is_running": self.is_running,
            "current_step": self.simulation_step,
            "tls_data_available": bool(self.monitoring_data.get('tls_snapshot', {}))
        }
        
    def get_tls_data(self) -> Dict[str, Any]:
        """Get TLS-specific data"""
        tls_snapshot = self.monitoring_data.get('tls_snapshot', {})
        return {
            "tls_snapshot": tls_snapshot,
            "traffic_light_count": len(tls_snapshot.get('traffic_lights', {})),
            "summary": tls_snapshot.get('summary', {}),
            "timestamp": tls_snapshot.get('timestamp', 0)
        }
    
    def get_available_scenarios(self) -> Dict[str, Any]:
        """Return available SUMO scenarios with verification"""
        try:
            verified_scenarios = {}

            for scenario_name, scenario_info in self.available_scenarios.items():
                config_file = scenario_info['config']
                config_path = os.path.join(self.sumo_configs_dir, config_file)

                # Check if the scenario file actually exists
                if os.path.exists(config_path):
                    verified_scenarios[scenario_name] = scenario_info
                    print(f"✅ Scenario verified: {scenario_name} -> {config_path}")
                else:
                    print(f"❌ Scenario file missing: {scenario_name} -> {config_path}")
                    # You might want to include it anyway or handle differently
                    verified_scenarios[scenario_name] = {
                        **scenario_info,
                        'file_exists': False,
                        'error': f"Config file not found: {config_path}"
                    }

            print(f"📊 Returning {len(verified_scenarios)} verified scenarios")
            return verified_scenarios

        except Exception as e:
            print(f"❌ Error in get_available_scenarios: {e}")
            return {}
    
    def check_sumo_availability(self) -> Dict[str, Any]:
        """Check if SUMO is properly installed and available"""
        try:
            result = subprocess.run(['sumo', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
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
        
    def get_tls_configs(self, scenario: str = None) -> Dict[str, Any]:
        """Get TLS configurations for current or specified scenario"""
        target_scenario = scenario or self.current_config
        if not target_scenario:
            return {"error": "No scenario specified and no current simulation"}
        
        configs = tls_config_service.get_all_configs_for_scenario(target_scenario)
        return {
            "scenario": target_scenario,
            "config_count": len(configs),
            "configs": configs
        }

# Global instance
optimized_sumo_service = OptimizedSumoService()

def init_optimized_sumo_service(app):
    """Initialize optimized SUMO service with app context"""
    optimized_sumo_service.app = app