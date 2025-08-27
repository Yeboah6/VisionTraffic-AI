from app import db
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import re

class Location(db.Model):
    __tablename__ = 'locations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100), nullable=False, index=True) 
    zone = db.Column(db.String(50), nullable=False, index=True)
    priority = db.Column(db.String(20), default='medium', index=True)
    description = db.Column(db.Text)
    location_type = db.Column(db.String(50), default='intersection', index=True)
    
    # Intersection specific
    intersection_type = db.Column(db.String(50))
    pedestrian_crossing = db.Column(db.String(20), default=True)
    bicycle_lanes = db.Column(db.String(20))
    
    # Address
    address = db.Column(db.String(200), index=True)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100), default='Ghana')
    
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    
    # Status and timestamps
    status = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    # Relationship
    signals = db.relationship('Signal', backref='locations', lazy=True)
    cameras = db.relationship('Camera', back_populates='location', lazy=True)
    sensors = db.relationship('Sensor', back_populates='location', lazy=True)
    incidents = db.relationship('Incident', back_populates='location', lazy=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='locations')
    
    def __repr__(self):
        return f'<Location {self.id}: {self.name}>'
    
    @staticmethod
    def generate_location_id(location_name=None):
        """Auto-generates LOC_MAIN_001 format"""
        prefix = "LOC_" + (
            re.sub(r'\W+', '', location_name.split()[0]).upper()[:3] 
            if location_name 
            else "MAIN"
        )
        
        last_loc = Location.query.filter(
            Location.location_id.like(f"{prefix}_%")
        ).order_by(Location.location_id.desc()).first()
        
        last_num = int(last_loc.location_id.split('_')[-1]) if last_loc else 0
        return f"{prefix}_{last_num + 1:03d}"
    
    def toggle_status(self):
        self.status = not self.status
        db.session.commit()
        return self.status
