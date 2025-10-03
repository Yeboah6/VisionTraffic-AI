from app.extensions import db
from datetime import datetime
import json

class Camera(db.Model):
    __tablename__ = 'cameras'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    camera_type = db.Column(db.String(20), nullable=False)  # 'real' or 'virtual'
    source = db.Column(db.String(500))  # URL for real, detector_id for virtual
    location_lat = db.Column(db.Float)
    location_lng = db.Column(db.Float)
    intersection_id = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.camera_type,
            'source': self.source,
            'location': {
                'lat': self.location_lat,
                'lng': self.location_lng
            },
            'intersection_id': self.intersection_id,
            'is_active': self.is_active
        }

class CameraMetrics(db.Model):
    __tablename__ = 'camera_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.String(50), nullable=False)
    vehicle_count = db.Column(db.Integer)
    average_speed = db.Column(db.Float)
    queue_length = db.Column(db.Integer)
    congestion_level = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'camera_id': self.camera_id,
            'vehicle_count': self.vehicle_count,
            'average_speed': self.average_speed,
            'queue_length': self.queue_length,
            'congestion_level': self.congestion_level,
            'timestamp': self.timestamp.isoformat()
        }