from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime

# Models
from ..models.user import User
from app.models.traffic_light import TrafficLightConfig
from ..models.incident import Incident

signal_bp = Blueprint('signal', __name__)

@signal_bp.route('/signals')
@login_required
def signals():
    now = datetime.now()
    user = current_user
    signals = TrafficLightConfig.query.all()
    
    incidents = Incident.query.filter(
    Incident.status.in_(['reported', 'investigating', 'in_progress'])
    ).order_by(Incident.created_at.desc()).limit(5).all()
    
    return render_template('signals/signal.html',
                           user=user,
                           current_date = now.strftime("%B %d, %Y"),
                           current_time = now.strftime("%I:%M %p"),
                           signals=signals,
                           incidents=incidents,
                        )

@signal_bp.route('/signals/list')
@login_required
def list():
    now = datetime.now()
    user = current_user
    signals = TrafficLightConfig.query.order_by(TrafficLightConfig.id).all()
    return render_template('signals/list.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           signals=signals
                        )    

@signal_bp.route('/signals/<string:id>')
@login_required
def view(id):
    now = datetime.now()
    user = current_user
    signal = TrafficLightConfig.query.get_or_404(str(id))
    
    return render_template('signals/view.html', 
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           signal=signal
                        )
