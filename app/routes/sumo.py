from flask import Blueprint, render_template, jsonify, request
from app.services.sumo_service import sumo_service
from app.models.traffic_light import TrafficLightConfig

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

# Get detailed information for a specific traffic light Endpoints
@sumo_bp.route('/api/traffic-lights/<tl_id>', methods=['GET'])
def get_traffic_light_detail(tl_id):
    """Get detailed information for a specific traffic light"""
    detail = sumo_service.get_traffic_light_analysis(tl_id)
    return jsonify(detail)

# Get historical data for a traffic light Endpoints
@sumo_bp.route('/api/traffic-lights/<tl_id>/history', methods=['GET'])
def get_traffic_light_history(tl_id):
    """Get historical data for a traffic light"""
    limit = request.args.get('limit', 100, type=int)
    history = sumo_service.get_traffic_light_history(tl_id, limit)
    return jsonify(history)

# Set traffic light to specific phase Endpoints
@sumo_bp.route('/api/traffic-lights/<tl_id>/set-phase', methods=['POST'])
def set_traffic_light_phase(tl_id):
    """Set traffic light to specific phase"""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    phase = data.get('phase')
    if phase is None:
        return jsonify({"error": "Phase parameter required"}), 400
    
    try:
        phase = int(phase)
    except ValueError:
        return jsonify({"error": "Phase must be an integer"}), 400
    
    result = sumo_service.set_traffic_light_phase(tl_id, phase)
    return jsonify(result)

# Change traffic light program Endpoints
@sumo_bp.route('/api/traffic-lights/<tl_id>/set-program', methods=['POST'])
def set_traffic_light_program(tl_id):
    """Change traffic light program"""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    program_id = data.get('program_id')
    if not program_id:
        return jsonify({"error": "program_id parameter required"}), 400
    
    result = sumo_service.set_traffic_light_program(tl_id, program_id)
    return jsonify(result)

# Get all traffic light configurations Endpoints
@sumo_bp.route('/api/traffic-lights/configs', methods=['GET'])
def get_traffic_light_configs():
    """Get all traffic light configurations"""
    configs = TrafficLightConfig.query.all()
    return jsonify([config.to_dict() for config in configs])

# Get configuration for a specific traffic light
@sumo_bp.route('/api/traffic-lights/<tl_id>/config', methods=['GET'])
def get_traffic_light_config(tl_id):
    """Get configuration for a specific traffic light"""
    config = TrafficLightConfig.query.filter_by(traffic_light_id=tl_id).first()
    if config:
        return jsonify(config.to_dict())
    else:
        return jsonify({"error": "Configuration not found"}), 404

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