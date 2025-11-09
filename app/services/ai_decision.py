import time
import random
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
from app.extensions import db
from app.services.db_queue import db_queue_service

class AIDecisionService:
    """
    Handles AI decision making and Q-learning for traffic light optimization
    """
    
    def __init__(self, app=None):
        self.app = app
        self.is_learning = True
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.2
        
        # Q-learning tables for each TLS
        self.q_tables = defaultdict(lambda: defaultdict(float))
        
        # Decision tracking
        self.optimization_decisions = deque(maxlen=500)
        
        # Performance thresholds
        self.congestion_threshold = 8
        self.waiting_threshold = 10
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
    
    def optimize_single_tls(self, tl_data: Dict, current_time: float) -> Dict[str, Any]:
        """Optimize a single SUMO traffic light using AI"""
        tl_id = tl_data['id']
        performance = tl_data.get('performance', {})
        
        # Extract key metrics for SUMO
        waiting_vehicles = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        current_phase = tl_data.get('phase', 0)
        phase_duration = tl_data.get('phase_duration', 0)
        
        # Q-learning state
        state = self._get_state_representation(tl_data)
        
        # Choose action using epsilon-greedy policy
        if random.random() < self.exploration_rate and self.is_learning:
            action = self._get_random_action()
        else:
            action = self._get_best_action(tl_id, state)
        
        # Apply SUMO-specific business rules and constraints
        action = self._apply_sumo_business_rules(action, tl_data, current_time)
        
        # Calculate expected reward
        expected_reward = self._calculate_reward(tl_data, action)
        
        # Update Q-table if learning
        if self.is_learning:
            scenario = tl_data.get('scenario', 'default')
            self._update_q_table(tl_id, state, scenario, action, expected_reward, current_time)

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
        
        self.optimization_decisions.append(decision)
        return decision
    
    def _get_state_representation(self, tl_data: Dict) -> str:
        """Convert SUMO TLS data to state representation for Q-learning"""
        performance = tl_data.get('performance', {})
        
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        current_phase = tl_data.get('phase', 0)
        
        # Discretize state for SUMO
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
        """Get available optimization actions for SUMO"""
        return [
            {
                'type': 'EXTEND_GREEN',
                'parameters': {'duration_increase': random.randint(5, 15)},
                'description': 'Extend current green phase in SUMO'
            },
            {
                'type': 'REDUCE_GREEN', 
                'parameters': {'duration_decrease': random.randint(5, 10)},
                'description': 'Reduce current green phase in SUMO'
            },
            {
                'type': 'SKIP_PHASE',
                'parameters': {'phases_to_skip': 1},
                'description': 'Skip to next phase in SUMO'
            },
            {
                'type': 'ADJUST_CYCLE',
                'parameters': {'cycle_adjustment': random.randint(-10, 10)},
                'description': 'Adjust cycle time in SUMO'
            },
            {
                'type': 'MAINTAIN',
                'parameters': {},
                'description': 'Maintain current SUMO configuration'
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
            'description': 'Maintain current SUMO configuration'
        }
    
    def _calculate_reward(self, tl_data: Dict, action: Dict) -> float:
        """Calculate reward for action in SUMO context"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        
        base_reward = 0
        
        # Reward for reducing waiting vehicles in SUMO
        if waiting < 3:
            base_reward += 10
        elif waiting < 6:
            base_reward += 5
        elif waiting > 10:
            base_reward -= 10
        
        # Reward for high efficiency in SUMO
        if efficiency > 80:
            base_reward += 8
        elif efficiency > 60:
            base_reward += 4
        elif efficiency < 40:
            base_reward -= 8
        
        # Action-specific rewards/penalties for SUMO
        if action['type'] == 'EXTEND_GREEN' and waiting > 5:
            base_reward += 5
        elif action['type'] == 'REDUCE_GREEN' and waiting < 2:
            base_reward += 3
        elif action['type'] == 'SKIP_PHASE' and efficiency < 50:
            base_reward += 4
        
        # Penalize frequent changes in SUMO
        if action['type'] != 'MAINTAIN':
            base_reward -= 1
        
        return base_reward
    
    def _update_q_table(self, tl_id: str, state: str, scenario: str, action: Dict, reward: float, current_time: float):
        """Update Q-table and store in database"""
        action_key = f"{state}_{action['type']}"

        # Q-learning update
        current_q = self.q_tables[tl_id].get(action_key, 0)
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_tables[tl_id][action_key] = new_q

        # Update visit count
        visit_count = self.q_tables[tl_id].get(f"{action_key}_count", 0) + 1
        self.q_tables[tl_id][f"{action_key}_count"] = visit_count

        # Store in database using db_queue_service with scenario timestamp
        if abs(new_q - current_q) > 0.01:  # Only store if meaningful change
            self._persist_q_table_to_db(tl_id, state, scenario, action, new_q, reward, visit_count, current_time)
    
    def _persist_q_table_to_db(self, tl_id: str, state: str, scenario: str, action: Dict, q_value: float, reward: float, visit_count: int, current_time: float):
        """Persist Q-table entry to database using db_queue_service"""
        try:
            # Prepare data for AIQTable model
            q_table_data = {
                'traffic_light_id': tl_id,
                'scenario': scenario,
                'state': state,
                'action': action['type'],
                'q_value': q_value,
                'visit_count': visit_count,
                'last_reward': reward,
            }

            # Use db_queue_service directly WITH APP CONTEXT
            if self.app and hasattr(db_queue_service, 'add_q_table_entry'):
                with self.app.app_context():
                    db_queue_service.add_q_table_entry(q_table_data)
                    print(f"💾 Q-table updated for {tl_id}: {state} -> {action['type']} (Q: {q_value:.2f})")
            else:
                # Fallback to emergency storage
                self._store_q_table_fallback(tl_id, scenario, state, action, q_value, reward, visit_count, current_time)

        except Exception as e:
            print(f"⚠️ Failed to persist Q-table to DB: {e}")
            # Fallback: Store in memory for later batch persistence
            self._store_q_table_fallback(tl_id, scenario, state, action, q_value, reward, visit_count, current_time)

    def _store_q_table_fallback(self, tl_id: str, scenario: str, state: str, action: Dict, q_value: float, reward: float, visit_count: int, current_time: float):
        """Fallback storage for Q-table when DB fails"""
        if not hasattr(self, '_q_table_pending_updates'):
            self._q_table_pending_updates = []

        update_record = {
            'traffic_light_id': tl_id,
            'scenario': scenario,
            'state': state,
            'action': action['type'],
            'q_value': q_value,
            'reward': reward,
            'visit_count': visit_count,
            'scenario_timestamp': current_time,
            'timestamp': datetime.utcnow().isoformat()
        }

        self._q_table_pending_updates.append(update_record)

        # Keep only recent updates to avoid memory issues
        if len(self._q_table_pending_updates) > 1000:
            self._q_table_pending_updates = self._q_table_pending_updates[-500:]

    def flush_pending_q_updates(self):
        """Flush pending Q-table updates using db_queue_service"""
        if not hasattr(self, '_q_table_pending_updates') or not self._q_table_pending_updates:
            return

        print(f"🔄 Flushing {len(self._q_table_pending_updates)} pending Q-table updates...")

        success_count = 0
        
        if not db_queue_service:
            print("⚠️ No database queue service available")
            return

        for update in self._q_table_pending_updates[:]:
            try:
                # Prepare data for AIQTable model
                q_data = {
                    'traffic_light_id': update['traffic_light_id'],
                    'scenario': update['scenario'],
                    'state': update['state'],
                    'action': update['action'],
                    'q_value': update['q_value'],
                    'visit_count': update['visit_count'],
                    'last_reward': update['reward'],
                }

                # Use db_queue_service method
                if hasattr(db_queue_service, 'add_q_table_entry'):
                    db_queue_service.add_q_table_entry(q_data)
                    success_count += 1
                    self._q_table_pending_updates.remove(update)

            except Exception as e:
                print(f"⚠️ Failed to flush Q-update for {update['traffic_light_id']}: {e}")
        
        print(f"✅ Flushed {success_count} Q-table updates to database")
        print(f"📊 Remaining in queue: {len(self._q_table_pending_updates)}")
    
    def _apply_sumo_business_rules(self, action: Dict, tl_data: Dict, current_time: float) -> Dict:
        """Apply SUMO-specific business rules and constraints to actions"""
        phase_duration = tl_data.get('phase_duration', 0)
        current_phase = tl_data.get('phase_name', '')
        
        # Rule: Don't extend green beyond 60 seconds in SUMO
        if action['type'] == 'EXTEND_GREEN':
            max_extension = 60 - phase_duration
            if max_extension <= 0:
                return self._get_default_action()
            action['parameters']['duration_increase'] = min(
                action['parameters']['duration_increase'], 
                max_extension
            )
        
        # Rule: Don't reduce green below minimum duration in SUMO
        elif action['type'] == 'REDUCE_GREEN':
            min_duration = 10
            if phase_duration - action['parameters']['duration_decrease'] < min_duration:
                return self._get_default_action()
        
        # Rule: Don't skip pedestrian phases during peak hours in SUMO
        elif action['type'] == 'SKIP_PHASE' and 'PEDESTRIAN' in current_phase:
            if self._is_peak_hour(current_time):
                return self._get_default_action()
        
        return action
    
    def _calculate_congestion_level(self, waiting_vehicles: int) -> int:
        """Calculate congestion level (0-10 scale) for SUMO"""
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
        """Generate human-readable reasoning for SUMO decision"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        
        reasons = []
        
        if action['type'] == 'EXTEND_GREEN':
            if waiting > 5:
                reasons.append(f"High congestion ({waiting} waiting vehicles)")
            if efficiency < 60:
                reasons.append("Low efficiency score")
            reasons.append("Extending green to clear backlog in SUMO")
        
        elif action['type'] == 'REDUCE_GREEN':
            if waiting < 3:
                reasons.append("Low congestion - optimizing SUMO cycle time")
            if efficiency > 80:
                reasons.append("High efficiency - minor SUMO adjustment")
        
        elif action['type'] == 'SKIP_PHASE':
            reasons.append("Inefficient phase detected - skipping to improve SUMO flow")
        
        elif action['type'] == 'MAINTAIN':
            reasons.append("Current SUMO configuration performing optimally")
        
        return "; ".join(reasons) if reasons else "No specific reasoning available"
    
    def _is_peak_hour(self, current_time: float) -> bool:
        """Check if current time is peak hour in SUMO"""
        hour = (current_time // 3600) % 24
        return (7 <= hour < 10) or (16 <= hour < 19)
    
    def set_learning_mode(self, enabled: bool):
        """Enable or disable AI learning mode for SUMO"""
        self.is_learning = enabled
        mode = "ENABLED" if enabled else "DISABLED"
        print(f"🎛️ SUMO AI Learning mode: {mode}")
    
    def update_parameters(self, learning_rate: float = None, discount_factor: float = None, 
                         exploration_rate: float = None):
        """Update AI learning parameters for SUMO"""
        if learning_rate is not None:
            self.learning_rate = max(0.01, min(1.0, learning_rate))
        if discount_factor is not None:
            self.discount_factor = max(0.1, min(0.99, discount_factor))
        if exploration_rate is not None:
            self.exploration_rate = max(0.05, min(0.5, exploration_rate))
        
        print(f"🔄 SUMO AI Parameters updated - LR: {self.learning_rate}, DF: {self.discount_factor}, ER: {self.exploration_rate}")
    
    def reset_learning(self):
        """Reset AI learning for SUMO (clear Q-tables)"""
        self.q_tables.clear()
        self.optimization_decisions.clear()
        print("🔄 SUMO AI Learning reset - all Q-tables and history cleared")

# Global instance
ai_decision_service = AIDecisionService()