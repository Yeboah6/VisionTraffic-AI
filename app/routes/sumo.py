from flask import Blueprint, render_template, jsonify, request, current_app
from app.extensions import db

# Services
from app.services.sumo_service import sumo_service
from app.services.camera_service import camera_service
from app.services.ai_traffic_service import ai_traffic_service

# Models
# from app.models.traffic_light import TrafficLightConfig
from app.models.camera import Camera, CameraMetrics


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

# Get all cameras and their current status
@sumo_bp.route('/api/cameras', methods=['GET'])
def get_cameras():
    """Get all cameras and their current status"""
    cameras = Camera.query.all()
    current_data = camera_service.get_combined_camera_data()
    
    return jsonify({
        'cameras': [cam.to_dict() for cam in cameras],
        'current_data': current_data
    })

# Add a new camera (real or virtual)
@sumo_bp.route('/api/cameras/add', methods=['POST'])
def add_camera():
    """Add a new camera (real or virtual)"""
    data = request.get_json()
    
    if data['type'] == 'real':
        camera_service.add_real_camera(
            data['id'],
            data['source'],
            data['location']
        )
        # Start processing if requested
        if data.get('start_processing', False):
            camera_service.start_real_camera_processing(data['id'])
    
    elif data['type'] == 'virtual':
        camera_service.add_virtual_camera(
            data['id'],
            data['detector_id'],
            data['location']
        )
    
    # Store in database
    camera = Camera(
        id=data['id'],
        name=data['name'],
        camera_type=data['type'],
        source=data.get('source') or data.get('detector_id'),
        location_lat=data['location']['lat'],
        location_lng=data['location']['lng'],
        intersection_id=data.get('intersection_id')
    )
    db.session.add(camera)
    db.session.commit()
    
    return jsonify({'success': True, 'camera': camera.to_dict()})

# Get recent AI decisions
@sumo_bp.route('/api/ai-decisions', methods=['GET'])
def get_ai_decisions():
    """Get recent AI decisions"""
    decisions = ai_traffic_service.decision_history[-50:]  # Last 50 decisions
    return jsonify(decisions)

# Get current camera data for dashboard
@sumo_bp.route('/api/camera-data', methods=['GET'])
def get_camera_data():
    """Get current camera data for dashboard"""
    sumo_service = current_app.sumo_service
    traci_conn = sumo_service.traci if sumo_service.is_running else None
    
    camera_data = camera_service.get_combined_camera_data(traci_conn)
    return jsonify(camera_data)

# @sumo_bp.route('/api/traffic-lights/<tl_id>/update-config', methods=['POST'])
# def update_traffic_light_config(tl_id):
#     """Manually update traffic light configuration"""
#     if not sumo_service.is_running or not sumo_service.traci:
#         return jsonify({"success": False, "error": "Simulation not running"})
    
#     try:
#         # Get current traffic light data
#         program_id = sumo_service.traci.trafficlight.getProgram(tl_id)
#         current_phase = sumo_service.traci.trafficlight.getPhase(tl_id)
        
#         # Manually call the update method
#         sumo_service._update_traffic_light_config(tl_id, program_id, current_phase)
        
#         # Check if config was created
#         from app.models.traffic_light import TrafficLightConfig
#         config = TrafficLightConfig.query.filter_by(traffic_light_id=tl_id).first()
        
#         if config:
#             return jsonify({
#                 "success": True,
#                 "message": f"Traffic light config updated for {tl_id}",
#                 "config": config.to_dict()
#             })
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": "Config still not created after update attempt"
#             })
            
#     except Exception as e:
#         return jsonify({"success": False, "error": f"Failed to update config: {str(e)}"})
 

# @sumo_bp.route('/api/force-tl-update', methods=['POST'])
# def force_traffic_light_update():
#     """Force an immediate traffic light data update"""
#     result = sumo_service.force_traffic_light_update()
#     return jsonify(result)

# @sumo_bp.route('/api/debug/traci', methods=['GET'])
# def debug_traci():
#     """Debug TraCI connection and available traffic lights"""
#     if not sumo_service.is_running or not sumo_service.traci:
#         return jsonify({"error": "Simulation not running"})
    
#     try:
#         import traci
#         tl_ids = sumo_service.traci.trafficlight.getIDList()
        
#         # Test individual traffic light access
#         tl_details = []
#         for tl_id in tl_ids[:3]:  # Test first 3 to avoid overload
#             try:
#                 state = sumo_service.traci.trafficlight.getRedYellowGreenState(tl_id)
#                 phase = sumo_service.traci.trafficlight.getPhase(tl_id)
#                 tl_details.append({
#                     'id': tl_id,
#                     'state': state,
#                     'phase': phase,
#                     'accessible': True
#                 })
#             except Exception as e:
#                 tl_details.append({
#                     'id': tl_id,
#                     'accessible': False,
#                     'error': str(e)
#                 })
        
#         return jsonify({
#             "traci_connected": True,
#             "traffic_light_count": len(tl_ids),
#             "traffic_light_ids": tl_ids,
#             "test_results": tl_details
#         })
        
#     except Exception as e:
#         return jsonify({"error": f"TraCI debug failed: {str(e)}"})