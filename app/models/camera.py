from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
import re

class Camera(db.Model):
    __tablename__ = 'cameras'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_id = db.Column(db.String(50), unique=True) #CAM_MAIN_001
    name = db.Column(db.String(100), nullable=False, index=True)
    camera_type = db.Column(db.String(50), nullable=False)
    manufacturer = db.Column(db.String(50), nullable=False)
    model_number = db.Column(db.String(50), nullable=False)
    resolution = db.Column(db.String(20), nullable=False)
    frame_rate = db.Column(db.String(10), nullable=False)
    ip_address = db.Column(db.String(15), nullable=False)
    stream_protocol = db.Column(db.String(10), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    stream_url_path = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Should be encrypted in production
    direction = db.Column(db.String(20))
    elevation = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    maintenance = db.Column(db.String(50))  # or another appropriate type
    camera_group = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    
    # Relationships
    location_id = db.Column(db.UUID(36), db.ForeignKey('locations.id'))
    location = db.relationship('Location', back_populates='cameras')
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='cameras')
    
    signal_id = db.Column(db.UUID(50), db.ForeignKey('signals.id'))
    
    @staticmethod
    def generate_display_id(location_name=None):
        """Auto-generates CAM_LOC_001 format"""
        prefix = "CAM_" + (
            re.sub(r'\W+', '', location_name.split()[0]).upper()[:3] 
            if location_name 
            else "UNK"
        )
        
        last_cam = Camera.query.filter(
            Camera.display_id.like(f"{prefix}_%")
        ).order_by(Camera.display_id.desc()).first()
        
        last_num = int(last_cam.display_id.split('_')[-1]) if last_cam else 0
        return f"{prefix}_{last_num + 1:03d}"
    
    def toggle_status(self):
        self.is_active = not self.is_active
        db.session.commit()
        return self.is_active