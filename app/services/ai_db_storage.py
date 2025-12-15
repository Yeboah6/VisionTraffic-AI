"""
AI Database Storage Service
Centralized, error-handled database operations for AI components.
Each method is self-contained with its own error handling.
"""

import uuid
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from functools import wraps

from app.extensions import db


class AIDBStorageError(Exception):
    """Custom exception for AI DB storage errors"""
    def __init__(self, operation: str, message: str, original_error: Exception = None):
        self.operation = operation
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{operation}] {message}")


def db_operation(operation_name: str):
    """Decorator for safe database operations with automatic rollback"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                return {'success': True, 'data': result, 'error': None}
            except Exception as e:
                db.session.rollback()
                error_msg = f"{operation_name} failed: {str(e)}"
                print(f"❌ {error_msg}")
                return {
                    'success': False, 
                    'data': None, 
                    'error': error_msg,
                    'exception': str(e)
                }
        return wrapper
    return decorator


class AIDBStorageService:
    """
    Handles all AI-related database operations with proper error handling.
    Each method returns a standardized response: {'success': bool, 'data': any, 'error': str}
    """
    
    def __init__(self, app=None):
        self.app = app
        self.stats = {
            'q_table_writes': 0,
            'q_table_reads': 0,
            'decision_logs': 0,
            'performance_logs': 0,
            'errors': 0
        }
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        print("✅ AI DB Storage Service initialized")
    
    # ==================== Q-TABLE OPERATIONS ====================
    
    @db_operation("Q-Table Save")
    def save_q_value(self, tl_id: str, scenario: str, state: str, 
                    action: str, q_value: float, reward: float,
                    success: bool = True) -> Dict[str, Any]:
        """Save or update a Q-value in the database"""
        from app.models.ai import AIQTable
        
        entry = AIQTable.query.filter_by(
            traffic_light_id=tl_id,
            scenario=scenario,
            state=state,
            action=action
        ).first()
        
        if entry:
            old_avg = entry.avg_reward or 0
            old_count = entry.visit_count or 0
            
            entry.q_value = q_value
            entry.visit_count = old_count + 1
            entry.last_reward = reward
            entry.avg_reward = (old_avg * old_count + reward) / (old_count + 1)
            
            old_success_rate = entry.success_rate or 0
            entry.success_rate = (old_success_rate * old_count + (1 if success else 0)) / (old_count + 1)
        else:
            entry = AIQTable(
                id=str(uuid.uuid4()),
                traffic_light_id=tl_id,
                scenario=scenario,
                state=state,
                action=action,
                q_value=q_value,
                visit_count=1,
                last_reward=reward,
                success_rate=1.0 if success else 0.0,
                avg_reward=reward
            )
            db.session.add(entry)
        
        db.session.commit()
        self.stats['q_table_writes'] += 1
        
        return {
            'id': entry.id,
            'q_value': q_value,
            'visit_count': entry.visit_count,
            'is_new': entry.visit_count == 1
        }
    
    @db_operation("Q-Table Bulk Save")
    def save_q_values_bulk(self, entries: List[Dict]) -> Dict[str, Any]:
        """Save multiple Q-values in a single transaction"""
        from app.models.ai import AIQTable
        
        saved_count = 0
        updated_count = 0
        
        for entry_data in entries:
            existing = AIQTable.query.filter_by(
                traffic_light_id=entry_data['tl_id'],
                scenario=entry_data.get('scenario', 'current'),
                state=entry_data['state'],
                action=entry_data['action']
            ).first()
            
            if existing:
                existing.q_value = entry_data['q_value']
                existing.visit_count = (existing.visit_count or 0) + 1
                existing.last_reward = entry_data.get('reward', 0)
                updated_count += 1
            else:
                new_entry = AIQTable(
                    id=str(uuid.uuid4()),
                    traffic_light_id=entry_data['tl_id'],
                    scenario=entry_data.get('scenario', 'current'),
                    state=entry_data['state'],
                    action=entry_data['action'],
                    q_value=entry_data['q_value'],
                    visit_count=1,
                    last_reward=entry_data.get('reward', 0),
                    avg_reward=entry_data.get('reward', 0)
                )
                db.session.add(new_entry)
                saved_count += 1
        
        db.session.commit()
        self.stats['q_table_writes'] += len(entries)
        
        return {
            'saved': saved_count,
            'updated': updated_count,
            'total': len(entries)
        }
    
    @db_operation("Q-Table Load")
    def load_q_table(self, scenario: str = 'current', 
                    tl_id: str = None) -> Dict[str, Dict[str, float]]:
        """Load Q-table from database into memory"""
        from app.models.ai import AIQTable
        
        query = AIQTable.query.filter_by(scenario=scenario)
        if tl_id:
            query = query.filter_by(traffic_light_id=tl_id)
        
        entries = query.all()
        
        q_table = {}
        for entry in entries:
            cache_key = f"{entry.traffic_light_id}_{entry.state}"
            if cache_key not in q_table:
                q_table[cache_key] = {}
            q_table[cache_key][entry.action] = entry.q_value
        
        self.stats['q_table_reads'] += 1
        
        return q_table
    
    @db_operation("Q-Table Stats")
    def get_q_table_stats(self, scenario: str = 'current') -> Dict[str, Any]:
        """Get Q-table statistics"""
        from app.models.ai import AIQTable
        
        total_entries = AIQTable.query.filter_by(scenario=scenario).count()
        
        action_stats = db.session.query(
            AIQTable.action,
            db.func.count(AIQTable.id).label('count'),
            db.func.avg(AIQTable.q_value).label('avg_q'),
            db.func.avg(AIQTable.success_rate).label('avg_success'),
            db.func.sum(AIQTable.visit_count).label('total_visits')
        ).filter_by(scenario=scenario).group_by(AIQTable.action).all()
        
        return {
            'total_entries': total_entries,
            'scenario': scenario,
            'actions': [
                {
                    'action': a.action,
                    'count': a.count,
                    'avg_q_value': round(float(a.avg_q or 0), 4),
                    'avg_success_rate': round(float(a.avg_success or 0), 4),
                    'total_visits': int(a.total_visits or 0)
                }
                for a in action_stats
            ]
        }
    
    @db_operation("Q-Table Clear")
    def clear_q_table(self, scenario: str = 'current', 
                     tl_id: str = None) -> Dict[str, int]:
        """Clear Q-table entries"""
        from app.models.ai import AIQTable
        
        query = AIQTable.query.filter_by(scenario=scenario)
        if tl_id:
            query = query.filter_by(traffic_light_id=tl_id)
        
        count = query.delete()
        db.session.commit()
        
        return {'deleted': count}
    
    # ==================== DECISION LOG OPERATIONS ====================
    
    @db_operation("Decision Log")
    def log_decision(self, scenario: str, timestamp: float,
                    tls_decisions: List[Dict], system_metrics: Dict,
                    ai_mode: str = 'BALANCED', 
                    exploration_rate: float = 0.1) -> Dict[str, Any]:
        """Log an AI decision batch"""
        from app.models.ai import AIDecisionLog
        
        decision_id = f"decision_{int(timestamp)}_{uuid.uuid4().hex[:8]}"
        
        total_decisions = len(tls_decisions)
        confidences = [d.get('confidence', 0) for d in tls_decisions]
        avg_confidence = statistics.mean(confidences) if confidences else 0
        rewards = [d.get('reward', 0) for d in tls_decisions]
        total_reward = sum(rewards)
        optimized_count = sum(1 for d in tls_decisions if d.get('action') != 'MAINTAIN')
        
        decision_log = AIDecisionLog(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            timestamp=timestamp,
            scenario=scenario,
            ai_mode=ai_mode,
            exploration_rate=exploration_rate,
            learning_enabled=True,
            system_action=system_metrics.get('action', 'BATCH_OPTIMIZE'),
            system_recommendation=system_metrics.get('recommendation', ''),
            optimization_ratio=optimized_count / total_decisions if total_decisions > 0 else 0,
            overall_congestion=system_metrics.get('congestion', 0),
            system_health=system_metrics.get('health', 1.0),
            total_tls_optimized=optimized_count,
            total_decisions=total_decisions,
            avg_confidence=avg_confidence,
            total_reward=total_reward
        )
        
        decision_log.set_tls_decisions(tls_decisions)
        
        db.session.add(decision_log)
        db.session.commit()
        
        self.stats['decision_logs'] += 1
        
        return {
            'decision_id': decision_id,
            'total_decisions': total_decisions,
            'avg_confidence': avg_confidence
        }
    
    @db_operation("Decision History")
    def get_decision_history(self, scenario: str = 'current',
                            limit: int = 50,
                            ai_mode: str = None) -> List[Dict]:
        """Get decision history"""
        from app.models.ai import AIDecisionLog
        
        query = AIDecisionLog.query.filter_by(scenario=scenario)
        if ai_mode:
            query = query.filter_by(ai_mode=ai_mode)
        
        decisions = query.order_by(
            AIDecisionLog.created_at.desc()
        ).limit(limit).all()
        
        return [d.to_dict() for d in decisions]
    
    @db_operation("Decision Detail")
    def get_decision_detail(self, decision_id: str) -> Optional[Dict]:
        """Get a specific decision by ID"""
        from app.models.ai import AIDecisionLog
        
        decision = AIDecisionLog.query.filter_by(decision_id=decision_id).first()
        return decision.to_dict() if decision else None
    
    # ==================== PERFORMANCE LOG OPERATIONS ====================
    
    @db_operation("Performance Log")
    def log_performance(self, scenario: str, period_type: str,
                       metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Log AI performance metrics"""
        from app.models.ai import AIPerformance
        
        now = datetime.utcnow()
        
        if period_type == 'HOURLY':
            period_start = now - timedelta(hours=1)
        elif period_type == 'DAILY':
            period_start = now - timedelta(days=1)
        elif period_type == 'WEEKLY':
            period_start = now - timedelta(weeks=1)
        else:
            period_start = now - timedelta(hours=1)
        
        performance = AIPerformance(
            id=str(uuid.uuid4()),
            scenario=scenario,
            period_start=period_start,
            period_end=now,
            period_type=period_type,
            total_decisions=metrics.get('total_decisions', 0),
            successful_decisions=metrics.get('successful_decisions', 0),
            failed_decisions=metrics.get('failed_decisions', 0),
            optimization_rate=metrics.get('optimization_rate', 0),
            avg_congestion_before=metrics.get('avg_congestion_before', 0),
            avg_congestion_after=metrics.get('avg_congestion_after', 0),
            congestion_reduction=metrics.get('congestion_reduction', 0),
            avg_efficiency_before=metrics.get('avg_efficiency_before', 0),
            avg_efficiency_after=metrics.get('avg_efficiency_after', 0),
            efficiency_improvement=metrics.get('efficiency_improvement', 0),
            avg_waiting_time_before=metrics.get('avg_waiting_before', 0),
            avg_waiting_time_after=metrics.get('avg_waiting_after', 0),
            waiting_time_reduction=metrics.get('waiting_reduction', 0),
            exploration_rate_avg=metrics.get('exploration_rate', 0),
            avg_reward_per_decision=metrics.get('avg_reward', 0),
            q_table_size=metrics.get('q_table_size', 0),
            learning_progress=metrics.get('learning_progress', 0)
        )
        
        db.session.add(performance)
        db.session.commit()
        
        self.stats['performance_logs'] += 1
        
        return {
            'id': performance.id,
            'period_type': period_type,
            'efficiency_improvement': metrics.get('efficiency_improvement', 0)
        }
    
    @db_operation("Performance History")
    def get_performance_history(self, scenario: str = 'current',
                               period_type: str = None,
                               limit: int = 24) -> List[Dict]:
        """Get performance history"""
        from app.models.ai import AIPerformance
        
        query = AIPerformance.query.filter_by(scenario=scenario)
        if period_type:
            query = query.filter_by(period_type=period_type)
        
        records = query.order_by(
            AIPerformance.period_end.desc()
        ).limit(limit).all()
        
        return [r.to_dict() for r in records]
    
    @db_operation("Performance Summary")
    def get_performance_summary(self, scenario: str = 'current',
                               hours: int = 24) -> Dict[str, Any]:
        """Get summarized performance metrics"""
        from app.models.ai import AIPerformance, AIDecisionLog, AIQTable
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        perf_records = AIPerformance.query.filter(
            AIPerformance.scenario == scenario,
            AIPerformance.period_end >= cutoff
        ).all()
        
        decision_count = AIDecisionLog.query.filter(
            AIDecisionLog.scenario == scenario,
            AIDecisionLog.created_at >= cutoff
        ).count()
        
        q_table_size = AIQTable.query.filter_by(scenario=scenario).count()
        
        if perf_records:
            avg_eff_improvement = statistics.mean([r.efficiency_improvement for r in perf_records])
            avg_cong_reduction = statistics.mean([r.congestion_reduction for r in perf_records])
            avg_wait_reduction = statistics.mean([r.waiting_time_reduction for r in perf_records])
            total_decisions = sum(r.total_decisions for r in perf_records)
            successful = sum(r.successful_decisions for r in perf_records)
            success_rate = successful / total_decisions if total_decisions > 0 else 0
        else:
            avg_eff_improvement = avg_cong_reduction = avg_wait_reduction = success_rate = 0
        
        return {
            'scenario': scenario,
            'time_window_hours': hours,
            'total_decisions': decision_count,
            'q_table_size': q_table_size,
            'performance_records': len(perf_records),
            'avg_efficiency_improvement': round(avg_eff_improvement, 2),
            'avg_congestion_reduction': round(avg_cong_reduction, 2),
            'avg_waiting_reduction': round(avg_wait_reduction, 2),
            'success_rate': round(success_rate * 100, 1)
        }
    
    # ==================== UTILITY METHODS ====================
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage operation statistics"""
        return {
            'stats': self.stats.copy(),
            'error_rate': self.stats['errors'] / max(1, sum(self.stats.values()))
        }
    
    def with_app_context(self, func):
        """Execute function with app context"""
        if self.app:
            with self.app.app_context():
                return func()
        return func()


# Global instance
ai_db_storage = AIDBStorageService()


def init_ai_db_storage(app):
    """Initialize AI DB storage service"""
    ai_db_storage.init_app(app)
    return ai_db_storage