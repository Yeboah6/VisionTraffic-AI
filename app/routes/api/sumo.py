from flask import Blueprint, render_template, jsonify, request, current_app
from typing import Dict
from app.extensions import db

# Services
from app.services.optimized_sumo_service import optimized_sumo_service as sumo_service


sumo_bp = Blueprint('sumo', __name__, url_prefix='/sumo')

@sumo_bp.route('/')
def dashboard():
    """SUMO simulation dashboard"""
    status = sumo_service.get_status()
    scenarios = sumo_service.get_available_scenarios()
    sumo_check = sumo_service.check_sumo_availability()
    
    return render_template('sumo/dashboard.html',
                         status=status,
                         scenarios=scenarios,
                         sumo_available=sumo_check['available'],
                         traci_available=sumo_check.get('traci_available', False))

# API Routes
# Simulation Status Endpoint
@sumo_bp.route('/api/status', methods=['GET'])
def get_status():
    """Get simulation status"""
    try:
        status = sumo_service.get_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
        
        # Enable AI if specified
        if data.get('enable_ai', False):
            sumo_service.enable_ai()
            
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
    try:
        result = sumo_service.stop_simulation()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Check SUMO availability
@sumo_bp.route('/api/check-sumo', methods=['GET'])
def check_sumo():
    """Check SUMO availability"""
    result = sumo_service.check_sumo_availability()
    return jsonify(result)

@sumo_bp.route('/api/tls/performance', methods=['GET'])
def get_performance_data():
    """Get overall performance metrics"""
    try:
        sim_data = sumo_service.get_simulation_data()
        tls_data = sumo_service.get_tls_data()
        
        if not tls_data.get('tls_snapshot'):
            return jsonify({
                'success': True,
                'performance': {
                    'average_efficiency': 0,
                    'overall_performance_grade': 'N/A',
                    'average_waiting_vehicles': 0,
                    'total_tls': 0,
                    'total_vehicles_observed': 0,
                    'scenario': 'N/A',
                    'timestamp': 0,
                    'successful_collections': 0,
                    'collection_errors': 0,
                    'logged_instances': 0,
                    'performance_grade_distribution': {'A': 0, 'B': 0, 'C': 0, 'D': 0}
                }
            })
        
        summary = tls_data['tls_snapshot'].get('summary', {})
        
        # Calculate grade distribution
        grade_dist = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for tl_info in tls_data['tls_snapshot'].get('traffic_lights', {}).values():
            grade = tl_info.get('performance', {}).get('performance_grade', 'D')
            if grade in grade_dist:
                grade_dist[grade] += 1
        
        return jsonify({
            'success': True,
            'performance': {
                'average_efficiency': summary.get('avg_efficiency', 0),
                'overall_performance_grade': _calculate_overall_grade(grade_dist),
                'average_waiting_vehicles': summary.get('total_waiting', 0) / max(1, summary.get('total_tls', 1)),
                'total_tls': summary.get('total_tls', 0),
                'total_vehicles_observed': summary.get('total_vehicles', 0),
                'scenario': sumo_service.current_config or 'N/A',
                'timestamp': tls_data['tls_snapshot'].get('timestamp', 0),
                'successful_collections': summary.get('total_tls', 0),
                'collection_errors': 0,
                'logged_instances': len(tls_data['tls_snapshot'].get('traffic_lights', {})),
                'performance_grade_distribution': grade_dist
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
def _calculate_overall_grade(grade_dist: Dict[str, int]) -> str:
    """Calculate overall performance grade from distribution"""
    total = sum(grade_dist.values())
    if total == 0:
        return 'N/A'
    
    # Calculate weighted score (A=4, B=3, C=2, D=1)
    weighted_sum = (
        grade_dist.get('A', 0) * 4 +
        grade_dist.get('B', 0) * 3 + 
        grade_dist.get('C', 0) * 2 +
        grade_dist.get('D', 0) * 1
    )
    
    average = weighted_sum / total
    
    if average >= 3.5:
        return 'A'
    elif average >= 2.5:
        return 'B'
    elif average >= 1.5:
        return 'C'
    else:
        return 'D'