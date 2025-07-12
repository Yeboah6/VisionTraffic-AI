from .. import db

class Incident(db.Model):
    __table__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.String(80), unique = True, nullable = False)