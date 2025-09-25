from datetime import datetime
from app import db

class TrafficLightLog(db.Model):
    __tablename__ = 'traffic_light_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    traffic_light_id = db.Column(db.String(50), nullable=False, index=True)
    scenario = db.Column(db.String(100), nullable=False)
    simulation_time = db.Column(db.Float, nullable=False)
    state = db.Column(db.String(20), nullable=False)  # RED, YELLOW, GREEN, etc.
    phase = db.Column(db.Integer, default=0)
    phase_name = db.Column(db.String(50))
    duration = db.Column(db.Float)  # Current phase duration
    next_switch = db.Column(db.Float)  # Time until next switch
    vehicle_count = db.Column(db.Integer, default=0)
    waiting_vehicles = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, **kwargs):
        # Handle both 'tl_id' and 'traffic_light_id' for backward compatibility
        if 'tl_id' in kwargs:
            kwargs['traffic_light_id'] = kwargs.pop('tl_id')
        super().__init__(**kwargs)
    
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
            'created_at': self.created_at.isoformat()
        }

class TrafficLightConfig(db.Model):
    __tablename__ = 'traffic_light_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    traffic_light_id = db.Column(db.String(50), nullable=False, unique=True, index=True)
    scenario = db.Column(db.String(100), nullable=False)
    program_id = db.Column(db.String(50), default='0')
    phases = db.Column(db.Text)  # JSON string of phase configurations
    current_phase_index = db.Column(db.Integer, default=0)
    cycle_time = db.Column(db.Float)
    offset = db.Column(db.Float, default=0)
    is_adaptive = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'traffic_light_id': self.traffic_light_id,
            'scenario': self.scenario,
            'program_id': self.program_id,
            'phases': self.phases,
            'current_phase_index': self.current_phase_index,
            'cycle_time': self.cycle_time,
            'offset': self.offset,
            'is_adaptive': self.is_adaptive,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }