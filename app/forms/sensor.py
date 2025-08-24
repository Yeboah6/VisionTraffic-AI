from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, IntegerField, BooleanField, TextAreaField, DateField
from wtforms.validators import DataRequired, Optional, Regexp, NumberRange, Length, IPAddress
from datetime import date

class SensorForm(FlaskForm):
    display_id = StringField('Sensor ID', validators=[DataRequired(), Length(max=50)])
    sensor_type = SelectField('Sensor Type', choices=[
        ('inductive loop', 'Inductive Loop'),
        ('radar', 'Radar'),
        ('lidar', 'LiDAR'),
        ('video detection', 'Video Setection')
    ], validators=[DataRequired()])
    lanes_monitored = IntegerField('Lanes Monitored', validators=[DataRequired(), NumberRange(min=1, max=8)])
    direction = SelectField('Direction', choices=[
        ('', 'Select direction...'),
        ('north', 'Northbound'),
        ('south', 'Southbound'),
        ('east', 'Eastbound'),
        ('west', 'Westbound'),
        ('all', 'All Directions')
        ], validators=[DataRequired()])
    installation_date = DateField('Installation Date', default=date.today, format='%Y-%m-%d')
    installation_notes = TextAreaField('Installation Notes')
    location = SelectField('Location', coerce=str, validators=[DataRequired()])
    is_active = BooleanField('Active Status')