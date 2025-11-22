"""
Background Q-Learning Service
Trains AI model from historical traffic data WITHOUT affecting simulation performance.
Learning happens in a separate thread, using logged data from the database.
"""

import threading
import time
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
import statistics

from app.extensions import db
from app.models.traffic_light import TrafficLightLog, TrafficPattern


class QLearningService:
    """
    Asynchronous Q-Learning that trains from historical data.
    Does NOT interfere with simulation performance.
    """
    
    def __init__(self, app=None):
        self.app = app
        
        # Q-Learning parameters
        self.learning_rate = 0.1          # Alpha: how much new info overrides old
        self.discount_factor = 0.95       # Gamma: importance of future rewards
        self.exploration_rate = 1.0       # Epsilon: exploration vs exploitation
        self.exploration_decay = 0.995    # How fast exploration decreases
        self.min_exploration = 0.01       # Minimum exploration rate
        
        # Q-Table: {state_key: {action: q_value}}
        self.q_table: Dict[str, Dict[str, float]] = {}
        
        # State discretization bins
        self.efficiency_bins = [0, 40, 60, 80, 100]      # Poor, Low, Medium, High
        self.waiting_bins = [0, 3, 6, 10, float('inf')]  # None, Low, Medium, High
        self.volume_bins = [0, 5, 10, 20, float('inf')]  # Low, Medium, High, Very High
        
        # Available actions
        self.actions = ['EXTEND_GREEN', 'REDUCE_GREEN', 'OPTIMIZE_TIMING', 'MAINTAIN']
        
        # Background learning thread
        self.learning_thread: Optional[threading.Thread] = None
        self.learning_running = False
        self.is_learning = True
        
        # Learning statistics
        self.stats = {
            'episodes_processed': 0,
            'q_table_updates': 0,
            'last_training_time': None,
            'training_batches': 0,
            'total_rewards': 0,
            'avg_reward_per_episode': 0,
            'convergence_history': deque(maxlen=100)
        }
        
        # Training configuration
        self.training_config = {
            'batch_size': 50,              # Logs to process per batch
            'training_interval': 60,        # Seconds between training batches
            'lookback_hours': 24,           # How far back to look for data
            'min_logs_for_training': 10,    # Minimum logs needed
            'save_interval': 300            # Save Q-table every 5 minutes
        }
        
        # Reward function weights
        self.reward_weights = {
            'efficiency_improvement': 2.0,
            'waiting_reduction': 1.5,
            'throughput_increase': 1.0,
            'stability_bonus': 0.5
        }
        
        print("🧠 Background Q-Learning Service initialized")
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self._load_q_table()
        print("✅ Background Q-Learning Service ready")
    
    # ==================== BACKGROUND LEARNING ====================
    
    def start_background_learning(self):
        """Start the background learning thread"""
        if self.learning_running:
            print("⚠️ Background learning already running")
            return
        
        self.learning_running = True
        self.learning_thread = threading.Thread(
            target=self._background_training_loop,
            daemon=True,
            name="QLearning-Background"
        )
        self.learning_thread.start()
        print("🚀 Background Q-Learning started")
    
    def stop_background_learning(self):
        """Stop the background learning thread"""
        self.learning_running = False
        if self.learning_thread and self.learning_thread.is_alive():
            self.learning_thread.join(timeout=5.0)
        self._save_q_table()
        print("⏹️ Background Q-Learning stopped")
    
    def _background_training_loop(self):
        """Main background training loop - runs independently of simulation"""
        last_save_time = time.time()
        
        print("🔄 Background training loop started")
        
        while self.learning_running:
            try:
                if self.is_learning and self.app:
                    # Train on historical data
                    with self.app.app_context():
                        self._train_from_historical_data()
                    
                    # Decay exploration rate
                    self._decay_exploration()
                    
                    # Periodically save Q-table
                    if time.time() - last_save_time > self.training_config['save_interval']:
                        self._save_q_table()
                        last_save_time = time.time()
                
                # Sleep between training batches
                time.sleep(self.training_config['training_interval'])
                
            except Exception as e:
                print(f"❌ Background training error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(60)  # Wait longer on error
    
    def _train_from_historical_data(self):
        """Train Q-learning from logged traffic data"""
        try:
            # Get recent logs
            cutoff_time = datetime.utcnow() - timedelta(
                hours=self.training_config['lookback_hours']
            )
            
            logs = TrafficLightLog.query.filter(
                TrafficLightLog.created_at >= cutoff_time
            ).order_by(
                TrafficLightLog.traffic_light_id,
                TrafficLightLog.simulation_time
            ).limit(self.training_config['batch_size'] * 10).all()
            
            if len(logs) < self.training_config['min_logs_for_training']:
                return
            
            # Group logs by traffic light for sequential learning
            logs_by_tl = self._group_logs_by_traffic_light(logs)
            
            total_reward = 0
            episodes_in_batch = 0
            
            for tl_id, tl_logs in logs_by_tl.items():
                if len(tl_logs) < 2:
                    continue
                
                # Process sequential log pairs as state transitions
                for i in range(len(tl_logs) - 1):
                    current_log = tl_logs[i]
                    next_log = tl_logs[i + 1]
                    
                    # Extract states
                    current_state = self._log_to_state(current_log)
                    next_state = self._log_to_state(next_log)
                    
                    # Infer action from state change
                    action = self._infer_action(current_log, next_log)
                    
                    # Calculate reward
                    reward = self._calculate_reward(current_log, next_log)
                    total_reward += reward
                    
                    # Update Q-value
                    self._update_q_value(current_state, action, reward, next_state)
                    
                    episodes_in_batch += 1
            
            # Update statistics
            if episodes_in_batch > 0:
                self.stats['episodes_processed'] += episodes_in_batch
                self.stats['training_batches'] += 1
                self.stats['total_rewards'] += total_reward
                self.stats['avg_reward_per_episode'] = (
                    self.stats['total_rewards'] / self.stats['episodes_processed']
                )
                self.stats['last_training_time'] = datetime.utcnow().isoformat()
                
                # Track convergence
                avg_batch_reward = total_reward / episodes_in_batch
                self.stats['convergence_history'].append(avg_batch_reward)
                
                print(f"📊 Trained on {episodes_in_batch} episodes, "
                      f"avg reward: {avg_batch_reward:.3f}, "
                      f"Q-table size: {len(self.q_table)}")
                
        except Exception as e:
            print(f"❌ Training error: {e}")
            import traceback
            traceback.print_exc()
    
    # ==================== Q-LEARNING CORE ====================
    
    def _log_to_state(self, log: TrafficLightLog) -> str:
        """Convert a traffic log to a discrete state string"""
        efficiency = log.efficiency_score or 50
        waiting = log.waiting_vehicles or 0
        volume = log.vehicle_count or 0
        phase = log.phase_name or 'UNKNOWN'
        
        # Discretize continuous values
        eff_bin = self._discretize(efficiency, self.efficiency_bins)
        wait_bin = self._discretize(waiting, self.waiting_bins)
        vol_bin = self._discretize(volume, self.volume_bins)
        
        # Create state key
        state_key = f"E{eff_bin}_W{wait_bin}_V{vol_bin}_{phase[:3]}"
        return state_key
    
    def _discretize(self, value: float, bins: List[float]) -> int:
        """Convert continuous value to discrete bin index"""
        for i, threshold in enumerate(bins[1:], 1):
            if value < threshold:
                return i - 1
        return len(bins) - 2
    
    def _infer_action(self, current_log: TrafficLightLog, 
                      next_log: TrafficLightLog) -> str:
        """Infer what action was taken between two states"""
        curr_waiting = current_log.waiting_vehicles or 0
        next_waiting = next_log.waiting_vehicles or 0
        curr_eff = current_log.efficiency_score or 50
        next_eff = next_log.efficiency_score or 50
        
        waiting_change = next_waiting - curr_waiting
        eff_change = next_eff - curr_eff
        
        # Infer action based on observed changes
        if waiting_change < -2 and eff_change > 5:
            return 'EXTEND_GREEN'
        elif waiting_change > 2 and eff_change > 0:
            return 'REDUCE_GREEN'
        elif abs(eff_change) > 10:
            return 'OPTIMIZE_TIMING'
        else:
            return 'MAINTAIN'
    
    def _calculate_reward(self, current_log: TrafficLightLog,
                         next_log: TrafficLightLog) -> float:
        """Calculate reward for state transition"""
        reward = 0.0
        
        # Efficiency improvement reward
        curr_eff = current_log.efficiency_score or 50
        next_eff = next_log.efficiency_score or 50
        eff_improvement = (next_eff - curr_eff) / 100
        reward += eff_improvement * self.reward_weights['efficiency_improvement']
        
        # Waiting reduction reward
        curr_waiting = current_log.waiting_vehicles or 0
        next_waiting = next_log.waiting_vehicles or 0
        if curr_waiting > 0:
            waiting_reduction = (curr_waiting - next_waiting) / max(curr_waiting, 1)
            reward += waiting_reduction * self.reward_weights['waiting_reduction']
        
        # Throughput reward
        curr_volume = current_log.vehicle_count or 0
        next_volume = next_log.vehicle_count or 0
        if curr_volume > 0:
            throughput_change = (next_volume - curr_volume) / max(curr_volume, 1)
            reward += throughput_change * self.reward_weights['throughput_increase']
        
        # Stability bonus (reward for maintaining good performance)
        if next_eff >= 70 and next_waiting <= 3:
            reward += self.reward_weights['stability_bonus']
        
        # Penalty for high congestion
        if next_waiting > 10:
            reward -= 0.5
        
        return reward
    
    def _update_q_value(self, state: str, action: str, 
                        reward: float, next_state: str):
        """Update Q-value using Q-learning update rule"""
        # Initialize state-action pairs if needed
        if state not in self.q_table:
            self.q_table[state] = {a: 0.0 for a in self.actions}
        if next_state not in self.q_table:
            self.q_table[next_state] = {a: 0.0 for a in self.actions}
        
        # Current Q-value
        current_q = self.q_table[state][action]
        
        # Maximum Q-value for next state
        max_next_q = max(self.q_table[next_state].values())
        
        # Q-learning update rule
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state][action] = new_q
        self.stats['q_table_updates'] += 1
    
    def _decay_exploration(self):
        """Decay exploration rate over time"""
        self.exploration_rate = max(
            self.min_exploration,
            self.exploration_rate * self.exploration_decay
        )
    
    # ==================== RECOMMENDATION GENERATION ====================
    
    def get_recommendation(self, tl_data: Dict, scenario: str) -> Dict[str, Any]:
        """
        Get AI recommendation based on learned Q-values.
        Called from pattern mode - does NOT run during simulation.
        """
        try:
            # Convert current data to state
            state = self._data_to_state(tl_data)
            
            # Get best action from Q-table
            if state in self.q_table:
                # Exploitation: choose best action
                q_values = self.q_table[state]
                best_action = max(q_values, key=q_values.get)
                confidence = self._calculate_confidence(q_values, best_action)
                
                return {
                    'action': best_action,
                    'action_type': 'Q_LEARNING',
                    'confidence': confidence,
                    'q_values': q_values,
                    'state': state,
                    'reasoning': self._build_reasoning(state, best_action, q_values),
                    'parameters': self._get_action_parameters(best_action, tl_data),
                    'expected_impact': self._estimate_impact(best_action, tl_data),
                    'learning_stats': {
                        'episodes_trained': self.stats['episodes_processed'],
                        'exploration_rate': self.exploration_rate
                    }
                }
            else:
                # State not seen before - use heuristic
                return self._heuristic_recommendation(tl_data, state)
                
        except Exception as e:
            print(f"❌ Recommendation error: {e}")
            return self._fallback_recommendation()
    
    def _data_to_state(self, tl_data: Dict) -> str:
        """Convert real-time TLS data to state string"""
        performance = tl_data.get('performance', {})
        
        efficiency = performance.get('efficiency_score', 50)
        waiting = performance.get('waiting_vehicles', 0)
        volume = performance.get('total_vehicles', 0)
        phase = tl_data.get('phase_name', 'UNK')[:3]
        
        eff_bin = self._discretize(efficiency, self.efficiency_bins)
        wait_bin = self._discretize(waiting, self.waiting_bins)
        vol_bin = self._discretize(volume, self.volume_bins)
        
        return f"E{eff_bin}_W{wait_bin}_V{vol_bin}_{phase}"
    
    def _calculate_confidence(self, q_values: Dict[str, float], 
                             best_action: str) -> float:
        """Calculate confidence based on Q-value distribution"""
        values = list(q_values.values())
        if not values:
            return 0.5
        
        best_value = q_values[best_action]
        
        # Confidence based on how much better the best action is
        if len(values) > 1:
            second_best = sorted(values, reverse=True)[1]
            if best_value > 0:
                advantage = (best_value - second_best) / abs(best_value)
                confidence = min(0.95, 0.5 + advantage * 0.5)
            else:
                confidence = 0.5
        else:
            confidence = 0.6
        
        # Adjust confidence based on training amount
        training_factor = min(1.0, self.stats['episodes_processed'] / 1000)
        confidence *= (0.5 + 0.5 * training_factor)
        
        return round(confidence, 3)
    
    def _build_reasoning(self, state: str, action: str, 
                        q_values: Dict[str, float]) -> str:
        """Build human-readable reasoning for the recommendation"""
        parts = state.split('_')
        
        eff_level = ['Poor', 'Low', 'Medium', 'High'][int(parts[0][1])]
        wait_level = ['None', 'Low', 'Medium', 'High'][int(parts[1][1])]
        vol_level = ['Low', 'Medium', 'High', 'Very High'][int(parts[2][1])]
        
        best_q = q_values[action]
        episodes = self.stats['episodes_processed']
        
        reasoning = (
            f"Q-Learning recommendation based on {episodes} training episodes | "
            f"State: {eff_level} efficiency, {wait_level} waiting, {vol_level} volume | "
            f"Q-value for {action}: {best_q:.3f} | "
            f"Exploration rate: {self.exploration_rate:.3f}"
        )
        
        return reasoning
    
    def _get_action_parameters(self, action: str, tl_data: Dict) -> Dict[str, Any]:
        """Get parameters for the recommended action"""
        waiting = tl_data.get('performance', {}).get('waiting_vehicles', 0)
        
        if action == 'EXTEND_GREEN':
            extension = 5 if waiting < 5 else 10 if waiting < 10 else 15
            return {
                'duration_change': extension,
                'reason': f'Extend green phase by {extension}s to reduce queue'
            }
        elif action == 'REDUCE_GREEN':
            return {
                'duration_change': -5,
                'reason': 'Reduce green phase to optimize cycle time'
            }
        elif action == 'OPTIMIZE_TIMING':
            return {
                'optimization_type': 'DYNAMIC',
                'reason': 'Adjust timing based on current flow'
            }
        else:
            return {
                'action': 'MONITOR',
                'reason': 'Current configuration is optimal'
            }
    
    def _estimate_impact(self, action: str, tl_data: Dict) -> Dict[str, str]:
        """Estimate impact of the recommended action"""
        performance = tl_data.get('performance', {})
        efficiency = performance.get('efficiency_score', 50)
        waiting = performance.get('waiting_vehicles', 0)
        
        impacts = {
            'EXTEND_GREEN': {
                'efficiency_change': '+5-15%' if efficiency < 70 else '+2-5%',
                'waiting_change': '-20-40%' if waiting > 5 else '-10-20%',
                'congestion_change': 'DECREASE'
            },
            'REDUCE_GREEN': {
                'efficiency_change': '+3-8%',
                'waiting_change': '+5-15%',
                'congestion_change': 'SLIGHT_INCREASE'
            },
            'OPTIMIZE_TIMING': {
                'efficiency_change': '+10-20%',
                'waiting_change': '-15-30%',
                'congestion_change': 'OPTIMIZE'
            },
            'MAINTAIN': {
                'efficiency_change': 'STABLE',
                'waiting_change': 'STABLE',
                'congestion_change': 'STABLE'
            }
        }
        
        impact = impacts.get(action, impacts['MAINTAIN'])
        impact['based_on'] = f'{self.stats["episodes_processed"]} learned episodes'
        
        return impact
    
    def _heuristic_recommendation(self, tl_data: Dict, state: str) -> Dict[str, Any]:
        """Fallback heuristic when state hasn't been seen"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 50)
        
        if waiting > 8 and efficiency < 60:
            action = 'EXTEND_GREEN'
            confidence = 0.6
        elif waiting < 2 and efficiency > 80:
            action = 'REDUCE_GREEN'
            confidence = 0.55
        elif waiting > 5:
            action = 'OPTIMIZE_TIMING'
            confidence = 0.5
        else:
            action = 'MAINTAIN'
            confidence = 0.65
        
        return {
            'action': action,
            'action_type': 'HEURISTIC_FALLBACK',
            'confidence': confidence,
            'state': state,
            'reasoning': f'Heuristic recommendation (state not in Q-table)',
            'parameters': self._get_action_parameters(action, tl_data),
            'expected_impact': self._estimate_impact(action, tl_data),
            'note': 'This state will be learned from future data'
        }
    
    def _fallback_recommendation(self) -> Dict[str, Any]:
        """Emergency fallback recommendation"""
        return {
            'action': 'MAINTAIN',
            'action_type': 'FALLBACK',
            'confidence': 0.3,
            'reasoning': 'Fallback mode - maintain current configuration',
            'parameters': {},
            'expected_impact': {'status': 'monitoring'}
        }
    
    # ==================== PERSISTENCE ====================
    
    def _save_q_table(self):
        """Save Q-table to database or file"""
        try:
            q_table_data = {
                'q_table': self.q_table,
                'stats': {
                    'episodes_processed': self.stats['episodes_processed'],
                    'q_table_updates': self.stats['q_table_updates'],
                    'exploration_rate': self.exploration_rate,
                    'saved_at': datetime.utcnow().isoformat()
                }
            }
            
            # Save to file
            import os
            save_path = os.path.join(
                os.path.dirname(__file__), 
                'q_table_backup.json'
            )
            
            with open(save_path, 'w') as f:
                json.dump(q_table_data, f)
            
            print(f"💾 Q-table saved: {len(self.q_table)} states")
            
        except Exception as e:
            print(f"❌ Error saving Q-table: {e}")
    
    def _load_q_table(self):
        """Load Q-table from file"""
        try:
            import os
            save_path = os.path.join(
                os.path.dirname(__file__), 
                'q_table_backup.json'
            )
            
            if os.path.exists(save_path):
                with open(save_path, 'r') as f:
                    data = json.load(f)
                
                self.q_table = data.get('q_table', {})
                saved_stats = data.get('stats', {})
                
                self.stats['episodes_processed'] = saved_stats.get('episodes_processed', 0)
                self.stats['q_table_updates'] = saved_stats.get('q_table_updates', 0)
                self.exploration_rate = saved_stats.get('exploration_rate', 1.0)
                
                print(f"📂 Q-table loaded: {len(self.q_table)} states, "
                      f"{self.stats['episodes_processed']} episodes")
            else:
                print("📂 No saved Q-table found, starting fresh")
                
        except Exception as e:
            print(f"❌ Error loading Q-table: {e}")
    
    # ==================== HELPER METHODS ====================
    
    def _group_logs_by_traffic_light(self, logs: List[TrafficLightLog]) -> Dict[str, List]:
        """Group logs by traffic light ID"""
        grouped = defaultdict(list)
        for log in logs:
            grouped[log.traffic_light_id].append(log)
        return grouped
    
    # ==================== PUBLIC API ====================
    
    def get_learning_status(self) -> Dict[str, Any]:
        """Get current learning status"""
        convergence = list(self.stats['convergence_history'])
        convergence_rate = 0.0
        
        if len(convergence) >= 10:
            recent = convergence[-10:]
            older = convergence[-20:-10] if len(convergence) >= 20 else convergence[:10]
            if older:
                recent_avg = statistics.mean(recent)
                older_avg = statistics.mean(older)
                if older_avg != 0:
                    convergence_rate = 1 - abs(recent_avg - older_avg) / abs(older_avg)
                    convergence_rate = max(0, min(1, convergence_rate))
        
        return {
            'is_learning': self.is_learning,
            'learning_running': self.learning_running,
            'exploration_rate': round(self.exploration_rate, 4),
            'q_table_size': len(self.q_table),
            'learning_stats': {
                'episodes_processed': self.stats['episodes_processed'],
                'q_table_updates': self.stats['q_table_updates'],
                'training_batches': self.stats['training_batches'],
                'avg_reward': round(self.stats['avg_reward_per_episode'], 4),
                'last_training': self.stats['last_training_time'],
                'convergence_rate': round(convergence_rate, 3)
            },
            'config': self.training_config
        }
    
    def enable_learning(self):
        """Enable Q-learning"""
        self.is_learning = True
        if not self.learning_running:
            self.start_background_learning()
        print("✅ Q-Learning enabled")
    
    def disable_learning(self):
        """Disable Q-learning (keeps Q-table)"""
        self.is_learning = False
        print("⏸️ Q-Learning paused (Q-table preserved)")
    
    def reset_learning(self):
        """Reset Q-table and statistics"""
        self.q_table = {}
        self.exploration_rate = 1.0
        self.stats = {
            'episodes_processed': 0,
            'q_table_updates': 0,
            'last_training_time': None,
            'training_batches': 0,
            'total_rewards': 0,
            'avg_reward_per_episode': 0,
            'convergence_history': deque(maxlen=100)
        }
        print("🔄 Q-Learning reset")
    
    def set_learning_parameters(self, learning_rate: float = None,
                                discount_factor: float = None,
                                exploration_rate: float = None):
        """Adjust learning parameters"""
        if learning_rate is not None:
            self.learning_rate = max(0.01, min(1.0, learning_rate))
        if discount_factor is not None:
            self.discount_factor = max(0.0, min(1.0, discount_factor))
        if exploration_rate is not None:
            self.exploration_rate = max(0.0, min(1.0, exploration_rate))
        
        print(f"🔧 Learning params: α={self.learning_rate}, "
              f"γ={self.discount_factor}, ε={self.exploration_rate}")


# Global instance
q_learning = QLearningService()


def init_q_learning(app):
    """Initialize and start background Q-learning"""
    q_learning.init_app(app)
    q_learning.start_background_learning()
    return q_learning