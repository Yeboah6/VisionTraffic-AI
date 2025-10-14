from datetime import datetime
from app.extensions import db
import re
import json
import uuid

class Incident(db.Model):
    __tablename__ = 'incidents'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id = db.Column(db.String(80), unique = True, nullable = False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    media_files = db.Column(db.Text, default='[]')
    status = db.Column(db.String(50), default='reported')  # reported, investigating, in_progress, resolved
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    creator = db.relationship('User', backref='incidents')
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location_rel = db.relationship('Location', backref='incidents')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'incident_id': self.incident_id,
            'description': self.description,
            'location_id': self.location_rel.id if self.location_rel else None,
            'type': self.type,
            'address':self.address,
            'severity': self.severity,
            'media_files': self.get_media_files(),
            'status': self.status,
            'updated_at': self.updated_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id,
            'creator': self.creator.username if self.creator else None
        }
        
    @property
    def media_files_list(self):
        """Property to easily access media files as list"""
        return self.get_media_files()
        
    def get_media_files(self):
        """Get media files as Python list - ENSURES ISOLATION"""
        if self.media_files:
            try:
                # Ensure we're working with this incident's data only
                clean_json = self.media_files.strip().replace(' ', '')
                if clean_json and clean_json != '[]':
                    parsed = json.loads(clean_json)
                    # Ensure we return a new list to prevent cross-contamination
                    return list(parsed) if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"❌ JSON decode error for incident {self.id}: {e}")
        return []  # Always return a new empty list
    
    def set_media_files(self, files_list):
        """Set media files from Python list - ENSURES ISOLATION"""
        if files_list and isinstance(files_list, list):
            # Create a new list to prevent reference issues
            clean_list = [str(item).strip() for item in files_list if item]
            self.media_files = json.dumps(clean_list, separators=(',', ':'))
        else:
            self.media_files = '[]'  # Explicit empty array
    
    def clear_media_files(self):
        """Explicitly clear media files for this incident"""
        self.media_files = '[]'
        
    def add_media_file(self, filename):
        """Add a single media file"""
        current_files = self.get_media_files()
        current_files.append(filename)
        self.set_media_files(current_files)
            
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

        # Format the number with leading zeros (3 digits)
        formatted_number = f"{next_number:03d}"
        
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