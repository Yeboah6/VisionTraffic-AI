from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
import re

class Sensor(db.Model):
    __tablename__ = 'sensors'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_id = db.Column(db.String(50), unique=True) #SEN_MAIN_001
    sensor_type = db.Column(db.String(50), nullable=False)
    lanes_monitored = db.Column(db.Integer, nullable=False)
    installation_date = db.Column(db.String(50))
    installation_note = db.Column(db.String(150))
    direction = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    location_id = db.Column(db.UUID(36), db.ForeignKey('locations.id'))
    location = db.relationship('Location', back_populates='sensors')
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='sensors')
    
    signal_id = db.Column(db.String(50), db.ForeignKey('signals.id'))
    
    @staticmethod
    def generate_display_id(location_name=None):
        """Auto-generates SEN_LOC_001 format"""
        prefix = "SEN_" + (
            re.sub(r'\W+', '', location_name.split()[0]).upper()[:3] 
            if location_name 
            else "UNK"
        )
        
        last_cam = Sensor.query.filter(
            Sensor.display_id.like(f"{prefix}_%")
        ).order_by(Sensor.display_id.desc()).first()
        
        last_num = int(last_cam.display_id.split('_')[-1]) if last_cam else 0
        return f"{prefix}_{last_num + 1:03d}"