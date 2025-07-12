from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
# @jwt_required()
@jwt_required_redirect
def dashboard():
    now = datetime.now()
    # Get the current user's identity from the JWT
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    # Get JWT data to check expiration client-side
    # jwt_data = get_jwt()
    # expires_at = jwt_data['exp']
    return render_template('dashboard/index.html', 
                       user = user, 
                       current_date = now.strftime("%B %d, %Y"), 
                       current_time = now.strftime("%I:%M %p"),
                    #    token_expires=expires_at
                    )

@main_bp.route('/location')
@jwt_required_redirect
def location():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/location.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )
    
    
@main_bp.route('/add/location')
@jwt_required_redirect
def addLocation():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/add-location.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/signal')
@jwt_required_redirect
def signalControl():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/signal.html', 
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/signal/manage')
@jwt_required_redirect
def signalManage():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/signal-manage.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/report')
def report():
    return render_template('dashboard/report.html')

@main_bp.route('/camera')
@jwt_required_redirect
def camera():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/camera.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/add/camera')
@jwt_required_redirect
def addCamera():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/add-cameras.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/incident')

@jwt_required_redirect
def incident():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/incident.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/incident/add')
@jwt_required_redirect
def addIncident():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/add-incident.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/settings')
@jwt_required_redirect
def settings():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/settings.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )