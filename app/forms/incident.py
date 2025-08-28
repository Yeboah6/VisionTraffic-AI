# app/forms/incident.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, IntegerField, MultipleFileField
# from wtforms.ext.sqlalchemy.fields import QuerySelectField
# from ..models.location import Location
from wtforms.validators import DataRequired, Optional

class IncidentForm(FlaskForm):
    incident_id = StringField('Incident ID', validators=[DataRequired()])
    type = SelectField('Incident Type', choices=[
        ('', 'Select type...'),
        ('accident', 'Accident'),
        ('congestion', 'Traffic Congestion'),
        ('roadwork', 'Roadwork'),
        ('weather', 'Weather Hazard'),
        ('disabled', 'Disabled Vehicle'),
        ('hazard', 'Road Hazard'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    
    severity = SelectField('Severity Level', choices=[
        ('', 'Select severity...'),
        ('critical', 'Critical (Emergency)'),
        ('major', 'Major (Severe Impact)'),
        ('moderate', 'Moderate'),
        ('minor', 'Minor')
    ], validators=[DataRequired()])
    
    title = StringField('Title', validators=[DataRequired()])
    status = SelectField('Status', choices=[
        ('', 'Select Status'),
        ('reported', 'Reported'),   
        ('in_progress', 'In Progress'), 
        ('resolved', 'Resolved'),   
        ('closed', 'Closed')
        ], validators=[DataRequired()])
    description = TextAreaField('Detailed Description', validators=[DataRequired()])
    location = SelectField('Specific Location', coerce=str, validators=[DataRequired()])
    location_type = SelectField('Location Type', choices=[
        ('', 'Select location type...'),
        ('intersection', 'Intersection'),
        ('highway', 'Highway/Freeway'),
        ('city_street', 'City Street'),
        ('residential', 'Residential Area'),
        ('bridge', 'Bridge'),
        ('parking_lot', 'Parking Lot')
    ], validators=[DataRequired()])
    
    lanes_affected = SelectField('Lanes Affected', choices=[
        ('', 'Select lanes...'),
        ('1', '1 lane'),
        ('2', '2 lanes'),
        ('3+', '3+ lanes'),
        ('all', 'All lanes'),
        ('shoulder', 'Shoulder only'),
        ('unknown', 'Unknown')
    ], validators=[DataRequired()])
    
    estimated_delay = SelectField('Estimated Delay', choices=[
        ('', 'Select delay...'),
        ('none', 'No significant delay'),
        ('5-15', '5-15 minutes'),
        ('15-30', '15-30 minutes'),
        ('30-60', '30-60 minutes'),
        ('60+', '60+ minutes'),
        ('unknown', 'Unknown')
    ], validators=[DataRequired()])
    
    emergency_services = SelectField('Emergency Services', choices=[
        ('', 'Select if applicable...'),
        ('police', 'Police on scene'),
        ('ambulance', 'Ambulance on scene'),
        ('fire', 'Fire department on scene'),
        ('multiple', 'Multiple services'),
        ('requesting', 'Requesting services')
    ], validators=[Optional()])
    
    vehicles_involved = IntegerField('Vehicles Involved', validators=[Optional()])
    injuries_reported = SelectField('Injuries Reported', choices=[
        ('', 'Select if applicable...'),
        ('none', 'No injuries'),
        ('minor', 'Minor injuries'),
        ('serious', 'Serious injuries'),
        ('fatal', 'Fatalities'),
        ('unknown', 'Unknown')
    ], validators=[Optional()])
    
    reporter_type = SelectField('Reporter Information', choices=[
        ('operator', 'Traffic Operator (Current User)'),
        ('police', 'Police Department'),
        ('public', 'Public Report'),
        ('ai', 'AI Detection System'),
        ('other', 'Other')
    ], validators=[Optional()])
    
    reporter_info = StringField('Reporter Details', validators=[Optional()])
    internal_notes = TextAreaField('Additional Notes', validators=[Optional()])
    media = MultipleFileField('Upload Evidence', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'mp4', 'mov', 'pdf', 'mp3'], 
                   'Only images, videos, and PDF files are allowed')
    ])
