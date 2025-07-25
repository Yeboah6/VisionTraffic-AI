from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User

incident_bp = Blueprint('incident', __name__)

@incident_bp.route('/incident')
@jwt_required()
def incident():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    
    # Fetch locations from the database (assuming a Location model exists)
    # locations = Location.query.all()  # Uncomment and modify as per your model
    
    return render_template('incidents/incident.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p")
                           # locations=locations  # Uncomment if you have locations to display
                           )
    
@incident_bp.route('/incident/add')
@jwt_required_redirect
def add_incident():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    
    # Logic to handle adding an incident can be added here
    
    return render_template('incidents/add.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p")
                           )