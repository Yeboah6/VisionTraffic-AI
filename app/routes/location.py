from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from datetime import datetime
from flask_login import current_user, login_required
from app.extensions import db
from ..models.user import User

from app.models.location import Location
from app.forms.location import LocationForm

location_bp = Blueprint('location', __name__)

@location_bp.route('/locations')
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
    
    return render_template('location/index.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           locations=locations,
                           pagination=locations_pagination,
                           locationCount=len(locationCount)
                           )

@location_bp.route('/locations/add', methods=['GET', 'POST'])
@login_required
def add_location():
    now = datetime.now()
    user = current_user
    
    form = LocationForm()
    if form.validate_on_submit():
        try:
            location = Location(
                name=form.name.data,
                description=form.description.data,
                city=form.city.data,
                region=form.region.data,
                country=form.country.data,
                latitude=float(form.latitude.data) if form.latitude.data else None,
                longitude=float(form.longitude.data) if form.longitude.data else None,
                user_id=current_user.id
            )

            db.session.add(location)
            db.session.commit()
            
            flash('Location added successfully!', 'success')
            return redirect(url_for('location.location'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving location: {str(e)}")
            flash(f'Error saving location: {str(e)}', 'error')
    locations = Location.query.all()
    return render_template('location/add.html', 
                           form=form,
                            user=user,
                            current_time=now.strftime("%I:%M %p"),
                           current_date=now.strftime("%B %d, %Y"),
                           locations=locations
                           )

@location_bp.route('/locations/view/<int:id>')
@login_required
def view_location(id):
    user = current_user
    now = datetime.now()
    location = Location.query.get_or_404(id)
    
    return render_template('location/view.html', 
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           location=location
                           )

@location_bp.route('/locations/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_location(id):
    user = current_user
    now = datetime.now()
    location = Location.query.get_or_404(id)
    
    form = LocationForm(obj=location)
    
    if form.validate_on_submit():
        try:
            location.name = form.name.data
            location.description = form.description.data
            location.city = form.city.data
            location.region = form.region.data
            location.country = form.country.data
            location.latitude = float(form.latitude.data) if form.latitude.data else None
            location.longitude = float(form.longitude.data) if form.longitude.data else None
            location.user_id = current_user.id
            db.session.commit()
            flash('Location updated successfully!', 'success')
            return redirect(url_for('location.view_location', id=location.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating location: {str(e)}")
            flash(f'Error updating location: {str(e)}', 'error')
    
    return render_template('location/edit.html', 
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           location=location,
                           form=form
                           )