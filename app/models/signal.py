from datetime import datetime
from app import db
import re
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Signal(db.Model):
    __tablename__ = 'signals'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_id = db.Column(db.String(50), unique=True)  # SIG_MAIN_001
    name = db.Column(db.String(100))
    address = db.Column(db.String(50), nullable=False)
    
    direction = db.Column(db.String(20), nullable=False)
    controller_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(15))
    protocol = db.Column(db.String(20), nullable=False)
    port = db.Column(db.Integer)
    
    default_cycle = db.Column(db.Integer, nullable=False)
    phases = db.Column(db.Integer, nullable=False)
    movement_description = db.Column(db.Text, nullable=False)
    min_duration = db.Column(db.Integer, nullable=False)
    max_duration = db.Column(db.Integer, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    location_id = db.Column(db.UUID(36), db.ForeignKey('locations.id'))
    location = db.relationship('Location', back_populates='signals')
    
    cameras = db.relationship('Camera', backref='signal', lazy=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator = db.relationship('User', backref='signals')

    @staticmethod
    def generate_id(name=None):
        """Auto-generates SIG_PREFIX_XXX format"""
        prefix = "SIG_" + (
            re.sub(r'\\W+', '', name.split()[0]).upper()[:4] 
            if name 
            else "UNK"
        )
        
        last_signal = Signal.query.filter(
            Signal.display_id.like(f"{prefix}_%")
        ).order_by(Signal.display_id.desc()).first()
        
        last_num = int(last_signal.display_id.split('_')[-1]) if last_signal else 0
        return f"{prefix}_{last_num + 1:03d}"
    
    def toggle_status(self):
        self.is_active = not self.is_active
        db.session.commit()
        return self.is_active