# app/forms/incident.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, MultipleFileField, SubmitField
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models.location import Location
from wtforms.validators import DataRequired, Optional

class IncidentForm(FlaskForm):
    incident_id = StringField('Incident ID')
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
        ], default="reported")
    description = TextAreaField('Detailed Description', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])

    media = MultipleFileField('Upload Evidence', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'mp4', 'mov', 'pdf', 'mp3'], 
                   'Only images, videos, and PDF files are allowed')
    ])
    location = SelectField('Location', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Submit Incident')