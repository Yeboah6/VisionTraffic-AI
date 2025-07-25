from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/camera')
@jwt_required_redirect
def camera():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('camera/camera.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )
    
@camera_bp.route('/add/camera')
@jwt_required_redirect
def addCamera():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('camera/add.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )