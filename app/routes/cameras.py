from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User
from ..forms.camera import CameraForm
from ..models.location import Location
from ..models.camera import Camera
from ..models.signal import Signal
from app import db

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/cameras')
@jwt_required_redirect
def camera():
    
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    
    # Fetch cameras from the database (assuming a Camera model exists)
    cameras = Camera.query.all()
    
    return render_template('camera/camera.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                            cameras=cameras
                           )
    
@camera_bp.route('/cameras/add', methods=['GET', 'POST'])
@jwt_required_redirect
def addCamera():
    
    form = CameraForm()
    
    # Populate dropdowns
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if request.method == 'GET':
        form.display_id.data = Camera.generate_display_id()
    
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    
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
@jwt_required_redirect
def view(id):
    camera = Camera.query.get_or_404(id)
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()
    
    return render_template('camera/view.html', 
                           user=user, 
                           current_date=now.strftime("%B %d, %Y"), 
                           current_time=now.strftime("%I:%M %p"),
                           camera=camera
                           )

@camera_bp.route('/cameras/<uuid:id>/edit', methods=['GET', 'POST'])
def edit(id):
    camera = Camera.query.get_or_404(id)
    form = CameraForm(obj=camera)
    
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
    
    return render_template('cameras/edit.html', camera=camera, form=form)


@camera_bp.route('/cameras/<uuid:id>/assign-signal', methods=['GET', 'POST'])
def assign_signal(id):
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
                         camera=camera, 
                         signals=signals)
    
@camera_bp.route('/cameras/<uuid:id>/test-connection')
def test_connection(id):
    camera = Camera.query.get_or_404(id)
    success, message = camera.test_rtsp_connection()
    return jsonify({'success': success, 'message': message})
