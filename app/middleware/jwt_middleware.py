from functools import wraps
from flask import redirect, url_for, flash
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError, WrongTokenError, RevokedTokenError, FreshTokenRequired

def jwt_required_redirect(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            if claims['exp'] < datetime.utcnow().timestamp():
                flash('Your session has expired. Please login again.', 'warning')
                return redirect(url_for('auth.login'))
            return fn(*args, **kwargs)
        except (NoAuthorizationError, InvalidHeaderError, WrongTokenError, RevokedTokenError, FreshTokenRequired) as e:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.login'))
    return wrapper