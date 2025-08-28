from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required,current_user
from datetime import datetime
from ..models.user import User

report_bp = Blueprint('report', __name__)


@report_bp.route('/report')
@login_required
def report():
    now = datetime.now()
    user = current_user
    return render_template('report/report.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )