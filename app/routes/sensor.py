from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User

sensor_bp = Blueprint('sensor', __name__)

@sensor_bp.route('/sensor')
@jwt_required_redirect
def sensor():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('sensor/sensor.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )
    
@sensor_bp.route('/add/sensor')
@jwt_required_redirect
def addSensor():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('sensor/add.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )