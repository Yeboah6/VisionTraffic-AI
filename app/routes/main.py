from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/dashboard')
# @jwt_required()
@login_required
def dashboard():
    now = datetime.now()
    user = current_user
    return render_template('dashboard/index.html', 
                       user = user,
                       current_date = now.strftime("%B %d, %Y"), 
                       current_time = now.strftime("%I:%M %p")
                    )

@main_bp.route('/report')
@login_required
def report():
    now = datetime.now()
    user = current_user
    return render_template('dashboard/report.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@main_bp.route('/settings')
@login_required
def settings():
    now = datetime.now()
    user = current_user
    return render_template('dashboard/settings.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )