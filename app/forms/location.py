from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional

class LocationForm(FlaskForm):
    name = StringField('Location Name', validators=[DataRequired()])
    id = StringField('Location ID')
    zone = SelectField('Zone/District', choices=[
        ('downtown', 'Downtown'),
        ('north', 'North District'),
        ('south', 'South District'),
        ('east', 'East District'),
        ('west', 'West District')
    ], validators=[DataRequired()])
    priority = SelectField('Priority Level', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], default='medium')
    description = TextAreaField('Description')
    
    # Intersection specific
    intersection_type = SelectField('Intersection Type', choices=[
        ('standard', 'Standard 4-way'),
        ('t-intersection', 'T-intersection'),
        ('y-intersection', 'Y-intersection'),
        ('roundabout', 'Roundabout')
    ], default='standard')
    pedestrian_crossing = SelectField('Pedestrian Crossing', 
                                    choices=[('yes', 'Yes'), ('no', 'No')],
                                    validators=[DataRequired()])
    bicycle_lanes = SelectField('Bicycle Lanes', 
                                    choices=[('yes', 'Yes'), ('no', 'No')],
                                    validators=[DataRequired()])
    
    # Address
    address = StringField('Street Address')
    city = StringField('City')
    state = StringField('State/Province')
    postal_code = StringField('ZIP/Postal Code')
    country = StringField('Country', default='Ghana')
    
    # Coordinates
    lat = FloatField('Latitude', validators=[DataRequired()])
    lng = FloatField('Longitude', validators=[DataRequired()])
    submit = SubmitField('Save Location')