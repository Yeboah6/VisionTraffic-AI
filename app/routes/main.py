from flask import Blueprint, render_template, request

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard/index.html')

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