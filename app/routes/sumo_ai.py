from flask import Blueprint, request, jsonify, current_app, render_template
from app.services.sumo_service import sumo_service
from app.services.ai_service import ai_service
import json
from datetime import datetime, timedelta

sumo_ai_bp = Blueprint('sumo_ai', __name__)

@sumo_ai_bp.route('/dashboard')
def dashboard():
    """Main dashboard with SUMO and AI integration"""
    return render_template('sumo_dashboard.html')

@sumo_ai_bp.route('/api/sumo/status', methods=['GET'])
def get_sumo_status():
    """Get the current status of the SUMO simulation"""
    return jsonify(sumo_service.get_current_state())

@sumo_ai_bp.route('/api/sumo/status/light', methods=['GET'])
def get_sumo_status_light():
    """Get a lightweight status of the SUMO simulation"""
    return jsonify(sumo_service.get_lightweight_status())

@sumo_ai_bp.route('/api/sumo/start', methods=['POST'])
def start_simulation():
    """Start a SUMO simulation"""
    data = request.get_json()
    config_file = data.get('config_file') if data else None
    ai_control = data.get('ai_control', True) if data else True
    
    # Set AI controller if enabled
    if ai_control:
        sumo_service.set_ai_controller(ai_service)
    else:
        sumo_service.set_ai_controller(None)
    
    if sumo_service.start_simulation(config_file):
        return jsonify({"status": "success", "message": "Simulation started", "ai_control": ai_control})
    else:
        return jsonify({"status": "error", "message": "Simulation already running or failed to start"}), 400

@sumo_ai_bp.route('/api/sumo/stop', methods=['POST'])
def stop_simulation():
    """Stop the running simulation"""
    if sumo_service.stop_simulation():
        return jsonify({"status": "success", "message": "Simulation stopped"})
    else:
        return jsonify({"status": "error", "message": "No simulation running"}), 400

@sumo_ai_bp.route('/api/sumo/control/traffic_light', methods=['POST'])
def control_traffic_light():
    """Control a traffic light"""
    data = request.get_json()
    if not data or 'tl_id' not in data or 'state' not in data:
        return jsonify({"status": "error", "message": "Missing required parameters"}), 400
    
    tl_id = data['tl_id']
    state = data['state']
    duration = data.get('duration')
    
    if sumo_service.control_traffic_light(tl_id, state, duration):
        return jsonify({"status": "success", "message": f"Traffic light {tl_id} updated"})
    else:
        return jsonify({"status": "error", "message": "Failed to update traffic light"}), 400

@sumo_ai_bp.route('/api/sumo/vehicle/<vehicle_id>', methods=['GET'])
def get_vehicle_info(vehicle_id):
    """Get information about a specific vehicle"""
    info = sumo_service.get_route_info(vehicle_id)
    if info:
        return jsonify({"status": "success", "data": info})
    else:
        return jsonify({"status": "error", "message": "Vehicle not found or simulation not running"}), 404

@sumo_ai_bp.route('/api/sumo/statistics', methods=['GET'])
def get_statistics():
    """Get simulation statistics"""
    stats = sumo_service.get_simulation_statistics()
    if 'error' in stats:
        return jsonify({"status": "error", "message": stats['error']}), 400
    
    return jsonify({
        "status": "success",
        "statistics": stats
    })

@sumo_ai_bp.route('/api/ai/predict/traffic', methods=['POST'])
def predict_traffic():
    """Predict traffic conditions"""
    data = request.get_json()
    steps = data.get('steps', 4) if data else 4
    
    # Get historical data from simulation
    if not sumo_service.simulation_running:
        return jsonify({"error": "Simulation not running"}), 400
    
    # In a real implementation, this would get historical data from database
    # For now, we'll use a simplified approach
    history_data = [
        {'congestion_level': 1.2, 'timestamp': (datetime.now() - timedelta(minutes=45)).isoformat()},
        {'congestion_level': 1.5, 'timestamp': (datetime.now() - timedelta(minutes=30)).isoformat()},
        {'congestion_level': 1.8, 'timestamp': (datetime.now() - timedelta(minutes=15)).isoformat()}
    ]
    
    predictions = ai_service.predict_traffic(history_data, steps)
    
    return jsonify({
        "status": "success",
        "predictions": predictions,
        "history": history_data
    })

@sumo_ai_bp.route('/api/ai/performance', methods=['GET'])
def get_ai_performance():
    """Get AI performance metrics"""
    metrics = ai_service.get_performance_metrics()
    return jsonify({
        "status": "success",
        "metrics": metrics
    })

@sumo_ai_bp.route('/api/ai/control', methods=['POST'])
def toggle_ai_control():
    """Toggle AI control on/off"""
    data = request.get_json()
    enabled = data.get('enabled', True) if data else True
    
    if enabled:
        sumo_service.set_ai_controller(ai_service)
        return jsonify({"status": "success", "message": "AI control enabled"})
    else:
        sumo_service.set_ai_controller(None)
        return jsonify({"status": "success", "message": "AI control disabled"})