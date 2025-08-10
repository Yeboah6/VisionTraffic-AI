from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.middleware.jwt_middleware import jwt_required_redirect
from datetime import datetime
from ..models.user import User
from ..models.location import Location
from app.models.signal import Signal
from app.forms.signal import SignalForm
from app import db
import uuid

signal_bp = Blueprint('signal', __name__)

@signal_bp.route('/signals')
@jwt_required_redirect
def signals():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email = current_user).first()
    
    # Fetch signals from the database (assuming a Signal model exists)
    # signals = Signal.query.all()  # Uncomment and modify as per your model
    
    return render_template('signals/signal.html',
                           user=user,
                           current_date = now.strftime("%B %d, %Y"),
                           current_time = now.strftime("%I:%M %p")
                           # signals=signals  # Uncomment if you have signals to display
                           )
    
@signal_bp.route('/signals/add', methods=['GET', 'POST'])
@jwt_required_redirect
def signalManage():
    now = datetime.now()
    current_user = get_jwt_identity()
    user = User.query.filter_by(email = current_user).first()
    
    form = SignalForm()
    locations = [('', 'Select...')] + [(loc.id, loc.name) for loc in Location.query.order_by(Location.name)]
    form.location_id.choices = locations
    
    
    if form.intersection_name.data:
        signal_id = Signal.generate_id(form.intersection_name.data)
    else:
        signal_id = "SIG_UNK_001"
    
    if form.validate_on_submit():
        try:
            signal = Signal(
                id=signal_id,
                intersection_name=form.intersection_name.data,
                direction=form.direction.data,
                controller_type=form.controller_type.data,
                ip_address=form.ip_address.data,
                protocol=form.protocol.data,
                default_cycle=form.default_cycle.data,
                phases=form.phases.data,
                location_id=form.location_id.data,
                address = form.address.data
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
def list():
    signals = Signal.query.order_by(Signal.id).all()
    return render_template('signals/list.html', signals=signals)    

@signal_bp.route('/signals/<string:id>')
def view(id):
    signal = Signal.query.get_or_404(str(id))
    return render_template('signals/view.html', signal=signal)

@signal_bp.route('/signals/<string:id>/edit', methods=['GET', 'POST'])
def edit(id):
    signal = Signal.query.get_or_404(str(id))
    form = SignalForm(obj=signal)
    
    if form.validate_on_submit():
        try:
            form.populate_obj(signal)
            db.session.commit()
            flash('Signal updated successfully!', 'success')
            return redirect(url_for('signal.view', id=signal.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating signal: {str(e)}', 'danger')
    
    return render_template('signals/edit.html', signal=signal, form=form)

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