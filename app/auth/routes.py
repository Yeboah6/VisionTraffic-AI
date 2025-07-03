# from app.auth import auth_bp
from flask import Blueprint, render_template

auth_bp = Blueprint('auth', __name__, template_folder='templates')

@auth_bp.route('/')
def login():
    return render_template('auth/login.html')