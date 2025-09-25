from flask import Blueprint, render_template, jsonify, request
from app.services.sumo_service import sumo_service

sumo_bp = Blueprint('sumo', __name__, url_prefix='/sumo')

@sumo_bp.route('/')
def dashboard():
    """SUMO simulation dashboard"""
    status = sumo_service.get_status()
    scenarios = sumo_service.get_available_scenarios()
    discovered = sumo_service.auto_discover_scenarios()
    sumo_check = sumo_service.check_sumo_availability()
    
    return render_template('sumo/dashboard.html',
                         status=status,
                         scenarios=scenarios,
                         discovered=discovered,
                         sumo_available=sumo_check['available'],
                         traci_available=sumo_check.get('traci_available', False))

# API Routes
# Simulation Status Endpoint
@sumo_bp.route('/api/status', methods=['GET'])
def get_status():
    """Get simulation status"""
    return jsonify(sumo_service.get_status())

# Scenario Management Endpoints
@sumo_bp.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    """Get available scenarios"""
    scenarios = sumo_service.get_available_scenarios()
    discovered = sumo_service.auto_discover_scenarios()
    return jsonify({**scenarios, **discovered})

# Start Simulation Endpoints
@sumo_bp.route('/api/start', methods=['POST'])
def start_simulation():
    """Start SUMO simulation"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        scenario = data.get('scenario')
        if not scenario:
            return jsonify({"error": "No scenario provided"}), 400
        
        # Robust GUI parameter handling
        gui_value = data.get('gui', True)
        
        # Handle different types of gui values
        if isinstance(gui_value, bool):
            gui = gui_value
        elif isinstance(gui_value, str):
            gui = gui_value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(gui_value, (int, float)):
            gui = bool(gui_value)
        else:
            gui = True  # Default to true for any other type
            
        result = sumo_service.start_simulation(scenario, gui)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# Stop Simulation Endpoint
@sumo_bp.route('/api/stop', methods=['POST'])
def stop_simulation():
    """Stop SUMO simulation"""
    result = sumo_service.stop_simulation()
    return jsonify(result)

# Check SUMO availability
@sumo_bp.route('/api/check-sumo', methods=['GET'])
def check_sumo():
    """Check SUMO availability"""
    result = sumo_service.check_sumo_availability()
    return jsonify(result)

# Enhanced Monitoring Endpoints
@sumo_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Get simulation statistics"""
    stats = sumo_service.get_simulation_stats()
    return jsonify(stats)

# Get current vehicle list with detailed information Endpoints
@sumo_bp.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    """Get current vehicle list with detailed information"""
    vehicles = sumo_service.get_vehicle_list()
    return jsonify(vehicles)

# Get traffic light states Endpoints
@sumo_bp.route('/api/traffic-lights', methods=['GET'])
def get_traffic_lights():
    """Get traffic light states"""
    traffic_lights = sumo_service.get_traffic_lights()
    return jsonify(traffic_lights)

# Get edge/lane statistics Endpoints
@sumo_bp.route('/api/edges', methods=['GET'])
def get_edges():
    """Get edge/lane statistics"""
    edges = sumo_service.get_edges()
    return jsonify(edges)

# Get detailed information for a specific vehicle Endpoints
@sumo_bp.route('/api/vehicle/<vehicle_id>', methods=['GET'])
def get_vehicle_detail(vehicle_id):
    """Get detailed information for a specific vehicle"""
    vehicles = sumo_service.get_vehicle_list()
    vehicle = next((v for v in vehicles if v['id'] == vehicle_id), None)
    if vehicle:
        return jsonify(vehicle)
    else:
        return jsonify({"error": "Vehicle not found"}), 404

# Get detailed info about a specific scenario Endpoints
@sumo_bp.route('/api/scenario-info/<scenario_name>', methods=['GET'])
def get_scenario_info(scenario_name):
    """Get detailed info about a specific scenario"""
    scenarios = sumo_service.get_available_scenarios()
    discovered = sumo_service.auto_discover_scenarios()
    all_scenarios = {**scenarios, **discovered}
    
    if scenario_name in all_scenarios:
        return jsonify(all_scenarios[scenario_name])
    else:
        return jsonify({"error": "Scenario not found"}), 404