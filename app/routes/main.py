from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User
from ..models.incident import Incident
from ..models.traffic_light import TrafficPattern

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    now = datetime.now()
    user = current_user
    
    incidents = Incident.query.filter(
    Incident.status.in_(['reported', 'investigating', 'in_progress'])
    ).order_by(Incident.created_at.desc()).limit(5).all()

    traffic_patterns = TrafficPattern.query.all()

    return render_template('dashboard/index.html', 
                       user = user,
                       current_date = now.strftime("%B %d, %Y"), 
                       current_time = now.strftime("%I:%M %p"),
                       incidents = incidents,
                       traffic_patterns = traffic_patterns
                    )
