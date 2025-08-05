from app import db
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime

class Signal(db.Model):
    __tablename__ = 'signals'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intersection_name = db.Column(db.String(100), nullable=False, index=True)
    
    #Location
    