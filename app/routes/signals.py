from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User

signal_bp = Blueprint('signal', __name__)

@signal_bp.route('/signals')
@jwt_required_redirect
def signals():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    
    # Fetch signals from the database (assuming a Signal model exists)
    # signals = Signal.query.all()  # Uncomment and modify as per your model
    
    return render_template('signals/signal.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p")
                           # signals=signals  # Uncomment if you have signals to display
                           )
    
@signal_bp.route('/signal/manage')
@jwt_required_redirect
def signalManage():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('signals/add.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )