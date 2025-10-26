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
            self.simulation_thread.start()
            
            # Wait for startup
            for _ in range(20):  # 2 second timeout
                if self.is_running:
                    break
                time.sleep(0.1)
            else:
                return {"success": False, "error": "Simulation failed to start"}
            
            return {
                "success": True,
                "message": f"High-performance simulation started with {scenario}",
                "scenario": scenario,
                "performance_config": self.performance_config
            }
            
        except Exception as e:
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
        """Optimized simulation loop with TLS data and config collection"""
        
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
            traci.start(sumo_cmd)
            self.traci = traci
            self.is_running = True
            
            from app.services.tls_data_service import tls_data_service
            from app.services.tls_config_service import tls_config_service

            # Ensure services have app context
            if self.app:
                tls_data_service.app = self.app
                tls_config_service.app = self.app
                ai_traffic_service.app = self.app

            print("✅ Optimized simulation running...")
            
            # STORE TLS CONFIGURATIONS AT STARTUP
            print("💾 Storing TLS configurations...")
            from app.services.tls_config_service import tls_config_service
            config_results = tls_config_service.store_bulk_tls_configs(traci, scenario)
            print(f"✅ TLS Configs: {config_results['success_count']} stored successfully")
            
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
    
    # AI FUNCTIONS - START
    # Apply AI optimization decisions to SUMO simulation
    # def _apply_ai_decisions(self, traci, ai_decision: Dict):
    #     """Apply AI optimization decisions to SUMO - SAFE VERSION"""
    #     try:
    #         applied_count = 0
            
    #         # STORE THE DECISION FIRST (this was missing!)
    #         from app.services.ai_traffic_service import ai_traffic_service
    #         if hasattr(ai_traffic_service, '_store_ai_decision'):
    #             ai_traffic_service._store_ai_decision(ai_decision, self.current_config)

    #         for decision in ai_decision.get('decisions', []):
    #             tl_id = decision['traffic_light_id']
    #             action = decision['action']

    #             try:
    #                 if action == 'EXTEND_GREEN':
    #                     # Safe: Extend current green phase
    #                     current_duration = traci.trafficlight.getPhaseDuration(tl_id)
    #                     new_duration = current_duration + 5  # Fixed 5-second extension
    #                     traci.trafficlight.setPhaseDuration(tl_id, new_duration)
    #                     applied_count += 1
    #                     print(f"🟢 Extended {tl_id} green phase to {new_duration}s")

    #                 elif action == 'REDUCE_GREEN':
    #                     # Safe: Reduce current green phase
    #                     current_duration = traci.trafficlight.getPhaseDuration(tl_id)
    #                     new_duration = max(10, current_duration - 5)  # Minimum 10 seconds
    #                     traci.trafficlight.setPhaseDuration(tl_id, new_duration)
    #                     applied_count += 1
    #                     print(f"🟡 Reduced {tl_id} green phase to {new_duration}s")

    #                 elif action == 'SKIP_PHASE':
    #                     # ⚠️ DANGEROUS - Disable for now
    #                     print(f"⏭️ SKIP_PHASE disabled for {tl_id} (unsafe)")
    #                     continue

    #                 elif action == 'ADJUST_CYCLE':
    #                     # ⚠️ COMPLEX - Disable for now  
    #                     print(f"🔄 ADJUST_CYCLE disabled for {tl_id} (complex)")
    #                     continue

    #                 elif action == 'MAINTAIN':
    #                     # Do nothing - this is safe
    #                     print(f"⏸️  Maintaining {tl_id} current state")
    #                     applied_count += 1

    #             except Exception as tl_error:
    #                 print(f"❌ Failed to apply {action} to {tl_id}: {tl_error}")
    #                 continue
                
    #         print(f"✅ Applied {applied_count}/{len(ai_decision.get('decisions', []))} AI decisions")
        
    #     except Exception as e:
    #         print(f"❌ Error applying AI decisions: {e}")
    
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
        """Collect only essential basic data"""
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
                    speeds = [traci.vehicle.getSpeed(veh_id) for veh_id in vehicle_ids[:5]]  # Sample 5 vehicles
                    avg_speed = sum(speeds) / len(speeds) * 3.6 if speeds else 0
                    self.monitoring_data['average_speed'] = avg_speed
                except:
                    self.monitoring_data['average_speed'] = 0
            
            # Update performance stats
            perf_stats = performance_monitor.get_current_performance()
            if perf_stats:
                self.monitoring_data['performance_stats'] = perf_stats
                
        except Exception as e:
            # Silent error for data collection
            pass
    
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
        """Return available SUMO scenarios"""
        return self.available_scenarios
    
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