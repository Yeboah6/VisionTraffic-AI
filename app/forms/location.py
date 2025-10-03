from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional

class LocationForm(FlaskForm):
    name = StringField('Location Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    city = StringField('City')
    region = StringField('Region/State')
    country = StringField('Country', default='Ghana')
    # Coordinates
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    submit = SubmitField('Save Location')