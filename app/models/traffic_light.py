from datetime import datetime
from app import db
import json
import uuid

class TrafficLightLog(db.Model):
    __tablename__ = 'traffic_light_logs'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    traffic_light_id = db.Column(db.String(100), nullable=False)
    scenario = db.Column(db.String(100), nullable=False)
    simulation_time = db.Column(db.Float, nullable=False)
    state = db.Column(db.String(20), nullable=False)  # RED, YELLOW, GREEN, etc.
    phase = db.Column(db.Integer, default=0)
    phase_name = db.Column(db.String(50))
    duration = db.Column(db.Float)  # Current phase duration
    next_switch = db.Column(db.Float)  # Time until next switch
    vehicle_count = db.Column(db.Integer, default=0)
    waiting_vehicles = db.Column(db.Integer, default=0)
    efficiency_score = db.Column(db.Integer, default=0)
    performance_grade = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    # config = db.relationship('TrafficLightConfig', 
    #                        foreign_keys=[traffic_light_id],
    #                        backref=db.backref('logs', lazy='dynamic'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'traffic_light_id': self.traffic_light_id,
            'scenario': self.scenario,
            'simulation_time': self.simulation_time,
            'state': self.state,
            'phase': self.phase,
            'phase_name': self.phase_name,
            'duration': self.duration,
            'next_switch': self.next_switch,
            'vehicle_count': self.vehicle_count,
            'waiting_vehicles': self.waiting_vehicles,
            'efficiency_score': self.efficiency_score,
            'performance_grade': self.performance_grade,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class TrafficLightConfig(db.Model):
    __tablename__ = 'traffic_light_configs'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    traffic_light_id = db.Column(db.String(100), nullable=False)
    scenario = db.Column(db.String(100), nullable=False)
    program_id = db.Column(db.String(100), nullable=False)
    phases = db.Column(db.Text, nullable=False)  # JSON string of phases
    current_phase_index = db.Column(db.Integer, default=0)
    cycle_time = db.Column(db.Float, default=0.0)
    is_adaptive = db.Column(db.Boolean, default=False)
    config_type = db.Column(db.String(50), default='STATIC')  # STATIC, ADAPTIVE, OPTIMIZED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint to prevent duplicates
    # __table_args__ = (
    #     db.UniqueConstraint('traffic_light_id', 'scenario', name='uq_traffic_light_scenario'),
    # )
    
    def to_dict(self):
        return {
            'id': self.id,
            'traffic_light_id': self.traffic_light_id,
            'scenario': self.scenario,
            'program_id': self.program_id,
            'phases': json.loads(self.phases) if self.phases else [],
            'current_phase_index': self.current_phase_index,
            'cycle_time': self.cycle_time,
            'is_adaptive': self.is_adaptive,
            'config_type': self.config_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
    def set_phases(self, phases_list):
        """Helper method to set phases as JSON string"""
        self.phases = json.dumps(phases_list)
    
    def get_phases(self):
        """Helper method to get phases as list"""
        return json.loads(self.phases) if self.phases else []