from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, IntegerField, BooleanField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Optional, Regexp, NumberRange, Length, IPAddress

class CameraForm(FlaskForm):
    #Camera ID
    display_id = StringField('Camera ID', validators=[DataRequired(), Length(max=50)])
    name = StringField('Name', validators=[Length(max=100)])
    address = StringField('Address', validators=[DataRequired()])
    camera_type = SelectField('Camera Type', choices=[
        ('', 'Select....'),
        ('fixed', 'Fixed'),
        ('ptz', 'PTZ'),
        ('traffic light', 'Traffic Light'),
    ], validators=[DataRequired()])
    manufacturer = SelectField('Manufacturer', choices=[
        ('', 'Select brand....'),
        ('hikvision', 'Hikvision'),
        ('dahua', 'Dahua'),
        ('bosch', 'Bosch'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    model_number = StringField('Model Number', validators=[DataRequired(), Length(max=50)])
    
    #Technical Configuration
    resolution = SelectField('Resolution', choices=[
        ('', 'Select Resolution...'),
        ('720p', '720p (HD)'),
        ('1080p', '1080p (Full HD)'),
        ('2k', '2K'),
        ('4k', '4K (UHD)'),
        ('5mp', '5MP'),
        ('8mp', '8MP')
    ],validators=[DataRequired()])
    frame_rate = SelectField('Frame Rate', choices=[
        ('', 'Select FPS...'),
        ('10fps', '10fps'),
        ('15fps', '15fps'),
        ('30fps', '30fps'),
        ('60fps', '60fps'),
    ], validators=[DataRequired()])
    ip_address = StringField('IP Address', validators=[DataRequired(), IPAddress(message='Invalid IP address')])
    stream_protocol = SelectField('Stream Protocol', choices=[
        ('', 'Select protocol...'),
        ('rtsp', 'RTSP'),
        ('rtmp', 'RTMP'),
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
    ], validators=[DataRequired()])
    port = IntegerField('Port', validators=[DataRequired(), NumberRange(min=1, max=65535)])
    stream_path = StringField('Stream Path', validators=[DataRequired(), Length(max=100)])
    rtsp_url = StringField('RTSP Url', validators=[DataRequired()])
    username = StringField('Username', validators=[DataRequired(), Length(max=50)])
    password = StringField('Password', validators=[DataRequired(), Length(max=100)])
    
    #Location Info
    location = SelectField('Location', coerce=str, validators=[DataRequired()])
    direction = SelectField('Direction',choices=[
        ('', 'Select direction.....'),
        ('north', 'Northbound'),
        ('south', 'Southbound'),
        ('east', 'Eastbound'),
        ('west', 'Westbound'),
        ('northeast', 'Northeast'),
        ('northwest', 'Northwest'),
        ('southeast', 'Southeast'),
        ('southwest', 'Southwest')
        ] ,validators=[DataRequired()])
    
    elevation = FloatField('Elevation (m)')

    #Additional Settings
    maintenance = SelectField('Maintenance Schedule', choices=[
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('none', 'None')
    ])
    camera_group = SelectField('Camer Group', choices=[
        ('no group', 'No group'),
        ('downtown', 'Downtown Cameras'),
        ('highway', 'Highway Cameras'),
        ('intersection', 'Intersection Cameras')
    ])
    notes = TextAreaField('Notes')
    is_active = BooleanField('Active Status')