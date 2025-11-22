from flask import Blueprint, render_template, jsonify, request, current_app
from app.extensions import db

# Services
from app.services.optimized_sumo_service import optimized_sumo_service as sumo_service
# from app.services.ai_traffic_service import ai_traffic_service

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
    try:
        scenarios = sumo_service.get_available_scenarios()
        print(f"🔍 Available scenarios: {scenarios}")  # Debug logging
        
        if not scenarios:
            return jsonify({"error": "No scenarios found", "scenarios": {}}), 404
        
        return jsonify({
            "success": True,
            "scenarios": scenarios,
            "count": len(scenarios)
        })
        
    except Exception as e:
        print(f"❌ Error getting scenarios: {e}")
        return jsonify({"error": f"Failed to get scenarios: {str(e)}"}), 500

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
        # Return the result immediately instead of waiting
        if result.get("success"):
            return jsonify({
                "success": True,
                "message": f"Simulation starting with {scenario}",
                "scenario": scenario,
                "starting": True  # Indicate it's starting
            })
        else:
            return jsonify(result), 400
        
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
