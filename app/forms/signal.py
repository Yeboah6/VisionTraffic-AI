from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional

class SignalForm(FlaskForm):
    id = StringField('Signal ID')
    intersection_name = StringField('Intersection Name')
    address = StringField('Address')
    