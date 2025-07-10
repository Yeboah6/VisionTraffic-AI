from flask import Blueprint, render_template, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.middleware.jwt_middleware import jwt_required_redirect
from ..models.user import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
# @jwt_required()
@jwt_required_redirect
def dashboard():
    # Get the current user's identity from the JWT
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    return render_template('dashboard/index.html', user=user)

@main_bp.route('/map')
def trafficMap():
    return render_template('dashboard/map.html')

@main_bp.route('/signal')
def signalControl():
    return render_template('dashboard/signal.html')

@main_bp.route('/signal/manage')
def signalManage():
    return render_template('dashboard/signal-manage.html')

@main_bp.route('/report')
def report():
    return render_template('dashboard/report.html')

@main_bp.route('/camera')
def camera():
    return render_template('dashboard/camera.html')

@main_bp.route('/add/camera')
def addCamera():
    return render_template('dashboard/add-cameras.html')

@main_bp.route('/incident')
def incident():
    return render_template('dashboard/incident.html')

@main_bp.route('/incident/add')
def addIncident():
    return render_template('dashboard/add-incident.html')

@main_bp.route('/settings')
def settings():
    return render_template('dashboard/settings.html')