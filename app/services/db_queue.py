import threading
import time
from collections import deque
from datetime import datetime
from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig
from app.models.ai import AIQTable, AIDecisionLog, AIPerformance
import json

class DatabaseQueueService:
    """
    High-performance async database operations - Prevents database I/O from blocking simulation
    """
    
    def __init__(self, app, max_queue_size=1000, flush_interval=5):
        self.app = app
        self.queue = deque(maxlen=max_queue_size)
        self.flush_interval = flush_interval  # seconds
        self.last_flush = time.time()
        self.is_processing = False
        self.stats = {
            'operations_queued': 0,
            'operations_processed': 0,
            'last_flush_size': 0,
            'average_flush_time': 0
        }
        
        # Start background flusher
        self._start_background_flusher()
    
    def _start_background_flusher(self):
        """Start background thread for periodic flushing"""
        def flusher():
            while True:
                time.sleep(self.flush_interval)
                if self.queue:
                    self.flush_queue()
        
        thread = threading.Thread(target=flusher, daemon=True)
        thread.start()
    
    def add_traffic_light_log(self, log_data):
        """Queue traffic light log for async writing"""
        print(f"📝 Adding TLS log to queue: {log_data.get('traffic_light_id')}")
        
        operation = {
            'type': 'traffic_light_log',
            'data': log_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1
        
        print(f"📊 Queue size: {len(self.queue)}")
        
        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:  # Reduced threshold for testing
            print("🔄 Auto-flushing queue...")
            self.flush_queue()
    
    def flush_queue(self):
        """Flush all queued operations to database with foreign key handling"""
        if not self.queue or not self.app:
            return
            
        start_time = time.time()
        self.is_processing = True
        
        try:
            with self.app.app_context():
                operations = list(self.queue)
                traffic_light_logs = []
                ai_decision_logs = []
                q_table_updates = []
                
                processed_count = 0
                error_count = 0
                
                # First, ensure all referenced configs exist
                # self._ensure_configs_exist(operations)
                
                for op in operations:
                    try:
                        if op['type'] == 'traffic_light_log':
                            log_data = op['data']
                            
                            # Get the config ID
                            # config_id = self._get_config_id(
                            #     log_data['traffic_light_id'],
                            #     log_data['scenario']
                            # )
                            
                            # Create the log with config_id
                            log_entry = TrafficLightLog(
                                traffic_light_id=log_data['traffic_light_id'],
                                scenario=log_data['scenario'],
                                simulation_time=log_data.get('simulation_time', 0),
                                state=log_data.get('state', ''),
                                phase=log_data.get('phase', 0),
                                phase_name=log_data.get('phase_name', 'UNKNOWN'),
                                duration=log_data.get('duration', 0),
                                next_switch=log_data.get('next_switch', 0),
                                vehicle_count=log_data.get('vehicle_count', 0),
                                waiting_vehicles=log_data.get('waiting_vehicles', 0),
                                efficiency_score=log_data.get('efficiency_score', 0),
                                performance_grade=log_data.get('performance_grade', 'D'),
                                created_at=log_data.get('created_at', datetime.utcnow())
                            )
                            
                            traffic_light_logs.append(log_entry)
                            processed_count += 1
                            
                        elif op['type'] == 'ai_decision_log':
                            # Handle AI decision logs
                            decision_data = op['data']
                            
                            from app.models.ai import AIDecisionLog
                            log_entry = AIDecisionLog(
                                decision_id=decision_data.get('decision_id', f"decision_{int(time.time())}"),
                                scenario=decision_data.get('scenario'),
                                timestamp=decision_data.get('timestamp', 0),
                                ai_mode=decision_data.get('ai_mode', 'BALANCED'),
                                exploration_rate=decision_data.get('exploration_rate', 0.2),
                                learning_enabled=decision_data.get('learning_enabled', True),
                                system_action=decision_data.get('system_action', 'MAINTAIN'),
                                system_recommendation=decision_data.get('system_recommendation', ''),
                                optimization_ratio=decision_data.get('optimization_ratio', 0),
                                overall_congestion=decision_data.get('overall_congestion', 0),
                                system_health=decision_data.get('system_health', 1.0),
                                total_tls_optimized=decision_data.get('total_tls_optimized', 0),
                                total_decisions=decision_data.get('total_decisions', 0),
                                avg_confidence=decision_data.get('avg_confidence', 0),
                                total_reward=decision_data.get('total_reward', 0),
                                created_at=decision_data.get('created_at', datetime.utcnow())
                            )
                            
                            # Handle TLS decisions JSON
                            tls_decisions = decision_data.get('tls_decisions', [])
                            if isinstance(tls_decisions, list):
                                log_entry.set_tls_decisions(tls_decisions)
                            else:
                                log_entry.tls_decisions = json.dumps([])
                            
                            ai_decision_logs.append(log_entry)
                            processed_count += 1
                            
                        elif op['type'] == 'q_table_update':
                            # Handle Q-table updates
                            q_data = op['data']
                            # config_id = self._get_config_id(
                            #     q_data['traffic_light_id'],
                            #     q_data['scenario']
                            # )
                            
                            from app.models.ai import AIQTable
                            q_entry = AIQTable(
                                traffic_light_id=q_data['traffic_light_id'],
                                scenario=q_data.get('scenario', 'current'),  # Ensure scenario is provided
                                state=q_data['state'],
                                action=q_data['action'],
                                q_value=q_data.get('q_value', 0),
                                visit_count=q_data.get('visit_count', 0),
                                last_reward=q_data.get('last_reward', 0),
                                success_rate=q_data.get('success_rate', 0),
                                avg_reward=q_data.get('avg_reward', 0)
                            )
                            
                            q_table_updates.append(q_entry)
                            processed_count += 1
                            
                    except Exception as op_error:
                        print(f"❌ Error processing operation: {op_error}")
                        error_count += 1
                        continue
                
                # Bulk insert traffic light logs
                if traffic_light_logs:
                    try:
                        db.session.bulk_save_objects(traffic_light_logs)
                        print(f"✅ Saved {len(traffic_light_logs)} TLS logs")
                    except Exception as e:
                        print(f"❌ Error saving TLS logs: {e}")
                        error_count += len(traffic_light_logs)
                
                # Bulk insert AI decision logs
                if ai_decision_logs:
                    try:
                        db.session.bulk_save_objects(ai_decision_logs)
                        print(f"✅ Saved {len(ai_decision_logs)} AI decision logs")
                    except Exception as e:
                        print(f"❌ Error saving AI decision logs: {e}")
                        error_count += len(ai_decision_logs)
                
                # Handle Q-table updates (upsert logic)
                if q_table_updates:
                    successful_q_updates = 0
                    for q_update in q_table_updates:
                        try:
                            # Use no_autoflush to prevent premature flushes
                            with db.session.no_autoflush:
                                existing = AIQTable.query.filter_by(
                                    traffic_light_id=q_update.traffic_light_id,
                                    scenario=q_update.scenario,
                                    state=q_update.state,
                                    action=q_update.action
                                ).first()

                                if existing:
                                    existing.q_value = q_update.q_value
                                    existing.visit_count = q_update.visit_count
                                    existing.last_reward = q_update.last_reward
                                    existing.success_rate = q_update.success_rate
                                    existing.avg_reward = q_update.avg_reward
                                    existing.updated_at = datetime.utcnow()
                                else:
                                    db.session.add(q_update)

                                successful_q_updates += 1
                        except Exception as e:
                            print(f"❌ Error processing Q-table update: {e}")
                            error_count += 1
                
                # Commit all changes
                db.session.commit()
                
                # Update statistics
                successful_operations = processed_count - error_count
                self.stats['operations_processed'] += successful_operations
                self.stats['last_flush_size'] = successful_operations
                self.stats['average_flush_time'] = time.time() - start_time
                
                print(f"✅ DB Queue: Successfully flushed {successful_operations} operations "
                      f"({error_count} errors) in {time.time() - start_time:.2f}s")
                
                # Clear processed operations
                self.queue.clear()
                
        except Exception as e:
            print(f"❌ DB Queue Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            
        finally:
            self.is_processing = False
            self.last_flush = time.time()
    
    def _ensure_configs_exist(self, operations):
        """Ensure TrafficLightConfig records exist for foreign key references"""
        configs_to_create = set()
        
        # Collect all unique (traffic_light_id, scenario) pairs
        for op in operations:
            data = op['data']
            if op['type'] == 'traffic_light_log':
                configs_to_create.add((data['traffic_light_id'], data['scenario']))
            elif op['type'] == 'ai_decision_log':
                # Only scenario needed for ai_decision_logs
                configs_to_create.add(('system', data['scenario']))
            elif op['type'] == 'q_table_update':
                configs_to_create.add((data['traffic_light_id'], data['scenario']))
        
        # Create missing configs
        for tl_id, scenario in configs_to_create:
            existing = TrafficLightConfig.query.filter_by(
                traffic_light_id=tl_id,
                scenario=scenario
            ).first()
            
            if not existing:
                # Create a minimal config
                new_config = TrafficLightConfig(
                    traffic_light_id=tl_id,
                    scenario=scenario,
                    program_id='auto_created',
                    phases=json.dumps([]),
                    config_type='AUTO_CREATED'
                )
                db.session.add(new_config)
        
        db.session.commit()
    
    def get_stats(self):
        """Get queue performance statistics"""
        return {
            **self.stats,
            'current_queue_size': len(self.queue),
            'time_since_last_flush': time.time() - self.last_flush,
            'is_processing': self.is_processing,
            'config_cache_size': len(self.config_cache),
            'scenario_cache_size': len(self.scenario_cache)
        }
        
    def add_ai_decision_log(self, decision_data):
        """Queue AI decision log for async writing - CORRECTED"""
        operation = {
            'type': 'ai_decision_log',
            'data': decision_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        print(f"📝 Added AI decision to queue: {decision_data.get('system_action', 'Unknown')}")

        # Auto-flush if queue is large
        if len(self.queue) >= 100:
            self.flush_queue()
            
    def add_q_table_update(self, q_table_data):
        """Queue Q-table update for async writing"""
        operation = {
            'type': 'q_table_update', 
            'data': q_table_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1
    
    def add_q_table_update(self, q_table_data):
        """Queue Q-table update for async writing - FIXED VERSION"""
        # Ensure scenario is provided
        if 'scenario' not in q_table_data or not q_table_data['scenario']:
            q_table_data['scenario'] = 'current'  # Default scenario
        
        operation = {
            'type': 'q_table_update',
            'data': q_table_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1
        
        # Auto-flush if queue is getting large
        if len(self.queue) >= 100:
            print("🔄 Auto-flushing queue...")
            self.flush_queue()
            
    def get_db_queue():
        """Get DB queue with thread-safe app context"""
        global db_queue_service
        if db_queue_service and db_queue_service.app:
            return db_queue_service
        
        # Try to get app from current context or create new context
        try:
            from flask import current_app
            if current_app:
                init_db_queue(current_app._get_current_object())
                return db_queue_service
        except:
            pass
        
        return None
    
    def add_ai_decision_safe(decision_data):
        """Thread-safe method to add AI decisions - STANDALONE FUNCTION"""
        queue = get_db_queue()
        if queue:
            queue.add_ai_decision_log(decision_data)  # Call instance method
            return True
        else:
            # Fallback: Print decision for debugging
            action = decision_data.get('system_action', 'Unknown')
            print(f"🤖 AI DECISION (QUEUE UNAVAILABLE): {action}")
            return False

# Global instance
db_queue_service = None

def init_db_queue(app):
    global db_queue_service
    db_queue_service = DatabaseQueueService(app)
    
def get_db_queue():
    return db_queue_service