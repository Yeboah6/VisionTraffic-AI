from flask import Blueprint, jsonify, request

# Services
from app.services.tls_data_service import tls_data_service
from app.services.tls_config_service import tls_config_service

tls_bp = Blueprint('tls', __name__)

@tls_bp.route('/api/tls/snapshot', methods=['GET'])
def get_tls_snapshot():
    """Get current TLS snapshot from running simulation"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        
        if not optimized_sumo_service.is_running:
            return jsonify({
                "success": False,
                "error": "No simulation running",
                "is_running": False
            }), 400
        
        # Get TLS data with fallback
        tls_data = optimized_sumo_service.get_tls_data()
        
        # Check if we actually have TLS data
        if not tls_data.get('tls_snapshot'):
            return jsonify({
                "success": False,
                "error": "TLS data not yet available (may be collecting)",
                "is_running": True,
                "simulation_step": optimized_sumo_service.simulation_step
            }), 425  # 425 Too Early
            
        return jsonify({
            "success": True,
            "is_running": True,
            "simulation_step": optimized_sumo_service.simulation_step,
            "data": tls_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to get TLS snapshot: {str(e)}"
        }), 500

@tls_bp.route('/api/tls/analysis/<tl_id>', methods=['GET'])
def get_tls_analysis(tl_id):
    """Get comprehensive analysis for a specific traffic light"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        analysis = tls_data_service.get_tls_analysis(tl_id, hours)
        
        if "error" in analysis:
            return jsonify({
                "success": False,
                "error": analysis["error"]
            }), 404
        
        return jsonify({
            "success": True,
            "analysis": analysis
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@tls_bp.route('/api/tls/realtime', methods=['GET'])
def get_realtime_tls_data():
    """Get real-time TLS data from service"""
    try:
        return jsonify({
            "success": True,
            "realtime_data": tls_data_service.real_time_data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Get all traffic lights in current simulation
@tls_bp.route('/api/tls/all', methods=['GET'])
def get_all_tls():
    """Get all traffic lights in current simulation"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        
        if not optimized_sumo_service.is_running:
            return jsonify({
                "success": False,
                "error": "No simulation running"
            }), 400
        
        tls_data = optimized_sumo_service.get_tls_data()
        traffic_lights = tls_data.get('tls_snapshot', {}).get('traffic_lights', {})
        
        return jsonify({
            "success": True,
            "traffic_lights": list(traffic_lights.keys()),
            "count": len(traffic_lights),
            "details": {
                tl_id: {
                    'state': data.get('state', ''),
                    'phase': data.get('phase', ''),
                    'phase_name': data.get('phase_name', '')
                }
                for tl_id, data in traffic_lights.items()
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Get overall TLS performance metrics
@tls_bp.route('/api/tls/performance', methods=['GET'])
def get_tls_performance():
    """Get overall TLS performance metrics"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        
        if not optimized_sumo_service.is_running:
            return jsonify({
                "success": False,
                "error": "No simulation running"
            }), 400
        
        tls_data = optimized_sumo_service.get_tls_data()
        summary = tls_data.get('tls_snapshot', {}).get('summary', {})
        
        return jsonify({
            "success": True,
            "performance": summary
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
# Get all TLS configurations for current scenario
@tls_bp.route('/api/tls/configs', methods=['GET'])
def get_all_tls_configs():
    """Get all TLS configurations for current scenario"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        
        scenario = request.args.get('scenario')
        configs_data = optimized_sumo_service.get_tls_configs(scenario)
        
        return jsonify({
            "success": True,
            "data": configs_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@tls_bp.route('/api/tls/configs/<tl_id>', methods=['GET'])
def get_tls_config(tl_id):
    """Get specific TLS configuration"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        
        scenario = request.args.get('scenario', optimized_sumo_service.current_config)
        if not scenario:
            return jsonify({
                "success": False,
                "error": "No scenario specified and no current simulation"
            }), 400
        
        config = tls_config_service.get_tls_config(tl_id, scenario)
        
        if not config:
            return jsonify({
                "success": False,
                "error": f"Configuration not found for {tl_id} in scenario {scenario}"
            }), 404
        
        return jsonify({
            "success": True,
            "config": config
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@tls_bp.route('/api/tls/configs/scenarios', methods=['GET'])
def get_config_scenarios():
    """Get all scenarios that have TLS configurations"""
    try:
        from app.extensions import db
        from app.models.traffic_light import TrafficLightConfig
        
        scenarios = db.session.query(TrafficLightConfig.scenario).distinct().all()
        scenario_list = [s[0] for s in scenarios]
        
        return jsonify({
            "success": True,
            "scenarios": scenario_list,
            "count": len(scenario_list)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@tls_bp.route('/api/tls/configs/stats', methods=['GET'])
def get_config_stats():
    """Get TLS configuration statistics"""
    try:
        scenario = request.args.get('scenario')
        if not scenario:
            return jsonify({
                "success": False,
                "error": "Scenario parameter required"
            }), 400
        
        configs = tls_config_service.get_all_configs_for_scenario(scenario)
        
        stats = {
            "total_configs": len(configs),
            "average_optimization_score": 0,
            "score_distribution": {"A": 0, "B": 0, "C": 0, "D": 0},
            "adaptive_count": 0,
            "average_cycle_time": 0
        }
        
        if configs:
            total_score = sum(config.get('optimization_score', 0) for config in configs)
            total_cycle_time = sum(config.get('cycle_time', 0) for config in configs)
            
            stats["average_optimization_score"] = round(total_score / len(configs), 2)
            stats["average_cycle_time"] = round(total_cycle_time / len(configs), 2)
            stats["adaptive_count"] = sum(1 for config in configs if config.get('is_adaptive', False))
            
            # Score distribution
            for config in configs:
                score = config.get('optimization_score', 0)
                if score >= 80:
                    stats["score_distribution"]["A"] += 1
                elif score >= 65:
                    stats["score_distribution"]["B"] += 1
                elif score >= 50:
                    stats["score_distribution"]["C"] += 1
                else:
                    stats["score_distribution"]["D"] += 1
        
        return jsonify({
            "success": True,
            "stats": stats,
            "scenario": scenario
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# @tls_bp.route('/api/tls/collection-status', methods=['GET'])
# def get_collection_status():
#     """Get TLS data collection status"""
#     try:
#         from app.services.optimized_sumo_service import optimized_sumo_service
        
#         status = optimized_sumo_service.get_data_collection_status()
        
#         return jsonify({
#             "success": True,
#             "collection_status": status
#         })
        
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500