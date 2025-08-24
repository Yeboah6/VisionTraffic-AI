from .. import db
from datetime import datetime
import re
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Incident(db.Model):
    __tablename__ = 'incidents'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = db.Column(db.String(80), unique = True, nullable = False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location_type = db.Column(db.String(50), nullable=False)
    lanes_affected = db.Column(db.String(50), nullable=False)
    estimated_delay = db.Column(db.String(50), nullable=False)
    emergency_services = db.Column(db.String(50))
    vehicles_involved = db.Column(db.Integer)
    injuries_reported = db.Column(db.String(50))
    reporter_type = db.Column(db.String(50))
    reporter_info = db.Column(db.String(100))
    internal_notes = db.Column(db.Text)
    media_files = db.Column(db.Text)  # Comma-separated filenames
    status = db.Column(db.String(20), default='reported')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    location_id = db.Column(db.UUID(36), db.ForeignKey('locations.id'))
    location = db.relationship('Location', back_populates='incidents')
    
        
    @classmethod
    def generate_id(cls, type=None):
        # Get current year
        current_year = datetime.now().year
        
        # Get the highest incident number for this year
        latest_incident = cls.query.filter(
            cls.incident_id.like(f'INC-{current_year}-%')
        ).order_by(cls.incident_id.desc()).first()
        
        if latest_incident:
            # Extract the number part from the latest incident ID
            match = re.search(r'INC-\d{4}-(\d+)', latest_incident.incident_id)
            if match:
                next_number = int(match.group(1)) + 1
            else:
                next_number = 1
        else:
            next_number = 1
        
        # Format the number with leading zeros (5 digits)
        formatted_number = f"{next_number:05d}"
        
        return f"INC-{current_year}-{formatted_number}"
    
    @classmethod
    def generate_unknown_id(cls):
        """Generate ID for incidents without intersection data"""
        current_year = datetime.now().year
        
        # Get the highest UNK incident number for this year
        latest_unknown = cls.query.filter(
            cls.incident_id.like(f'INC-{current_year}-UNK-%')
        ).order_by(cls.incident_id.desc()).first()
        
        if latest_unknown:
            # Extract the number part
            match = re.search(r'INC-\d{4}-UNK-(\d+)', latest_unknown.incident_id)
            if match:
                next_number = int(match.group(1)) + 1
            else:
                next_number = 1
        else:
            next_number = 1
        
        formatted_number = f"{next_number:03d}"
        return f"INC-{current_year}-UNK-{formatted_number}"