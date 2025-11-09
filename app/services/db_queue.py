import random
import threading
import time
from collections import deque
from datetime import datetime
from app.extensions import db
import json
from sqlalchemy import and_
from typing import Dict
import uuid

# Import models
from app.models.traffic_light import TrafficLightLog, TrafficPattern
from app.models.ai import AIQTable, AIDecisionLog
from app.models.emergency_veh import EmergencyVehicleLog

class DatabaseQueueService:
    """
    High-performance async database operations for traffic logs and patterns
    """
    
    def __init__(self, max_queue_size=1000, flush_interval=5):
        self.app = None
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
        
        # AI-specific queues for better organization
        self.ai_decision_queue = deque(maxlen=500)
        self.q_table_queue = deque(maxlen=1000)
        self.traffic_pattern_queue = deque(maxlen=500)
        self.performance_metric_queue = deque(maxlen=300)
        
        # Start background flusher
        self._start_background_flusher()
    
    def init_app(self, app):
        self.app = app
        print("✅ DB Queue Service initialized")
    
    def _start_background_flusher(self):
        """Start background thread for periodic flushing"""
        def flusher():
            while True:
                time.sleep(self.flush_interval)
                if self.queue:
                    self.flush_queue()
        
        thread = threading.Thread(target=flusher, daemon=True)
        thread.start()
    
    # Traffic Log
    def add_traffic_light_log(self, log_data: Dict):
        """Queue traffic light log for async writing"""
        operation = {
            'type': 'traffic_light_log',
            'data': log_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # Traffic Pattern
    def add_traffic_pattern(self, pattern_data: Dict):
        """Queue traffic pattern for async writing"""
        operation = {
            'type': 'traffic_pattern',
            'data': pattern_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # AI Decision Log
    def add_ai_decision_log(self, decision_data: Dict):
        """Queue AI decision log for async writing"""
        operation = {
            'type': 'ai_decision_log',
            'data': decision_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # Q-Table Entry
    def add_q_table_entry(self, q_table_data: Dict):
        """Queue Q-table entry for async writing"""
        operation = {
            'type': 'ai_q_table',
            'data': q_table_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # Performance Metric
    def add_performance_metric(self, performance_data: Dict):
        """Queue AI performance metric for async writing"""
        operation = {
            'type': 'ai_performance_metric',
            'data': performance_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # AI Training Log        
    def add_ai_training_log(self, training_data: Dict):
        """Queue AI training log for async writing"""
        operation = {
            'type': 'ai_training_log',
            'data': training_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # Emergency Vehicle Log
    def add_emergency_log(self, emergency_data: Dict):
        """Queue emergency vehicle log for async writing"""
        operation = {
            'type': 'emergency_log',
            'data': emergency_data,
            'timestamp': datetime.utcnow()
        }
        self.queue.append(operation)
        self.stats['operations_queued'] += 1

        # Auto-flush if queue is getting large
        if len(self.queue) >= 50:
            self.flush_queue()
    
    # Emergency Vehicls Schedule
    # def add_emergency_schedule(self, emergency_schedule_data: Dict):
    #     """Queue emergency vehicle schedule for async writing"""
    #     operation = {
    #         'type': 'emergency_schedule',
    #         'data': emergency_schedule_data,
    #         'timestamp': datetime.utcnow()
    #     }
    #     self.queue.append(operation)
    #     self.stats['operations_queued'] += 1

    #     # Auto-flush if queue is getting large
    #     if len(self.queue) >= 50:
    #         self.flush_queue()
    
    def flush_queue(self):
        """Flush all queued operations to database"""
        if not self.queue or not self.app:
            print("🟡 flush_queue: No queue items or app context")
            return

        start_time = time.time()
        self.is_processing = True

        try:
            with self.app.app_context():
                
                # Ensure we start with a clean session state
                db.session.rollback()
                
                operations = list(self.queue)
                print(f"🔍 flush_queue: Processing {len(operations)} operations")

                traffic_light_logs = []
                traffic_patterns = []
                ai_decision_logs = []
                ai_q_tables = []
                emergency_logs = []
                ai_performance_metrics = []
                ai_training_logs = []

                processed_count = 0
                error_count = 0

                for i, op in enumerate(operations):
                    try:
                        print(f"🔍 Operation {i}: {op['type']} for {op['data'].get('traffic_light_id', 'unknown')}")

                        if op['type'] == 'traffic_light_log':
                            log_data = op['data']

                            log_entry = TrafficLightLog(
                                id=log_data.get('id', str(uuid.uuid4())),
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
                            print(f"✅ Created log entry for {log_data['traffic_light_id']}")

                        elif op['type'] == 'traffic_pattern':
                            pattern_data = op['data']

                            pattern_entry = TrafficPattern(
                                id=pattern_data.get('id', str(uuid.uuid4())),
                                traffic_light_id=pattern_data['traffic_light_id'],
                                scenario=pattern_data.get('scenario'),
                                interval_start=pattern_data.get('interval_start', datetime.utcnow()),
                                interval_end=pattern_data.get('interval_end', datetime.utcnow()),
                                pattern_type=pattern_data.get('pattern_type', 'UNKNOWN'),
                                pattern_metrics=pattern_data.get('pattern_metrics', {}),
                                phase_patterns=pattern_data.get('phase_patterns', {}),
                                confidence_score=pattern_data.get('confidence_score', 0),
                                recommendations=pattern_data.get('recommendations', []),
                                created_at=datetime.utcnow()
                            )

                            traffic_patterns.append(pattern_entry)
                            processed_count += 1
                            print(f"✅ Created pattern entry for {pattern_data['traffic_light_id']}")

                        elif op['type'] == 'ai_decision_log':
                            decision_data = op['data']
                            
                            # Convert timestamp to float if it's a datetime object
                            timestamp = decision_data.get('timestamp')
                            if isinstance(timestamp, datetime):
                                timestamp = timestamp.timestamp()
                            elif timestamp is None:
                                timestamp = time.time()
                                
                            # Ensure tls_decisions is properly serialized
                            tls_decisions = decision_data.get('tls_decisions', '[]')
                            if isinstance(tls_decisions, (list, dict)):
                                tls_decisions = json.dumps(tls_decisions, default=self._json_serializer)

                            decision_entry = AIDecisionLog(
                                id=decision_data.get('id', str(uuid.uuid4())),
                                decision_id=decision_data['decision_id'],
                                scenario=decision_data.get('scenario', 'default'),
                                timestamp=timestamp,
                                ai_mode=decision_data.get('ai_mode', 'BALANCED'),
                                system_action=decision_data.get('system_action', 'MAINTAIN'),
                                system_recommendation=decision_data.get('system_recommendation', ''),
                                optimization_ratio=decision_data.get('optimization_ratio', 0),
                                overall_congestion=decision_data.get('overall_congestion', 0),
                                system_health=decision_data.get('system_health', 0),
                                total_decisions=decision_data.get('total_decisions', 0),
                                total_tls_optimized=decision_data.get('total_tls_optimized', 0),
                                tls_decisions=decision_data.get('tls_decisions', '[]'),
                                created_at=decision_data.get('created_at', datetime.utcnow())
                            )

                            ai_decision_logs.append(decision_entry)
                            processed_count += 1
                            print(f"✅ Created AI decision log for scenario {decision_data.get('scenario', 'default')}")

                        elif op['type'] == 'ai_q_table':
                            q_data = op['data']

                            try:
                                # Individual transaction for each Q-table update
                                existing_entry = AIQTable.query.filter_by(
                                    traffic_light_id=q_data['traffic_light_id'],
                                    scenario=q_data.get('scenario', 'default'),
                                    state=q_data['state'],
                                    action=q_data['action']
                                ).first()

                                if existing_entry:
                                    # UPDATE
                                    existing_entry.q_value = float(q_data.get('q_value', existing_entry.q_value))
                                    existing_entry.visit_count = int(q_data.get('visit_count', existing_entry.visit_count + 1))
                                    existing_entry.last_reward = float(q_data.get('last_reward', existing_entry.last_reward))
                                    print(f"🔄 Updated Q-table: {q_data['traffic_light_id']}")
                                else:
                                    # INSERT
                                    q_entry = AIQTable(
                                        id=str(uuid.uuid4()),
                                        traffic_light_id=q_data['traffic_light_id'],
                                        scenario=q_data.get('scenario', 'default'),
                                        state=q_data['state'],
                                        action=q_data['action'],
                                        q_value=float(q_data.get('q_value', 0)),
                                        visit_count=int(q_data.get('visit_count', 0)),
                                        last_reward=float(q_data.get('last_reward', 0)),
                                    )
                                    db.session.add(q_entry)
                                    print(f"✅ Created Q-table: {q_data['traffic_light_id']}")

                                # COMMIT IMMEDIATELY for this operation
                                db.session.commit()
                                processed_count += 1

                            except Exception as e:
                                print(f"❌ Q-table operation failed: {e}")
                                db.session.rollback()
                                error_count += 1

                        elif op['type'] == 'emergency_log':
                            emergency_data = op['data']
                            
                            # FIX: Ensure details field is properly serialized to JSON
                            details = emergency_data.get('details', {})
                            if isinstance(details, dict):
                                # Convert any datetime objects in details to strings
                                details = self._convert_datetime_to_string(details)
                                details_json = json.dumps(details, default=self._json_serializer)
                            else:
                                details_json = '{}'
                                
                            # FIX: Convert detected_at to datetime if it's a string
                            detected_at = emergency_data.get('detected_at')
                            if isinstance(detected_at, str):
                                try:
                                    detected_at = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                                except:
                                    detected_at = datetime.utcnow()
                            elif not isinstance(detected_at, datetime):
                                detected_at = datetime.utcnow()
                                
                            # FIX: Convert cleared_at to datetime if it's a string or None
                            cleared_at = emergency_data.get('cleared_at')
                            if isinstance(cleared_at, str):
                                try:
                                    cleared_at = datetime.fromisoformat(cleared_at.replace('Z', '+00:00'))
                                except:
                                    cleared_at = None
                            elif cleared_at is not None and not isinstance(cleared_at, datetime):
                                cleared_at = None

                            # Create EmergencyVehicleLog entry
                            emergency_entry = EmergencyVehicleLog(
                                id=emergency_data.get('id', f"emergency_{int(time.time())}_{random.randint(1000, 9999)}"),
                                scenario=emergency_data['scenario'],
                                vehicle_id=emergency_data['vehicle_id'],
                                vehicle_type=emergency_data['vehicle_type'],
                                vehicle_class=emergency_data.get('vehicle_class'),
                                original_type=emergency_data.get('original_type'),
                                traffic_light_id=emergency_data['traffic_light_id'],
                                lane_id=emergency_data['lane_id'],
                                road_id=emergency_data.get('road_id'),
                                speed=float(emergency_data.get('speed', 0)),
                                position=float(emergency_data.get('position', 0)),
                                distance_to_intersection=float(emergency_data.get('distance_to_intersection', 0)),
                                time_to_intersection=float(emergency_data.get('time_to_intersection', 0)),
                                priority=emergency_data['priority'],
                                is_scheduled=emergency_data.get('is_scheduled', False),
                                detected_at=emergency_data.get('detected_at', datetime.utcnow()),
                                scenario_timestamp=emergency_data['scenario_timestamp'],
                                details=details_json  
                            )

                            db.session.add(emergency_entry)
                            processed_count += 1
                            print(f"✅ Created emergency log for vehicle {emergency_data['vehicle_id']}")
                        
                        # elif op['type'] == 'emergency_schedule':
                        #     emergency_schedule_data = op['data']
                            
                        #     # FIX: Ensure details field is properly serialized to JSON
                        #     details = emergency_schedule_data.get('details', {})
                        #     if isinstance(details, dict):
                        #         details = self._convert_datetime_to_string(details)
                        #         details_json = json.dumps(details, default=self._json_serializer)
                        #     else:
                        #         details_json = '{}'

                        #     # FIX: Handle route_edges serialization
                        #     route_edges = emergency_schedule_data.get('route_edges', [])
                        #     if isinstance(route_edges, (list, dict)):
                        #         route_edges_json = json.dumps(route_edges, default=self._json_serializer)
                        #     else:
                        #         route_edges_json = '[]'

                        #     # FIX: Handle estimated_arrival_times serialization
                        #     arrival_times = emergency_schedule_data.get('estimated_arrival_times', {})
                        #     if isinstance(arrival_times, dict):
                        #         arrival_times_json = json.dumps(arrival_times, default=self._json_serializer)
                        #     else:
                        #         arrival_times_json = '{}'

                        #     # Create EmergencyVehicleRegistry entry
                        #     emergency_schedule_entry = EmergencyVehicleRegistry(
                        #         id=emergency_schedule_data.get('id', f"emergency_{int(time.time())}_{random.randint(1000, 9999)}"),
                        #         scenario=emergency_schedule_data['scenario'],
                        #         vehicle_id=emergency_schedule_data['vehicle_id'],
                        #         vehicle_type=emergency_schedule_data['vehicle_type'],
                        #         scheduled_departure=float(emergency_schedule_data.get('scheduled_departure', 0)),
                        #         from_edge=emergency_schedule_data['from_edge'],
                        #         to_edge=emergency_schedule_data['to_edge'],
                        #         route_edges=emergency_schedule_data['route_edges'],
                        #         status=emergency_schedule_data.get('status', 'SCHEDULED'),
                        #         estimated_arrival_time=float(emergency_schedule_data.get('estimated_arrival_time', 0)),
                        #         created_at=datetime.utcnow(),
                        #         details=details_json
                        #     )

                        #     db.session.add(emergency_schedule_entry)
                        #     processed_count += 1
                        #     print(f"✅ Created emergency schedule for vehicle {emergency_schedule_data['vehicle_id']}")

                    except Exception as op_error:
                        print(f"❌ Error processing operation {i}: {op_error}")
                        import traceback
                        traceback.print_exc()
                        error_count += 1
                        continue
                    
                # Debug: Check what we're about to save
                print(f"🔍 About to save: {len(traffic_light_logs)} TLS logs, {len(traffic_patterns)} patterns, {len(ai_decision_logs)} AI decisions, {len(ai_q_tables)} Q-table entries")

                # Bulk insert traffic light logs
                if traffic_light_logs:
                    try:
                        print("🔍 Adding TLS logs to session...")
                        db.session.add_all(traffic_light_logs)
                        print("🔍 Flushing TLS logs...")
                        db.session.flush()  # This should trigger any constraint errors
                        print("✅ Successfully flushed TLS logs to session")
                    except Exception as e:
                        print(f"❌ Error during TLS logs flush: {e}")
                        import traceback
                        traceback.print_exc()
                        error_count += len(traffic_light_logs)

                # Bulk insert traffic patterns
                if traffic_patterns:
                    try:
                        print("🔍 Adding traffic patterns to session...")
                        db.session.add_all(traffic_patterns)
                        print("🔍 Flushing traffic patterns...")
                        db.session.flush()
                        print("✅ Successfully flushed traffic patterns to session")
                    except Exception as e:
                        print(f"❌ Error during traffic patterns flush: {e}")
                        import traceback
                        traceback.print_exc()
                        error_count += len(traffic_patterns)
                        
                # Bulk insert AI decision logs
                if ai_decision_logs:
                    try:
                        print("🔍 Adding AI decision logs to session...")
                        db.session.add_all(ai_decision_logs)
                        print("🔍 Flushing AI decision logs...")
                        db.session.flush()
                        print("✅ Successfully flushed AI decision logs to session")
                    except Exception as e:
                        print(f"❌ Error during AI decision logs flush: {e}")
                        import traceback
                        traceback.print_exc()
                        error_count += len(ai_decision_logs)
                        db.session.rollback()
                        
                # Bulk insert AI Q-table entries
                if ai_q_tables:
                    try:
                        print("🔍 Adding AI Q-table entries to session...")
                        db.session.add_all(ai_q_tables)
                        print("🔍 Flushing AI Q-table entries...")
                        db.session.flush()
                        print("✅ Successfully flushed AI Q-table entries to session")
                    except Exception as e:
                        print(f"❌ Error during AI Q-table flush: {e}")
                        import traceback
                        traceback.print_exc()
                        error_count += len(ai_q_tables)
                        db.session.rollback()
                        
                # Bulk insert Emergency Vehicle Logs
                if emergency_logs:
                    try:
                        print("🔍 Adding Emergency Vehicle Logs to session...")
                        db.session.add_all(emergency_logs)
                        print("🔍 Flushing Emergency Vehicle Logs...")
                        db.session.flush()
                        print("✅ Successfully flushed Emergency Vehicle Logs to session")
                    except Exception as e:
                        print(f"❌ Error during Emergency Vehicle Logs flush: {e}")
                        import traceback
                        traceback.print_exc()
                        error_count += len(emergency_logs)
                        db.session.rollback()
                        
                # Bulk insert Emergency Vehicle Schedules
                # if emergency_schedule_logs:
                #     try:
                #         print("🔍 Adding Emergency Vehicle Schedules to session...")
                #         db.session.add_all(emergency_schedule_logs)
                #         print("🔍 Flushing Emergency Vehicle Schedules...")
                #         db.session.flush()
                #         print("✅ Successfully flushed Emergency Vehicle Schedules to session")
                #     except Exception as e:
                #         print(f"❌ Error during Emergency Vehicle Schedules flush: {e}")
                #         import traceback
                #         traceback.print_exc()
                #         error_count += len(emergency_schedule_logs)
                #         db.session.rollback()

                # Commit all changes
                if error_count == 0:
                    print("🔍 Committing transaction...")
                    db.session.commit()
                    print("✅ Transaction committed successfully")

                    # Verify the data was actually saved
                    try:
                        if traffic_light_logs:
                            first_log = traffic_light_logs[0]
                            saved_count = TrafficLightLog.query.filter_by(
                                traffic_light_id=first_log.traffic_light_id
                            ).count()
                            print(f"🔍 Verification: Found {saved_count} logs for {first_log.traffic_light_id} in DB")

                        if traffic_patterns:
                            first_pattern = traffic_patterns[0]
                            pattern_count = TrafficPattern.query.filter_by(
                                traffic_light_id=first_pattern.traffic_light_id
                            ).count()
                            print(f"🔍 Verification: Found {pattern_count} patterns for {first_pattern.traffic_light_id} in DB")

                        if ai_decision_logs:
                            decision_count = AIDecisionLog.query.count()
                            print(f"🔍 Verification: Found {decision_count} AI decision logs in DB")

                        if ai_q_tables:
                            q_table_count = AIQTable.query.count()
                            print(f"🔍 Verification: Found {q_table_count} Q-table entries in DB")
                            
                        if emergency_logs:
                            emergency_count = EmergencyVehicleLog.query.count()
                            print(f"🔍 Verification: Found {emergency_count} Emergency Vehicle Logs in DB")
                            
                        if emergency_schedule_logs:
                            schedule_count = EmergencyVehicleRegistry.query.count()
                            print(f"🔍 Verification: Found {schedule_count} Emergency Vehicle Schedules in DB")

                    except Exception as verify_error:
                        print(f"⚠️ Could not verify save: {verify_error}")
                else:
                    print(f"⚠️ Skipping commit due to {error_count} errors")
                    db.session.rollback()

                # Update statistics
                successful_operations = processed_count - error_count
                self.stats['operations_processed'] += successful_operations
                self.stats['last_flush_size'] = successful_operations
                self.stats['average_flush_time'] = time.time() - start_time

                print(f"✅ DB Queue: Processed {successful_operations} successful operations "
                      f"({error_count} errors) in {time.time() - start_time:.2f}s")

                # Clear processed operations only if successful
                if error_count == 0:
                    self.queue.clear()
                    print("🔍 Queue cleared")
                else:
                    print(f"⚠️ Keeping {len(self.queue)} operations in queue due to errors")

        except Exception as e:
            print(f"❌ DB Queue Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            print("🔄 Session rolled back due to error")

        finally:
            self.is_processing = False
            self.last_flush = time.time()
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    def _convert_datetime_to_string(self, data):
        """Recursively convert datetime objects to strings in a dictionary"""
        if isinstance(data, dict):
            return {k: self._convert_datetime_to_string(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetime_to_string(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data
    
    def get_stats(self):
        """Get queue performance statistics"""
        return {
            **self.stats,
            'current_queue_size': len(self.queue),
            'time_since_last_flush': time.time() - self.last_flush,
            'is_processing': self.is_processing
        }

def init_db_queue(app):
    """Initialize the DB queue service"""
    db_queue_service.init_app(app)
    
# Global instance
db_queue_service = DatabaseQueueService()