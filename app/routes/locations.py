from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from datetime import datetime
from app import db
from ..models.user import User
from app.models.location import Location
from app.forms.location import LocationForm
from flask_login import login_required, current_user
# from geoalchemy2.functions import ST_MakePoint

loc_bp = Blueprint('loc', __name__)

@loc_bp.route('/locations')
@login_required
def location():
    now = datetime.now()
    user = current_user
    locations = Location.query.all()
    
    return render_template('locations/location.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           locations=locations  # Uncomment if you have locations to display
                           )
    
@loc_bp.route('/locations/add', methods=['GET', 'POST'])
@login_required
def addLocation():
    user = current_user
    form = LocationForm()
    
    if form.name.data:
        location_id = Location.generate_location_id(form.name.data)
    else:
        location_id = "LOC_MAIN_001"
    
    if form.validate_on_submit():
        try:
            location = Location(
                location_id=location_id,
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
            
            flash('Location added successfully!', 'success')
            return redirect(url_for('loc.location'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving location: {str(e)}")
            flash(f'Error saving location: {str(e)}', 'error')
    
    return render_template('locations/add.html',
                         form=form,
                         user=user,
                         current_date=datetime.now().strftime("%B %d, %Y"),
                         current_time=datetime.now().strftime("%I:%M %p")
                         )


@loc_bp.route('/locations/<uuid:location_id>')
@login_required
def viewLocation(location_id):
    user = current_user
    location = Location.query.get_or_404(location_id)
    
    return render_template('locations/view.html',
                         location=location,
                         user=user,
                         current_date=datetime.now().strftime("%B %d, %Y"),
                         current_time=datetime.now().strftime("%I:%M %p"))
    

@loc_bp.route('/locations/<uuid:location_id>/edit', methods=['GET', 'POST'])
@login_required
def editLocation(location_id):
    user = current_user
    location = Location.query.get_or_404(location_id)
    form = LocationForm(obj=location)  # Pre-populate form with location data

    if form.validate_on_submit():
        try:
            form.populate_obj(location)  # Update location with form data
            location.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Location updated successfully!', 'success')
            return redirect(url_for('loc.viewLocation', location_id=location.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating location: {str(e)}")
            flash(f'Error updating location: {str(e)}', 'error')

    return render_template('locations/edit.html',
                         form=form,
                         location=location,
                         user=user,
                         current_date=datetime.now().strftime("%B %d, %Y"),
                         current_time=datetime.now().strftime("%I:%M %p"))
