from app.extensions import db
from datetime import datetime

class EmergencyVehicleLog(db.Model):
    """Database model for emergency vehicle detection logs"""
    __tablename__ = 'emergency_vehicle_logs'
    
    id = db.Column(db.String, primary_key=True)
    scenario = db.Column(db.String(100), nullable=False)
    
    # Vehicle information
    vehicle_id = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)  # AMBULANCE, FIRE_TRUCK, POLICE
    original_type = db.Column(db.String(100))  # Original SUMO vehicle type
    vehicle_class = db.Column(db.String(50))  # e.g., emergency, private, public
    
    # Location information
    traffic_light_id = db.Column(db.String(100), nullable=False)
    lane_id = db.Column(db.String(100), nullable=False)
    road_id = db.Column(db.String(100))
    
    # Vehicle status
    speed = db.Column(db.Float, default=0.0)
    position = db.Column(db.Float, default=0.0)
    distance_to_intersection = db.Column(db.Float, default=0.0)
    time_to_intersection = db.Column(db.Float, default=0.0)
    
    # Emergency priority
    priority = db.Column(db.String(20), nullable=False)
    is_scheduled = db.Column(db.Boolean, default=False)
    
    # Timestamps
    detected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    scenario_timestamp = db.Column(db.Float, nullable=False)
    
    # Additional metadata
    details = db.Column(db.JSON)  # Store full emergency data as JSON
    
    def __repr__(self):
        return f'<EmergencyVehicleLog {self.vehicle_type} {self.vehicle_id} at {self.traffic_light_id}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'scenario': self.scenario,
            'vehicle_id': self.vehicle_id,
            'vehicle_type': self.vehicle_type,
            'original_type': self.original_type,
            'vehicle_class': self.vehicle_class,
            'traffic_light_id': self.traffic_light_id,
            'lane_id': self.lane_id,
            'road_id': self.road_id,
            'speed': self.speed,
            'position': self.position,
            'distance_to_intersection': self.distance_to_intersection,
            'time_to_intersection': self.time_to_intersection,
            'priority': self.priority,
            'is_scheduled': self.is_scheduled,
            'response_action': self.response_action,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'scenario_timestamp': self.scenario_timestamp,
            'details': self.details
        }
        
class EmergencySchedule(db.Model):
    """Database model for pre-registered emergency vehicles"""
    __tablename__ = 'emergency_schedules'
    
    id = db.Column(db.String(64), primary_key=True)
    scenario = db.Column(db.String(100), nullable=False)
    
    # Vehicle information
    vehicle_id = db.Column(db.String(100), nullable=False)
    emergency_type = db.Column(db.String(50), nullable=False)  # AMBULANCE, FIRE_TRUCK, POLICE
    priority = db.Column(db.String(20), nullable=False)  # CRITICAL, HIGH, MEDIUM
    description = db.Column(db.Text)
    
    # Timing information
    departure_time = db.Column(db.Float, nullable=False)  # Simulation time
    estimated_duration = db.Column(db.Float, default=300.0)  # seconds
    
    # Route information
    # scheduled_departure = db.Column(db.Float, default=0.0)
    from_location = db.Column(db.String(100), nullable=False)
    to_location = db.Column(db.String(100), nullable=False)
    route_edges = db.Column(db.JSON, nullable=False)  # List of edges for the route
    
    # Status tracking
    status = db.Column(db.String(20), default='SCHEDULED')  # SCHEDULED, DEPARTED, ACTIVE, CLEARED
    actual_departure = db.Column(db.Float)  # Actual departure time
    completed_at = db.Column(db.Float)  # Completion time
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    
    def __repr__(self):
        return f'<EmergencySchedule {self.vehicle_id} ({self.status})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'scenario': self.scenario,
            'emergency_type': self.emergency_type,
            'priority': self.priority,
            'vehicle_id': self.vehicle_id,
            'description': self.description,
            'departure_time': self.departure_time,
            'estimated_duration': self.estimated_duration,
            'from_location': self.from_location,
            'to_location': self.to_location,
            'route_edges': self.route_edges,
            'status': self.status,
            'actual_departure': self.actual_departure,
            'completed_at': self.completed_at,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
class GreenWaveSchedule(db.Model):
    """Database model for scheduled green waves"""
    __tablename__ = 'green_wave_schedules'
    
    id = db.Column(db.String(64), primary_key=True)
    emergency_id = db.Column(db.String(64), nullable=False)
    
    # Traffic light information
    traffic_light_id = db.Column(db.String(100), nullable=False)
    edge = db.Column(db.String(100))
    
    # Green wave details
    green_wave_type = db.Column(db.String(50), default='EMERGENCY')  # EMERGENCY, MAINTENANCE, SPECIAL_EVENT
    description = db.Column(db.Text)
    
    # Timing information
    scheduled_start = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Float, default=30.0)
    # arrival_time = db.Column(db.Float)  # Estimated emergency vehicle arrival
    
    # Status tracking
    status = db.Column(db.String(20), default='SCHEDULED')  # SCHEDULED, ACTIVE, COMPLETED
    activated_at = db.Column(db.Float)
    completed_at = db.Column(db.Float)
    
    def __repr__(self):
        return f'<GreenWaveSchedule {self.traffic_light_id} for {self.emergency_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'emergency_id': self.emergency_id,
            'traffic_light_id': self.traffic_light_id,
            'edge': self.edge,
            'green_wave_type': self.green_wave_type,
            'description': self.description,
            'scheduled_start': self.scheduled_start,
            'duration': self.duration,
            'status': self.status,
            'activated_at': self.activated_at,
            'completed_at': self.completed_at
        }