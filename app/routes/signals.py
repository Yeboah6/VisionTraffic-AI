from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from ..models.user import User
from ..models.location import Location
from app.models.signal import Signal
from app.forms.signal import SignalForm
from app import db

signal_bp = Blueprint('signal', __name__)

@signal_bp.route('/signals')
@login_required
def signals():
    now = datetime.now()
    user = current_user
    signals = Signal.query.all()
    
    return render_template('signals/signal.html',
                           user=user,
                           current_date = now.strftime("%B %d, %Y"),
                           current_time = now.strftime("%I:%M %p"),
                           signals=signals  
                        )
    
@signal_bp.route('/signals/add', methods=['GET', 'POST'])
@login_required
def signalManage():
    now = datetime.now()
    user = current_user

    form = SignalForm()
    locations = [('', 'Select...')] + [(loc.id, loc.name) for loc in Location.query.order_by(Location.name)]
    form.location_id.choices = locations
    
    if form.name.data:
        signal_id = Signal.generate_id(form.name.data)
    else:
        signal_id = "SIG_UNK_001"
    
    if form.validate_on_submit():
        try:
            signal = Signal(
                display_id=signal_id,
                name=form.name.data,
                direction=form.direction.data,
                controller_type=form.controller_type.data,
                ip_address=form.ip_address.data,
                protocol=form.protocol.data,
                default_cycle=form.default_cycle.data,
                phases=form.phases.data,
                location_id=form.location_id.data,
                address = form.address.data,
                created_by=user.id
            )
            
            db.session.add(signal)
            db.session.commit()
            flash('Signal added successfully!', 'success')
            return redirect(url_for('signal.list'))
        except Exception as e:
            db.session.rollback()
            print(form.errors)
            flash(f'Error adding signal: {str(e)}', 'danger')
    return render_template('signals/add.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                            form = form,
                            signal_id=signal_id,
                            locations=locations
                        )

@signal_bp.route('/signals/list')
@login_required
def list():
    now = datetime.now()
    user = current_user
    signals = Signal.query.order_by(Signal.id).all()
    return render_template('signals/list.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           signals=signals
                        )    

@signal_bp.route('/signals/<string:id>')
@login_required
def view(id):
    now = datetime.now()
    user = current_user
    signal = Signal.query.get_or_404(str(id))
    return render_template('signals/view.html', 
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p"),
                           signal=signal
                        )

@signal_bp.route('/signals/<string:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    now = datetime.now()
    user = current_user
    signal = Signal.query.get_or_404(str(id))
    form = SignalForm(obj=signal)
    
    # CRITICAL: Set choices BEFORE form validation
    locations = Location.query.order_by('name').all()
    form.location_id.choices = [(loc.id, loc.name) for loc in locations]
    print(f"Available choices: {form.location_id.choices}")
    
    # Set current value
    form.location_id.data = signal.location_id
    print(f"Form location_id data set to: {form.location_id.data}")
    
    if form.validate_on_submit():
        try:
            print(f"Submitted location_id: {form.location_id.data}")
            signal.name = form.name.data
            signal.direction = form.direction.data
            signal.controller_type = form.controller_type.data
            signal.ip_address = form.ip_address.data
            signal.protocol = form.protocol.data
            signal.default_cycle = form.default_cycle.data
            signal.phases = form.phases.data
            signal.address = form.address.data
            signal.location_id = form.location_id.data
            
            db.session.commit()
            flash('Signal updated successfully!', 'success')
            return redirect(url_for('signal.view', id=signal.id))
        except Exception as e:
            print(f"Form errors: {form.errors}")
            db.session.rollback()
            flash(f'Error updating signal: {str(e)}', 'danger')
            if form.location_id.errors:
                print(f"Location ID errors: {form.location_id.errors}")
    
    return render_template('signals/edit.html', 
                           user=user,
                           current_date=now.strftime("%B %d, %Y"), 
                           current_time=now.strftime("%I:%M %p"),
                           signal=signal, 
                           form=form
                        )

@signal_bp.route('/signals/<string:id>/delete', methods=['POST'])
def delete(id):
    signal = Signal.query.get_or_404(str(id))
    
    try:
        db.session.delete(signal)
        db.session.commit()
        flash('Signal deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting signal: {str(e)}', 'danger')
    
    return redirect(url_for('signal.list'))

@signal_bp.route('/signals/<string:id>/toggle-status', methods=['POST'])
def toggle_status(id):
    signal = Signal.query.get_or_404(str(id))
    new_status = signal.toggle_status()
    return jsonify({
        'success': True,
        'is_active': new_status,
        'message': f"Signal {'activated' if new_status else 'deactivated'}"
    })