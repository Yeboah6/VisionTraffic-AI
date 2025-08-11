from datetime import datetime
from app import db
import re

class Signal(db.Model):
    __tablename__ = 'signals'

    id = db.Column(db.String(50), primary_key=True)  # SIG_MAIN_001
    intersection_name = db.Column(db.String(100))
    
    direction = db.Column(db.String(20), nullable=False)
    controller_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(15))
    protocol = db.Column(db.String(20), nullable=False)
    default_cycle = db.Column(db.Integer, nullable=False)
    phases = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    location_id = db.Column(db.UUID, db.ForeignKey('locations.id'), nullable=False)
    address = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    cameras = db.relationship('Camera', backref='signal', lazy=True)

    @staticmethod
    def generate_id(intersection_name=None):
        """Auto-generates SIG_PREFIX_XXX format"""
        prefix = "SIG_" + (
            re.sub(r'\\W+', '', intersection_name.split()[0]).upper()[:4] 
            if intersection_name 
            else "UNK"
        )
        
        last_signal = Signal.query.filter(
            Signal.id.like(f"{prefix}_%")
        ).order_by(Signal.id.desc()).first()
        
        last_num = int(last_signal.id.split('_')[-1]) if last_signal else 0
        return f"{prefix}_{last_num + 1:03d}"
    
    def toggle_status(self):
        self.is_active = not self.is_active
        db.session.commit()
        return self.is_active