from app.extensions import db
from datetime import datetime
import json
import uuid

class AIDecisionLog(db.Model):
    __tablename__ = 'ai_decision_logs'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = db.Column(db.String(100), unique=True, nullable=False)
    timestamp = db.Column(db.Float, nullable=False)  # Simulation time
    scenario = db.Column(db.String(100), nullable=False)
    
    # AI System Info
    ai_mode = db.Column(db.String(50), nullable=False)  # AGGRESSIVE, BALANCED, CONSERVATIVE
    exploration_rate = db.Column(db.Float, default=0.2)
    learning_enabled = db.Column(db.Boolean, default=True)
    
    # System-level Decisions
    system_action = db.Column(db.String(100), nullable=False)
    system_recommendation = db.Column(db.Text, nullable=True)
    optimization_ratio = db.Column(db.Float, default=0.0)
    overall_congestion = db.Column(db.Float, default=0.0)
    system_health = db.Column(db.Float, default=1.0)
    
    # Performance Metrics
    total_tls_optimized = db.Column(db.Integer, default=0)
    total_decisions = db.Column(db.Integer, default=0)
    avg_confidence = db.Column(db.Float, default=0.0)
    total_reward = db.Column(db.Float, default=0.0)
    
    # Individual TLS Decisions (stored as JSON)
    tls_decisions = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'decision_id': self.decision_id,
            'timestamp': self.timestamp,
            'scenario': self.scenario,
            'ai_mode': self.ai_mode,
            'exploration_rate': self.exploration_rate,
            'learning_enabled': self.learning_enabled,
            'system_action': self.system_action,
            'system_recommendation': self.system_recommendation,
            'optimization_ratio': self.optimization_ratio,
            'overall_congestion': self.overall_congestion,
            'system_health': self.system_health,
            'total_tls_optimized': self.total_tls_optimized,
            'total_decisions': self.total_decisions,
            'avg_confidence': self.avg_confidence,
            'total_reward': self.total_reward,
            'tls_decisions': json.loads(self.tls_decisions) if self.tls_decisions else [],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def set_tls_decisions(self, decisions_list):
        """Store TLS decisions as JSON"""
        self.tls_decisions = json.dumps(decisions_list)
    
    def get_tls_decisions(self):
        """Retrieve TLS decisions as list"""
        return json.loads(self.tls_decisions) if self.tls_decisions else []
    
class AIQTable(db.Model):
    __tablename__ = 'ai_q_table'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    traffic_light_id = db.Column(db.String(100), nullable=False)
    scenario = db.Column(db.String(100), nullable=False, default='current')
    
    # State-Action Pair
    state = db.Column(db.String(200), nullable=False)  # e.g., "LOW_LOW_MAIN_GREEN"
    action = db.Column(db.String(50), nullable=False)  # e.g., "EXTEND_GREEN"
    
    # Q-Learning Values
    q_value = db.Column(db.Float, default=0.0)
    visit_count = db.Column(db.Integer, default=0)
    last_reward = db.Column(db.Float, default=0.0)
    
    # Performance Metrics
    success_rate = db.Column(db.Float, default=0.0)
    avg_reward = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('traffic_light_id', 'scenario', 'state', 'action', name='unique_state_action'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'traffic_light_id': self.traffic_light_id,
            'scenario': self.scenario,
            'state': self.state,
            'action': self.action,
            'q_value': self.q_value,
            'visit_count': self.visit_count,
            'last_reward': self.last_reward,
            'success_rate': self.success_rate,
            'avg_reward': self.avg_reward,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
class AIPerformance(db.Model):
    __tablename__ = 'ai_performance'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario = db.Column(db.String(100), nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    period_type = db.Column(db.String(50), nullable=False)  # HOURLY, DAILY, WEEKLY
    
    # Decision Metrics
    total_decisions = db.Column(db.Integer, default=0)
    successful_decisions = db.Column(db.Integer, default=0)
    failed_decisions = db.Column(db.Integer, default=0)
    optimization_rate = db.Column(db.Float, default=0.0)
    
    # Traffic Performance
    avg_congestion_before = db.Column(db.Float, default=0.0)
    avg_congestion_after = db.Column(db.Float, default=0.0)
    congestion_reduction = db.Column(db.Float, default=0.0)
    
    avg_efficiency_before = db.Column(db.Float, default=0.0)
    avg_efficiency_after = db.Column(db.Float, default=0.0)
    efficiency_improvement = db.Column(db.Float, default=0.0)
    
    avg_waiting_time_before = db.Column(db.Float, default=0.0)
    avg_waiting_time_after = db.Column(db.Float, default=0.0)
    waiting_time_reduction = db.Column(db.Float, default=0.0)
    
    # AI Learning Metrics
    exploration_rate_avg = db.Column(db.Float, default=0.0)
    avg_reward_per_decision = db.Column(db.Float, default=0.0)
    q_table_size = db.Column(db.Integer, default=0)
    learning_progress = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'scenario': self.scenario,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'period_type': self.period_type,
            'total_decisions': self.total_decisions,
            'successful_decisions': self.successful_decisions,
            'failed_decisions': self.failed_decisions,
            'optimization_rate': self.optimization_rate,
            'avg_congestion_before': self.avg_congestion_before,
            'avg_congestion_after': self.avg_congestion_after,
            'congestion_reduction': self.congestion_reduction,
            'avg_efficiency_before': self.avg_efficiency_before,
            'avg_efficiency_after': self.avg_efficiency_after,
            'efficiency_improvement': self.efficiency_improvement,
            'avg_waiting_time_before': self.avg_waiting_time_before,
            'avg_waiting_time_after': self.avg_waiting_time_after,
            'waiting_time_reduction': self.waiting_time_reduction,
            'exploration_rate_avg': self.exploration_rate_avg,
            'avg_reward_per_decision': self.avg_reward_per_decision,
            'q_table_size': self.q_table_size,
            'learning_progress': self.learning_progress,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        

class AI_Decision(db.Model):
    __tablename__ = 'ai_decisions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    traffic_light_id = db.Column(db.String(50), nullable=False)
    decision_type = db.Column(db.String(20), nullable=False)  # EXTEND_GREEN, REDUCE_GREEN, MAINTAIN
    decision_parameters = db.Column(db.JSON, nullable=False)
    confidence_score = db.Column(db.Float, default=0.5)
    q_value = db.Column(db.Float, default=0.0)
    state_key = db.Column(db.String(100))
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    simulation_step = db.Column(db.Integer, default=0)
    scenario = db.Column(db.String(50))
    reasoning = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'traffic_light_id': self.traffic_light_id,
            'decision_type': self.decision_type,
            'decision_parameters': self.decision_parameters,
            'confidence_score': self.confidence_score,
            'q_value': self.q_value,
            'state_key': self.state_key,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'simulation_step': self.simulation_step,
            'scenario': self.scenario,
            'reasoning': self.reasoning,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }