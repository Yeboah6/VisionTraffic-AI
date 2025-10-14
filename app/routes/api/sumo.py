from flask import Blueprint, render_template, jsonify, request, current_app
from app.extensions import db

# Services
from app.services.optimized_sumo_service import optimized_sumo_service as sumo_service
# from app.services.camera_service import camera_service
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



# Get current vehicle list with detailed information Endpoints
# @sumo_bp.route('/api/vehicles', methods=['GET'])
# def get_vehicles():
#     """Get current vehicle list with detailed information"""
#     vehicles = sumo_service.get_vehicle_list()
#     return jsonify(vehicles)





# Get all cameras and their current status
# @sumo_bp.route('/api/cameras', methods=['GET'])
# def get_cameras():
#     """Get all cameras and their current status"""
#     cameras = Camera.query.all()
#     current_data = camera_service.get_combined_camera_data()
    
#     return jsonify({
#         'cameras': [cam.to_dict() for cam in cameras],
#         'current_data': current_data
#     })

# Add a new camera (real or virtual)
# @sumo_bp.route('/api/cameras/add', methods=['POST'])
# def add_camera():
#     """Add a new camera (real or virtual)"""
#     data = request.get_json()
    
#     if data['type'] == 'real':
#         camera_service.add_real_camera(
#             data['id'],
#             data['source'],
#             data['location']
#         )
#         # Start processing if requested
#         if data.get('start_processing', False):
#             camera_service.start_real_camera_processing(data['id'])
    
#     elif data['type'] == 'virtual':
#         camera_service.add_virtual_camera(
#             data['id'],
#             data['detector_id'],
#             data['location']
#         )
    
#     # Store in database
#     camera = Camera(
#         id=data['id'],
#         name=data['name'],
#         camera_type=data['type'],
#         source=data.get('source') or data.get('detector_id'),
#         location_lat=data['location']['lat'],
#         location_lng=data['location']['lng'],
#         intersection_id=data.get('intersection_id')
#     )
#     db.session.add(camera)
#     db.session.commit()
    
#     return jsonify({'success': True, 'camera': camera.to_dict()})

# Get recent AI decisions
# @sumo_bp.route('/api/ai-decisions', methods=['GET'])
# def get_ai_decisions():
#     """Get recent AI decisions"""
#     decisions = ai_traffic_service.decision_history[-50:]  # Last 50 decisions
#     return jsonify(decisions)

# Get current camera data for dashboard
# @sumo_bp.route('/api/camera-data', methods=['GET'])
# def get_camera_data():
#     """Get current camera data for dashboard"""
#     sumo_service = current_app.sumo_service
#     traci_conn = sumo_service.traci if sumo_service.is_running else None
    
#     camera_data = camera_service.get_combined_camera_data(traci_conn)
#     return jsonify(camera_data)