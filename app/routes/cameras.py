from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User
from ..forms.camera import CameraForm
from ..models.location import Location
from ..models.camera import Camera
from ..models.signal import Signal
from app import db

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/cameras')
@login_required
def camera():
    now = datetime.now()
    user = current_user
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Validate per_page to prevent excessive values
    if per_page not in [10, 25, 50, 100]:
        per_page = 10
    
    # Paginate the query
    cameras_pagination = Camera.query.order_by(
        Camera.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    cameras = cameras_pagination.items
    
    return render_template('camera/camera.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"),
                           current_time=now.strftime("%I:%M %p"),
                           cameras=cameras,
                           pagination=cameras_pagination
                           )
    
@camera_bp.route('/cameras/add', methods=['GET', 'POST'])
@login_required
def addCamera():
    form = CameraForm()
    
    # Populate dropdowns
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if request.method == 'GET':
        form.display_id.data = Camera.generate_display_id()
    
    now = datetime.now()
    user = current_user
    
    if form.validate_on_submit():
        try:
            camera = Camera(
                display_id=form.display_id.data,
                name=form.name.data,
                camera_type=form.camera_type.data,
                manufacturer=form.manufacturer.data,
                model_number=form.model_number.data,
                resolution=form.resolution.data,
                frame_rate=form.frame_rate.data,
                ip_address=form.ip_address.data,
                stream_protocol=form.stream_protocol.data,
                port=form.port.data,
                stream_url_path=form.stream_url_path.data,
                username=form.username.data,
                password=form.password.data,  # In production, encrypt this!
                location_id=form.location.data,
                direction=form.direction.data,
                elevation=form.elevation.data,
                maintenance=form.maintenance.data,
                camera_group=form.camera_group.data,
                notes=form.notes.data,
                created_by=user.id
            )
            
            db.session.add(camera)
            db.session.commit()
            flash('Camera registered successfully!', 'success')
            return redirect(url_for('camera.camera'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering camera: {str(e)}', 'danger')
    
    return render_template('camera/add.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           form = form
                        )
    
@camera_bp.route('/generate-id', methods=['POST'])
def generate_id():
    location_name = request.json.get('location_name')
    return jsonify({
        'display_id': Camera.generate_display_id(location_name)
    })

@camera_bp.route('/cameras/<uuid:id>')
@login_required
def view(id):
    camera = Camera.query.get_or_404(id)
    now = datetime.now()
    user = current_user
    
    return render_template('camera/view.html', 
                           user=user, 
                           current_date=now.strftime("%B %d, %Y"), 
                           current_time=now.strftime("%I:%M %p"),
                           camera=camera
                           )

@camera_bp.route('/cameras/<uuid:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    now = datetime.now()
    user = current_user
    
    camera = Camera.query.get_or_404(id)
    form = CameraForm(obj=camera)
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if form.validate_on_submit():
        try:
            # Update basic fields
            form.populate_obj(camera)
            
            # Handle password separately (only if changed)
            if form.password.data:
                camera.password = form.password.data
            
            db.session.commit()
            flash('Camera updated successfully!', 'success')
            return redirect(url_for('camera.view', id=camera.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating camera: {str(e)}', 'danger')
    
    return render_template('camera/edit.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"), 
                           camera=camera, 
                           form=form
                        )

@camera_bp.route('/cameras/<uuid:id>/assign-signal', methods=['GET', 'POST'])
@login_required
def assign_signal(id):
    now = datetime.now()
    user = current_user
    
    camera = Camera.query.get_or_404(id)
    
    if request.method == 'POST':
        signal_id = request.json.get('signal_id')
        signal = Signal.query.get(signal_id) if signal_id else None
        
        camera.signal = signal
        db.session.commit()
        
        return jsonify({'success': True})
    
    # GET request - show assignment page
    signals = Signal.query.order_by(Signal.id).all()
    return render_template('camera/assign.html', 
                         user = user,
                         current_date = now.strftime("%B %d, %Y"), 
                         current_time = now.strftime("%I:%M %p"),
                         camera=camera, 
                         signals=signals
                        )
    
@camera_bp.route('/cameras/<uuid:id>/test-connection')
def test_connection(id):
    camera = Camera.query.get_or_404(id)
    success, message = camera.test_rtsp_connection()
    return jsonify({'success': success, 'message': message})

@camera_bp.route('/cameras/<string:id>/toggle-status', methods=['POST'])
def toggle_status(id):
    camera = Camera.query.get_or_404(str(id))
    new_status = camera.toggle_status()
    return jsonify({
        'success': True,
        'is_active': new_status,
        'message': f"Signal {'activated' if new_status else 'deactivated'}"
    })

@camera_bp.route('/cameras/<uuid:id>/delete', methods=['POST'])
@login_required
def delete_sensor(id):
    try:
        camera = Camera.query.get_or_404(str(id))
        
        # Optional: Check if user has permission to delete
        if camera.created_by != current_user.id and not current_user.is_admin:
            flash('You do not have permission to delete this camera.', 'error')
            return redirect(url_for('camera.camera'))
        
        db.session.delete(camera)
        db.session.commit()
        
        flash('Camera deleted successfully!', 'success')
        return redirect(url_for('camera.camera'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting camera: {str(e)}', 'error')
        return redirect(url_for('camera.camera'))