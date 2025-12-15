"""
AI API Endpoints - Updated for Q-Learning Integration
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List, Any

# Services
from app.services.q_learning import simple_ai_optimizer
from app.services.optimized_sumo_service import optimized_sumo_service

ai_bp = Blueprint('ai', __name__)

def success_response(data=None, message=None, **kwargs):
    """Create standardized success response"""
    response = {'success': True}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    response.update(kwargs)
    return jsonify(response)

def error_response(error, status_code=500, **kwargs):
    """Create standardized error response"""
    response = {'success': False, 'error': str(error)}
    response.update(kwargs)
    return jsonify(response), status_code

# ==================== AI STATUS AND CONTROL ====================

@ai_bp.route('/api/ai/status', methods=['GET'])
def get_ai_status():
    """Get comprehensive AI status"""
    try:
        # Get optimizer status
        optimizer_status = simple_ai_optimizer.get_status()
        
        # Get integration status from SUMO service
        integration_status = optimized_sumo_service.get_ai_status()
        
        return success_response(
            data={
                'optimizer': optimizer_status,
                'integration': integration_status,
                'summary': {
                    'ai_enabled': integration_status['ai_enabled'],
                    'simulation_running': optimized_sumo_service.is_running,
                    'decisions_made': optimizer_status['decisions_made'],
                    'episodes_learned': optimizer_status['episodes_learned'],
                    'success_rate': f"{optimizer_status['success_rate']}%",
                    'states_learned': optimizer_status['states_learned'],
                    'patterns_created': optimizer_status['patterns_created'],
                    'exploration_rate': optimizer_status['exploration_rate']
                }
            }
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/enable', methods=['POST'])
def enable_ai():
    """
    Enable AI optimization
    
    ⚠️ IMPORTANT: AI can only be toggled when simulation is running
    """
    try:
        if not optimized_sumo_service.is_running:
            return error_response(
                "Cannot enable AI - no simulation running. Start a simulation first.",
                status_code=400
            )
        
        optimized_sumo_service.enable_ai()
        
        return success_response(
            message='AI optimization enabled - will apply decisions every 30 simulation steps',
            status=optimized_sumo_service.get_ai_status(),
            note='AI will begin optimizing traffic lights in the current simulation'
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/disable', methods=['POST'])
def disable_ai():
    """
    Disable AI optimization
    
    Note: This stops AI from making new decisions but doesn't revert previous optimizations
    """
    try:
        optimized_sumo_service.disable_ai()
        
        return success_response(
            message='AI optimization disabled',
            status=optimized_sumo_service.get_ai_status(),
            note='AI will stop making optimization decisions. Learning data is preserved.'
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/toggle', methods=['POST'])
def toggle_ai():
    """Toggle AI optimization on/off"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', True)
        
        if not optimized_sumo_service.is_running:
            return error_response(
                "Cannot toggle AI - no simulation running",
                status_code=400
            )
        
        if enabled:
            optimized_sumo_service.enable_ai()
        else:
            optimized_sumo_service.disable_ai()
        
        return success_response(
            message=f"AI optimization {'enabled' if enabled else 'disabled'}",
            enabled=enabled,
            status=optimized_sumo_service.get_ai_status()
        )
    except Exception as e:
        return error_response(e)

# ==================== LEARNING MANAGEMENT ====================

@ai_bp.route('/api/ai/learning/status', methods=['GET'])
def get_learning_status():
    """Get detailed learning status"""
    try:
        status = simple_ai_optimizer.get_status()
        
        return success_response(
            data={
                'decisions_made': status['decisions_made'],
                'episodes_learned': status['episodes_learned'],
                'success_rate': status['success_rate'],
                'total_reward': status['total_reward'],
                'exploration_rate': status['exploration_rate'],
                'states_learned': status['states_learned'],
                'patterns_created': status['patterns_created'],
                'learning_parameters': {
                    'learning_rate': simple_ai_optimizer.learning_rate,
                    'discount_factor': simple_ai_optimizer.discount_factor,
                    'min_exploration': simple_ai_optimizer.min_exploration
                }
            }
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/learning/save', methods=['POST'])
def save_learning():
    """Manually save learning state to disk"""
    try:
        simple_ai_optimizer._save_q_table()
        
        return success_response(
            message="Learning state saved to simple_q_table.json",
            stats=simple_ai_optimizer.get_status(),
            file_location='project root directory'
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/learning/reset', methods=['POST'])
def reset_learning():
    """Reset learning (clear Q-table) - REQUIRES CONFIRMATION"""
    try:
        data = request.get_json() or {}
        confirm = data.get('confirm', False)
        
        if not confirm:
            return error_response(
                "Please confirm reset by setting confirm=true",
                status_code=400,
                warning="This will delete all learned Q-values and reset AI to initial state"
            )
        
        # Clear Q-table
        simple_ai_optimizer.q_table.clear()
        simple_ai_optimizer.stats = {
            'decisions': 0,
            'learned_episodes': 0,
            'success_rate': 0.5,
            'total_reward': 0,
            'patterns_created': 0
        }
        simple_ai_optimizer.exploration_rate = 0.3
        simple_ai_optimizer.created_patterns.clear()
        
        # Clear last state tracking
        simple_ai_optimizer.last_state = {}
        simple_ai_optimizer.last_action = {}
        simple_ai_optimizer.last_performance = {}
        
        return success_response(
            message="Learning reset complete - all Q-values cleared",
            status=simple_ai_optimizer.get_status(),
            note="AI will start learning from scratch"
        )
    except Exception as e:
        return error_response(e)

# ==================== Q-TABLE AND KNOWLEDGE ====================

@ai_bp.route('/api/ai/knowledge/q-table', methods=['GET'])
def get_q_table():
    """Get Q-table information"""
    try:
        limit = int(request.args.get('limit', 20))
        
        top_strategies = simple_ai_optimizer._get_top_strategies(limit)
        
        # Calculate action distribution
        action_counts = {'EXTEND_GREEN': 0, 'REDUCE_GREEN': 0, 'MAINTAIN': 0}
        for state_key, q_values in simple_ai_optimizer.q_table.items():
            best_action = max(q_values, key=q_values.get)
            action_counts[best_action] = action_counts.get(best_action, 0) + 1
        
        return success_response(
            data={
                'total_states': simple_ai_optimizer.get_status()['states_learned'],
                'top_strategies': top_strategies,
                'action_distribution': action_counts,
                'exploration_rate': simple_ai_optimizer.exploration_rate,
                'q_table_size': len(simple_ai_optimizer.q_table)
            }
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/knowledge/state/<state_key>', methods=['GET'])
def get_state_knowledge(state_key):
    """Get knowledge for a specific state"""
    try:
        if state_key not in simple_ai_optimizer.q_table:
            return error_response(
                f"State '{state_key}' not found in Q-table",
                status_code=404,
                available_states=list(simple_ai_optimizer.q_table.keys())[:10]
            )
        
        q_values = simple_ai_optimizer.q_table[state_key]
        best_action = max(q_values, key=q_values.get)
        
        return success_response(
            data={
                'state': state_key,
                'q_values': q_values,
                'best_action': best_action,
                'best_q_value': q_values[best_action],
                'confidence': min(0.95, q_values[best_action] / 10.0) if q_values[best_action] > 0 else 0.5
            }
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/knowledge/export', methods=['GET'])
def export_knowledge():
    """Export all AI knowledge"""
    try:
        export_data = {
            'q_table': dict(simple_ai_optimizer.q_table),
            'stats': simple_ai_optimizer.stats,
            'exploration_rate': simple_ai_optimizer.exploration_rate,
            'created_patterns': list(simple_ai_optimizer.created_patterns),
            'top_strategies': simple_ai_optimizer._get_top_strategies(50),
            'exported_at': datetime.utcnow().isoformat(),
            'parameters': {
                'learning_rate': simple_ai_optimizer.learning_rate,
                'discount_factor': simple_ai_optimizer.discount_factor,
                'min_exploration': simple_ai_optimizer.min_exploration
            }
        }
        
        return success_response(
            data=export_data,
            message="AI knowledge exported successfully"
        )
    except Exception as e:
        return error_response(e)

# ==================== RECOMMENDATIONS ====================

@ai_bp.route('/api/ai/recommendations', methods=['GET'])
def get_ai_recommendations():
    """Get AI recommendations based on learned strategies"""
    try:
        limit = int(request.args.get('limit', 5))
        
        top_strategies = simple_ai_optimizer._get_top_strategies(limit)
        
        # Convert to recommendation format
        recommendations = []
        for strategy in top_strategies:
            recommendations.append({
                'state': strategy['state'],
                'action': strategy['action'],
                'confidence': min(0.95, strategy['q_value'] / 10.0),
                'q_value': strategy['q_value'],
                'reasoning': f"Learned from {simple_ai_optimizer.stats['learned_episodes']} episodes",
                'expected_impact': _get_impact_for_action(strategy['action']),
                'source': 'Q_LEARNING'
            })
        
        # Get current simulation recommendations if available
        current_recommendations = []
        if optimized_sumo_service.is_running:
            current_recommendations = optimized_sumo_service.monitoring_data.get('ai_recommendations', [])
        
        return success_response(
            data={
                'learned_recommendations': recommendations,
                'current_simulation_recommendations': current_recommendations,
                'count': len(recommendations),
                'total_learned_states': simple_ai_optimizer.get_status()['states_learned']
            }
        )
    except Exception as e:
        return error_response(e)

# ==================== SIMULATION INTEGRATION ====================

@ai_bp.route('/api/ai/simulation/status', methods=['GET'])
def get_simulation_ai_status():
    """Get AI status specifically for current simulation"""
    try:
        if not optimized_sumo_service.is_running:
            return success_response(
                data={
                    'simulation_running': False,
                    'message': 'No simulation currently running'
                }
            )
        
        ai_status = optimized_sumo_service.get_ai_status()
        sim_data = optimized_sumo_service.get_simulation_data()
        
        return success_response(
            data={
                'simulation_running': True,
                'ai_enabled': ai_status['ai_enabled'],
                'current_step': ai_status['simulation_step'],
                'ai_optimization_interval': ai_status['ai_optimization_interval'],
                'recent_recommendations': ai_status['last_recommendations'][:5],
                'scenario': optimized_sumo_service.current_config,
                'tls_count': len(sim_data['monitoring'].get('tls_snapshot', {}).get('traffic_lights', {}))
            }
        )
    except Exception as e:
        return error_response(e)

# ==================== STATISTICS AND ANALYTICS ====================

@ai_bp.route('/api/ai/statistics/summary', methods=['GET'])
def get_ai_statistics():
    """Get AI performance statistics"""
    try:
        status = simple_ai_optimizer.get_status()
        
        # Calculate averages
        avg_reward = (status['total_reward'] / max(1, status['episodes_learned']))
        
        return success_response(
            data={
                'learning_statistics': {
                    'decisions_made': status['decisions_made'],
                    'episodes_learned': status['episodes_learned'],
                    'total_reward': round(status['total_reward'], 2),
                    'avg_reward_per_episode': round(avg_reward, 3),
                    'success_rate': status['success_rate']
                },
                'knowledge_statistics': {
                    'states_learned': status['states_learned'],
                    'patterns_created': status['patterns_created'],
                    'exploration_rate': status['exploration_rate']
                },
                'top_strategies': status['top_strategies']
            }
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/statistics/performance', methods=['GET'])
def get_performance_metrics():
    """Get detailed performance metrics"""
    try:
        status = simple_ai_optimizer.get_status()
        
        # Get all strategies grouped by action
        strategies_by_action = {
            'EXTEND_GREEN': [],
            'REDUCE_GREEN': [],
            'MAINTAIN': []
        }
        
        for state_key, q_values in simple_ai_optimizer.q_table.items():
            for action, q_value in q_values.items():
                if q_value > 0:
                    strategies_by_action[action].append({
                        'state': state_key,
                        'q_value': q_value
                    })
        
        # Calculate average Q-values per action
        action_performance = {}
        for action, strategies in strategies_by_action.items():
            if strategies:
                avg_q = sum(s['q_value'] for s in strategies) / len(strategies)
                action_performance[action] = {
                    'count': len(strategies),
                    'avg_q_value': round(avg_q, 2),
                    'max_q_value': round(max(s['q_value'] for s in strategies), 2)
                }
            else:
                action_performance[action] = {
                    'count': 0,
                    'avg_q_value': 0,
                    'max_q_value': 0
                }
        
        return success_response(
            data={
                'performance_by_action': action_performance,
                'overall': {
                    'success_rate': status['success_rate'],
                    'total_reward': status['total_reward'],
                    'episodes': status['episodes_learned']
                }
            }
        )
    except Exception as e:
        return error_response(e)

# ==================== SYSTEM HEALTH ====================

@ai_bp.route('/api/ai/health', methods=['GET'])
def get_ai_health():
    """Get AI system health status"""
    try:
        status = simple_ai_optimizer.get_status()
        integration_status = optimized_sumo_service.get_ai_status()
        
        # Calculate health score (0-100)
        health_score = 0
        
        # Integration health (20%)
        if integration_status['ai_enabled'] and optimized_sumo_service.is_running:
            health_score += 20
        
        # Learning activity health (30%)
        if status['episodes_learned'] > 100:
            health_score += 30
        elif status['episodes_learned'] > 50:
            health_score += 20
        elif status['episodes_learned'] > 10:
            health_score += 10
        
        # Knowledge health (30%)
        states_learned = status['states_learned']
        if states_learned > 20:
            health_score += 30
        elif states_learned > 10:
            health_score += 20
        elif states_learned > 5:
            health_score += 10
        
        # Performance health (20%)
        success_rate = status['success_rate']
        health_score += min(20, (success_rate / 100) * 20)
        
        # Determine status
        if health_score >= 70:
            health_status = 'HEALTHY'
        elif health_score >= 40:
            health_status = 'DEGRADED'
        else:
            health_status = 'UNHEALTHY'
        
        return success_response(
            data={
                'health_score': round(health_score),
                'health_status': health_status,
                'components': {
                    'ai_enabled': integration_status['ai_enabled'],
                    'simulation_running': optimized_sumo_service.is_running,
                    'episodes_learned': status['episodes_learned'],
                    'states_learned': states_learned,
                    'success_rate': f"{success_rate}%",
                    'patterns_created': status['patterns_created']
                },
                'recommendations': _get_health_recommendations(health_score, status, integration_status)
            }
        )
    except Exception as e:
        return error_response(e)

def _get_health_recommendations(health_score: int, optimizer_status: Dict, integration_status: Dict) -> List[str]:
    """Get health recommendations"""
    recommendations = []
    
    if not optimized_sumo_service.is_running:
        recommendations.append("Start a simulation to enable AI learning")
    
    if not integration_status['ai_enabled'] and optimized_sumo_service.is_running:
        recommendations.append("Enable AI optimization in the running simulation to start learning")
    
    if optimizer_status['episodes_learned'] < 50:
        recommendations.append("Run simulation longer to collect more learning data")
    
    if optimizer_status['states_learned'] < 10:
        recommendations.append("More diverse traffic conditions needed for better learning")
    
    if optimizer_status['success_rate'] < 50:
        recommendations.append("Success rate is low - AI needs more training time")
    
    if optimizer_status['exploration_rate'] > 0.2 and optimizer_status['episodes_learned'] > 200:
        recommendations.append("Exploration rate is still high - consider reducing it")
    
    if not recommendations:
        recommendations.append("System is healthy - AI is learning effectively")
    
    return recommendations

# ==================== TESTING & DEBUG ENDPOINTS ====================

@ai_bp.route('/api/ai/test/decision', methods=['POST'])
def test_ai_decision():
    """Test AI decision making with sample data"""
    try:
        data = request.get_json() or {}
        
        # Sample traffic light data
        sample_tl_data = data.get('tl_data', {
            'id': 'test_tl_01',
            'phase_name': 'green',
            'performance': {
                'waiting_vehicles': data.get('waiting', 5),
                'total_vehicles': data.get('total', 8),
                'efficiency_score': data.get('efficiency', 60)
            }
        })
        
        # Get current state
        state = simple_ai_optimizer._get_state(sample_tl_data)
        state_key = simple_ai_optimizer._state_to_key(state)
        
        # Make decision
        action, confidence = simple_ai_optimizer._make_decision(state_key, state)
        
        # Get Q-values
        q_values = simple_ai_optimizer.q_table[state_key]
        
        # Get parameters
        parameters = simple_ai_optimizer._get_action_parameters(action, sample_tl_data)
        
        return success_response(
            data={
                'input': sample_tl_data,
                'state': state,
                'state_key': state_key,
                'decision': {
                    'action': action,
                    'confidence': confidence,
                    'parameters': parameters,
                    'q_values': q_values
                },
                'note': 'This is a test decision - not applied to simulation'
            }
        )
    except Exception as e:
        return error_response(e)

@ai_bp.route('/api/ai/debug/info', methods=['GET'])
def get_debug_info():
    """Get debug information about AI system"""
    try:
        return success_response(
            data={
                'optimizer': {
                    'class': 'SimpleAIOptimizer',
                    'q_table_size': len(simple_ai_optimizer.q_table),
                    'learning_rate': simple_ai_optimizer.learning_rate,
                    'discount_factor': simple_ai_optimizer.discount_factor,
                    'exploration_rate': simple_ai_optimizer.exploration_rate,
                    'min_exploration': simple_ai_optimizer.min_exploration,
                    'pattern_threshold': simple_ai_optimizer.pattern_threshold
                },
                'integration': {
                    'service': 'OptimizedSumoService',
                    'ai_enabled': optimized_sumo_service.ai_enabled,
                    'simulation_running': optimized_sumo_service.is_running,
                    'optimization_interval': optimized_sumo_service.performance_config.get('ai_optimization_interval', 30)
                },
                'files': {
                    'q_table_file': 'simple_q_table.json',
                    'location': 'project root directory'
                }
            }
        )
    except Exception as e:
        return error_response(e)

# ==================== HELPER FUNCTIONS ====================

def _get_impact_for_action(action: str) -> Dict[str, str]:
    """Get expected impact for an action"""
    impacts = {
        'EXTEND_GREEN': {
            'efficiency': '+5-15%',
            'waiting': '-20-40%',
            'congestion': 'DECREASE'
        },
        'REDUCE_GREEN': {
            'efficiency': '+3-8%',
            'waiting': '+5-15%',
            'congestion': 'SLIGHT_INCREASE'
        },
        'MAINTAIN': {
            'efficiency': 'STABLE',
            'waiting': 'STABLE',
            'congestion': 'STABLE'
        }
    }
    return impacts.get(action, impacts['MAINTAIN'])

def init_ai_routes(app):
    """Initialize AI routes with app context"""
    simple_ai_optimizer.init_app(app)
    print("✅ AI routes initialized with Q-learning")