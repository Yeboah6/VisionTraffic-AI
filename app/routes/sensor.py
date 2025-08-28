from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User
from ..forms.sensor import SensorForm
from ..models.location import Location
from ..models.sensor import Sensor
from ..models.signal import Signal
from app import db

sensor_bp = Blueprint('sensor', __name__)

@sensor_bp.route('/sensors')
@login_required
def sensor():
    sensors = Sensor.query.order_by(Sensor.display_id).all()
    now = datetime.now()
    user = current_user
    
    # Get page number from query parameters, default to 1
    # page = request.args.get('page', 1, type=int)
    # per_page = 6  # Number of incidents per page
    
    # # Paginate the query
    # sensors_pagination = Sensor.query.order_by(
    #     Sensor.created_at.desc()
    # ).paginate(page=page, per_page=per_page, error_out=False)
    
    # sensors = sensors_pagination.items
    
    return render_template('sensor/sensor.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                            sensors=sensors 
                           )
    
@sensor_bp.route('/sensors/add', methods=['GET', 'POST'])
@login_required
def addSensor():
    form = SensorForm()
    
    # Populate dropdowns
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]
    
    if request.method == 'GET':
        form.display_id.data = Sensor.generate_display_id()
    
    now = datetime.now()
    user = current_user
    
    if form.validate_on_submit():
        try:
            sensor = Sensor(
                display_id=form.display_id.data or Sensor.generate_display_id(
                    Location.query.get(form.location.data).name
                ),
                sensor_type=form.sensor_type.data,
                lanes_monitored=form.lanes_monitored.data,
                direction=form.direction.data,
                installation_date=form.installation_date.data,
                installation_note=form.installation_notes.data,
                location_id=form.location.data,
                created_by=user.id
            )
            db.session.add(sensor)
            db.session.commit()
            flash('Sensor added successfully!', 'success')
            return redirect(url_for('sensor.sensor'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding sensor: {str(e)}', 'danger')

    return render_template('sensor/add.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           form = form
                           )
    
@sensor_bp.route('/sensors/<uuid:id>')
@login_required
def view(id):
    now = datetime.now()
    user = current_user
    
    sensor = Sensor.query.get_or_404(id)
    return render_template('sensor/view.html', 
                            user=user,
                            current_date=now.strftime("%B %d, %Y"), 
                            current_time=now.strftime("%I:%M %p"),
                            sensor=sensor)
    
@sensor_bp.route('/sensors/<uuid:id>/edit', methods=['GET', 'POST']) 
@login_required
def edit(id):
    now = datetime.now()
    user = current_user
    
    sensor = Sensor.query.get_or_404(id)
    form = SensorForm(obj=sensor)
    form.location.choices = [(loc.id, loc.name) for loc in Location.query.order_by('name')]

    if form.validate_on_submit():
        try:
            form.populate_obj(sensor)
            db.session.commit()
            flash('Sensor updated successfully!', 'success')
            return redirect(url_for('sensor.view', id=sensor.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating sensor: {str(e)}', 'danger')

    return render_template('sensor/edit.html', sensor=sensor, 
                            user=user,
                            current_date=now.strftime("%B %d, %Y"), 
                            current_time=now.strftime("%I:%M %p"),
                           form=form)

@sensor_bp.route('/sensors/<uuid:id>/test', methods=['POST'])
def test_sensor(id):
    sensor = Sensor.query.get_or_404(id)
    # Implement actual sensor testing logic
    return jsonify({
        'success': True,
        'message': 'Sensor test completed successfully'
    })
    
@sensor_bp.route('/sensors/<string:id>/toggle-status', methods=['POST'])
def toggle_status(id):
    sensor = Sensor.query.get_or_404(str(id))
    new_status = sensor.toggle_status()
    return jsonify({
        'success': True,
        'is_active': new_status,
        'message': f"Signal {'activated' if new_status else 'deactivated'}"
    })
    
@sensor_bp.route('/sensors/<uuid:id>/assign-signal', methods=['GET', 'POST'])
@login_required
def assign_signal(id):
    now = datetime.now()
    user = current_user
    
    sensor = Sensor.query.get_or_404(id)
    
    if request.method == 'POST':
        signal_id = request.json.get('signal_id')
        signal = Signal.query.get(signal_id) if signal_id else None
        
        sensor.signal = signal
        db.session.commit()
        
        return jsonify({'success': True})
    
    # GET request - show assignment page
    signals = Signal.query.order_by(Signal.id).all()
    return render_template('sensor/assign.html', 
                         user = user,
                         current_date = now.strftime("%B %d, %Y"), 
                         current_time = now.strftime("%I:%M %p"),
                         sensor=sensor, 
                         signals=signals
                        )
    
@sensor_bp.route('/sensors/<uuid:id>/delete', methods=['POST'])
@login_required
def delete_sensor(id):
    try:
        sensor = Sensor.query.get_or_404(str(id))
        
        # Optional: Check if user has permission to delete
        if sensor.created_by != current_user.id and not current_user.is_admin:
            flash('You do not have permission to delete this sensor.', 'error')
            return redirect(url_for('sensor.sensor'))
        
        db.session.delete(sensor)
        db.session.commit()
        
        flash('Sensor deleted successfully!', 'success')
        return redirect(url_for('sensor.sensors'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting sensor: {str(e)}', 'error')
        return redirect(url_for('sensor.sensor'))
    
# @sensor_bp.route('/sensors/<uuid:id>/remove-signal', methods=['POST'])
# @login_required
# def remove_signal(id):
#     sensor = Sensor.query.get_or_404(id)
#     sensor.signal = None
#     db.session.commit()
#     flash('Signal unassigned from sensor successfully!', 'success')
#     return redirect(url_for('sensor.view', id=sensor.id))