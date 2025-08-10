# from functools import wraps
# from datetime import datetime
# from flask import redirect, url_for, flash, request, current_app
# from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
# from flask_jwt_extended.exceptions import JWTExtendedException

# def jwt_required_redirect(fn):
#     @wraps(fn)
#     def wrapper(*args, **kwargs):
#         try:
#             verify_jwt_in_request()
#             jwt_data = get_jwt()
            
#             # Check token expiration
#             if datetime.utcnow().timestamp() > jwt_data['exp']:
#                 flash('Your session has expired. Please login again.', 'warning')
#                 return redirect(url_for('auth.login', next=request.url))
                
#             return fn(*args, **kwargs)
            
#         except JWTExtendedException as e:
#             current_app.logger.warning(f"JWT validation failed: {str(e)}")
#             flash('Please login to access this page', 'warning')
#             return redirect(url_for('auth.login', next=request.url))
            
#     return wrapper

from functools import wraps
from datetime import datetime
from flask import request, redirect, url_for, flash, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from flask_jwt_extended.exceptions import JWTExtendedException

def jwt_required_redirect(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            jwt_data = get_jwt()
            # Check token expiration
            if datetime.utcnow().timestamp() > jwt_data['exp']:
                flash('Your session has expired. Please login again.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            return fn(*args, **kwargs)
        except JWTExtendedException as e:
            current_app.logger.warning(f"JWT validation failed: {str(e)}")
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.login', next=request.url))
    return wrapper