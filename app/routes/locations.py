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
    
    # Get page number from query parameters, default to 1
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Number of locations per page (matches your grid layout)
    
    locationCount = Location.query.all()
    
    # Paginate the query
    locations_pagination = Location.query.order_by(
        Location.name.asc()  # Or use Location.created_at.desc() for newest first
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    locations = locations_pagination.items
    
    return render_template('locations/location.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           locations=locations,
                           pagination=locations_pagination,
                           locationCount=len(locationCount)
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
                         current_time=datetime.now().strftime("%I:%M %p")
                         )
    

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

@loc_bp.route('/locations/<string:id>/toggle-status', methods=['POST'])
def toggle_status(id):
    location = Location.query.get_or_404(str(id))
    new_status = location.toggle_status()
    return jsonify({
        'success': True,
        'status': new_status,
        'message': f"Signal {'activated' if new_status else 'pending'}"
    })
    
@loc_bp.route('/locations/<uuid:id>/delete', methods=['POST'])
@login_required
def delete_location(id):
    try:
        location = Location.query.get_or_404(str(id))
        
        # Optional: Check if user has permission to delete
        if location.created_by != current_user.id and not current_user.is_admin:
            flash('You do not have permission to delete this location.', 'error')
            return redirect(url_for('loc.location'))
        
        db.session.delete(location)
        db.session.commit()
        
        flash('location deleted successfully!', 'success')
        return redirect(url_for('loc.location'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting location: {str(e)}', 'error')
        return redirect(url_for('loc.location'))