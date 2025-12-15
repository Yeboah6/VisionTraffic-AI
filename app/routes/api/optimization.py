"""
Add these API endpoints to your Flask app routes.
"""

from flask import Blueprint, jsonify, request
from app.services.optimized_sumo_service import optimized_sumo_service
from app.services.tls_optimization import tls_optimization_service
# from app.services.ai_decision import enhanced_ai_decision_service

optimization_bp = Blueprint('optimization', __name__)


# ==================== TLS OPTIMIZATION CONTROL ====================

@optimization_bp.route('/optimization/enable', methods=['POST'])
def enable_optimization():
    """Enable AI-driven TLS optimization during simulation"""
    try:
        optimized_sumo_service.enable_tls_optimization()
        tls_optimization_service.enable_optimization()
        
        return jsonify({
            'success': True,
            'message': 'TLS optimization enabled',
            'status': optimized_sumo_service.get_optimization_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/disable', methods=['POST'])
def disable_optimization():
    """Disable AI-driven TLS optimization"""
    try:
        optimized_sumo_service.disable_tls_optimization()
        tls_optimization_service.disable_optimization()
        
        return jsonify({
            'success': True,
            'message': 'TLS optimization disabled',
            'status': optimized_sumo_service.get_optimization_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/interval', methods=['POST'])
def set_optimization_interval():
    """Set optimization interval (how often optimizations are applied)"""
    try:
        data = request.get_json()
        interval = data.get('interval', 30)
        
        optimized_sumo_service.set_optimization_interval(interval)
        tls_optimization_service.set_optimization_interval(interval)
        
        return jsonify({
            'success': True,
            'message': f'Optimization interval set to {interval} steps',
            'interval': interval
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/confidence-threshold', methods=['POST'])
def set_confidence_threshold():
    """Set minimum confidence threshold for applying optimizations"""
    try:
        data = request.get_json()
        threshold = data.get('threshold', 0.6)
        
        tls_optimization_service.set_confidence_threshold(threshold)
        
        return jsonify({
            'success': True,
            'message': f'Confidence threshold set to {threshold}',
            'threshold': threshold
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/safety-limits', methods=['POST'])
def update_safety_limits():
    """Update safety constraint limits"""
    try:
        limits = request.get_json()
        
        tls_optimization_service.update_safety_limits(limits)
        
        return jsonify({
            'success': True,
            'message': 'Safety limits updated',
            'limits': tls_optimization_service.safety_limits
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== OPTIMIZATION STATUS & STATISTICS ====================

@optimization_bp.route('/optimization/status', methods=['GET'])
def get_optimization_status():
    """Get current optimization status"""
    try:
        return jsonify({
            'success': True,
            'simulation_status': optimized_sumo_service.get_optimization_status(),
            'service_stats': tls_optimization_service.get_optimization_stats(),
            # 'ai_status': enhanced_ai_decision_service.get_ai_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/stats', methods=['GET'])
def get_optimization_stats():
    """Get detailed optimization statistics"""
    try:
        return jsonify({
            'success': True,
            'stats': tls_optimization_service.get_optimization_stats()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/history', methods=['GET'])
def get_optimization_history():
    """Get optimization history"""
    try:
        tl_id = request.args.get('tl_id')
        limit = int(request.args.get('limit', 20))
        
        history = tls_optimization_service.get_tls_optimization_history(tl_id, limit)
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@optimization_bp.route('/optimization/recent', methods=['GET'])
def get_recent_optimizations():
    """Get recent optimizations from database"""
    try:
        scenario = request.args.get('scenario')
        limit = int(request.args.get('limit', 50))
        
        optimizations = tls_optimization_service.get_recent_optimizations(scenario, limit)
        
        return jsonify({
            'success': True,
            'optimizations': optimizations,
            'count': len(optimizations)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
