"""
Enhanced AI Decision Service
Works in TWO modes:
1. LIVE MODE: During simulation - analyzes real-time TLS data
2. PATTERN MODE: Without simulation - generates recommendations from historical patterns
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
import statistics

from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficPattern

from app.services.q_learning import q_learning

class EnhancedAIDecisionService:
    """
    Dual-mode AI service:
    - Analyzes live data during simulation
    - Generates recommendations from patterns when idle
    """
    
    def __init__(self, app=None):
        self.app = app
        self.is_learning = True
        self.recommendation_mode = True
        
        # AI Mode configuration
        self.ai_modes = {
            'PATTERN_ONLY': 'pattern',
            'Q_LEARNING': 'q_learning', 
            'HYBRID': 'hybrid',
            'DISABLED': 'disabled'
        }
        self.current_ai_mode = 'HYBRID' 
        
        self.q_learning_service = None
        self.q_learning_ready = False
        
        # Pattern cache
        self.pattern_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update = 0
        
        # Decision tracking
        self.decision_history = deque(maxlen=100)
        self.pattern_matches = defaultdict(int)
        self.q_learning_decisions = defaultdict(int)
        
        # Mode tracking
        self.is_simulation_running = False
        self.last_simulation_time = 0
        
        # Confidence thresholds
        self.min_confidence_threshold = 0.6
        self.high_confidence_threshold = 0.8
        
        self.simulation_mode = False
        
        # Q-learning integration
        # self.q_learning_enabled = True
        self.hybrid_confidence_threshold = 0.7
        
        print("🤖 Enhanced AI Decision Service with Q-Learning initialized")
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        print("🤖 Enhanced AI Decision Service initialized (Dual Mode)")
        self.q_learning_service = q_learning
        self.q_learning_service.init_app(app)
        
        if self.current_ai_mode in ['Q_LEARNING', 'HYBRID']:
            self.q_learning_service.start_background_learning()
            self.q_learning_ready = True
            
        self._load_historical_patterns()
    
    def set_ai_mode(self, mode: str):
        """Set AI operation mode - Updated"""
        if mode in self.ai_modes:
            self.current_ai_mode = mode
            print(f"🔧 AI Mode set to: {mode}")
            
            # Enable/disable background Q-learning based on mode
            if mode in ['Q_LEARNING', 'HYBRID']:
                if self.q_learning_service:
                    self.q_learning_service.enable_learning()
                    if not self.q_learning_service.learning_running:
                        self.q_learning_service.start_background_learning()
                    self.q_learning_ready = True
            else:
                if self.q_learning_service:
                    self.q_learning_service.disable_learning()
                    # Don't stop - just pause learning
        else:
            print(f"❌ Invalid AI mode: {mode}")
    
    def get_ai_status(self) -> Dict[str, Any]:
        """Get comprehensive AI status - Updated"""
        pattern_stats = self.get_decision_statistics()
        
        # Get Q-learning stats from background service
        q_learning_stats = {}
        if self.q_learning_service:
            q_learning_stats = self.q_learning_service.get_learning_status()
        
        return {
            'current_mode': self.current_ai_mode,
            'pattern_based': pattern_stats,
            'q_learning': q_learning_stats,
            'hybrid_enabled': self.current_ai_mode == 'HYBRID',
            'recommendation_mode': self.recommendation_mode,
            'simulation_running': self.is_simulation_running,
            'q_learning_ready': self.q_learning_ready
        }
    
    # ==================== LIVE MODE (During Simulation) ====================
    
    def optimize_single_tls(self, tl_data: Dict, current_time: float, scenario: str) -> Dict[str, Any]:
        """
        LIVE MODE: Analyze real-time TLS data during simulation
        """
        
        if self.simulation_mode:
            return self._get_minimal_recommendation(tl_data)
        
        self.is_simulation_running = True
        self.last_simulation_time = time.time()
        
        tl_id = tl_data['id']
        
        try:
            
            # Choose AI method based on current mode
            if self.current_ai_mode == 'DISABLED':
                recommendation = self._get_fallback_recommendation(tl_id, tl_data, current_time)
                
            elif self.current_ai_mode == 'PATTERN_ONLY':
                recommendation = self._pattern_based_optimization(tl_data, current_time, scenario)
                
            elif self.current_ai_mode == 'Q_LEARNING':
                recommendation = self._q_learning_optimization(tl_data, scenario, current_time)
                
            elif self.current_ai_mode == 'HYBRID':
                recommendation = self._hybrid_optimization(tl_data, current_time, scenario)
                
            else:
                recommendation = self._get_fallback_recommendation(tl_id, tl_data, current_time)
            
            # current_state = self._analyze_current_state(tl_data)
            # pattern_match = self._find_matching_pattern(tl_id, scenario, current_state, current_time)
            # recommendation = self._generate_recommendation(tl_id, current_state, pattern_match, tl_data)
            
            # Track decision
            self.decision_history.append({
                'timestamp': current_time,
                'tl_id': tl_id,
                'recommendation': recommendation,
                'ai_mode': self.current_ai_mode,
                'mode': 'LIVE'
            })
            
            # Log to database
            self._log_ai_decision(tl_id, scenario, current_time, recommendation, 
                                self._analyze_current_state(tl_data))
            
            return recommendation
            
        except Exception as e:
            print(f"❌ Error in live AI decision for {tl_id}: {e}")
            return self._get_fallback_recommendation(tl_id, tl_data, current_time)
    
    def _pattern_based_optimization(self, tl_data: Dict, current_time: float, scenario: str) -> Dict[str, Any]:
        """Pattern-based optimization (existing logic)"""
        current_state = self._analyze_current_state(tl_data)
        pattern_match = self._find_matching_pattern(tl_data['id'], scenario, current_state, current_time)
        
        if pattern_match:
            return self._pattern_based_recommendation(tl_data['id'], current_state, pattern_match, tl_data)
        else:
            return self._rule_based_recommendation(tl_data['id'], current_state, tl_data)
    
    def _q_learning_optimization(self, tl_data: Dict, scenario: str, 
                                  current_time: float) -> Dict[str, Any]:
        """
        Q-learning based optimization - Updated to use background service
        """
        if not self.q_learning_service:
            return self._get_fallback_recommendation(tl_data['id'], tl_data, current_time)
        
        # Get recommendation from pre-trained Q-table (fast lookup, no learning)
        recommendation = self.q_learning_service.get_recommendation(tl_data, scenario)
        
        # Track Q-learning decision
        self.q_learning_decisions[recommendation['action']] += 1
        
        # Add timestamp and TL ID
        recommendation['timestamp'] = current_time
        recommendation['tl_id'] = tl_data['id']
        recommendation['should_apply'] = False  # Recommendation only
        recommendation['mode'] = 'LIVE'
        
        return recommendation
    
    def _hybrid_optimization(self, tl_data: Dict, current_time: float, 
                             scenario: str) -> Dict[str, Any]:
        """
        Hybrid optimization - Updated to use background Q-learning
        """
        tl_id = tl_data['id']
        current_state = self._analyze_current_state(tl_data)
        
        # Get pattern-based recommendation
        pattern_match = self._find_matching_pattern(tl_id, scenario, current_state, current_time)
        if pattern_match:
            pattern_rec = self._pattern_based_recommendation(tl_id, current_state, pattern_match, tl_data)
        else:
            pattern_rec = self._rule_based_recommendation(tl_id, current_state, tl_data)
        pattern_confidence = pattern_rec['confidence']
        
        # Get Q-learning recommendation (fast lookup from pre-trained table)
        q_learning_rec = {'action': 'MAINTAIN', 'confidence': 0.0}
        if self.q_learning_service and self.q_learning_ready:
            q_learning_rec = self.q_learning_service.get_recommendation(tl_data, scenario)
        q_learning_confidence = q_learning_rec.get('confidence', 0.0)
        
        # Choose recommendation with higher confidence
        if q_learning_confidence >= pattern_confidence and q_learning_confidence > self.hybrid_confidence_threshold:
            final_recommendation = q_learning_rec
            final_recommendation['decision_source'] = 'Q_LEARNING'
            final_recommendation['hybrid_confidence'] = q_learning_confidence
            self.q_learning_decisions[q_learning_rec['action']] += 1
        else:
            final_recommendation = pattern_rec
            final_recommendation['decision_source'] = 'PATTERN_BASED'
            final_recommendation['hybrid_confidence'] = pattern_confidence
            if pattern_match:
                self.pattern_matches[pattern_rec['action']] += 1
        
        # Add hybrid metadata
        final_recommendation['hybrid_comparison'] = {
            'pattern_confidence': pattern_confidence,
            'q_learning_confidence': q_learning_confidence,
            'selected_source': final_recommendation['decision_source'],
            'q_learning_ready': self.q_learning_ready
        }
        
        final_recommendation['tl_id'] = tl_id
        final_recommendation['timestamp'] = current_time
        final_recommendation['should_apply'] = False
        final_recommendation['mode'] = 'LIVE'
        
        return final_recommendation
    
    # ==================== PATTERN MODE (Without Simulation) ====================
    
    def _get_minimal_recommendation(self, tl_data: Dict) -> Dict[str, Any]:
        """Minimal recommendation for simulation-only mode"""
        return {
            'action': 'MAINTAIN',
            'action_type': 'SIMULATION_MODE',
            'confidence': 0.0,
            'reasoning': 'AI disabled during simulation',
            'should_apply': False,
            'mode': 'DISABLED'
        }
    
    def _get_pattern_based_recommendations(self, scenario: str, limit: int) -> List[Dict[str, Any]]:
        """Get pattern-based recommendations"""
        recommendations = []
        
        try:
            with self.app.app_context():
                recent_patterns = TrafficPattern.query.filter(
                    TrafficPattern.scenario == scenario,
                    TrafficPattern.confidence_score >= self.min_confidence_threshold
                ).order_by(
                    TrafficPattern.confidence_score.desc(),
                    TrafficPattern.updated_at.desc()
                ).limit(limit).all()
                
                for pattern in recent_patterns:
                    rec = self._create_recommendation_from_pattern(pattern)
                    recommendations.append(rec)
                    
        except Exception as e:
            print(f"❌ Error getting pattern recommendations: {e}")
        
        return recommendations
    
    def generate_recommendations_from_patterns(self, scenario: str, 
                                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        Enhanced pattern mode with Q-learning insights
        """
        try:
            # Get pattern-based recommendations
            pattern_recommendations = self._get_pattern_based_recommendations(scenario, limit)
            
            # If in hybrid mode, add Q-learning insights
            if self.current_ai_mode in ['HYBRID', 'Q_LEARNING']:
                q_learning_insights = self._get_q_learning_insights(scenario, limit // 2)
                pattern_recommendations.extend(q_learning_insights)
            
            # Sort by confidence and limit
            pattern_recommendations.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            return pattern_recommendations[:limit]
            
        except Exception as e:
            print(f"❌ Error generating enhanced recommendations: {e}")
            return []
    
    def _get_q_learning_insights(self, scenario: str, limit: int) -> List[Dict[str, Any]]:
        """Get Q-learning insights for pattern mode - Updated"""
        insights = []
        
        try:
            if not self.q_learning_service:
                return insights
            
            # Get Q-learning status
            q_status = self.q_learning_service.get_learning_status()
            
            # Create insight recommendation based on learned Q-values
            insight_rec = {
                'tl_id': 'Q-LEARNING-INSIGHT',
                'timestamp': datetime.utcnow().isoformat(),
                'action': 'ANALYZE_PATTERNS',
                'action_type': 'Q_LEARNING_INSIGHT',
                'parameters': {
                    'q_table_size': q_status['q_table_size'],
                    'exploration_rate': q_status['exploration_rate'],
                    'episodes_processed': q_status['learning_stats']['episodes_processed'],
                    'convergence_rate': q_status['learning_stats']['convergence_rate']
                },
                'confidence': min(0.8, q_status['learning_stats']['convergence_rate']),
                'success_rate': 0.7,
                'pattern_matched': False,
                'pattern_type': 'Q_LEARNING_INSIGHT',
                'match_type': 'AI_LEARNING',
                'reasoning': self._build_q_learning_insight_reasoning(q_status),
                'recommendations': [
                    f"Q-table contains {q_status['q_table_size']} learned states",
                    f"Learning has processed {q_status['learning_stats']['episodes_processed']} episodes",
                    f"Model convergence: {q_status['learning_stats']['convergence_rate']:.1%}",
                    f"Background learning: {'Active' if q_status['learning_running'] else 'Paused'}"
                ],
                'expected_impact': {
                    'efficiency_change': 'LEARNING',
                    'waiting_change': 'OPTIMIZING',
                    'congestion_change': 'ANALYZING',
                    'based_on': f"Q-learning with {q_status['learning_stats']['episodes_processed']} episodes"
                },
                'display_priority': 'HIGH' if q_status['learning_stats']['convergence_rate'] > 0.5 else 'MEDIUM',
                'should_apply': False,
                'mode': 'PATTERN_ONLY',
                'q_learning_insight': True,
                'learning_status': {
                    'is_active': q_status['learning_running'],
                    'avg_reward': q_status['learning_stats']['avg_reward']
                }
            }
            
            insights.append(insight_rec)
            
        except Exception as e:
            print(f"❌ Error getting Q-learning insights: {e}")
        
        return insights
    
    def _build_q_learning_insight_reasoning(self, q_status: Dict) -> str:
        """Build reasoning string for Q-learning insight"""
        parts = []
        
        episodes = q_status['learning_stats']['episodes_processed']
        convergence = q_status['learning_stats']['convergence_rate']
        q_size = q_status['q_table_size']
        
        if episodes > 1000:
            parts.append(f"Well-trained model ({episodes} episodes)")
        elif episodes > 100:
            parts.append(f"Developing model ({episodes} episodes)")
        else:
            parts.append(f"Early learning stage ({episodes} episodes)")
        
        if convergence > 0.7:
            parts.append("High confidence predictions")
        elif convergence > 0.4:
            parts.append("Moderate confidence")
        else:
            parts.append("Still learning optimal strategies")
        
        parts.append(f"{q_size} states learned")
        
        if q_status['learning_running']:
            parts.append("Actively improving")
        else:
            parts.append("Learning paused")
        
        return " | ".join(parts)
    
    def _get_recommendations_from_cache(self, scenario: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recommendations from cached patterns when database is unavailable
        """
        try:
            # Filter cached patterns by scenario
            cached_patterns = [
                pattern for key, pattern in self.pattern_cache.items()
                if pattern.get('scenario') == scenario
                and pattern.get('confidence_score', 0) >= self.min_confidence_threshold
            ]
            
            # Sort by confidence and limit
            cached_patterns.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
            cached_patterns = cached_patterns[:limit]
            
            if not cached_patterns:
                print(f"ℹ️ No cached patterns found for scenario: {scenario}")
                return []
            
            recommendations = []
            
            for pattern_data in cached_patterns:
                # Convert cached pattern data to recommendation format
                recommendation = {
                    'tl_id': pattern_data.get('traffic_light_id', 'unknown'),
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': pattern_data.get('best_action', 'MAINTAIN'),
                    'action_type': 'PATTERN_BASED',
                    'parameters': self._get_action_parameters_from_pattern(
                        pattern_data.get('best_action', 'MAINTAIN'), 
                        pattern_data.get('pattern_metrics', {})
                    ),
                    'confidence': pattern_data.get('confidence_score', 0.5),
                    'success_rate': pattern_data.get('action_success_rate', 0.5),
                    'pattern_matched': True,
                    'pattern_type': pattern_data.get('pattern_type', 'UNKNOWN'),
                    'match_type': 'CACHED_PATTERN',
                    'reasoning': f"Cached pattern from {pattern_data.get('traffic_light_id', 'unknown')}",
                    'recommendations': pattern_data.get('recommendations', []),
                    'expected_impact': self._estimate_impact_from_cached_pattern(pattern_data),
                    'display_priority': 'HIGH' if pattern_data.get('confidence_score', 0) >= self.high_confidence_threshold else 'MEDIUM',
                    'should_apply': False,
                    'mode': 'PATTERN_ONLY',
                    'interval_info': {
                        'start': pattern_data.get('interval_start'),
                        'end': pattern_data.get('interval_end'),
                        'sample_size': pattern_data.get('sample_size', 0)
                    },
                    'metrics_summary': {
                        'avg_efficiency': pattern_data.get('pattern_metrics', {}).get('efficiency', {}).get('average', 0),
                        'avg_waiting': pattern_data.get('pattern_metrics', {}).get('congestion', {}).get('average_waiting', 0),
                        'avg_volume': pattern_data.get('pattern_metrics', {}).get('volume', {}).get('average_volume', 0)
                    }
                }
                recommendations.append(recommendation)
            
            print(f"✅ Generated {len(recommendations)} recommendations from cached patterns")
            return recommendations
            
        except Exception as e:
            print(f"❌ Error getting recommendations from cache: {e}")
            return []
    
    def _estimate_impact_from_cached_pattern(self, pattern_data: Dict) -> Dict[str, str]:
        """
        Estimate impact from cached pattern data
        """
        action = pattern_data.get('best_action', 'MAINTAIN')
        metrics = pattern_data.get('pattern_metrics', {})
        
        efficiency = metrics.get('efficiency', {})
        congestion = metrics.get('congestion', {})
        
        avg_efficiency = efficiency.get('average', 0)
        avg_waiting = congestion.get('average_waiting', 0)
        
        if action == 'EXTEND_GREEN':
            return {
                'efficiency_change': '+5-10%' if avg_efficiency < 70 else '+2-5%',
                'waiting_change': '-20-30%' if avg_waiting > 5 else '-10-15%',
                'congestion_change': 'DECREASE',
                'based_on': f'Cached pattern with {pattern_data.get("sample_size", 0)} samples'
            }
        elif action == 'REDUCE_GREEN':
            return {
                'efficiency_change': '+3-5%',
                'waiting_change': 'MAINTAIN' if avg_waiting < 3 else '+5-10%',
                'congestion_change': 'SLIGHT_INCREASE',
                'based_on': f'Cached pattern with {pattern_data.get("sample_size", 0)} samples'
            }
        elif action == 'OPTIMIZE_TIMING':
            return {
                'efficiency_change': '+10-15%',
                'waiting_change': '-15-25%',
                'congestion_change': 'DECREASE',
                'based_on': f'Cached pattern with {pattern_data.get("sample_size", 0)} samples'
            }
        else:  # MAINTAIN
            return {
                'efficiency_change': 'STABLE',
                'waiting_change': 'STABLE',
                'congestion_change': 'STABLE',
                'based_on': f'Cached pattern with {pattern_data.get("sample_size", 0)} samples'
            }
    
    def _create_recommendation_from_pattern(self, pattern: TrafficPattern) -> Dict[str, Any]:
        """
        Create a recommendation dictionary from a TrafficPattern
        """
        metrics = pattern.pattern_metrics or {}
        
        # Extract key metrics
        efficiency = metrics.get('efficiency', {})
        congestion = metrics.get('congestion', {})
        volume = metrics.get('volume', {})
        
        # Estimate expected impact based on pattern type
        expected_impact = self._estimate_impact_from_pattern(pattern, metrics)
        
        # Build reasoning from pattern data
        reasoning = self._build_pattern_only_reasoning(pattern, metrics)
        
        recommendation = {
            'tl_id': pattern.traffic_light_id,
            'timestamp': pattern.updated_at.isoformat() if pattern.updated_at else datetime.utcnow().isoformat(),
            'action': pattern.best_action or 'MAINTAIN',
            'action_type': 'PATTERN_BASED',
            'parameters': self._get_action_parameters_from_pattern(pattern.best_action, metrics),
            'confidence': pattern.confidence_score or 0.5,
            'success_rate': pattern.action_success_rate or 0.5,
            'pattern_matched': True,
            'pattern_type': pattern.pattern_type,
            'match_type': 'HISTORICAL_PATTERN',
            'reasoning': reasoning,
            'recommendations': pattern.recommendations or [],
            'expected_impact': expected_impact,
            'display_priority': 'HIGH' if pattern.confidence_score >= self.high_confidence_threshold else 'MEDIUM',
            'should_apply': False,
            'mode': 'PATTERN_ONLY',
            'interval_info': {
                'start': pattern.interval_start,
                'end': pattern.interval_end,
                'sample_size': pattern.sample_size
            },
            'metrics_summary': {
                'avg_efficiency': efficiency.get('average', 0),
                'avg_waiting': congestion.get('average_waiting', 0),
                'avg_volume': volume.get('average_volume', 0),
                'efficiency_trend': efficiency.get('trend', 'UNKNOWN')
            }
        }
        
        return recommendation
    
    def _estimate_impact_from_pattern(self, pattern: TrafficPattern, 
                                      metrics: Dict) -> Dict[str, str]:
        """
        Estimate impact based on pattern's historical data
        """
        action = pattern.best_action
        efficiency = metrics.get('efficiency', {})
        congestion = metrics.get('congestion', {})
        
        avg_efficiency = efficiency.get('average', 0)
        avg_waiting = congestion.get('average_waiting', 0)
        trend = efficiency.get('trend', 'STABLE')
        
        if action == 'EXTEND_GREEN':
            return {
                'efficiency_change': '+5-10%' if avg_efficiency < 70 else '+2-5%',
                'waiting_change': '-20-30%' if avg_waiting > 5 else '-10-15%',
                'congestion_change': 'DECREASE',
                'based_on': f'Pattern with {pattern.sample_size} samples'
            }
        elif action == 'REDUCE_GREEN':
            return {
                'efficiency_change': '+3-5%',
                'waiting_change': 'MAINTAIN' if avg_waiting < 3 else '+5-10%',
                'congestion_change': 'SLIGHT_INCREASE',
                'based_on': f'Pattern with {pattern.sample_size} samples'
            }
        elif action == 'OPTIMIZE_TIMING':
            return {
                'efficiency_change': '+10-15%',
                'waiting_change': '-15-25%',
                'congestion_change': 'DECREASE',
                'based_on': f'Pattern with {pattern.sample_size} samples'
            }
        else:  # MAINTAIN
            return {
                'efficiency_change': 'STABLE',
                'waiting_change': 'STABLE',
                'congestion_change': 'STABLE',
                'based_on': f'Pattern with {pattern.sample_size} samples'
            }
    
    def _build_pattern_only_reasoning(self, pattern: TrafficPattern, 
                                      metrics: Dict) -> str:
        """
        Build reasoning when working from patterns only (no live data)
        """
        reasons = []
        
        # Pattern info
        confidence = (pattern.confidence_score or 0) * 100
        sample_size = pattern.sample_size or 0
        
        reasons.append(f"Historical pattern analysis ({confidence:.0f}% confidence)")
        reasons.append(f"Based on {sample_size} observations")
        
        # Pattern type
        pattern_type = pattern.pattern_type or 'UNKNOWN'
        reasons.append(f"Pattern type: {pattern_type.replace('_', ' ').title()}")
        
        # Historical success
        success_rate = (pattern.action_success_rate or 0) * 100
        reasons.append(f"Historical success rate: {success_rate:.0f}%")
        
        # Metrics summary
        efficiency = metrics.get('efficiency', {})
        congestion = metrics.get('congestion', {})
        
        avg_eff = efficiency.get('average', 0)
        avg_wait = congestion.get('average_waiting', 0)
        
        reasons.append(f"Historical: {avg_eff:.0f}% efficiency, {avg_wait:.1f} avg waiting")
        
        # Interval info
        if isinstance(pattern.interval_start, (int, float)):
            reasons.append(f"Simulation interval: {int(pattern.interval_start)}-{int(pattern.interval_end)}s")
        
        return " | ".join(reasons)
    
    def _get_action_parameters_from_pattern(self, action: str, metrics: Dict) -> Dict[str, Any]:
        """
        Get action parameters based on pattern metrics
        """
        congestion = metrics.get('congestion', {})
        avg_waiting = congestion.get('average_waiting', 0)
        
        if action == 'EXTEND_GREEN':
            extension = 5 if avg_waiting < 5 else 10 if avg_waiting < 10 else 15
            return {
                'duration_change': extension,
                'reason': f'Historical data shows {avg_waiting:.1f} avg waiting vehicles'
            }
        
        elif action == 'REDUCE_GREEN':
            return {
                'duration_change': -5,
                'reason': f'Historical efficiency suggests optimization opportunity'
            }
        
        elif action == 'OPTIMIZE_TIMING':
            return {
                'optimization_type': 'DYNAMIC',
                'reason': 'Pattern suggests timing adjustments needed'
            }
        
        else:  # MAINTAIN
            return {
                'action': 'MONITOR',
                'reason': 'Historical pattern shows stable performance'
            }
    
    # ==================== INTELLIGENT MODE DETECTION ====================
    
    def get_current_mode(self) -> str:
        """
        Determine if we're in LIVE or PATTERN mode
        """
        # If simulation updated within last 30 seconds, we're in LIVE mode
        if time.time() - self.last_simulation_time < 30:
            return 'LIVE'
        else:
            return 'PATTERN'
    
    def get_recommendations(self, scenario: str, limit: int = 10, 
                           force_pattern_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Smart recommendation getter - automatically chooses mode
        """
        current_mode = self.get_current_mode()
        
        if force_pattern_mode or current_mode == 'PATTERN':
            # Use pattern-based recommendations
            print(f"📊 Getting recommendations from patterns (simulation {'not ' if current_mode == 'PATTERN' else ''}running)")
            return self.generate_recommendations_from_patterns(scenario, limit)
        else:
            # Use recent live decisions
            print(f"🎮 Getting recommendations from live simulation")
            recent_decisions = [
                d['recommendation'] for d in list(self.decision_history)[-limit:]
                if d.get('mode') == 'LIVE'
            ]
            return recent_decisions
    
    # ==================== EXISTING METHODS (Keep All) ====================
    
    def _analyze_current_state(self, tl_data: Dict) -> Dict[str, Any]:
        """Analyze current traffic state from TLS data"""
        performance = tl_data.get('performance', {})
        
        waiting_vehicles = performance.get('waiting_vehicles', 0)
        efficiency_score = performance.get('efficiency_score', 0)
        total_vehicles = performance.get('total_vehicles', 0)
        congestion_level = performance.get('congestion_level', 'LOW')
        
        state = {
            'waiting_vehicles': waiting_vehicles,
            'efficiency_score': efficiency_score,
            'total_vehicles': total_vehicles,
            'congestion_level': congestion_level,
            'phase_name': tl_data.get('phase_name', 'UNKNOWN'),
            'state_string': tl_data.get('state', ''),
            'waiting_category': self._categorize_waiting(waiting_vehicles),
            'efficiency_category': self._categorize_efficiency(efficiency_score),
            'volume_category': self._categorize_volume(total_vehicles)
        }
        
        return state
    
    def _find_matching_pattern(self, tl_id: str, scenario: str, 
                               current_state: Dict, simulation_time: float) -> Optional[Dict]:
        """Find matching pattern from database"""
        try:
            if time.time() - self.last_cache_update > self.cache_ttl:
                self._refresh_pattern_cache()
            
            interval_size = 500
            current_interval = (int(simulation_time) // interval_size) * interval_size
            pattern_key = f"{tl_id}_{scenario}_{current_interval}"
            
            if pattern_key in self.pattern_cache:
                pattern = self.pattern_cache[pattern_key]
                confidence = self._calculate_pattern_confidence(pattern, current_state)
                
                if confidence >= self.min_confidence_threshold:
                    return {
                        **pattern,
                        'match_confidence': confidence,
                        'match_type': 'EXACT_INTERVAL'
                    }
            
            # Try adjacent intervals
            for offset in [-500, 500]:
                adjacent_interval = current_interval + offset
                adjacent_key = f"{tl_id}_{scenario}_{adjacent_interval}"
                
                if adjacent_key in self.pattern_cache:
                    pattern = self.pattern_cache[adjacent_key]
                    confidence = self._calculate_pattern_confidence(pattern, current_state) * 0.8
                    
                    if confidence >= self.min_confidence_threshold:
                        return {
                            **pattern,
                            'match_confidence': confidence,
                            'match_type': 'ADJACENT_INTERVAL'
                        }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error finding pattern match: {e}")
            return None
    
    def _calculate_pattern_confidence(self, pattern: Dict, current_state: Dict) -> float:
        """Calculate pattern confidence"""
        confidence_factors = []
        
        pattern_confidence = pattern.get('confidence_score', 0)
        confidence_factors.append(pattern_confidence * 0.3)
        
        sample_size = pattern.get('sample_size', 0)
        sample_confidence = min(1.0, sample_size / 20)
        confidence_factors.append(sample_confidence * 0.2)
        
        success_rate = pattern.get('action_success_rate', 0.5)
        confidence_factors.append(success_rate * 0.3)
        
        similarity = self._calculate_state_similarity(pattern, current_state)
        confidence_factors.append(similarity * 0.2)
        
        return round(sum(confidence_factors), 3)
    
    def _calculate_state_similarity(self, pattern: Dict, current_state: Dict) -> float:
        """Calculate state similarity"""
        metrics = pattern.get('pattern_metrics', {})
        if not metrics:
            return 0.5
        
        similarity_scores = []
        
        # Efficiency similarity
        pattern_efficiency = metrics.get('efficiency', {}).get('average', 50)
        current_efficiency = current_state.get('efficiency_score', 50)
        efficiency_diff = abs(pattern_efficiency - current_efficiency)
        efficiency_similarity = max(0, 1 - (efficiency_diff / 100))
        similarity_scores.append(efficiency_similarity)
        
        # Waiting similarity
        pattern_waiting = metrics.get('congestion', {}).get('average_waiting', 5)
        current_waiting = current_state.get('waiting_vehicles', 5)
        waiting_diff = abs(pattern_waiting - current_waiting)
        waiting_similarity = max(0, 1 - (waiting_diff / 10))
        similarity_scores.append(waiting_similarity)
        
        # Volume similarity
        pattern_volume = metrics.get('volume', {}).get('average_volume', 5)
        current_volume = current_state.get('total_vehicles', 5)
        volume_diff = abs(pattern_volume - current_volume)
        volume_similarity = max(0, 1 - (volume_diff / 10))
        similarity_scores.append(volume_similarity)
        
        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.5
    
    def _generate_recommendation(self, tl_id: str, current_state: Dict, 
                                 pattern_match: Optional[Dict], tl_data: Dict) -> Dict[str, Any]:
        """Generate recommendation"""
        if pattern_match:
            recommendation = self._pattern_based_recommendation(tl_id, current_state, pattern_match, tl_data)
        else:
            recommendation = self._rule_based_recommendation(tl_id, current_state, tl_data)
        
        recommendation['recommendation_mode'] = True
        recommendation['timestamp'] = datetime.utcnow().isoformat()
        recommendation['tl_id'] = tl_id
        
        return recommendation
    
    def _pattern_based_recommendation(self, tl_id: str, current_state: Dict, 
                                     pattern_match: Dict, tl_data: Dict) -> Dict[str, Any]:
        """Pattern-based recommendation"""
        best_action = pattern_match.get('best_action', 'MAINTAIN')
        action_success_rate = pattern_match.get('action_success_rate', 0.5)
        match_confidence = pattern_match.get('match_confidence', 0.5)
        pattern_type = pattern_match.get('pattern_type', 'UNKNOWN')
        recommendations = pattern_match.get('recommendations', [])
        
        action_params = self._get_action_parameters(best_action, current_state)
        expected_impact = self._estimate_action_impact(best_action, current_state, pattern_match)
        reasoning = self._build_pattern_reasoning(pattern_match, current_state, best_action)
        
        return {
            'action': best_action,
            'action_type': 'PATTERN_BASED',
            'parameters': action_params,
            'confidence': match_confidence,
            'success_rate': action_success_rate,
            'pattern_type': pattern_type,
            'pattern_matched': True,
            'match_type': pattern_match.get('match_type', 'EXACT'),
            'reasoning': reasoning,
            'recommendations': recommendations[:3],
            'expected_impact': expected_impact,
            'should_apply': False,
            'display_priority': 'HIGH' if match_confidence >= self.high_confidence_threshold else 'MEDIUM'
        }
    
    def _rule_based_recommendation(self, tl_id: str, current_state: Dict, 
                                   tl_data: Dict) -> Dict[str, Any]:
        """Rule-based fallback recommendation"""
        waiting = current_state.get('waiting_vehicles', 0)
        efficiency = current_state.get('efficiency_score', 0)
        congestion = current_state.get('congestion_level', 'LOW')
        
        if waiting > 8 and efficiency < 60:
            action = 'EXTEND_GREEN'
            reasoning = f"High congestion ({waiting} waiting) with low efficiency ({efficiency}%)"
            confidence = 0.65
        elif waiting < 2 and efficiency > 80:
            action = 'REDUCE_GREEN'
            reasoning = f"Low congestion with high efficiency - optimize cycle time"
            confidence = 0.60
        elif waiting > 5 and efficiency < 70:
            action = 'OPTIMIZE_TIMING'
            reasoning = f"Moderate congestion - timing optimization recommended"
            confidence = 0.55
        else:
            action = 'MAINTAIN'
            reasoning = "Traffic conditions within acceptable range"
            confidence = 0.70
        
        action_params = self._get_action_parameters(action, current_state)
        
        return {
            'action': action,
            'action_type': 'RULE_BASED',
            'parameters': action_params,
            'confidence': confidence,
            'success_rate': 0.5,
            'pattern_type': 'HEURISTIC',
            'pattern_matched': False,
            'match_type': 'NONE',
            'reasoning': reasoning,
            'recommendations': [f"Current: {congestion} congestion", f"Efficiency: {efficiency}%"],
            'expected_impact': {'status': 'estimated'},
            'should_apply': False,
            'display_priority': 'LOW'
        }
    
    def _get_action_parameters(self, action: str, current_state: Dict) -> Dict[str, Any]:
        """Get action parameters"""
        waiting = current_state.get('waiting_vehicles', 0)
        
        if action == 'EXTEND_GREEN':
            extension = 5 if waiting < 10 else 10 if waiting < 15 else 15
            return {'duration_change': extension, 'reason': 'Reduce waiting queue'}
        elif action == 'REDUCE_GREEN':
            return {'duration_change': -5, 'reason': 'Optimize cycle time'}
        elif action == 'OPTIMIZE_TIMING':
            return {'optimization_type': 'DYNAMIC', 'reason': 'Balance flow'}
        else:
            return {'action': 'MONITOR', 'reason': 'Current config optimal'}
    
    def _estimate_action_impact(self, action: str, current_state: Dict, 
                                pattern_match: Dict) -> Dict[str, str]:
        """Estimate action impact"""
        metrics = pattern_match.get('pattern_metrics', {})
        
        if not metrics:
            return {'status': 'unknown'}
        
        efficiency_trend = metrics.get('efficiency', {}).get('trend', 'STABLE')
        avg_efficiency = metrics.get('efficiency', {}).get('average', 0)
        avg_waiting = metrics.get('congestion', {}).get('average_waiting', 0)
        
        current_efficiency = current_state.get('efficiency_score', 0)
        current_waiting = current_state.get('waiting_vehicles', 0)
        
        if action == 'EXTEND_GREEN':
            efficiency_change = '+5-10%' if current_efficiency < avg_efficiency else '+2-5%'
            waiting_change = '-20-30%' if current_waiting > avg_waiting else '-10-15%'
            congestion_change = 'DECREASE'
        elif action == 'REDUCE_GREEN':
            efficiency_change = '+3-5%'
            waiting_change = '+5-10%' if current_waiting < 3 else '+10-20%'
            congestion_change = 'SLIGHT_INCREASE'
        else:
            efficiency_change = 'MAINTAIN'
            waiting_change = 'MAINTAIN'
            congestion_change = 'STABLE'
        
        return {
            'efficiency_change': efficiency_change,
            'waiting_change': waiting_change,
            'congestion_change': congestion_change,
            'based_on': f'{pattern_match.get("sample_size", 0)} historical samples'
        }
    
    def _build_pattern_reasoning(self, pattern_match: Dict, current_state: Dict, 
                                 action: str) -> str:
        """Build pattern reasoning"""
        reasons = []
        
        match_type = pattern_match.get('match_type', 'UNKNOWN')
        confidence = pattern_match.get('match_confidence', 0) * 100
        sample_size = pattern_match.get('sample_size', 0)
        
        reasons.append(f"Pattern match ({match_type.lower()}, {confidence:.0f}% confidence)")
        reasons.append(f"Based on {sample_size} historical observations")
        
        pattern_type = pattern_match.get('pattern_type', 'UNKNOWN')
        reasons.append(f"Pattern: {pattern_type.replace('_', ' ').title()}")
        
        success_rate = pattern_match.get('action_success_rate', 0) * 100
        reasons.append(f"Action '{action}' has {success_rate:.0f}% success rate")
        
        waiting = current_state.get('waiting_vehicles', 0)
        efficiency = current_state.get('efficiency_score', 0)
        reasons.append(f"Current: {waiting} waiting, {efficiency}% efficiency")
        
        return " | ".join(reasons)
    
    def _refresh_pattern_cache(self):
        """Refresh pattern cache from database"""
        if not self.app:
            return
        
        try:
            with self.app.app_context():
                cutoff_date = datetime.utcnow() - timedelta(days=7)
                
                patterns = TrafficPattern.query.filter(
                    TrafficPattern.created_at >= cutoff_date
                ).all()
                
                self.pattern_cache.clear()
                
                for pattern in patterns:
                    interval_start = pattern.interval_start
                    
                    if isinstance(interval_start, (int, float)):
                        interval_key = int(interval_start)
                    else:
                        continue
                    
                    cache_key = f"{pattern.traffic_light_id}_{pattern.scenario}_{interval_key}"
                    
                    self.pattern_cache[cache_key] = {
                        'pattern_id': pattern.id,
                        'traffic_light_id': pattern.traffic_light_id,
                        'scenario': pattern.scenario,
                        'interval_start': interval_start,
                        'interval_end': pattern.interval_end,
                        'pattern_type': pattern.pattern_type,
                        'best_action': pattern.best_action,
                        'action_success_rate': pattern.action_success_rate or 0.5,
                        'confidence_score': pattern.confidence_score or 0.5,
                        'sample_size': pattern.sample_size or 1,
                        'pattern_metrics': pattern.pattern_metrics or {},
                        'recommendations': pattern.recommendations or [],
                        'created_at': pattern.created_at,
                        'updated_at': pattern.updated_at
                    }
                
                self.last_cache_update = time.time()
                
                unique_tls = len(set([p.traffic_light_id for p in patterns]))
                print(f"✅ Pattern cache refreshed: {len(self.pattern_cache)} patterns ({unique_tls} traffic lights)")
                
        except Exception as e:
            print(f"⚠️ Error refreshing pattern cache: {e}")
            import traceback
            traceback.print_exc()
    
    def _log_ai_decision(self, tl_id: str, scenario: str, simulation_time: float,
                        recommendation: Dict, current_state: Dict):
        """Log AI decision to database"""
        try:
            from app.services.db_queue import db_queue_service
            
            if not self.app or not db_queue_service:
                return
            
            with self.app.app_context():
                log_data = {
                    'id': f"ai_{tl_id}_{int(simulation_time)}",
                    'traffic_light_id': tl_id,
                    'scenario': scenario,
                    'simulation_time': simulation_time,
                    'recommended_action': recommendation.get('action', 'MAINTAIN'),
                    'action_type': recommendation.get('action_type', 'RULE_BASED'),
                    'confidence': recommendation.get('confidence', 0),
                    'pattern_matched': recommendation.get('pattern_matched', False),
                    'reasoning': recommendation.get('reasoning', ''),
                    'current_waiting': current_state.get('waiting_vehicles', 0),
                    'current_efficiency': current_state.get('efficiency_score', 0),
                    'created_at': datetime.utcnow()
                }
                
                db_queue_service.add_ai_decision_log(log_data)
                
        except Exception as e:
            print(f"⚠️ Error logging AI decision: {e}")
    
    def _get_fallback_recommendation(self, tl_id: str, tl_data: Dict, 
                                    current_time: float) -> Dict[str, Any]:
        """Fallback recommendation"""
        return {
            'action': 'MAINTAIN',
            'action_type': 'FALLBACK',
            'parameters': {},
            'confidence': 0.3,
            'success_rate': 0.5,
            'pattern_type': 'FALLBACK',
            'pattern_matched': False,
            'reasoning': 'Fallback mode - maintain current configuration',
            'recommendations': ['System operating in safe mode'],
            'expected_impact': {'status': 'monitoring'},
            'should_apply': False,
            'display_priority': 'LOW',
            'timestamp': current_time
        }
    
    def _load_historical_patterns(self):
        """Load patterns on startup"""
        print("📚 Loading historical patterns...")
        self._refresh_pattern_cache()
    
    # Helper methods
    def _categorize_waiting(self, waiting: int) -> str:
        return 'LOW' if waiting < 3 else 'MEDIUM' if waiting < 8 else 'HIGH'
    
    def _categorize_efficiency(self, efficiency: float) -> str:
        return 'LOW' if efficiency < 60 else 'MEDIUM' if efficiency < 80 else 'HIGH'
    
    def _categorize_volume(self, volume: int) -> str:
        return 'LOW' if volume < 5 else 'MEDIUM' if volume < 10 else 'HIGH'
    
    # Public API methods
    def get_decision_statistics(self) -> Dict[str, Any]:
        """Get AI decision statistics"""
        if not self.decision_history:
            return {
                'message': 'No decisions made yet',
                'total_decisions': 0,
                'pattern_match_rate': 0,
                'patterns_in_cache': len(self.pattern_cache),
                'cache_age_seconds': int(time.time() - self.last_cache_update),
                'recommendation_mode': self.recommendation_mode,
                'current_mode': self.get_current_mode()
            }
        
        recent_decisions = list(self.decision_history)[-20:]
        pattern_matched_count = sum(1 for d in recent_decisions if d.get('recommendation', {}).get('pattern_matched'))
        
        return {
            'total_decisions': len(recent_decisions),
            'pattern_match_rate': round(pattern_matched_count / len(recent_decisions) * 100, 1) if recent_decisions else 0,
            'patterns_in_cache': len(self.pattern_cache),
            'cache_age_seconds': int(time.time() - self.last_cache_update),
            'recommendation_mode': self.recommendation_mode,
            'current_mode': self.get_current_mode(),
            'last_decision': recent_decisions[-1] if recent_decisions else None
        }
    
    def get_tl_recommendations(self, tl_id: str, scenario: str) -> List[Dict]:
        """Get recent recommendations for a specific traffic light"""
        recommendations = [
            d for d in self.decision_history 
            if d.get('tl_id') == tl_id
        ]
        return list(recommendations)[-10:]


# Global instance
enhanced_ai_decision_service = EnhancedAIDecisionService()