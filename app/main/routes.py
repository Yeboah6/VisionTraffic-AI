from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard/index.html')

@main_bp.route('/dashboard2')
def dashboard2():
    return render_template('base2.html')