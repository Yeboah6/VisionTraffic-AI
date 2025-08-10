from app import db
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime

class Location(db.Model):
    __tablename__ = 'locations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(100), nullable=False, index=True)
    zone = db.Column(db.String(50), nullable=False, index=True)
    priority = db.Column(db.String(20), default='medium', index=True)
    description = db.Column(db.Text)
    location_type = db.Column(db.String(50), default='intersection', index=True)
    
    # Intersection specific
    intersection_type = db.Column(db.String(50))
    pedestrian_crossing = db.Column(db.Boolean, default=True)
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
    status = db.Column(db.String(20), default='pending', index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='locations')
    
    # Relationship
    signals = db.relationship('Signal', backref='locations', lazy=True)
    
    def __repr__(self):
        return f'<Location {self.id}: {self.name}>'
