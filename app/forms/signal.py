from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Optional, Regexp, NumberRange

class SignalForm(FlaskForm):
    display_id = StringField('Signal ID', validators=[
        DataRequired(),
    ])
    
    intersection_name = StringField('Intersection Name')
    location_id = SelectField('Location Name', coerce=str, validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    
    direction = SelectField('Direction', choices=[
        ('northbound', 'Northbound'),
        ('southbound', 'Southbound'),
        ('eastbound', 'Eastbound'),
        ('westbound', 'Westbound')
    ], validators=[DataRequired()])
    
    # Technical Configuration
    controller_type = SelectField('Controller Type', choices=[
        ('ntcip', 'NTCIP'),
        ('scats', 'SCATS'),
        ('siemens', 'Siemens'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    
    ip_address = StringField('IP Address')
    protocol = SelectField('Protocol', choices=[
        ('tcp_ip', 'TCP/IP'),
        ('rs485', 'RS-485'),
        ('wireless', 'Wireless')
    ], validators=[DataRequired()])
    
    default_cycle = IntegerField('Default Cycle (seconds)', 
                               validators=[DataRequired(), NumberRange(min=30, max=300)])
    
    phases = IntegerField('Phases', 
                         validators=[DataRequired(), NumberRange(min=2, max=8)])
    is_active = BooleanField('Active Status')