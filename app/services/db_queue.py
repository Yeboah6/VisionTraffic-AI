import threading
import time
from collections import deque
from datetime import datetime
from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficPattern
from app.models.ai import AIQTable, AIDecisionLog
import json
from sqlalchemy import and_
from typing import Dict
import uuid

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
    
    def flush_queue(self):
        """Flush all queued operations to database"""
        if not self.queue or not self.app:
            print("🟡 flush_queue: No queue items or app context")
            return

        start_time = time.time()
        self.is_processing = True

        try:
            with self.app.app_context():
                operations = list(self.queue)
                print(f"🔍 flush_queue: Processing {len(operations)} operations")

                traffic_light_logs = []
                traffic_patterns = []

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
                                id=pattern_data.get('id', str(uuid.uuid4())),  # ← ADD ID HERE TOO
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

                    except Exception as op_error:
                        print(f"❌ Error processing operation {i}: {op_error}")
                        import traceback
                        traceback.print_exc()
                        error_count += 1
                        continue
                    
                # Debug: Check what we're about to save
                print(f"🔍 About to save: {len(traffic_light_logs)} TLS logs, {len(traffic_patterns)} patterns")

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

                # Commit all changes
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

                except Exception as verify_error:
                    print(f"⚠️ Could not verify save: {verify_error}")

                # Update statistics
                successful_operations = processed_count - error_count
                self.stats['operations_processed'] += successful_operations
                self.stats['last_flush_size'] = successful_operations
                self.stats['average_flush_time'] = time.time() - start_time

                print(f"✅ DB Queue: Successfully committed {successful_operations} operations "
                      f"({error_count} errors) in {time.time() - start_time:.2f}s")

                # Clear processed operations
                self.queue.clear()
                print("🔍 Queue cleared")

        except Exception as e:
            print(f"❌ DB Queue Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            print("🔄 Session rolled back due to error")

        finally:
            self.is_processing = False
            self.last_flush = time.time()
    
    def get_stats(self):
        """Get queue performance statistics"""
        return {
            **self.stats,
            'current_queue_size': len(self.queue),
            'time_since_last_flush': time.time() - self.last_flush,
            'is_processing': self.is_processing
        }

# Global instance

def init_db_queue(app):
    """Initialize the DB queue service"""
    db_queue_service.init_app(app)
    
# def get_db_queue():
#     return db_queue_service

db_queue_service = DatabaseQueueService()