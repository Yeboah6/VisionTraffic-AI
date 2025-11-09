from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..models.user import User
from .. import db
from app.forms.user import RegisterForm, LoginForm
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)

def validate_password(password):
    """Password validation: at least 8 chars, one uppercase, one lowercase, one number"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, ""

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('signal.signals'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        
        if user and user.check_password(password):
            if user.is_active:
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()

                flash(f'Welcome back, {user.username}!', 'success')

                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                if user.is_admin == True:
                    return redirect(url_for('signal.signals'))
                else:
                    return redirect(url_for('user.user_dashboard'))
            else:
                flash('Your account has been deactivated.', 'danger')
        else:
            flash('Invalid username/email or password.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        
        if not email or '@' not in email:
            errors.append('Please provide a valid email address')
        
        if not password:
            errors.append('Password is required')
        else:
            is_valid, msg = validate_password(password)
            if not is_valid:
                errors.append(msg)
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', 
                                 username=username, 
                                 email=email
                                )
        
        # Create new user
        try:
            new_user = User(
                username=username,
                email=email
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Registration error: {str(e)}')
            flash('An error occurred during registration. Please try again.', 'danger')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
