from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from app import db
from ..models.user import User
from app.models.location import Location
from app.forms.location import LocationForm
from geoalchemy2.functions import ST_MakePoint

loc_bp = Blueprint('loc', __name__)

@loc_bp.route('/locations')
@jwt_required_redirect
def location():
    now = datetime.now()
    current_user = get_jwt_identity()
    if not current_user:
        return redirect(url_for('auth.login', next=request.url))
    
    user = User.query.filter_by(email=current_user).first_or_404()
    
    # Fetch locations from the database (assuming a Location model exists)
    locations = Location.query.all()
    
    return render_template('locations/location.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           locations=locations  # Uncomment if you have locations to display
                           )
    
@loc_bp.route('/locations/add', methods=['GET', 'POST'])
@jwt_required_redirect
def addLocation():
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first_or_404()
    form = LocationForm()
    
    if form.validate_on_submit():
        try:
            # Convert pedestrian_crossing to boolean properly
            # pedestrian_crossing = form.pedestrian_crossing.data if form.pedestrian_crossing.data is not None else False
            
            location = Location(
                name=form.name.data,
                zone=form.zone.data,
                priority=form.priority.data,
                description=form.description.data,
                intersection_type=form.intersection_type.data,
                pedestrian_crossing=bool(form.pedestrian_crossing.data),
                bicycle_lanes=form.bicycle_lanes.data,
                address=form.address.data,
                city=form.city.data,
                state=form.state.data,
                postal_code=form.postal_code.data,
                country=form.country.data,
                lat=float(form.lat.data) if form.lat.data else None,
                lng=float(form.lng.data) if form.lng.data else None,
                status='pending',
                created_by=user.id
            )

            db.session.add(location)
            db.session.commit()
            # print(location)
            
            flash('Location added successfully!', 'success')
            return redirect(url_for('loc.location'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving location: {str(e)}")
            flash(f'Error saving location: {str(e)}', 'error')
    
    # Handle form errors
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
                
    # Add this to your route temporarily
    print("Database URL:", current_app.config['SQLALCHEMY_DATABASE_URI'])
    
    return render_template('locations/add.html',
                         form=form,
                         user=user,
                         current_date=datetime.now().strftime("%B %d, %Y"),
                         current_time=datetime.now().strftime("%I:%M %p"))
