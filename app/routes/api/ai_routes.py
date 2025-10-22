from flask import Blueprint, jsonify, request
from app.services.ai_traffic_service import ai_traffic_service

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/api/ai/status', methods=['GET'])
def get_ai_status():
    """Get AI system status"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        ai_status = optimized_sumo_service.get_ai_status()
        
        return jsonify({
            "success": True,
            "ai_status": ai_status
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/optimization/enable', methods=['POST'])
def enable_ai_optimization():
    """Enable AI optimization"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        optimized_sumo_service.enable_ai_optimization()
        
        return jsonify({
            "success": True,
            "message": "AI optimization enabled"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/optimization/disable', methods=['POST'])
def disable_ai_optimization():
    """Disable AI optimization"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        optimized_sumo_service.disable_ai_optimization()
        
        return jsonify({
            "success": True,
            "message": "AI optimization disabled"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/optimization/interval', methods=['POST'])
def set_ai_optimization_interval():
    """Set AI optimization interval"""
    try:
        interval = request.json.get('interval', 30)
        
        from app.services.optimized_sumo_service import optimized_sumo_service
        optimized_sumo_service.set_ai_optimization_interval(interval)
        
        return jsonify({
            "success": True,
            "message": f"AI optimization interval set to {interval} steps"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/mode', methods=['POST'])
def set_ai_mode():
    """Set AI optimization mode"""
    try:
        mode = request.json.get('mode', 'BALANCED')
        
        ai_traffic_service.set_optimization_mode(mode)
        
        return jsonify({
            "success": True,
            "message": f"AI mode set to {mode}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/learning/enable', methods=['POST'])
def enable_ai_learning():
    """Enable AI learning"""
    try:
        ai_traffic_service.enable_learning()
        
        return jsonify({
            "success": True,
            "message": "AI learning enabled"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/learning/disable', methods=['POST'])
def disable_ai_learning():
    """Disable AI learning"""
    try:
        ai_traffic_service.disable_learning()
        
        return jsonify({
            "success": True,
            "message": "AI learning disabled"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# @ai_bp.route('/api/ai/train/historical', methods=['POST'])
# def train_ai_historical():
#     """Train AI on historical data"""
#     try:
#         days = request.json.get('days', 7)
        
#         result = ai_traffic_service.train_on_historical_data(days)
        
#         return jsonify(result)
        
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500

@ai_bp.route('/api/ai/decisions/recent', methods=['GET'])
def get_recent_ai_decisions():
    """Get recent AI decisions"""
    try:
        from app.services.optimized_sumo_service import optimized_sumo_service
        
        recent_decisions = list(ai_traffic_service.optimization_decisions)[-10:]
        
        return jsonify({
            "success": True,
            "recent_decisions": recent_decisions,
            "total_decisions": len(ai_traffic_service.optimization_decisions),
            "last_decision": optimized_sumo_service.last_ai_decision
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@ai_bp.route('/api/ai/performance', methods=['GET'])
def get_ai_performance():
    """Get AI performance metrics"""
    try:
        recent_decisions = list(ai_traffic_service.optimization_decisions)[-50:]
        
        if not recent_decisions:
            return jsonify({
                "success": True,
                "message": "No AI decisions yet",
                "performance": {}
            })
        
        # Calculate performance metrics
        total_optimizations = sum(d['total_tls_optimized'] for d in recent_decisions)
        avg_congestion = sum(d['overall_congestion'] for d in recent_decisions) / len(recent_decisions)
        avg_health = sum(d['system_health'] for d in recent_decisions) / len(recent_decisions)
        
        optimization_rates = [d['total_tls_optimized'] / len(d.get('decisions', [1])) for d in recent_decisions if d.get('decisions')]
        avg_optimization_rate = sum(optimization_rates) / len(optimization_rates) if optimization_rates else 0
        
        return jsonify({
            "success": True,
            "performance": {
                "decisions_analyzed": len(recent_decisions),
                "total_optimizations": total_optimizations,
                "average_congestion": round(avg_congestion, 2),
                "average_system_health": round(avg_health, 2),
                "average_optimization_rate": round(avg_optimization_rate, 2),
                "performance_trend": "IMPROVING" if avg_health > 0.7 else "STABLE" if avg_health > 0.5 else "DECLINING"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 
        
@ai_bp.route('/api/ai/debug/storage-status', methods=['GET'])
def debug_ai_storage_status():
    """Check AI decision storage status"""
    try:
        from app.services.ai_traffic_service import ai_traffic_service
        from app.services.db_queue import get_db_queue
        from app.models.ai import AIDecisionLog
        
        queue = get_db_queue()
        db_count = AIDecisionLog.query.count() if hasattr(AIDecisionLog, 'query') else 0
        emergency_count = len(ai_traffic_service.emergency_storage)
        
        return jsonify({
            "success": True,
            "storage_status": {
                "db_queue_available": queue is not None,
                "decisions_in_database": db_count,
                "decisions_in_emergency_storage": emergency_count,
                "total_ai_decisions_made": len(ai_traffic_service.optimization_decisions),
                "last_decision": list(ai_traffic_service.optimization_decisions)[-1] if ai_traffic_service.optimization_decisions else None
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ai_bp.route('/api/ai/debug/flush-emergency', methods=['POST'])
def flush_emergency_storage():
    """Flush emergency storage to database"""
    try:
        from app.services.ai_traffic_service import ai_traffic_service
        ai_traffic_service.flush_emergency_storage()
        
        return jsonify({
            "success": True,
            "message": "Emergency storage flush attempted"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500