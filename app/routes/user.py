from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
# from ..models.user import User
# from ..models.location import Location
# from app.models.signal import Signal
# from app.forms.signal import SignalForm
from app import db

user_bp = Blueprint('user', __name__)

@user_bp.route('/user')
@login_required
def users():
    now = datetime.now()
    user = current_user
    
    return render_template('user/index.html',
                           user=user,
                           current_date = now.strftime("%B %d, %Y"),
                           current_time = now.strftime("%I:%M %p"),
                        #    users=users  
                        )
    
@user_bp.route('/user/profile')
@login_required
def profile():
    now = datetime.now()
    user = current_user
    
    return render_template('user/profile.html',
                           user=user,
                           current_date = now.strftime("%B %d, %Y"),
                           current_time = now.strftime("%I:%M %p"),
                        #    users=users  
                        )
    
@user_bp.route('/user/settings')
@login_required
def settings():
    now = datetime.now()
    user = current_user
    
    return render_template('user/settings.html',
                           user=user,
                           current_date = now.strftime("%B %d, %Y"),
                           current_time = now.strftime("%I:%M %p"),
                        #    users=users  
                        )