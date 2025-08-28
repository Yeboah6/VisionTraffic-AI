from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User
from app import db
from app.models.incident import Incident
from app.models.location import Location
from app.forms.incident import IncidentForm
from werkzeug.utils import secure_filename
import os
import uuid

incident_bp = Blueprint('incident', __name__)

@incident_bp.route('/incident')
@login_required
def incident():
    now = datetime.now()
    user = current_user
    
    # Get page number from query parameters, default to 1
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Number of incidents per page
    
    # Paginate the query
    incidents_pagination = Incident.query.order_by(
        Incident.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    incidents = incidents_pagination.items
    
    return render_template('incidents/incident.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           incidents=incidents,
                           pagination=incidents_pagination
                           )
    
@incident_bp.route('/incident/add', methods=['GET', 'POST'])
@login_required
def add_incident():
    now = datetime.now()
    user = current_user
    
    form = IncidentForm()
    
    if form.type.data:
        incident_id = Incident.generate_id(form.type.data)
    else:
        incident_id = Incident.generate_unknown_id()
    
    # Populate dropdowns
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if form.validate_on_submit():
        # Handle file uploads
        uploaded_files = []
        if 'media_files' in request.files:
            files = request.files.getlist('media_files')
            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))
                    uploaded_files.append(unique_filename)
                    
        # Create new incident
        incident = Incident(
            id=str(uuid.uuid4()), 
            incident_id = incident_id,
            type=form.type.data,
            severity=form.severity.data,
            title=form.title.data,
            description=form.description.data,
            location_type=form.location_type.data,
            location_id=form.location.data,
            lanes_affected=form.lanes_affected.data,
            estimated_delay=form.estimated_delay.data,
            emergency_services=form.emergency_services.data,
            vehicles_involved=form.vehicles_involved.data or 0,
            injuries_reported=form.injuries_reported.data,
            reporter_type=form.reporter_type.data,
            reporter_info=form.reporter_info.data if form.reporter_type.data in ['public', 'other'] else None,
            internal_notes=form.internal_notes.data,
            media_files=','.join(uploaded_files) if uploaded_files else None,
            user_id=current_user.id,
            status='reported'
        )
        
        db.session.add(incident)
        db.session.commit()
        
        flash('Incident report submitted successfully!', 'success')
        return redirect(url_for('incident.incident'))
    else:
        print("Form errors:", form.errors)  # This will show the exact error
    
    return render_template('incidents/add.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           form = form
                           )
    
@incident_bp.route('/incident/<uuid:id>')
@login_required
def view_incident(id):
    user = current_user
    now = datetime.now()
    incident = Incident.query.get_or_404(id)
    return render_template('incidents/view.html', 
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           incident=incident
                           )

@incident_bp.route('/incident/<uuid:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_incident(id):
    user=current_user
    now = datetime.now()
    incident = Incident.query.get_or_404(id)
    
    form = IncidentForm(obj=incident)
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if form.validate_on_submit():
        # Manual assignment instead of populate_obj
        incident.type = form.type.data
        incident.title = form.title.data
        incident.description = form.description.data
        incident.severity = form.severity.data
        incident.status = form.status.data
        incident.vehicles_involved = form.vehicles_involved.data
        incident.lanes_affected = form.lanes_affected.data
        incident.emergency_services = form.emergency_services.data
        incident.reporter_info = form.reporter_info.data
        incident.type = form.type.data
        
        # Handle location relationship properly
        location_id = form.location.data
        if location_id:
            location = Location.query.get(location_id)
            incident.location = location
        else:
            incident.location = None
        
        db.session.commit()
        flash('Incident updated successfully!', 'success')
        return redirect(url_for('incident.view_incident', id=incident.id))
    
    return render_template('incidents/edit.html', 
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           incident=incident, 
                           form=form,
                           user=user
                           )