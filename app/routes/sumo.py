# app/routes/sumo.py
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
import logging
from app.services.sumo_service import sumo_service

logger = logging.getLogger(__name__)

sumo_bp = Blueprint('sumo', __name__, url_prefix='/sumo')

@sumo_bp.route('/dashboard')
@login_required
def dashboard():
    """SUMO simulation dashboard"""
    return render_template('sumo/dashboard.html')

@sumo_bp.route('/api/start', methods=['POST'])
@login_required
def start_simulation():
    """Start SUMO simulation"""
    try:
        data = request.get_json() or {}
        config_file = data.get('config_file', 'complex.sumocfg')
        gui = data.get('gui', False)
        
        success = sumo_service.start_simulation(config_file, gui)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Simulation started successfully',
                'config_file': config_file
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to start simulation'
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting simulation: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/stop', methods=['POST'])
@login_required
def stop_simulation():
    """Stop SUMO simulation"""
    try:
        sumo_service.stop_simulation()
        return jsonify({
            'status': 'success',
            'message': 'Simulation stopped successfully'
        })
    except Exception as e:
        logger.error(f"Error stopping simulation: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/step', methods=['POST'])
@login_required
def step_simulation():
    """Advance simulation by one step"""
    try:
        success = sumo_service.step_simulation()
        
        if success:
            return jsonify({
                'status': 'success',
                'data': sumo_service.get_simulation_data()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Simulation not running or step failed'
            }), 400
            
    except Exception as e:
        logger.error(f"Error stepping simulation: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/status')
@login_required
def simulation_status():
    """Get simulation status and current data"""
    try:
        return jsonify({
            'status': 'success',
            'running': sumo_service.is_running(),
            'data': sumo_service.get_simulation_data()
        })
    except Exception as e:
        logger.error(f"Error getting simulation status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/run_continuous', methods=['POST'])
@login_required
def run_continuous():
    """Start continuous simulation"""
    try:
        data = request.get_json() or {}
        max_steps = data.get('max_steps', 3600)
        
        if not sumo_service.is_running():
            return jsonify({
                'status': 'error',
                'message': 'Simulation not started. Start simulation first.'
            }), 400
        
        success = sumo_service.run_continuous_simulation(max_steps)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Continuous simulation started',
                'max_steps': max_steps
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to start continuous simulation'
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting continuous simulation: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/vehicles')
@login_required
def get_vehicles():
    """Get current vehicles information"""
    try:
        data = sumo_service.get_simulation_data()
        return jsonify({
            'status': 'success',
            'vehicles': data['vehicles'],
            'total_vehicles': data['total_vehicles'],
            'average_speed': data['average_speed']
        })
    except Exception as e:
        logger.error(f"Error getting vehicles: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/vehicles/<vehicle_id>')
@login_required
def get_vehicle(vehicle_id):
    """Get specific vehicle information"""
    try:
        vehicle_info = sumo_service.get_vehicle_info(vehicle_id)
        
        if vehicle_info:
            return jsonify({
                'status': 'success',
                'vehicle': vehicle_info
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Vehicle not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting vehicle {vehicle_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/traffic_lights')
@login_required
def get_traffic_lights():
    """Get current traffic lights information"""
    try:
        data = sumo_service.get_simulation_data()
        return jsonify({
            'status': 'success',
            'traffic_lights': data['traffic_lights']
        })
    except Exception as e:
        logger.error(f"Error getting traffic lights: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/traffic_lights/<tl_id>/phase', methods=['POST'])
@login_required
def set_traffic_light_phase(tl_id):
    """Set traffic light phase"""
    try:
        data = request.get_json() or {}
        phase = data.get('phase')
        
        if phase is None:
            return jsonify({
                'status': 'error',
                'message': 'Phase number required'
            }), 400
        
        success = sumo_service.set_traffic_light_phase(tl_id, int(phase))
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Traffic light {tl_id} phase set to {phase}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to set traffic light {tl_id} phase'
            }), 500
            
    except Exception as e:
        logger.error(f"Error setting traffic light phase: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    """Add a vehicle to the simulation"""
    try:
        data = request.get_json() or {}
        route_id = data.get('route_id')
        vehicle_id = data.get('vehicle_id')
        depart_time = data.get('depart_time')
        
        if not route_id:
            return jsonify({
                'status': 'error',
                'message': 'Route ID is required'
            }), 400
        
        success = sumo_service.add_vehicle(route_id, vehicle_id, depart_time)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Vehicle added successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add vehicle'
            }), 500
            
    except Exception as e:
        logger.error(f"Error adding vehicle: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/network')
@login_required
def get_network_info():
    """Get network information"""
    try:
        network_info = sumo_service.get_network_info()
        return jsonify({
            'status': 'success',
            'network': network_info
        })
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sumo_bp.route('/api/statistics')
@login_required
def get_statistics():
    """Get simulation statistics"""
    try:
        data = sumo_service.get_simulation_data()
        
        # Calculate additional statistics
        vehicles = data['vehicles']
        waiting_vehicles = sum(1 for v in vehicles.values() if v.get('waiting_time', 0) > 0)
        total_waiting_time = sum(v.get('waiting_time', 0) for v in vehicles.values())
        
        statistics = {
            'current_time': data['current_time'],
            'total_vehicles': data['total_vehicles'],
            'average_speed': data['average_speed'],
            'waiting_vehicles': waiting_vehicles,
            'total_waiting_time': total_waiting_time,
            'average_waiting_time': total_waiting_time / len(vehicles) if vehicles else 0,
            'traffic_lights_count': len(data['traffic_lights'])
        }
        
        return jsonify({
            'status': 'success',
            'statistics': statistics
        })
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500