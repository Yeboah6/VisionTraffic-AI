import threading
import time
import os
import sys
import subprocess
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.extensions import db

# Services
from app.services.db_queue import db_queue_service
from app.services.performance_monitor import performance_monitor
from app.services.tls_data_service import tls_data_service
from app.services.tls_config_service import tls_config_service
from app.services.traffic_pattern_analyzer import traffic_pattern_analyzer
from app.services.q_learning import simple_ai_optimizer

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
        # self.ai_optimization_enabled = False
        # self.last_ai_decision = None
        # self.ai_optimization_interval = 0  # Apply AI every 30 steps
        # self.last_ai_decision = None
        self._last_tls_update_step = 0  # Track last update
        
        self.ai_enabled = False
        self.background_learning_enabled = True  # Always learn in background
        self.ai_decisions = []
        self.learning_queue = []
        self.ai_optimization_interval = 30
        
        # Performance optimization settings
        self.performance_config = {
            'data_update_interval': 10,          # Update data every 10 steps
            'tls_update_interval': 20,           # Update TL every 20 steps  
            'min_sleep_time': 0.001,             # Minimum sleep for headless
            'gui_sleep_time': 0.01,              # Sleep for GUI mode
            'max_steps': 100000,                 # Safety limit
            'print_interval': 100                # Print progress every 100 steps
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
            'accra': {
                'config': 'accra_37.sumocfg',
                'name': 'Highway Simulation',
                'description': 'Multi-lane highway with merging',
                'complexity': 'Advanced'
            },
            'carprice': {
                'config': 'carprice.sumocfg',
                'name': 'Caprice Scenario',
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
        from app.services.db_queue import db_queue_service

        if db_queue_service:
            db_queue_service.app = app
        if tls_data_service:
            tls_data_service.app = app

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

            # Ensure services have app context
            if self.app:
                with self.app.app_context():
                    traffic_pattern_analyzer.init_app(self.app)
                    tls_data_service.init_app(self.app)
                    tls_config_service.init_app(self.app)

            print("✅ Optimized simulation running...")
            
            self.ai_optimization_enabled = False
            print("🚫 AI optimization DISABLED for maximum performance")
            
            # Enable automatic pattern analysis
            traffic_pattern_analyzer.auto_analysis_enabled = False
            traffic_pattern_analyzer.stop_auto_analysis()
            print("✅ Automatic pattern analysis ENABLED - will run every 15 simulation minutes")
            
            # STORE TLS CONFIGURATIONS AT STARTUP
            print("💾 Storing TLS configurations...")
            from app.services.tls_config_service import tls_config_service
            config_results = tls_config_service.store_bulk_tls_configs(traci, scenario)
            print(f"✅ TLS Configs: {config_results['success_count']} stored successfully")
            
            # CREATE EMERGENCY VEHICLE REGISTRY AT STARTUP
            print("🚨 Creating emergency vehicle registry...")
            
            # Performance tracking
            last_data_update = 0
            last_tls_update = 0
            last_perf_log = time.time()
            steps_since_print = 0
            
            print("✅ Optimized simulation with TLS data and configs running...")
            
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
                        
                    # 4. AI LEARNING (always in background)
                    if self.simulation_step % self.ai_optimization_interval == 0:
                        self._process_ai_learning(traci, current_time, scenario)
                    
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

    def enable_ai(self):
        """Enable AI optimization (applies decisions)"""
        self.ai_enabled = True
        print("🤖 AI optimization ENABLED - will apply decisions")

    def disable_ai(self):
        """Disable AI optimization (still learns in background)"""
        self.ai_enabled = False
        print("🤖 AI optimization DISABLED (background learning continues)")

    def get_ai_status(self) -> Dict[str, Any]:
        """Get comprehensive AI status"""
        optimizer_status = simple_ai_optimizer.get_status()

        return {
            'ai_enabled': self.ai_enabled,
            'background_learning': self.background_learning_enabled,
            'simulation_running': self.is_running,
            'simulation_step': self.simulation_step,
            'decisions_made': optimizer_status['decisions_made'],
            'episodes_learned': optimizer_status['episodes_learned'],
            'states_learned': optimizer_status['states_learned'],
            'success_rate': optimizer_status['success_rate'],
            'ai_optimization_interval': self.ai_optimization_interval,
            'last_recommendations': self.ai_decisions[-5:] if self.ai_decisions else [],
            'learning_queue_size': len(self.learning_queue)
        }

    def _process_ai_learning(self, traci, current_time: float, scenario: str):
        """Process AI learning from current traffic data"""
        if not self.is_running or not self.background_learning_enabled:
            return

        try:
            # Get TLS snapshot for learning
            tls_snapshot = self.monitoring_data.get('tls_snapshot', {})
            traffic_lights = tls_snapshot.get('traffic_lights', {})

            if not traffic_lights:
                return

            # Process each traffic light for learning
            for tl_id, tl_data in traffic_lights.items():
                # Prepare data for AI
                ai_tl_data = {
                    'id': tl_id,
                    'phase_name': tl_data.get('current_phase', 'green'),
                    'performance': {
                        'waiting_vehicles': tl_data.get('waiting_count', 0),
                        'total_vehicles': tl_data.get('vehicles_passed', 0),
                        'efficiency_score': tl_data.get('efficiency', 50)
                    }
                }

                # Get AI decision (for learning even if not applying)
                decision = simple_ai_optimizer.get_decision(
                    ai_tl_data, 
                    scenario, 
                    current_time
                )

                # Store for later application if AI is enabled
                if self.ai_enabled:
                    self.ai_decisions.append(decision)

                    # Apply decision if it's time
                    if len(self.ai_decisions) % self.ai_optimization_interval == 0:
                        self._apply_ai_decision(decision, traci)

        except Exception as e:
            print(f"⚠️ AI learning error: {e}")

    def _apply_ai_decision(self, decision: Dict, traci):
        """Apply AI decision to simulation"""
        try:
            tl_id = decision['tl_id']
            action = decision['action']
            params = decision['parameters']

            if action == 'EXTEND_GREEN':
                # Get current phase duration and extend
                current_duration = traci.trafficlight.getPhaseDuration(tl_id)
                new_duration = current_duration + params['duration_change']
                traci.trafficlight.setPhaseDuration(tl_id, new_duration)
                print(f"🤖 Extended {tl_id} green by {params['duration_change']}s")

            elif action == 'REDUCE_GREEN':
                current_duration = traci.trafficlight.getPhaseDuration(tl_id)
                new_duration = max(
                    params['min_duration'], 
                    current_duration + params['duration_change']
                )
                traci.trafficlight.setPhaseDuration(tl_id, new_duration)
                print(f"🤖 Reduced {tl_id} green by {-params['duration_change']}s")

            # MAINTAIN action requires no changes

            # Log the applied decision
            if hasattr(self, 'app') and self.app:
                with self.app.app_context():
                    from app.models.ai import AI_Decision
                    from datetime import datetime
                    import uuid

                    ai_decision = AI_Decision(
                        id=str(uuid.uuid4()),
                        traffic_light_id=tl_id,
                        decision_type=action,
                        decision_parameters=params,
                        confidence_score=decision['confidence'],
                        q_value=decision.get('q_value', 0),
                        state_key=decision.get('state', ''),
                        applied_at=datetime.utcnow(),
                        simulation_step=self.simulation_step,
                        scenario=self.current_config,
                        reasoning=decision.get('reasoning', '')
                    )

                    db.session.add(ai_decision)
                    db.session.commit()

        except Exception as e:
            print(f"⚠️ Failed to apply AI decision: {e}")
    
    def get_pattern_analysis_status(self) -> Dict[str, Any]:
        """Get status of automatic pattern analysis"""
        if hasattr(self, 'traci') and self.traci:
            current_time = self.traci.simulation.getTime()
            schedule = traffic_pattern_analyzer.get_analysis_schedule(current_time)
            
            return {
                "auto_analysis_enabled": traffic_pattern_analyzer.auto_analysis_enabled,
                "analysis_interval": schedule["analysis_interval"],
                "current_simulation_time": current_time,
                "next_analysis_time": schedule["next_analysis_time"],
                "time_until_next_analysis": schedule["time_until_next_analysis"],
                "last_analysis_time": schedule["last_analysis_time"],
                "analysis_history_count": schedule["analysis_history_count"],
                "last_analysis_result": self.monitoring_data.get('last_pattern_analysis')
            }
        else:
            return {"error": "No active simulation"}
    
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
            "has_traci": self.traci is not None,
            "operation_mode": "DATA_COLLECTION_ONLY",
            "ai_optimization_enabled": False
        }
    
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