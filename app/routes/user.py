from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User
from ..models.incident import Incident

user_bp = Blueprint('user', __name__)

@user_bp.route('/user/dashboard')
@login_required
def user_dashboard():
    user=current_user
    now = datetime.now()
    
    incidents = Incident.query.filter(
    Incident.status.in_(['reported', 'investigating', 'in_progress'])
    ).order_by(Incident.created_at.desc()).limit(5).all()
    return render_template('users/index.html', 
                       user = user,
                       current_date = now.strftime("%B %d, %Y"), 
                       current_time = now.strftime("%I:%M %p"),
                       incidents = incidents
                    )
    
@user_bp.route('/user/incident/details/<string:id>')
@login_required
def incident_details(id):
    user = current_user
    incident = Incident.query.get_or_404(id)
    return render_template('users/view.html', 
                           user=user, 
                           incident=incident
                           )
    
@user_bp.route('/user/profile')
@login_required
def user_profile():
    user = current_user
    return render_template('users/profile.html', user=user)

@user_bp.route('/user/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    user = current_user
    if request.method == 'POST':
        # Handle form submission for updating user settings
        pass
    return render_template('users/settings.html', user=user)