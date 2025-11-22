from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from app.models.user import User
from app.extensions import db
from app.forms.user import RegisterForm, LoginForm
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import re
import pyotp

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
            if not user.is_active:
                flash('Your account has been deactivated.', 'danger')
                return render_template('auth/login.html')
            
            # Check if 2FA is enabled
            if user.two_factor_enabled and user.totp_secret:
                # Store user_id in session temporarily for 2FA verification
                session['2fa_user_id'] = user.id
                session['2fa_remember'] = remember
                
                # Return JSON response for AJAX request
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'requires_2fa': True,
                        'message': '2FA verification required'
                    }), 200
                
                # For non-AJAX requests, redirect to 2FA page
                return render_template('auth/login.html', show_2fa=True, username=username)
            else:
                # No 2FA, proceed with normal login
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                db.session.commit()

                flash(f'Welcome back, {user.username}!', 'success')

                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                if user.is_admin:
                    return redirect(url_for('signal.signals'))
                else:
                    return redirect(url_for('user.user_dashboard'))
        else:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Invalid username/email or password.'
                }), 401
            flash('Invalid username/email or password.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/verify-2fa', methods=['POST'])
def verify_2fa_login():
    """Verify 2FA code during login"""
    if current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Already authenticated'}), 400
    
    # Get user_id from session
    user_id = session.get('2fa_user_id')
    if not user_id:
        if request.is_json:
            return jsonify({'success': False, 'message': 'No pending 2FA verification'}), 400
        flash('Session expired. Please login again.', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('2fa_user_id', None)
        session.pop('2fa_remember', None)
        if request.is_json:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        flash('User not found. Please login again.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Get 2FA token from request
    if request.is_json:
        data = request.get_json()
        token = data.get('token', '').strip()
    else:
        token = request.form.get('token', '').strip()
    
    if not token:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Verification code is required',
                'errors': ['Verification code is required']
            }), 400
        flash('Verification code is required', 'danger')
        return render_template('auth/login.html', show_2fa=True)
    
    # Verify the token
    try:
        totp = pyotp.TOTP(user.totp_secret)
        
        if totp.verify(token, valid_window=1):  # Allow 1 step before/after for clock skew
            # 2FA verification successful - complete login
            remember = session.get('2fa_remember', False)
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Clear 2FA session data
            session.pop('2fa_user_id', None)
            session.pop('2fa_remember', None)
            
            if request.is_json:
                redirect_url = url_for('signal.signals') if user.is_admin else url_for('user.user_dashboard')
                return jsonify({
                    'success': True,
                    'message': f'Welcome back, {user.username}!',
                    'redirect_url': redirect_url
                }), 200
            
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.is_admin:
                return redirect(url_for('signal.signals'))
            else:
                return redirect(url_for('user.user_dashboard'))
        else:
            # Invalid token
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Invalid verification code',
                    'errors': ['Invalid or expired code. Please try again.']
                }), 400
            flash('Invalid verification code. Please try again.', 'danger')
            return render_template('auth/login.html', show_2fa=True)
            
    except Exception as e:
        current_app.logger.error(f'2FA verification error: {str(e)}')
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Verification failed',
                'error': str(e)
            }), 500
        flash('Verification failed. Please try again.', 'danger')
        return render_template('auth/login.html', show_2fa=True)


@auth_bp.route('/cancel-2fa', methods=['POST'])
def cancel_2fa():
    """Cancel 2FA verification and return to login"""
    session.pop('2fa_user_id', None)
    session.pop('2fa_remember', None)
    
    if request.is_json:
        return jsonify({'success': True, 'message': '2FA cancelled'}), 200
    
    return redirect(url_for('auth.login'))

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
