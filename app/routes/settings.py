from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime

from ..models.user import User

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def settings():
    # now = datetime.now()
    user = current_user
    
    return render_template('settings/index.html',
                           user=user
                           )