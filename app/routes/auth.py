from flask import Blueprint, render_template, request,jsonify, redirect, url_for, flash
from flask_jwt_extended import get_jwt_identity, create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt
from ..models.user import User
from .. import db
from app.forms import RegisterForm, LoginForm
import bcrypt
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            # Create JWT token
            access_token = create_access_token(
                identity=user.email,
                # additional_claims={"user_id": user.id}
                expires_delta = timedelta(minutes=30)  # Set token expiration time
            )
            
            # Prepare response
            response = redirect(url_for('main.dashboard'))
            set_access_cookies(response, access_token)
            
            flash('Login successful!', 'success')
            return response
        
        flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            return render_template('auth/register.html', form=form, error="Username already exists")
        
        hashed_password = bcrypt.hashpw(form.password.data.encode('utf-8'), bcrypt.gensalt())
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash = hashed_password.decode('utf-8')
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form = form)

@auth_bp.route('/logout', methods=['GET'])
def logout():
    response = redirect(url_for('auth.login'))
    unset_jwt_cookies(response)
    flash('You have been logged out', 'info')
    return response

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)  # Requires valid refresh token
def refresh_token():
    try:
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=current_user)
        response = jsonify({'status': 'success'})
        set_access_cookies(response, new_token)
        return response, 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 401
