from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Optional, Regexp, NumberRange

class SignalForm(FlaskForm):
    display_id = StringField('Signal ID',)
    
    name = StringField('Name')
    location_id = SelectField('Location Name', coerce=str, validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    
    direction = SelectField('Direction', choices=[
        ('northbound', 'Northbound'),
        ('southbound', 'Southbound'),
        ('eastbound', 'Eastbound'),
        ('westbound', 'Westbound')
    ], validators=[DataRequired()])
    
    intersection_type = SelectField('Intersection Type', choices=[
    ('standard', 'Standard 4-way'),
    ('t-intersection', 'T-intersection'),
    ('y-intersection', 'Y-intersection'),
    ('roundabout', 'Roundabout')
    ], default='standard')
    
    # Technical Configuration
    controller_type = SelectField('Controller Type', choices=[
        ('scats', 'SCATS'),
        ('siemens', 'Siemens'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    
    ip_address = StringField('IP Address')
    protocol = SelectField('Protocol', choices=[
        ('ntcip', 'NTCIP'),
        ('tcp_ip', 'TCP/IP'),
        ('rs485', 'RS-485'),
        ('wireless', 'Wireless')
    ], validators=[DataRequired()])
    port = IntegerField('Port', validators=[DataRequired()])
    
    #Movement Configuration
    phases = IntegerField('Phases', 
                         validators=[DataRequired(), NumberRange(min=2, max=8)])
    default_cycle = IntegerField('Default Cycle (seconds)', 
                               validators=[DataRequired(), NumberRange(min=30)])
    movement_description = StringField('Movement Description', validators=[DataRequired()])
    min_duration = IntegerField('Min Duration', validators=[DataRequired(), NumberRange(min=10)])
    max_duration = IntegerField('Max Duration', validators=[DataRequired(), NumberRange(min=60)])
    is_active = BooleanField('Active Status')