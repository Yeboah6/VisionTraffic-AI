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
    
    # Relationships
    # scenario_configs = db.relationship('TrafficLightConfig', 
    #                                  foreign_keys=[scenario],
    #                                  backref=db.backref('ai_decisions', lazy='dynamic'))
    
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
    
    # Relationships
    # config = db.relationship('TrafficLightConfig', 
    #                        foreign_keys=[traffic_light_id, scenario],
    #                        backref=db.backref('q_table_entries', lazy='dynamic'))
    
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
    
    # Relationships
    # scenario_configs = db.relationship('TrafficLightConfig', 
    #                                  foreign_keys=[scenario],
    #                                  backref=db.backref('ai_performance', lazy='dynamic'))
    
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
        
class TrafficPattern(db.Model):
    __tablename__ = 'traffic_patterns'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    traffic_light_id = db.Column(db.String(100), nullable=False)
    scenario = db.Column(db.String(100), nullable=False)
    pattern_type = db.Column(db.String(50), nullable=False)  # DAILY, WEEKLY, PEAK_HOURS
    
    # Time-based patterns
    time_period = db.Column(db.String(50), nullable=False)  # MORNING_PEAK, EVENING_PEAK, etc.
    day_of_week = db.Column(db.Integer, nullable=True)  # 0-6 (Monday-Sunday)
    hour_of_day = db.Column(db.Integer, nullable=True)  # 0-23
    
    # Pattern metrics
    avg_vehicle_count = db.Column(db.Float, default=0.0)
    avg_waiting_vehicles = db.Column(db.Float, default=0.0)
    avg_efficiency = db.Column(db.Float, default=0.0)
    congestion_probability = db.Column(db.Float, default=0.0)
    
    # Optimal settings for this pattern
    recommended_phase_duration = db.Column(db.Float, default=30.0)
    recommended_cycle_time = db.Column(db.Float, default=120.0)
    optimal_actions = db.Column(db.Text, nullable=True)  # JSON of best actions
    
    confidence_score = db.Column(db.Float, default=0.0)
    pattern_strength = db.Column(db.Float, default=0.0)  # How strong this pattern is
    
    sample_size = db.Column(db.Integer, default=0)
    last_observed = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # config = db.relationship('TrafficLightConfig', 
    #                        foreign_keys=[traffic_light_id],
    #                        backref=db.backref('traffic_patterns', lazy='dynamic'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'traffic_light_id': self.traffic_light_id,
            'scenario': self.scenario,
            'pattern_type': self.pattern_type,
            'time_period': self.time_period,
            'day_of_week': self.day_of_week,
            'hour_of_day': self.hour_of_day,
            'avg_vehicle_count': self.avg_vehicle_count,
            'avg_waiting_vehicles': self.avg_waiting_vehicles,
            'avg_efficiency': self.avg_efficiency,
            'congestion_probability': self.congestion_probability,
            'recommended_phase_duration': self.recommended_phase_duration,
            'recommended_cycle_time': self.recommended_cycle_time,
            'optimal_actions': json.loads(self.optimal_actions) if self.optimal_actions else [],
            'confidence_score': self.confidence_score,
            'pattern_strength': self.pattern_strength,
            'sample_size': self.sample_size,
            'last_observed': self.last_observed.isoformat() if self.last_observed else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def set_optimal_actions(self, actions_list):
        """Store optimal actions as JSON"""
        self.optimal_actions = json.dumps(actions_list)
    
    def get_optimal_actions(self):
        """Retrieve optimal actions as list"""
        return json.loads(self.optimal_actions) if self.optimal_actions else []