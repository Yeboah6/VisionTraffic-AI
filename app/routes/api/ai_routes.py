"""
AI Recommendations API Endpoints
Flask routes for accessing AI decision recommendations
"""

from flask import Blueprint, app, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict

from app.services.ai_decision import enhanced_ai_decision_service
from app.services.q_learning import q_learning

from app.models.ai import AIDecisionLog
from app.extensions import db

ai_bp = Blueprint('ai', __name__)


# @ai_bp.route('/api/ai/recommendations', methods=['GET'])
# def get_ai_recommendations():
#     """
#     Get current AI recommendations for all traffic lights
#     SMART MODE: Automatically switches between LIVE and PATTERN mode
#     """
#     try:
#         scenario = request.args.get('scenario', 'accra')
#         limit = int(request.args.get('limit', 10))
#         force_pattern = request.args.get('force_pattern', 'false').lower() == 'true'
        
#         # Get decision statistics
#         stats = enhanced_ai_decision_service.get_decision_statistics()
#         current_mode = stats.get('current_mode', 'UNKNOWN')
        
#         print(f"📊 AI Recommendations API called - Mode: {current_mode}, Scenario: {scenario}")
        
#         # Use smart mode detection
#         recommendations = enhanced_ai_decision_service.get_recommendations(
#             scenario=scenario,
#             limit=limit,
#             force_pattern_mode=force_pattern
#         )
        
#         # Format recommendations
#         formatted_recommendations = []
#         total_confidence = 0
        
#         for rec in recommendations:
#             # Handle both dict and recommendation objects
#             if isinstance(rec, dict):
#                 formatted_recommendations.append({
#                     'tl_id': rec.get('tl_id'),
#                     'timestamp': rec.get('timestamp'),
#                     'action': rec.get('action'),
#                     'action_type': rec.get('action_type'),
#                     'parameters': rec.get('parameters', {}),
#                     'confidence': rec.get('confidence', 0),
#                     'success_rate': rec.get('success_rate', 0.5),
#                     'pattern_matched': rec.get('pattern_matched', False),
#                     'pattern_type': rec.get('pattern_type'),
#                     'match_type': rec.get('match_type'),
#                     'reasoning': rec.get('reasoning', ''),
#                     'recommendations': rec.get('recommendations', []),
#                     'expected_impact': rec.get('expected_impact', {}),
#                     'display_priority': rec.get('display_priority', 'MEDIUM'),
#                     'mode': rec.get('mode', current_mode),
#                     'interval_info': rec.get('interval_info'),
#                     'metrics_summary': rec.get('metrics_summary')
#                 })
#                 total_confidence += rec.get('confidence', 0)
        
#         # Calculate average confidence
#         avg_confidence = round((total_confidence / len(formatted_recommendations) * 100), 1) if formatted_recommendations else 0
        
#         # Enhanced statistics
#         enhanced_stats = {
#             **stats,
#             'avg_confidence': avg_confidence,
#             'active_recommendations': len(formatted_recommendations),
#             'scenario': scenario,
#             'mode': current_mode,
#             'mode_description': 'Live simulation data' if current_mode == 'LIVE' else 'Historical pattern analysis'
#         }
        
#         print(f"✅ Returning {len(formatted_recommendations)} recommendations in {current_mode} mode")
        
#         return jsonify({
#             'success': True,
#             'recommendations': formatted_recommendations,
#             'statistics': enhanced_stats,
#             'timestamp': datetime.utcnow().isoformat(),
#             'mode': current_mode
#         })
        
#     except Exception as e:
#         print(f"❌ Error getting AI recommendations: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({
#             'success': False,
#             'error': str(e),
#             'recommendations': [],
#             'statistics': {},
#             'mode': 'ERROR'
#         }), 500


# @ai_bp.route('/api/ai/recommendations/<tl_id>', methods=['GET'])
# def get_tl_recommendations(tl_id: str):
#     """
#     Get recommendations for a specific traffic light
#     """
#     try:
#         scenario = request.args.get('scenario', 'accra')
        
#         # Get recommendations for this traffic light
#         recommendations = enhanced_ai_decision_service.get_tl_recommendations(tl_id, scenario)
        
#         if not recommendations:
#             return jsonify({
#                 'success': True,
#                 'traffic_light_id': tl_id,
#                 'recommendations': [],
#                 'message': 'No recommendations found for this traffic light'
#             })
        
#         # Format recommendations
#         formatted_recs = []
#         for rec in recommendations:
#             rec_data = rec.get('recommendation', {})
#             formatted_recs.append({
#                 'timestamp': rec.get('timestamp'),
#                 'action': rec_data.get('action'),
#                 'confidence': rec_data.get('confidence'),
#                 'reasoning': rec_data.get('reasoning'),
#                 'pattern_matched': rec_data.get('pattern_matched')
#             })
        
#         return jsonify({
#             'success': True,
#             'traffic_light_id': tl_id,
#             'recommendations': formatted_recs,
#             'total': len(formatted_recs)
#         })
        
#     except Exception as e:
#         print(f"❌ Error getting TL recommendations: {e}")
#         return jsonify({
#             'success': False,
#             'error': str(e),
#             'recommendations': []
#         }), 500


# @ai_bp.route('/api/ai/statistics', methods=['GET'])
# def get_ai_statistics():
#     """
#     Get detailed AI performance statistics
#     """
#     try:
#         # Get decision statistics
#         stats = enhanced_ai_decision_service.get_decision_statistics()
        
#         # Query database for historical performance
#         last_24h = datetime.utcnow() - timedelta(hours=24)
        
#         db_decisions = AIDecisionLog.query.filter(
#             AIDecisionLog.created_at >= last_24h
#         ).all()
        
#         # Calculate additional metrics
#         if db_decisions:
#             total_db_decisions = len(db_decisions)
#             avg_confidence_db = sum(d.confidence for d in db_decisions) / total_db_decisions
#             pattern_matched_db = sum(1 for d in db_decisions if d.pattern_matched)
            
#             db_stats = {
#                 'total_decisions_24h': total_db_decisions,
#                 'avg_confidence_24h': round(avg_confidence_db * 100, 1),
#                 'pattern_match_rate_24h': round(pattern_matched_db / total_db_decisions * 100, 1) if total_db_decisions > 0 else 0
#             }
#         else:
#             db_stats = {
#                 'total_decisions_24h': 0,
#                 'avg_confidence_24h': 0,
#                 'pattern_match_rate_24h': 0
#             }
        
#         return jsonify({
#             'success': True,
#             'statistics': {
#                 **stats,
#                 **db_stats
#             },
#             'timestamp': datetime.utcnow().isoformat()
#         })
        
#     except Exception as e:
#         print(f"❌ Error getting AI statistics: {e}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500


# @ai_bp.route('/api/ai/pattern-cache/refresh', methods=['POST'])
# def refresh_pattern_cache():
#     """
#     Manually refresh the AI pattern cache
#     """
#     try:
#         enhanced_ai_decision_service._refresh_pattern_cache()
        
#         stats = enhanced_ai_decision_service.get_decision_statistics()
        
#         return jsonify({
#             'success': True,
#             'message': 'Pattern cache refreshed successfully',
#             'patterns_loaded': stats.get('patterns_in_cache', 0),
#             'timestamp': datetime.utcnow().isoformat()
#         })
        
#     except Exception as e:
#         print(f"❌ Error refreshing pattern cache: {e}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500


# @ai_bp.route('/api/ai/decision-history', methods=['GET'])
# def get_decision_history():
#     """
#     Get historical AI decisions from database
#     """
#     try:
#         tl_id = request.args.get('tl_id')
#         scenario = request.args.get('scenario', 'accra')
#         hours = int(request.args.get('hours', 24))
#         limit = int(request.args.get('limit', 50))
        
#         # Query database
#         cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
#         query = AIDecisionLog.query.filter(
#             AIDecisionLog.created_at >= cutoff_time,
#             AIDecisionLog.scenario == scenario
#         )
        
#         if tl_id:
#             query = query.filter(AIDecisionLog.traffic_light_id == tl_id)
        
#         decisions = query.order_by(
#             AIDecisionLog.created_at.desc()
#         ).limit(limit).all()
        
#         # Format results
#         history = []
#         for decision in decisions:
#             history.append({
#                 'id': decision.id,
#                 'traffic_light_id': decision.traffic_light_id,
#                 'scenario': decision.scenario,
#                 'simulation_time': decision.simulation_time,
#                 'recommended_action': decision.recommended_action,
#                 'action_type': decision.action_type,
#                 'confidence': round(decision.confidence * 100, 1),
#                 'pattern_matched': decision.pattern_matched,
#                 'reasoning': decision.reasoning,
#                 'current_waiting': decision.current_waiting,
#                 'current_efficiency': decision.current_efficiency,
#                 'created_at': decision.created_at.isoformat()
#             })
        
#         return jsonify({
#             'success': True,
#             'history': history,
#             'total': len(history),
#             'time_range_hours': hours,
#             'traffic_light_id': tl_id,
#             'scenario': scenario
#         })
        
#     except Exception as e:
#         print(f"❌ Error getting decision history: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({
#             'success': False,
#             'error': str(e),
#             'history': []
#         }), 500


# @ai_bp.route('/api/ai/patterns/matched', methods=['GET'])
# def get_matched_patterns():
#     """
#     Get information about patterns that have been matched
#     """
#     try:
#         scenario = request.args.get('scenario', 'accra')
        
#         # Get pattern match statistics from decision history
#         recent_decisions = list(enhanced_ai_decision_service.decision_history)[-50:]
        
#         matched_patterns = []
#         pattern_types = defaultdict(int)
#         match_types = defaultdict(int)
        
#         for decision in recent_decisions:
#             rec = decision.get('recommendation', {})
#             if rec.get('pattern_matched'):
#                 matched_patterns.append({
#                     'tl_id': decision.get('tl_id'),
#                     'timestamp': decision.get('timestamp'),
#                     'pattern_type': rec.get('pattern_type'),
#                     'match_type': rec.get('match_type'),
#                     'confidence': rec.get('confidence'),
#                     'action': rec.get('action')
#                 })
                
#                 pattern_types[rec.get('pattern_type', 'UNKNOWN')] += 1
#                 match_types[rec.get('match_type', 'UNKNOWN')] += 1
        
#         return jsonify({
#             'success': True,
#             'matched_patterns': matched_patterns[-20:],  # Last 20
#             'pattern_type_distribution': dict(pattern_types),
#             'match_type_distribution': dict(match_types),
#             'total_matches': len(matched_patterns),
#             'scenario': scenario
#         })
        
#     except Exception as e:
#         print(f"❌ Error getting matched patterns: {e}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500


@ai_bp.route('/ai/status', methods=['GET'])
def get_ai_status():
    """Get comprehensive AI status including Q-learning"""
    try:
        status = enhanced_ai_decision_service.get_ai_status()
        
        return jsonify({
            'success': True,
            'ai_enabled': enhanced_ai_decision_service.current_ai_mode != 'DISABLED',
            'current_mode': status['current_mode'],
            'mode': status['current_mode'],
            'q_learning': status.get('q_learning', {}),
            'pattern_based': status.get('pattern_based', {}),
            'stats': {
                'total_decisions': status.get('pattern_based', {}).get('total_decisions', 0),
                'pattern_match_rate': status.get('pattern_based', {}).get('pattern_match_rate', 0),
                'patterns_in_cache': status.get('pattern_based', {}).get('patterns_in_cache', 0),
                'applied_optimizations': 0,
                'baseline_collections': 0
            },
            'implications': _get_mode_implications(status['current_mode'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/toggle', methods=['POST'])
def toggle_ai():
    """Toggle AI optimization on/off"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', True)
        
        if enabled:
            enhanced_ai_decision_service.set_ai_mode('HYBRID')
        else:
            enhanced_ai_decision_service.set_ai_mode('DISABLED')
        
        status = enhanced_ai_decision_service.get_ai_status()
        
        return jsonify({
            'success': True,
            'current_state': enabled,
            'mode': status['current_mode'],
            'stats': {
                'total_decisions': status.get('pattern_based', {}).get('total_decisions', 0)
            },
            'implications': _get_mode_implications(status['current_mode'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
@ai_bp.route('/ai/set-mode', methods=['POST'])
def set_ai_mode():
    """Set AI operation mode"""
    try:
        data = request.get_json() or {}
        mode = data.get('mode', 'HYBRID')
        
        valid_modes = ['PATTERN_ONLY', 'Q_LEARNING', 'HYBRID', 'DISABLED']
        if mode not in valid_modes:
            return jsonify({
                'success': False,
                'error': f'Invalid mode. Valid modes: {valid_modes}'
            }), 400
        
        enhanced_ai_decision_service.set_ai_mode(mode)
        status = enhanced_ai_decision_service.get_ai_status()
        
        return jsonify({
            'success': True,
            'mode': mode,
            'status': status,
            'message': f'AI mode set to {mode}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== Q-LEARNING MANAGEMENT ====================

@ai_bp.route('/ai/q-learning/status', methods=['GET'])
def get_q_learning_status():
    """Get detailed Q-learning status"""
    try:
        status = q_learning.get_learning_status()
        
        return jsonify({
            'success': True,
            'status': status,
            'summary': {
                'is_active': status['learning_running'],
                'is_learning': status['is_learning'],
                'states_learned': status['q_table_size'],
                'episodes': status['learning_stats']['episodes_processed'],
                'convergence': f"{status['learning_stats']['convergence_rate']*100:.1f}%"
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/start', methods=['POST'])
def start_q_learning():
    """Start background Q-learning"""
    try:
        q_learning.start_background_learning()
        
        return jsonify({
            'success': True,
            'message': 'Background Q-learning started',
            'status': q_learning.get_learning_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/pause', methods=['POST'])
def pause_q_learning():
    """Pause Q-learning (keeps thread running but stops updates)"""
    try:
        q_learning.disable_learning()
        
        return jsonify({
            'success': True,
            'message': 'Q-learning paused',
            'is_learning': q_learning.is_learning
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/resume', methods=['POST'])
def resume_q_learning():
    """Resume Q-learning"""
    try:
        q_learning.enable_learning()
        
        return jsonify({
            'success': True,
            'message': 'Q-learning resumed',
            'is_learning': q_learning.is_learning
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/stop', methods=['POST'])
def stop_q_learning():
    """Stop background Q-learning (preserves Q-table)"""
    try:
        q_learning.stop_background_learning()
        
        return jsonify({
            'success': True,
            'message': 'Background Q-learning stopped (Q-table preserved)',
            'status': q_learning.get_learning_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/reset', methods=['POST'])
def reset_q_learning():
    """Reset Q-learning (clears Q-table and stats)"""
    try:
        # Confirm reset
        data = request.get_json() or {}
        confirm = data.get('confirm', False)
        
        if not confirm:
            return jsonify({
                'success': False,
                'error': 'Please confirm reset by setting confirm=true',
                'warning': 'This will delete all learned Q-values!'
            }), 400
        
        q_learning.reset_learning()
        
        return jsonify({
            'success': True,
            'message': 'Q-learning reset complete',
            'status': q_learning.get_learning_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/params', methods=['GET'])
def get_q_learning_params():
    """Get current Q-learning parameters"""
    try:
        return jsonify({
            'success': True,
            'params': {
                'learning_rate': q_learning.learning_rate,
                'discount_factor': q_learning.discount_factor,
                'exploration_rate': q_learning.exploration_rate,
                'min_exploration': q_learning.min_exploration,
                'exploration_decay': q_learning.exploration_decay
            },
            'training_config': q_learning.training_config,
            'reward_weights': q_learning.reward_weights
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_bp.route('/ai/q-learning/params', methods=['POST'])
def set_q_learning_params():
    """Update Q-learning parameters"""
    try:
        data = request.get_json() or {}
        
        q_learning.set_learning_parameters(
            learning_rate=data.get('learning_rate'),
            discount_factor=data.get('discount_factor'),
            exploration_rate=data.get('exploration_rate')
        )
        
        return jsonify({
            'success': True,
            'message': 'Parameters updated',
            'params': {
                'learning_rate': q_learning.learning_rate,
                'discount_factor': q_learning.discount_factor,
                'exploration_rate': q_learning.exploration_rate
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== RECOMMENDATIONS ====================

@ai_bp.route('/ai/recommendations', methods=['GET'])
def get_ai_recommendations():
    """Get AI recommendations for traffic signals"""
    try:
        scenario = request.args.get('scenario', 'accra')
        limit = int(request.args.get('limit', 10))
        force_pattern = request.args.get('force_pattern', 'false').lower() == 'true'
        
        recommendations = enhanced_ai_decision_service.get_recommendations(
            scenario=scenario,
            limit=limit,
            force_pattern_mode=force_pattern
        )
        
        # Get statistics
        stats = enhanced_ai_decision_service.get_decision_statistics()
        q_stats = q_learning.get_learning_status()
        
        # Calculate average confidence
        confidences = [r.get('confidence', 0) for r in recommendations if r]
        avg_confidence = sum(confidences) / len(confidences) * 100 if confidences else 0
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'count': len(recommendations),
            'statistics': {
                'total_decisions': stats.get('total_decisions', 0),
                'pattern_match_rate': stats.get('pattern_match_rate', 0),
                'patterns_in_cache': stats.get('patterns_in_cache', 0),
                'avg_confidence': round(avg_confidence, 1),
                'current_mode': enhanced_ai_decision_service.get_current_mode(),
                'q_learning_episodes': q_stats['learning_stats']['episodes_processed'],
                'q_learning_convergence': q_stats['learning_stats']['convergence_rate']
            },
            'mode': enhanced_ai_decision_service.current_ai_mode,
            'scenario': scenario
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'recommendations': [],
            'statistics': {}
        }), 500

@ai_bp.route('/ai/recommendations/<tl_id>', methods=['GET'])
def get_tl_recommendations(tl_id):
    """Get recommendations for a specific traffic light"""
    try:
        scenario = request.args.get('scenario', 'accra')
        
        recommendations = enhanced_ai_decision_service.get_tl_recommendations(
            tl_id=tl_id,
            scenario=scenario
        )
        
        return jsonify({
            'success': True,
            'traffic_light_id': tl_id,
            'recommendations': recommendations,
            'count': len(recommendations)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== HELPER FUNCTIONS ====================
def _get_mode_implications(mode: str) -> list:
    """Get human-readable implications for AI mode"""
    implications = {
        'HYBRID': [
            'AI combines pattern matching and Q-learning',
            'Best accuracy with learned optimizations',
            'Background learning continues improving'
        ],
        'Q_LEARNING': [
            'Pure reinforcement learning mode',
            'Decisions based on learned Q-values',
            'May be less accurate until fully trained'
        ],
        'PATTERN_ONLY': [
            'Uses historical pattern matching only',
            'No Q-learning optimization',
            'Good for stable, predictable traffic'
        ],
        'DISABLED': [
            'AI optimization disabled',
            'Baseline data collection mode',
            'Manual signal timing only'
        ]
    }
    return implications.get(mode, ['Unknown mode'])

# @ai_bp.route('/ai/recommendations', methods=['GET'])
# def get_ai_recommendations():
#     """Get AI recommendations (supports all modes)"""
#     try:
#         scenario = request.args.get('scenario', 'accra')
#         limit = int(request.args.get('limit', 10))
        
#         recommendations = enhanced_ai_decision_service.generate_recommendations_from_patterns(
#             scenario, limit
#         )
        
#         return jsonify({
#             'success': True,
#             'recommendations': recommendations,
#             'count': len(recommendations),
#             'scenario': scenario,
#             'ai_mode': enhanced_ai_decision_service.current_ai_mode
#         })
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': f"Failed to get AI recommendations: {str(e)}"
#         }), 500

# @ai_bp.route('/ai/q-learning/reset', methods=['POST'])
# def reset_q_learning():
#     """Reset Q-learning (clear Q-table)"""
#     try:
#         from app.services.q_learning import q_learning_ai_service
#         q_learning_ai_service.reset_learning()
        
#         return jsonify({
#             'success': True,
#             'message': "Q-learning reset successfully"
#         })
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': f"Failed to reset Q-learning: {str(e)}"
#         }), 500

# @ai_bp.route('/ai/q-learning/statistics', methods=['GET'])
# def get_q_learning_stats():
#     """Get Q-learning statistics"""
#     try:
#         from app.services.q_learning import q_learning_ai_service
#         stats = q_learning_ai_service.get_learning_status()
        
#         return jsonify({
#             'success': True,
#             'statistics': stats
#         })
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': f"Failed to get Q-learning statistics: {str(e)}"
#         }), 500