# routes/emergency_routes.py - Updated routes
from flask import Blueprint, render_template, request, jsonify
# from app.services.emergency_scheduler import emergency_scheduler
from app.services.emergency import emergency_service
from app.models.traffic_light import TrafficLightConfig
from datetime import datetime

emergency_bp = Blueprint('emergency', __name__, url_prefix='/api/emergency')


@emergency_bp.route('/greenwave-schedule', methods=['GET'])
def greenwave_schedule():

    return render_template('emergency/greenwave_schedule.html')

@emergency_bp.route('/emergency-schedule', methods=['GET'])
def emergency_schedule():

    return render_template('emergency/emergency_schedule.html')

@emergency_bp.route('/active-emergency', methods=['GET'])
def active_emergency():

    return render_template('emergency/active_emergency.html')

# @emergency_bp.route('/schedule', methods=['POST'])
# def schedule_emergency():
#     """Schedule emergency vehicle via web form"""
#     try:
#         data = request.get_json()
        
#         # Validate required fields - ADD SCENARIO TO REQUIRED FIELDS
#         required_fields = ['scenario', 'emergency_type', 'priority', 'vehicle_id', 'departure_time', 'route_edges']
#         for field in required_fields:
#             if field not in data:
#                 return jsonify({
#                     "success": False,
#                     "error": f"Missing required field: {field}"
#                 }), 400
        
#         result = emergency_scheduler.schedule_emergency(data)
        
#         if result['success']:
#             return jsonify({
#                 "success": True,
#                 "message": result['message'],
#                 "emergency_id": result['emergency_id']
#             }), 201
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": result['error']
#             }), 400
            
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": f"Server error: {str(e)}"
#         }), 500

# @emergency_bp.route('/green-wave/schedule', methods=['POST'])
# def schedule_green_wave():
#     """Schedule green wave manually via web form"""
#     try:
#         data = request.get_json()
        
#         # Validate required fields
#         required_fields = ['traffic_light_id', 'scheduled_start', 'duration']
#         for field in required_fields:
#             if field not in data:
#                 return jsonify({
#                     "success": False,
#                     "error": f"Missing required field: {field}"
#                 }), 400
        
#         result = emergency_scheduler.schedule_green_wave(data)
        
#         if result['success']:
#             return jsonify({
#                 "success": True,
#                 "message": result['message'],
#                 "green_wave_id": result['green_wave_id']
#             }), 201
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": result['error']
#             }), 400
            
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": f"Server error: {str(e)}"
#         }), 500
        
# @emergency_bp.route('/traffic-lights/<tl_id>', methods=['GET'])
# def get_traffic_light_details(tl_id):
#     """Get detailed information about a specific traffic light"""
#     try:
#         details = emergency_scheduler.get_traffic_light_details(tl_id)
#         if details:
#             return jsonify({
#                 "success": True,
#                 "traffic_light": details
#             }), 200
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": f"Traffic light {tl_id} not found"
#             }), 404
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# @emergency_bp.route('/traffic-lights/for-edge/<edge>', methods=['GET'])
# def get_traffic_lights_for_edge(edge):
#     """Get traffic lights that control a specific edge"""
#     try:
#         traffic_lights = emergency_scheduler.get_traffic_lights_for_edge(edge)
#         return jsonify({
#             "success": True,
#             "edge": edge,
#             "traffic_lights": traffic_lights,
#             "count": len(traffic_lights)
#         }), 200
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# @emergency_bp.route('/active', methods=['GET'])
# def get_active_emergencies():
#     """Get all active emergency schedules"""
#     try:
#         emergencies = emergency_scheduler.get_active_emergencies()
#         return jsonify({
#             "success": True,
#             "emergencies": emergencies,
#             "count": len(emergencies)
#         }), 200
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# @emergency_bp.route('/green-wave/active', methods=['GET'])
# def get_active_green_waves():
#     """Get all active green wave schedules"""
#     try:
#         green_waves = emergency_scheduler.get_active_green_waves()
#         return jsonify({
#             "success": True,
#             "green_waves": green_waves,
#             "count": len(green_waves)
#         }), 200
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# @emergency_bp.route('/<emergency_id>/cancel', methods=['POST'])
# def cancel_emergency(emergency_id):
#     """Cancel a scheduled emergency"""
#     try:
#         result = emergency_scheduler.cancel_emergency(emergency_id)
        
#         if result['success']:
#             return jsonify({
#                 "success": True,
#                 "message": result['message']
#             }), 200
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": result['error']
#             }), 400
            
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

# @emergency_bp.route('/green-wave/<green_wave_id>/cancel', methods=['POST'])
# def cancel_green_wave(green_wave_id):
#     """Cancel a scheduled green wave"""
#     try:
#         result = emergency_scheduler.cancel_green_wave(green_wave_id)
        
#         if result['success']:
#             return jsonify({
#                 "success": True,
#                 "message": result['message']
#             }), 200
#         else:
#             return jsonify({
#                 "success": False,
#                 "error": result['error']
#             }), 400
            
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500
    
# @emergency_bp.route('/route-details', methods=['POST'])
# def get_route_details():
#     """Get detailed information about a route including TLS-controlled edges"""
#     try:
#         data = request.get_json()
#         edges = data.get('edges', [])
        
#         if not edges:
#             return jsonify({
#                 "success": False,
#                 "error": "No edges provided"
#             }), 400
        
#         route_details = {
#             'edges': edges,
#             'traffic_lights': [],
#             'estimated_time': 0,
#             'total_lanes': 0,
#             'edge_details': []
#         }
        
#         # Calculate route details based on TLS config
#         edge_travel_times = {
#             'E0': 10.0, '-E0': 10.0, 'E1': 12.0, '-E1': 12.0,
#             'E2': 8.0, '-E2': 8.0, 'E0.55': 10.0, '-E0.55': 10.0
#         }
        
#         total_time = 0
#         controlled_lanes = set()
        
#         for edge in edges:
#             # Get traffic lights for this edge
#             tls_for_edge = emergency_scheduler.get_traffic_lights_for_edge(edge)
#             edge_tls = [tls['traffic_light_id'] for tls in tls_for_edge]
            
#             # Add to route traffic lights
#             for tl_id in edge_tls:
#                 if tl_id not in route_details['traffic_lights']:
#                     route_details['traffic_lights'].append(tl_id)
            
#             # Get TLS details for lane information
#             if tls_for_edge:
#                 tls_details = emergency_scheduler.get_traffic_light_details(tls_for_edge[0]['traffic_light_id'])
#                 if tls_details and 'controlled_lanes' in tls_details:
#                     for lane in tls_details['controlled_lanes']:
#                         if lane.startswith(edge + '_'):
#                             controlled_lanes.add(lane)
            
#             # Calculate travel time
#             travel_time = edge_travel_times.get(edge, 10.0)
#             total_time += travel_time
            
#             # Add edge details
#             route_details['edge_details'].append({
#                 'edge': edge,
#                 'traffic_lights': edge_tls,
#                 'travel_time': travel_time,
#                 'lanes': len([lane for lane in controlled_lanes if lane.startswith(edge + '_')])
#             })
        
#         route_details['estimated_time'] = total_time
#         route_details['total_lanes'] = len(controlled_lanes)
        
#         return jsonify({
#             "success": True,
#             "route_details": route_details
#         }), 200
        
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": f"Server error: {str(e)}"
#         }), 500

# @emergency_bp.route('/traffic-lights', methods=['GET'])
# def get_traffic_lights():
#     """Get all available traffic lights from TLS config, optionally filtered by scenario"""
#     try:
#         scenario = request.args.get('scenario')
        
#         if scenario:
#             # Filter by specific scenario
#             traffic_lights = emergency_scheduler.get_traffic_lights_by_scenario(scenario)
#         else:
#             # Get all traffic lights
#             traffic_lights = emergency_scheduler.get_available_traffic_lights()
            
#         return jsonify({
#             "success": True,
#             "traffic_lights": traffic_lights,
#             "count": len(traffic_lights),
#             "scenario": scenario or "all"
#         }), 200
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500
    
@emergency_bp.route('/available-routes', methods=['GET'])
def get_available_routes():
    """Get predefined route options with real TLS-controlled edges"""
    try:
        
        scenario = request.args.get('scenario', 'accra')
        
        # Get all TLS configurations to understand network topology
        tls_configs = TrafficLightConfig.query.filter_by(scenario=scenario).all()
        
        # Build network topology from TLS controlled lanes
        edge_to_tls = {}
        for config in tls_configs:
            if config.controlled_lanes:
                for lane in config.controlled_lanes:
                    edge = lane.split('_')[0]  # Extract edge from lane ID
                    if edge not in edge_to_tls:
                        edge_to_tls[edge] = []
                    if config.traffic_light_id not in edge_to_tls[edge]:
                        edge_to_tls[edge].append(config.traffic_light_id)
        
        # Define routes based on actual network topology
        routes = {
            "hospital_to_city_center": {
                "name": "Hospital to City Center",
                "edges": [],
                "estimated_time": 0,
                "description": "Route from main hospital to city center",
                "traffic_lights": []
            },
            "fire_station_to_industrial": {
                "name": "Fire Station to Industrial Area", 
                "edges": [],
                "estimated_time": 0,
                "description": "Route from fire station to industrial area",
                "traffic_lights": []
            },
            "police_hq_to_residential": {
                "name": "Police HQ to Residential Area",
                "edges": [],
                "estimated_time": 0,
                "description": "Route from police headquarters to residential area",
                "traffic_lights": []
            }
        }
        
        # Auto-generate routes based on available edges
        available_edges = list(edge_to_tls.keys())
        
        if available_edges:
            # Create simple routes using available edges
            if len(available_edges) >= 3:
                routes["hospital_to_city_center"]["edges"] = available_edges[:3]
                routes["fire_station_to_industrial"]["edges"] = [available_edges[2], available_edges[0], available_edges[1]]
                routes["police_hq_to_residential"]["edges"] = [available_edges[1], available_edges[0], available_edges[2]]
            else:
                # Fallback to hardcoded edges if not enough data
                routes["hospital_to_city_center"]["edges"] = ["E0", "E1", "E2"]
                routes["fire_station_to_industrial"]["edges"] = ["E2", "E0.55", "E1"]
                routes["police_hq_to_residential"]["edges"] = ["E1", "E0", "E2"]
        
        # Calculate route details based on actual edge lengths and speed limits
        edge_travel_times = {}
        try:
            # Get edge information from SUMO network
            for edge_id in edge_to_tls.keys():
            # Default values if edge details cannot be retrieved
                length = 100  # meters
                speed_limit = 13.89  # 50 km/h in m/s
            
            try:
                # Try to get actual edge details from TrafficLightConfig
                edge_config = TrafficLightConfig.query.filter(
                TrafficLightConfig.controlled_lanes.like(f"{edge_id}_%")
                ).first()
                
                if edge_config and edge_config.edge_length and edge_config.speed_limit:
                    length = edge_config.edge_length
                    speed_limit = edge_config.speed_limit
            except:
                pass
            
            # Calculate travel time in seconds
            travel_time = length / speed_limit
            edge_travel_times[edge_id] = round(travel_time, 1)
            
            # Add reverse edge with same travel time
            if edge_id.startswith('-'):
                edge_travel_times[edge_id[1:]] = round(travel_time, 1)
            else:
                edge_travel_times[f'-{edge_id}'] = round(travel_time, 1)
        except:
            # Fallback to default times if calculation fails
            edge_travel_times = {
            'E0': 10.0, '-E0': 10.0, 'E1': 12.0, '-E1': 12.0,
            'E2': 8.0, '-E2': 8.0, 'E0.55': 10.0, '-E0.55': 10.0
            }
        
        for route_name, route_info in routes.items():
            total_time = 0
            route_traffic_lights = []
            
            for edge in route_info['edges']:
                # Add travel time
                travel_time = edge_travel_times.get(edge, 10.0)
                total_time += travel_time
                
                # Add traffic lights for this edge
                if edge in edge_to_tls:
                    for tl_id in edge_to_tls[edge]:
                        if tl_id not in route_traffic_lights:
                            route_traffic_lights.append(tl_id)
            
            route_info['estimated_time'] = total_time
            route_info['traffic_lights'] = route_traffic_lights
        
        return jsonify({
            "success": True,
            "routes": routes
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

##########################################################
@emergency_bp.route('/stats', methods=['GET'])
def get_emergency_stats():
    """
    Get emergency service statistics
    """
    try:
        stats = emergency_service.get_stats()
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get emergency stats: {str(e)}'
        }), 500

@emergency_bp.route('/active', methods=['GET'])
def get_active_emergencies():
    """
    Get currently active emergency vehicles
    """
    try:
        active_emergencies = list(emergency_service.active_emergencies.values())
        
        return jsonify({
            'success': True,
            'data': {
                'active_emergencies': active_emergencies,
                'count': len(active_emergencies)
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get active emergencies: {str(e)}'
        }), 500

@emergency_bp.route('/registry', methods=['GET'])
def get_emergency_registry():
    """
    Get all registered emergency vehicles
    """
    try:
        registry = list(emergency_service.emergency_registry.values())
        
        return jsonify({
            'success': True,
            'data': {
                'registry': registry,
                'count': len(registry)
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get emergency registry: {str(e)}'
        }), 500

@emergency_bp.route('/vehicles', methods=['GET'])
def get_all_emergency_data():
    """
    Get comprehensive emergency vehicle data including stats, active, and registry
    """
    try:
        stats = emergency_service.get_stats()
        active_emergencies = list(emergency_service.active_emergencies.values())
        registry = list(emergency_service.emergency_registry.values())
        
        return jsonify({
            'success': True,
            'data': {
                'statistics': stats,
                'active_emergencies': active_emergencies,
                'emergency_registry': registry,
                'summary': {
                    'total_registered': len(registry),
                    'currently_active': len(active_emergencies),
                    'green_waves_activated': stats.get('green_waves_activated', 0)
                }
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get emergency data: {str(e)}'
        }), 500

@emergency_bp.route('/vehicle/<vehicle_id>', methods=['GET'])
def get_emergency_vehicle(vehicle_id):
    """
    Get specific emergency vehicle data by ID
    """
    try:
        # Check active emergencies first
        if vehicle_id in emergency_service.active_emergencies:
            vehicle_data = emergency_service.active_emergencies[vehicle_id]
            status = 'ACTIVE'
        # Check registry
        elif vehicle_id in emergency_service.emergency_registry:
            vehicle_data = emergency_service.emergency_registry[vehicle_id]
            status = 'REGISTERED'
        else:
            return jsonify({
                'success': False,
                'error': f'Emergency vehicle {vehicle_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'vehicle': vehicle_data,
                'status': status
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get emergency vehicle data: {str(e)}'
        }), 500

@emergency_bp.route('/types', methods=['GET'])
def get_emergency_types():
    """
    Get emergency vehicle type statistics
    """
    try:
        type_counts = {}
        priority_counts = {}
        
        # Count by type from registry
        for vehicle_data in emergency_service.emergency_registry.values():
            vehicle_type = vehicle_data.get('emergency_type', 'UNKNOWN')
            priority = vehicle_data.get('priority', 'MEDIUM')
            
            type_counts[vehicle_type] = type_counts.get(vehicle_type, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return jsonify({
            'success': True,
            'data': {
                'type_distribution': type_counts,
                'priority_distribution': priority_counts,
                'detection_patterns': emergency_service.emergency_patterns
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get emergency types: {str(e)}'
        }), 500

@emergency_bp.route('/status', methods=['GET'])
def get_emergency_service_status():
    """
    Get overall emergency service status
    """
    try:
        stats = emergency_service.get_stats()
        
        # Determine service health status
        total_vehicles = len(emergency_service.emergency_registry)
        active_vehicles = len(emergency_service.active_emergencies)
        
        status = "HEALTHY"
        if total_vehicles == 0 and active_vehicles == 0:
            status = "INACTIVE"
        elif active_vehicles > 0 and stats.get('green_waves_activated', 0) == 0:
            status = "MONITORING"
        elif stats.get('green_waves_activated', 0) > 0:
            status = "ACTIVE_GREEN_WAVES"
        
        return jsonify({
            'success': True,
            'data': {
                'service_status': status,
                'is_operational': True,
                'summary': {
                    'total_registered_vehicles': total_vehicles,
                    'currently_active_vehicles': active_vehicles,
                    'green_waves_activated': stats.get('green_waves_activated', 0),
                    'detected_emergencies': stats.get('detected_emergencies', 0)
                },
                'last_updated': datetime.utcnow().isoformat()
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get service status: {str(e)}'
        }), 500