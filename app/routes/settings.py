from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
import re
import pyotp
import qrcode
import io
import base64

from ..models.user import User

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def settings():
    # now = datetime.now()
    user = current_user
    teams = User.query.all()
    
    return render_template('settings/index.html',
                           user=user,
                           teams=teams
                           )
    
def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

@settings_bp.route('/add-team-member', methods=['POST'])
@login_required
def add_team_member():
    """
    Add a new team member
    Requires admin privileges
    """
    # Check if user is admin
    if not current_user.is_admin:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Unauthorized. Admin privileges required.'
            }), 403
        flash('Unauthorized. Admin privileges required.', 'error')
        return redirect(url_for('main.settings'))
    
    # Get data from request
    if request.is_json:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', 'Emergency Operator').strip()
        password = data.get('password', '')
    else:
        username = request.form.get('member-name', '').strip()
        email = request.form.get('member-email', '').strip()
        role = request.form.get('member-role', 'Emergency Operator').strip()
        password = request.form.get('member-password', '')
    
    # Validation
    errors = []
    
    if not username:
        errors.append('Username is required')
    elif len(username) < 3:
        errors.append('Username must be at least 3 characters long')
    elif len(username) > 64:
        errors.append('Username must not exceed 64 characters')
    
    if not email:
        errors.append('Email is required')
    elif not validate_email(email):
        errors.append('Invalid email format')
    
    if not password:
        errors.append('Password is required')
    else:
        is_valid, message = validate_password(password)
        if not is_valid:
            errors.append(message)
    
    if not role:
        errors.append('Role is required')
    
    # Check if username already exists
    if username and User.query.filter_by(username=username).first():
        errors.append('Username already exists')
    
    # Check if email already exists
    if email and User.query.filter_by(email=email).first():
        errors.append('Email already exists')
    
    if errors:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('main.settings'))
    
    try:
        # Create new user
        new_user = User(
            username=username,
            email=email,
            role=role,
            is_admin=(role.lower() == 'admin'),
            is_active=True
        )
        new_user.set_password(password)
        
        # Add to database
        db.session.add(new_user)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Team member {username} added successfully',
                'user': {
                    'id': new_user.id,
                    'username': new_user.username,
                    'email': new_user.email,
                    'role': new_user.role,
                    'is_admin': new_user.is_admin,
                    'created_at': new_user.created_at.isoformat() if new_user.created_at else None
                }
            }), 201
        
        flash(f'Team member {username} added successfully', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to add team member',
                'error': str(e)
            }), 500
        flash('Failed to add team member. Please try again.', 'error')
        return redirect(url_for('main.settings'))


@settings_bp.route('/remove-team-member/<int:user_id>', methods=['DELETE', 'POST'])
@login_required
def remove_team_member(user_id):
    """
    Remove a team member
    Requires admin privileges
    """
    # Check if user is admin
    if not current_user.is_admin:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Unauthorized. Admin privileges required.'
            }), 403
        flash('Unauthorized. Admin privileges required.', 'error')
        return redirect(url_for('main.settings'))
    
    # Prevent self-deletion
    if user_id == current_user.id:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Cannot remove yourself from the team'
            }), 400
        flash('Cannot remove yourself from the team', 'error')
        return redirect(url_for('main.settings'))
    
    try:
        user = User.query.get(user_id)
        if not user:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'User not found'
                }), 404
            flash('User not found', 'error')
            return redirect(url_for('main.settings'))
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Team member {username} removed successfully'
            }), 200
        
        flash(f'Team member {username} removed successfully', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to remove team member',
                'error': str(e)
            }), 500
        flash('Failed to remove team member. Please try again.', 'error')
        return redirect(url_for('main.settings'))


@settings_bp.route('/update-team-member/<int:user_id>', methods=['PUT', 'POST'])
@login_required
def update_team_member(user_id):
    """
    Update a team member's role
    Requires admin privileges
    """
    # Check if user is admin
    if not current_user.is_admin:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Unauthorized. Admin privileges required.'
            }), 403
        flash('Unauthorized. Admin privileges required.', 'error')
        return redirect(url_for('main.settings'))
    
    try:
        user = User.query.get(user_id)
        if not user:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'User not found'
                }), 404
            flash('User not found', 'error')
            return redirect(url_for('main.settings'))
        
        # Get new role
        if request.is_json:
            data = request.get_json()
            new_role = data.get('role', '').strip()
        else:
            new_role = request.form.get('role', '').strip()
        
        if not new_role:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Role is required'
                }), 400
            flash('Role is required', 'error')
            return redirect(url_for('main.settings'))
        
        user.role = new_role
        user.is_admin = (new_role.lower() == 'admin')
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Team member {user.username} updated successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'is_admin': user.is_admin
                }
            }), 200
        
        flash(f'Team member {user.username} updated successfully', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to update team member',
                'error': str(e)
            }), 500
        flash('Failed to update team member. Please try again.', 'error')
        return redirect(url_for('main.settings'))


#####################################

@settings_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """
    Change user password
    Requires current password for verification
    """
    # Get data from request
    if request.is_json:
        data = request.get_json()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
    else:
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
    
    # Validation
    errors = []
    
    if not current_password:
        errors.append('Current password is required')
    elif not current_user.check_password(current_password):
        errors.append('Current password is incorrect')
    
    if not new_password:
        errors.append('New password is required')
    else:
        is_valid, message = validate_password(new_password)
        if not is_valid:
            errors.append(message)
    
    # Check if new password is same as current
    if current_password and new_password and current_password == new_password:
        errors.append('New password must be different from current password')
    
    if errors:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('main.settings'))
    
    try:
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Password changed successfully'
            }), 200
        
        flash('Password changed successfully', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to change password',
                'error': str(e)
            }), 500
        flash('Failed to change password. Please try again.', 'error')
        return redirect(url_for('main.settings'))


@settings_bp.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    """
    Update user profile information (username and email)
    """
    # Get data from request
    if request.is_json:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
    else:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
    
    # Validation
    errors = []
    
    if not username:
        errors.append('Username is required')
    elif len(username) < 3:
        errors.append('Username must be at least 3 characters long')
    elif len(username) > 64:
        errors.append('Username must not exceed 64 characters')
    
    if not email:
        errors.append('Email is required')
    elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        errors.append('Invalid email format')
    
    # Check if username already exists (excluding current user)
    if username and username != current_user.username:
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            errors.append('Username already exists')
    
    # Check if email already exists (excluding current user)
    if email and email != current_user.email:
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            errors.append('Email already exists')
    
    if errors:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('main.settings'))
    
    try:
        # Update profile
        current_user.username = username
        current_user.email = email
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Profile updated successfully',
                'user': {
                    'username': current_user.username,
                    'email': current_user.email
                }
            }), 200
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to update profile',
                'error': str(e)
            }), 500
        flash('Failed to update profile. Please try again.', 'error')
        return redirect(url_for('main.settings'))


@settings_bp.route('/setup-2fa', methods=['POST'])
@login_required
def setup_2fa():
    """
    Generate 2FA secret and QR code for user
    """
    try:
        # Generate secret for 2FA
        secret = pyotp.random_base32()
        
        # Store secret temporarily (you should add these columns to User model)
        current_user.totp_secret = secret
        current_user.two_factor_enabled = False  # Not enabled until verified
        db.session.commit()
        
        # Generate provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=current_user.email,
            issuer_name='Traffic Management System'
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': '2FA setup initiated',
                'secret': secret,
                'qr_code': f'data:image/png;base64,{img_str}',
                'manual_entry': secret
            }), 200
        
        flash('2FA setup initiated. Scan the QR code with your authenticator app.', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to setup 2FA',
                'error': str(e)
            }), 500
        flash('Failed to setup 2FA. Please try again.', 'error')
        return redirect(url_for('main.settings'))


@settings_bp.route('/verify-2fa', methods=['POST'])
@login_required
def verify_2fa():
    """
    Verify 2FA token and enable 2FA for user
    """
    # Get data from request
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
        flash('Verification code is required', 'error')
        return redirect(url_for('main.settings'))
    
    try:
        # Verify token
        if not hasattr(current_user, 'totp_secret') or not current_user.totp_secret:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Please setup 2FA first',
                    'errors': ['2FA not set up']
                }), 400
            flash('Please setup 2FA first', 'error')
            return redirect(url_for('main.settings'))
        
        totp = pyotp.TOTP(current_user.totp_secret)
        
        if totp.verify(token, valid_window=1):
            # Enable 2FA
            current_user.two_factor_enabled = True
            db.session.commit()
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': '2FA enabled successfully'
                }), 200
            
            flash('2FA enabled successfully', 'success')
            return redirect(url_for('main.settings'))
        else:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Invalid verification code',
                    'errors': ['Invalid verification code']
                }), 400
            flash('Invalid verification code', 'error')
            return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to verify 2FA',
                'error': str(e)
            }), 500
        flash('Failed to verify 2FA. Please try again.', 'error')
        return redirect(url_for('main.settings'))


@settings_bp.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    """
    Disable 2FA for user
    """
    # Get password for verification
    if request.is_json:
        data = request.get_json()
        password = data.get('password', '')
    else:
        password = request.form.get('password', '')
    
    if not password:
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Password is required',
                'errors': ['Password required for verification']
            }), 400
        flash('Password required for verification', 'error')
        return redirect(url_for('main.settings'))
    
    if not current_user.check_password(password):
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Incorrect password',
                'errors': ['Incorrect password']
            }), 400
        flash('Incorrect password', 'error')
        return redirect(url_for('main.settings'))
    
    try:
        # Disable 2FA
        current_user.two_factor_enabled = False
        current_user.totp_secret = None
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': '2FA disabled successfully'
            }), 200
        
        flash('2FA disabled successfully', 'success')
        return redirect(url_for('main.settings'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'success': False,
                'message': 'Failed to disable 2FA',
                'error': str(e)
            }), 500
        flash('Failed to disable 2FA. Please try again.', 'error')
        return redirect(url_for('main.settings'))