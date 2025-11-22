from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
import os
import uuid
from app.extensions import db
from werkzeug.utils import secure_filename
from app.utils.allowed_file import allowed_file, get_file_type

from app.forms.incident import IncidentForm
from app.models.incident import Incident
from app.models.location import Location
from ..models.user import User

incident_bp = Blueprint('incident', __name__)

@incident_bp.route('/incidents')
@login_required
def incidents():
    now = datetime.now()
    user = current_user
    
    incidentsCount = Incident.query.all()
    
    # Fetch incidents from the database
    incidents = Incident.query.filter(
    Incident.status.in_(['reported', 'investigating', 'in_progress'])
    ).order_by(Incident.created_at.desc()).limit(4).all()
    
    return render_template('incident/index.html', 
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           user=user,
                            incidents=incidents,
                            incidentsCount=incidentsCount
                           )
    
@incident_bp.route('/incidents/add', methods=['GET', 'POST'])
@login_required
def incident_add():
    now = datetime.now()
    user = current_user
    form = IncidentForm()
    
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if form.validate_on_submit():
        uploaded_files = []
        if 'media_files' in request.files:
            files = request.files.getlist('media_files')
            
            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    
                    # Save to static/uploads
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)
                    
                    # ✅ FIX: Store only the filename, not a complex object
                    uploaded_files.append(unique_filename)
                    print(f"✅ Saved file: {unique_filename}")
        
        # Generate incident ID
        if form.type.data:
            incident_id = Incident.generate_id(form.type.data)
        else:
            incident_id = Incident.generate_unknown_id()
            
        try:
            # Create incident
            incident = Incident(
                id=str(uuid.uuid4()),
                incident_id=incident_id,
                type=form.type.data,
                severity=form.severity.data,
                title=form.title.data,
                description=form.description.data,
                address=form.address.data,
                status='reported',
                location_id=form.location.data,
                user_id=current_user.id
            )
            
            # ✅ FIX: Use the setter method with simple filenames
            incident.set_media_files(uploaded_files)
            
            db.session.add(incident)
            db.session.commit()
            
            print(f"✅ Incident saved with {len(uploaded_files)} media files")
            print(f"✅ Raw DB storage: {incident.media_files}")
            print(f"✅ Parsed files: {incident.get_media_files()}")
            
            flash(f'Incident added successfully! {len(uploaded_files)} media files uploaded.', 'success')
            return redirect(url_for('incident.incidents'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving incident: {str(e)}")
            flash(f'Error saving incident: {str(e)}', 'error')
            
    return render_template('incident/add.html', 
                           current_date=now.strftime("%B %d, %Y"), 
                           current_time=now.strftime("%I:%M %p"),
                           user=user,
                           form=form
                           )
    
@incident_bp.route('/incidents/view/<string:id>')
@login_required
def view_incident(id):
    now = datetime.now()
    user = current_user
    
    incident = Incident.query.get_or_404(id)
    print(incident)
    return render_template('incident/view.html',
                    user=user,
                    incident=incident,
                    current_date=now.strftime("%B %d, %Y"),
                    current_time=now.strftime("%I:%M %p"),
                    )
    
@incident_bp.route('/incidents/edit/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_incident(id):
    now = datetime.now()
    user = current_user

    incident = Incident.query.get_or_404(id)
    
    form = IncidentForm(obj=incident)
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if form.validate_on_submit():
        incident.type = form.type.data
        incident.title = form.title.data
        incident.description = form.description.data
        incident.severity = form.severity.data
        incident.status = form.status.data
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
    return render_template('incident/edit.html',
                    user=user,
                    incident=incident,
                    current_date=now.strftime("%B %d, %Y"),
                    current_time=now.strftime("%I:%M %p"),
                    form=form
                    )
    
@incident_bp.route('/incidents/<uuid:id>/delete', methods=['POST'])
@login_required
def delete_incident(id):
    try:
        incident = Incident.query.get_or_404(str(id))
        
        # Optional: Check if user has permission to delete
        if incident.creator != current_user.id and not current_user.is_admin:
            flash('You do not have permission to delete this incident.', 'error')
            return redirect(url_for('incident.incident'))
        
        db.session.delete(incident)
        db.session.commit()
        
        flash('Incident deleted successfully!', 'success')
        return redirect(url_for('incident.incident'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting incident: {str(e)}', 'error')
        return redirect(url_for('incident.incident'))