from flask import Blueprint, render_template, request

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard/index.html')

@main_bp.route('/map')
def trafficMap():
    return render_template('dashboard/map.html')