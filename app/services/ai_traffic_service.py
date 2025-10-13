import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import deque, defaultdict
import random
import json
from app.extensions import db
import uuid

# Models
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig
from app.models.ai import AIDecisionLog, AIQTable, TrafficPattern

# Services
from app.services.db_queue import db_queue_service
from app.services.tls_data_service import tls_data_service

class AITrafficService:
    """
    AI-powered traffic light optimization service
    Uses reinforcement learning and predictive analytics to optimize TLS controls
    """
    
    def __init__(self, app=None):
        self.app = app
        self.is_learning = True
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.2
        
        # Q-learning tables for each TLS
        self.q_tables = defaultdict(lambda: defaultdict(float))
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self.optimization_decisions = deque(maxlen=500)
        
        # Models and thresholds
        self.congestion_threshold = 8  # vehicles
        self.waiting_threshold = 10  # seconds
        self.optimization_modes = ['AGGRESSIVE', 'BALANCED', 'CONSERVATIVE']
        self.current_mode = 'BALANCED'
        
        # Pattern recognition
        self.traffic_patterns = defaultdict(lambda: deque(maxlen=100))
        self.time_based_profiles = defaultdict(dict)
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def make_traffic_decision(self, tls_snapshot: Dict, current_time: float) -> Dict[str, Any]:
        """
        Make AI-driven optimization decision for traffic lights
        """
        if not tls_snapshot or not tls_snapshot.get('traffic_lights'):
            return self._get_default_decision()
        
        try:
            decisions = []
            overall_congestion = 0
            total_tls = len(tls_snapshot['traffic_lights'])
            
            for tl_id, tl_data in tls_snapshot['traffic_lights'].items():
                tl_decision = self._optimize_single_tls(tl_data, current_time)
                decisions.append(tl_decision)
                overall_congestion += tl_decision.get('congestion_level', 0)
            
            # Calculate overall metrics
            avg_congestion = overall_congestion / total_tls if total_tls > 0 else 0
            system_health = self._calculate_system_health(decisions)
            
            # System-level optimization
            system_decision = self._make_system_decision(decisions, avg_congestion, system_health)
            
            decision_data = {
                'timestamp': current_time,
                'decisions': decisions,
                'system_decision': system_decision,
                'overall_congestion': avg_congestion,
                'system_health': system_health,
                'ai_mode': self.current_mode,
                'total_tls_optimized': len([d for d in decisions if d['action'] != 'MAINTAIN'])
            }
            
            # Store decision in database
            self._store_ai_decision(decision_data, tls_snapshot.get('scenario', 'unknown'))

            return decision_data
            
        except Exception as e:
            print(f"❌ AI decision error: {e}")
            return self._get_default_decision()
        
    def _store_ai_decision(self, decision_data: Dict, scenario: str):
        """Store AI decision in database"""
        if not db_queue_service:
            return
        
        try:
            # Prepare decision log
            decision_log = {
                'decision_id': f"ai_decision_{uuid.uuid4().hex[:16]}",
                'timestamp': decision_data['timestamp'],
                'scenario': scenario,
                'ai_mode': decision_data['ai_mode'],
                'exploration_rate': self.exploration_rate,
                'learning_enabled': self.is_learning,
                'system_action': decision_data['system_decision']['system_action'],
                'system_recommendation': decision_data['system_decision']['recommendation'],
                'optimization_ratio': decision_data['system_decision']['optimization_ratio'],
                'overall_congestion': decision_data['overall_congestion'],
                'system_health': decision_data['system_health'],
                'total_tls_optimized': decision_data['total_tls_optimized'],
                'total_decisions': len(decision_data['decisions']),
                'avg_confidence': sum(d.get('confidence', 0) for d in decision_data['decisions']) / len(decision_data['decisions']) if decision_data['decisions'] else 0,
                'total_reward': sum(d.get('expected_reward', 0) for d in decision_data['decisions']),
                'tls_decisions': json.dumps(decision_data['decisions'])
            }
            
            db_queue_service.add_ai_decision_log(decision_log)
            
        except Exception as e:
            print(f"⚠️ Error storing AI decision: {e}")
    
    def _optimize_single_tls(self, tl_data: Dict, current_time: float) -> Dict[str, Any]:
        """Optimize a single traffic light using AI"""
        tl_id = tl_data['id']
        performance = tl_data.get('performance', {})
        lane_data = tl_data.get('lane_data', {})
        
        # Extract key metrics
        waiting_vehicles = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        current_phase = tl_data.get('phase', 0)
        phase_duration = tl_data.get('phase_duration', 0)
        
        # Get traffic patterns for this TLS
        pattern_key = f"{tl_id}_{self._get_time_period(current_time)}"
        current_pattern = self._analyze_current_pattern(tl_data, current_time)
        
        # Q-learning state
        state = self._get_state_representation(tl_data)
        
        # Choose action using epsilon-greedy policy
        if random.random() < self.exploration_rate and self.is_learning:
            action = self._get_random_action()
        else:
            action = self._get_best_action(tl_id, state)
        
        # Apply business rules and constraints
        action = self._apply_business_rules(action, tl_data, current_time)
        
        # Calculate expected reward
        expected_reward = self._calculate_reward(tl_data, action)
        
        # Update Q-table if learning
        if self.is_learning:
            self._update_q_table(tl_id, state, action, expected_reward)
        
        decision = {
            'traffic_light_id': tl_id,
            'action': action['type'],
            'parameters': action['parameters'],
            'expected_reward': expected_reward,
            'congestion_level': self._calculate_congestion_level(waiting_vehicles),
            'confidence': self._calculate_confidence(tl_id, state, action),
            'reasoning': self._generate_reasoning(tl_data, action, expected_reward),
            'timestamp': current_time
        }
        
        return decision
    
    def _get_state_representation(self, tl_data: Dict) -> str:
        """Convert TLS data to state representation for Q-learning"""
        performance = tl_data.get('performance', {})
        lane_data = tl_data.get('lane_data', {})
        
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        current_phase = tl_data.get('phase', 0)
        
        # Discretize state
        waiting_level = 'LOW' if waiting < 3 else 'MEDIUM' if waiting < 8 else 'HIGH'
        efficiency_level = 'LOW' if efficiency < 60 else 'MEDIUM' if efficiency < 80 else 'HIGH'
        phase_type = tl_data.get('phase_name', 'UNKNOWN')
        
        return f"{waiting_level}_{efficiency_level}_{phase_type}"
    
    def _get_best_action(self, tl_id: str, state: str) -> Dict[str, Any]:
        """Get best action from Q-table for given state"""
        actions = self._get_available_actions()
        
        # If state not in Q-table, return default action
        if state not in self.q_tables[tl_id]:
            return self._get_default_action()
        
        # Find action with highest Q-value
        best_action = None
        best_value = float('-inf')
        
        for action in actions:
            action_key = f"{state}_{action['type']}"
            q_value = self.q_tables[tl_id].get(action_key, 0)
            
            if q_value > best_value:
                best_value = q_value
                best_action = action
        
        return best_action if best_action else self._get_default_action()
    
    def _get_available_actions(self) -> List[Dict[str, Any]]:
        """Get available optimization actions"""
        return [
            {
                'type': 'EXTEND_GREEN',
                'parameters': {'duration_increase': random.randint(5, 15)},
                'description': 'Extend current green phase'
            },
            {
                'type': 'REDUCE_GREEN', 
                'parameters': {'duration_decrease': random.randint(5, 10)},
                'description': 'Reduce current green phase'
            },
            {
                'type': 'SKIP_PHASE',
                'parameters': {'phases_to_skip': 1},
                'description': 'Skip to next phase'
            },
            {
                'type': 'ADJUST_CYCLE',
                'parameters': {'cycle_adjustment': random.randint(-10, 10)},
                'description': 'Adjust cycle time'
            },
            {
                'type': 'MAINTAIN',
                'parameters': {},
                'description': 'Maintain current configuration'
            }
        ]
    
    def _get_random_action(self) -> Dict[str, Any]:
        """Get random action for exploration"""
        actions = self._get_available_actions()
        return random.choice(actions)
    
    def _get_default_action(self) -> Dict[str, Any]:
        """Get default maintain action"""
        return {
            'type': 'MAINTAIN',
            'parameters': {},
            'description': 'Maintain current configuration'
        }
    
    def _calculate_reward(self, tl_data: Dict, action: Dict) -> float:
        """Calculate reward for action"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        
        base_reward = 0
        
        # Reward for reducing waiting vehicles
        if waiting < 3:
            base_reward += 10
        elif waiting < 6:
            base_reward += 5
        elif waiting > 10:
            base_reward -= 10
        
        # Reward for high efficiency
        if efficiency > 80:
            base_reward += 8
        elif efficiency > 60:
            base_reward += 4
        elif efficiency < 40:
            base_reward -= 8
        
        # Action-specific rewards/penalties
        if action['type'] == 'EXTEND_GREEN' and waiting > 5:
            base_reward += 5
        elif action['type'] == 'REDUCE_GREEN' and waiting < 2:
            base_reward += 3
        elif action['type'] == 'SKIP_PHASE' and efficiency < 50:
            base_reward += 4
        
        # Penalize frequent changes
        if action['type'] != 'MAINTAIN':
            base_reward -= 1
        
        return base_reward
    
    def _update_q_table(self, tl_id: str, state: str, action: Dict, reward: float):
        """Update Q-table and store in database - FIXED VERSION"""
        action_key = f"{state}_{action['type']}"
        
        # Q-learning update
        current_q = self.q_tables[tl_id].get(action_key, 0)
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_tables[tl_id][action_key] = new_q
        
        # Store in database - ONLY if we have scenario context
        db_queue = get_db_queue()
        if db_queue and hasattr(self, 'current_scenario'):
            try:
                q_table_data = {
                    'traffic_light_id': tl_id,
                    'scenario': self.current_scenario,  # Use current scenario
                    'state': state,
                    'action': action['type'],
                    'q_value': new_q,
                    'visit_count': self.q_tables[tl_id].get(f"{action_key}_count", 0) + 1,
                    'last_reward': reward
                }
                
                # Update visit count
                self.q_tables[tl_id][f"{action_key}_count"] = self.q_tables[tl_id].get(f"{action_key}_count", 0) + 1
                
                db_queue.add_q_table_update(q_table_data)
                
            except Exception as e:
                print(f"⚠️ Error storing Q-table update: {e}")
    
    def _apply_business_rules(self, action: Dict, tl_data: Dict, current_time: float) -> Dict:
        """Apply business rules and constraints to actions"""
        phase_duration = tl_data.get('phase_duration', 0)
        current_phase = tl_data.get('phase_name', '')
        
        # Rule: Don't extend green beyond 60 seconds
        if action['type'] == 'EXTEND_GREEN':
            max_extension = 60 - phase_duration
            if max_extension <= 0:
                return self._get_default_action()
            action['parameters']['duration_increase'] = min(
                action['parameters']['duration_increase'], 
                max_extension
            )
        
        # Rule: Don't reduce green below minimum duration
        elif action['type'] == 'REDUCE_GREEN':
            min_duration = 10
            if phase_duration - action['parameters']['duration_decrease'] < min_duration:
                return self._get_default_action()
        
        # Rule: Don't skip pedestrian phases during peak hours
        elif action['type'] == 'SKIP_PHASE' and 'PEDESTRIAN' in current_phase:
            if self._is_peak_hour(current_time):
                return self._get_default_action()
        
        return action
    
    def _calculate_congestion_level(self, waiting_vehicles: int) -> int:
        """Calculate congestion level (0-10 scale)"""
        if waiting_vehicles < 3:
            return 2
        elif waiting_vehicles < 6:
            return 5
        elif waiting_vehicles < 10:
            return 7
        else:
            return 9
    
    def _calculate_confidence(self, tl_id: str, state: str, action: Dict) -> float:
        """Calculate confidence in decision (0-1 scale)"""
        action_key = f"{state}_{action['type']}"
        q_value = self.q_tables[tl_id].get(action_key, 0)
        
        # Normalize Q-value to confidence score
        confidence = min(1.0, max(0.0, (q_value + 10) / 20))
        return round(confidence, 2)
    
    def _generate_reasoning(self, tl_data: Dict, action: Dict, reward: float) -> str:
        """Generate human-readable reasoning for decision"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        
        reasons = []
        
        if action['type'] == 'EXTEND_GREEN':
            if waiting > 5:
                reasons.append(f"High congestion ({waiting} waiting vehicles)")
            if efficiency < 60:
                reasons.append("Low efficiency score")
            reasons.append("Extending green to clear backlog")
        
        elif action['type'] == 'REDUCE_GREEN':
            if waiting < 3:
                reasons.append("Low congestion - optimizing cycle time")
            if efficiency > 80:
                reasons.append("High efficiency - minor adjustment")
        
        elif action['type'] == 'SKIP_PHASE':
            reasons.append("Inefficient phase detected - skipping to improve flow")
        
        elif action['type'] == 'MAINTAIN':
            reasons.append("Current configuration performing optimally")
        
        return "; ".join(reasons) if reasons else "No specific reasoning available"
    
    def _make_system_decision(self, decisions: List[Dict], avg_congestion: float, system_health: float) -> Dict[str, Any]:
        """Make system-level optimization decision"""
        # Count optimization actions
        optimization_actions = len([d for d in decisions if d['action'] != 'MAINTAIN'])
        total_decisions = len(decisions)
        
        optimization_ratio = optimization_actions / total_decisions if total_decisions > 0 else 0
        
        # Determine system action based on metrics
        if avg_congestion > 7 and system_health < 0.6:
            system_action = 'AGGRESSIVE_OPTIMIZATION'
            recommendation = 'Apply aggressive optimization to reduce congestion'
        elif avg_congestion > 5 or optimization_ratio > 0.3:
            system_action = 'BALANCED_OPTIMIZATION'
            recommendation = 'Continue balanced optimization approach'
        else:
            system_action = 'MINIMAL_INTERVENTION'
            recommendation = 'System performing well - minimal intervention needed'
        
        return {
            'system_action': system_action,
            'recommendation': recommendation,
            'optimization_ratio': round(optimization_ratio, 2),
            'avg_congestion': round(avg_congestion, 2),
            'system_health': round(system_health, 2)
        }
    
    def _calculate_system_health(self, decisions: List[Dict]) -> float:
        """Calculate overall system health (0-1 scale)"""
        if not decisions:
            return 1.0
        
        total_confidence = sum(d.get('confidence', 0) for d in decisions)
        avg_congestion = sum(d.get('congestion_level', 0) for d in decisions) / len(decisions)
        
        # Normalize metrics to health score
        confidence_score = total_confidence / len(decisions)
        congestion_score = 1.0 - (avg_congestion / 10)  # Convert 0-10 scale to 0-1
        
        system_health = (confidence_score * 0.6) + (congestion_score * 0.4)
        return max(0.0, min(1.0, system_health))
    
    def _get_time_period(self, current_time: float) -> str:
        """Convert simulation time to time period"""
        hour = (current_time // 3600) % 24
        
        if 7 <= hour < 10:
            return 'MORNING_PEAK'
        elif 10 <= hour < 16:
            return 'DAY_OFFPEAK'
        elif 16 <= hour < 19:
            return 'EVENING_PEAK'
        else:
            return 'NIGHT'
    
    def _analyze_current_pattern(self, tl_data: Dict, current_time: float) -> Dict[str, Any]:
        """Analyze current traffic pattern"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        
        return {
            'waiting_trend': 'INCREASING' if waiting > 5 else 'STABLE' if waiting > 2 else 'DECREASING',
            'efficiency_trend': 'HIGH' if efficiency > 80 else 'MEDIUM' if efficiency > 60 else 'LOW',
            'time_period': self._get_time_period(current_time),
            'congestion_level': self._calculate_congestion_level(waiting)
        }
    
    def _is_peak_hour(self, current_time: float) -> bool:
        """Check if current time is peak hour"""
        hour = (current_time // 3600) % 24
        return (7 <= hour < 10) or (16 <= hour < 19)
    
    def _get_default_decision(self) -> Dict[str, Any]:
        """Get default decision when optimization fails"""
        return {
            'timestamp': datetime.utcnow().timestamp(),
            'decisions': [],
            'system_decision': {
                'system_action': 'MAINTAIN',
                'recommendation': 'No optimization - system in maintenance mode',
                'optimization_ratio': 0,
                'avg_congestion': 0,
                'system_health': 1.0
            },
            'overall_congestion': 0,
            'system_health': 1.0,
            'ai_mode': self.current_mode,
            'total_tls_optimized': 0
        }
    
    # AI Management Methods
    def set_optimization_mode(self, mode: str):
        """Set AI optimization mode"""
        if mode.upper() in self.optimization_modes:
            self.current_mode = mode.upper()
            print(f"✅ AI mode set to: {self.current_mode}")
        else:
            print(f"⚠️ Invalid AI mode: {mode}")
    
    def enable_learning(self):
        """Enable Q-learning"""
        self.is_learning = True
        print("✅ AI learning enabled")
    
    def disable_learning(self):
        """Disable Q-learning (deployment mode)"""
        self.is_learning = False
        print("✅ AI learning disabled - deployment mode")
    
    def get_ai_status(self) -> Dict[str, Any]:
        """Get AI system status"""
        total_states = sum(len(q_table) for q_table in self.q_tables.values())
        total_decisions = len(self.optimization_decisions)
        
        recent_decisions = list(self.optimization_decisions)[-10:]
        optimization_rate = sum(1 for d in recent_decisions if d['total_tls_optimized'] > 0) / 10 if recent_decisions else 0
        
        return {
            'learning_enabled': self.is_learning,
            'current_mode': self.current_mode,
            'exploration_rate': self.exploration_rate,
            'total_tls_tracked': len(self.q_tables),
            'total_states_learned': total_states,
            'total_decisions_made': total_decisions,
            'recent_optimization_rate': round(optimization_rate, 2),
            'performance_history_size': len(self.performance_history)
        }
    
    def train_on_historical_data(self, days: int = 7):
        """Train AI on historical data"""
        if not self.app:
            return {"success": False, "error": "No app context"}
        
        try:
            with self.app.app_context():
                # Get historical data
                since_time = datetime.utcnow() - timedelta(days=days)
                historical_logs = TrafficLightLog.query.filter(
                    TrafficLightLog.created_at >= since_time
                ).order_by(TrafficLightLog.created_at).all()
                
                print(f"🤖 Training AI on {len(historical_logs)} historical records...")
                
                # Group logs by TLS and time
                tls_groups = defaultdict(list)
                for log in historical_logs:
                    tls_groups[log.traffic_light_id].append(log)
                
                # Train on each TLS
                trained_count = 0
                for tl_id, logs in tls_groups.items():
                    if self._train_on_tls_history(tl_id, logs):
                        trained_count += 1
                
                return {
                    "success": True,
                    "trained_tls_count": trained_count,
                    "total_logs_processed": len(historical_logs),
                    "message": f"AI trained on {trained_count} traffic lights"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _train_on_tls_history(self, tl_id: str, logs: List[TrafficLightLog]) -> bool:
        """Train Q-learning on historical data for a TLS"""
        try:
            # Sort logs by time
            logs.sort(key=lambda x: x.created_at)
            
            # Process in sequences
            for i in range(len(logs) - 1):
                current_log = logs[i]
                next_log = logs[i + 1]
                
                # Create state representation
                state = self._get_state_from_log(current_log)
                
                # Infer action (simplified - in reality would need action history)
                action = self._infer_action_from_logs(current_log, next_log)
                
                # Calculate reward
                reward = self._calculate_reward_from_logs(current_log, next_log)
                
                # Update Q-table
                if state and action:
                    action_key = f"{state}_{action['type']}"
                    current_q = self.q_tables[tl_id].get(action_key, 0)
                    new_q = current_q + self.learning_rate * (reward - current_q)
                    self.q_tables[tl_id][action_key] = new_q
            
            return True
            
        except Exception as e:
            print(f"❌ Training error for {tl_id}: {e}")
            return False
    
    def _get_state_from_log(self, log: TrafficLightLog) -> str:
        """Get state representation from log"""
        waiting_level = 'LOW' if log.waiting_vehicles < 3 else 'MEDIUM' if log.waiting_vehicles < 8 else 'HIGH'
        efficiency_level = 'LOW' if (log.efficiency_score or 0) < 60 else 'MEDIUM' if (log.efficiency_score or 0) < 80 else 'HIGH'
        
        return f"{waiting_level}_{efficiency_level}_{log.phase_name}"
    
    def _infer_action_from_logs(self, current_log: TrafficLightLog, next_log: TrafficLightLog) -> Optional[Dict]:
        """Infer action from consecutive logs (simplified)"""
        # This is a simplified inference - real implementation would need action logs
        phase_change = next_log.phase - current_log.phase
        
        if phase_change != 0:
            return {'type': 'SKIP_PHASE', 'parameters': {'phases_to_skip': phase_change}}
        else:
            return self._get_default_action()
    
    def _calculate_reward_from_logs(self, current_log: TrafficLightLog, next_log: TrafficLightLog) -> float:
        """Calculate reward from consecutive logs"""
        waiting_improvement = (current_log.waiting_vehicles or 0) - (next_log.waiting_vehicles or 0)
        efficiency_improvement = (next_log.efficiency_score or 0) - (current_log.efficiency_score or 0)
        
        return waiting_improvement * 2 + efficiency_improvement * 0.5

# Global instance
ai_traffic_service = AITrafficService()

def init_ai_traffic_service(app):
    """Initialize AI traffic service"""
    ai_traffic_service.init_app(app)