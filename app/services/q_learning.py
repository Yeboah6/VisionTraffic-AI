"""
Clean AI System - DECISIONS ONLY, NO SUMO INTEGRATION
All SUMO/TraCI operations handled by optimized_sumo_service.py
"""

import time
from typing import Dict, List, Any, Optional
from collections import defaultdict
import random
import json
from datetime import datetime
import uuid

from app.extensions import db
from app.models.traffic_light import TrafficPattern


class SimpleAIOptimizer:
    """
    Pure AI Decision Engine
    - Receives traffic state data
    - Makes optimization decisions
    - Learns from results
    - NO TraCI/SUMO interaction
    """
    
    def __init__(self, app=None):
        self.app = app
        
        # Q-learning parameters
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.3
        self.min_exploration = 0.05
        
        # Q-table: state -> action -> value
        self.q_table = defaultdict(lambda: {
            'EXTEND_GREEN': 0.0,
            'REDUCE_GREEN': 0.0,
            'MAINTAIN': 0.0
        })
        
        # Experience tracking for learning
        self.last_state = {}      # tl_id -> state
        self.last_action = {}     # tl_id -> action
        self.last_performance = {} # tl_id -> performance metrics
        
        # Statistics
        self.stats = {
            'decisions': 0,
            'learned_episodes': 0,
            'success_rate': 0.5,
            'total_reward': 0,
            'patterns_created': 0
        }
        
        # Pattern creation threshold
        self.pattern_threshold = 5.0
        self.created_patterns = set()
        
        print("🎯 Simple AI Optimizer initialized (decisions only)")
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self._load_q_table()
        print("✅ Simple AI Optimizer ready")
    
    # ==================== MAIN DECISION METHOD ====================
    
    def get_decision(self, tl_data: Dict, scenario: str, 
                    simulation_time: float) -> Dict[str, Any]:
        """
        Get AI decision for a traffic light
        
        Args:
            tl_data: Traffic light data with 'id', 'phase_name', 'performance'
            scenario: Scenario name
            simulation_time: Current simulation time
            
        Returns:
            Decision dict with 'action', 'confidence', 'parameters'
        """
        tl_id = tl_data['id']
        
        # STEP 1: Learn from previous action (if any)
        if tl_id in self.last_state and tl_id in self.last_action:
            self._learn_from_previous(tl_id, tl_data)
        
        # STEP 2: Get current state
        current_state = self._get_state(tl_data)
        state_key = self._state_to_key(current_state)
        
        # STEP 3: Make decision
        action, confidence = self._make_decision(state_key, current_state)
        
        # STEP 4: Calculate action parameters
        parameters = self._get_action_parameters(action, tl_data)
        
        # STEP 5: Store for next learning cycle
        self.last_state[tl_id] = current_state
        self.last_action[tl_id] = action
        self.last_performance[tl_id] = tl_data['performance']
        
        self.stats['decisions'] += 1
        
        # STEP 6: Check pattern creation
        if self.stats['decisions'] % 50 == 0:
            self._check_create_patterns(scenario, simulation_time)
        
        return {
            'tl_id': tl_id,
            'action': action,
            'confidence': confidence,
            'parameters': parameters,
            'state': state_key,
            'q_value': self.q_table[state_key][action],
            'reasoning': self._get_reasoning(action, current_state, confidence)
        }
    
    # ==================== STATE ANALYSIS ====================
    
    def _get_state(self, tl_data: Dict) -> Dict:
        """Extract state from traffic light data"""
        perf = tl_data.get('performance', {})
        
        waiting = perf.get('waiting_vehicles', 0)
        efficiency = perf.get('efficiency_score', 50)
        total = perf.get('total_vehicles', 0)
        phase = tl_data.get('phase_name', 'green').lower()
        
        # Categorize
        wait_cat = 'L' if waiting <= 3 else 'M' if waiting <= 7 else 'H'
        vol_cat = 'L' if total <= 4 else 'M' if total <= 9 else 'H'
        phase_cat = 'G' if 'green' in phase else 'Y' if 'yellow' in phase else 'R'
        
        return {
            'waiting': waiting,
            'efficiency': efficiency,
            'total': total,
            'wait_cat': wait_cat,
            'vol_cat': vol_cat,
            'phase_cat': phase_cat
        }
    
    def _state_to_key(self, state: Dict) -> str:
        """Convert state dict to string key"""
        return f"{state['wait_cat']}_{state['vol_cat']}_{state['phase_cat']}"
    
    # ==================== DECISION MAKING ====================
    
    def _make_decision(self, state_key: str, state: Dict) -> tuple:
        """
        Make decision using Q-learning
        Returns: (action, confidence)
        """
        q_values = self.q_table[state_key]
        
        # Exploration vs Exploitation
        if random.random() < self.exploration_rate:
            # Explore: random action
            action = random.choice(list(q_values.keys()))
            confidence = 0.5
        else:
            # Exploit: best action
            action = max(q_values, key=q_values.get)
            max_q = q_values[action]
            confidence = min(0.95, 0.5 + (max_q / 20.0)) if max_q > 0 else 0.5
        
        # Decay exploration rate
        self.exploration_rate = max(self.min_exploration, self.exploration_rate * 0.9995)
        
        return action, confidence
    
    def _get_action_parameters(self, action: str, tl_data: Dict) -> Dict:
        """Calculate action parameters based on traffic state"""
        waiting = tl_data['performance'].get('waiting_vehicles', 0)
        
        if action == 'EXTEND_GREEN':
            # More waiting = more extension
            extension = 5 if waiting < 5 else 10 if waiting < 10 else 15
            return {
                'duration_change': extension,
                'max_duration': 35,
                'reason': f'{waiting} vehicles waiting'
            }
        
        elif action == 'REDUCE_GREEN':
            return {
                'duration_change': -5,
                'min_duration': 10,
                'reason': 'Optimize cycle time'
            }
        
        else:  # MAINTAIN
            return {
                'duration_change': 0,
                'reason': 'Current timing optimal'
            }
    
    def _get_reasoning(self, action: str, state: Dict, confidence: float) -> str:
        """Generate human-readable reasoning"""
        waiting = state['waiting']
        efficiency = state['efficiency']
        
        if action == 'EXTEND_GREEN':
            return f"High traffic ({waiting} waiting, {efficiency:.0f}% efficient) - extend green"
        elif action == 'REDUCE_GREEN':
            return f"Light traffic ({waiting} waiting) - reduce green for efficiency"
        else:
            return f"Optimal conditions ({waiting} waiting, {efficiency:.0f}% efficient) - maintain"
    
    # ==================== LEARNING ====================
    
    def _learn_from_previous(self, tl_id: str, current_tl_data: Dict):
        """Learn from the previous action's results"""
        old_state = self.last_state[tl_id]
        action = self.last_action[tl_id]
        old_perf = self.last_performance[tl_id]
        new_perf = current_tl_data['performance']
        
        # Calculate reward
        reward = self._calculate_reward(old_perf, new_perf)
        self.stats['total_reward'] += reward
        
        # Q-learning update
        new_state = self._get_state(current_tl_data)
        old_state_key = self._state_to_key(old_state)
        new_state_key = self._state_to_key(new_state)
        
        old_q = self.q_table[old_state_key][action]
        max_next_q = max(self.q_table[new_state_key].values())
        
        new_q = old_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - old_q
        )
        
        self.q_table[old_state_key][action] = new_q
        self.stats['learned_episodes'] += 1
        
        # Update success rate
        if reward > 0:
            self.stats['success_rate'] = self.stats['success_rate'] * 0.95 + 0.05
        else:
            self.stats['success_rate'] = self.stats['success_rate'] * 0.98
        
        # Print progress
        if self.stats['learned_episodes'] % 100 == 0:
            print(f"🧠 Learned {self.stats['learned_episodes']} episodes, "
                  f"Reward: {reward:.2f}, Q: {old_state_key}={new_q:.2f}")
        
        # Save periodically
        if self.stats['learned_episodes'] % 200 == 0:
            self._save_q_table()
    
    def _calculate_reward(self, old_perf: Dict, new_perf: Dict) -> float:
        """Calculate reward for the transition"""
        old_wait = old_perf.get('waiting_vehicles', 0)
        new_wait = new_perf.get('waiting_vehicles', 0)
        old_eff = old_perf.get('efficiency_score', 50)
        new_eff = new_perf.get('efficiency_score', 50)
        
        reward = 0
        
        # Reward for reducing waiting
        if new_wait < old_wait:
            reward += (old_wait - new_wait) * 0.3
        
        # Reward for improving efficiency
        if new_eff > old_eff:
            reward += (new_eff - old_eff) * 0.05
        
        # Penalty for high congestion
        if new_wait > 10:
            reward -= 0.5
        
        # Bonus for optimal state
        if new_wait < 3 and new_eff > 85:
            reward += 1.0
        
        return reward
    
    # ==================== PATTERN CREATION ====================
    
    def _check_create_patterns(self, scenario: str, simulation_time: float):
        """Check Q-table and create patterns for successful strategies"""
        if not self.app:
            return
        
        patterns_to_create = []
        
        for state_key, q_values in self.q_table.items():
            for action, q_value in q_values.items():
                if q_value > self.pattern_threshold:
                    pattern_id = f"{state_key}_{action}"
                    
                    if pattern_id in self.created_patterns:
                        continue
                    
                    interval_start = int(simulation_time // 150) * 150
                    interval_end = interval_start + 150
                    
                    patterns_to_create.append({
                        'scenario': scenario,
                        'interval_start': interval_start,
                        'interval_end': interval_end,
                        'state_key': state_key,
                        'best_action': action,
                        'q_value': q_value,
                        'confidence': min(0.95, q_value / 10.0)
                    })
                    
                    self.created_patterns.add(pattern_id)
        
        if patterns_to_create:
            self._create_patterns_in_db(patterns_to_create)
    
    def _create_patterns_in_db(self, patterns_data: List[Dict]):
        """Create patterns in database with proper app context"""
        try:
            with self.app.app_context():
                created = 0
                
                for pdata in patterns_data:
                    metrics = {
                        'efficiency': {'average': 70},
                        'congestion': {'average_waiting': 3},
                        'learning_metadata': {
                            'q_value': pdata['q_value'],
                            'confidence': pdata['confidence'],
                            'source': 'Q_LEARNING'
                        }
                    }
                    
                    pattern = TrafficPattern(
                        id=str(uuid.uuid4()),
                        traffic_light_id='AI_LEARNED',
                        scenario=pdata['scenario'],
                        interval_start=pdata['interval_start'],
                        interval_end=pdata['interval_end'],
                        pattern_type='Q_LEARNED',
                        pattern_metrics=metrics,
                        state_key=pdata['state_key'],
                        best_action=pdata['best_action'],
                        action_success_rate=pdata['confidence'],
                        confidence_score=pdata['confidence'],
                        sample_size=1,
                        recommendations=[
                            f"Q-learning: {pdata['state_key']} -> {pdata['best_action']}",
                            f"Q-value: {pdata['q_value']:.2f}"
                        ]
                    )
                    
                    db.session.add(pattern)
                    created += 1
                
                db.session.commit()
                self.stats['patterns_created'] += created
                print(f"📊 Created {created} patterns in database")
                
        except Exception as e:
            print(f"⚠️ Error creating patterns: {e}")
            try:
                db.session.rollback()
            except:
                pass
    
    # ==================== PERSISTENCE ====================
    
    def _save_q_table(self):
        """Save Q-table to JSON"""
        try:
            data = {
                'q_table': dict(self.q_table),
                'stats': self.stats,
                'exploration_rate': self.exploration_rate,
                'created_patterns': list(self.created_patterns),
                'saved_at': time.time()
            }
            
            with open('simple_q_table.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"💾 Q-table saved: {len(self.q_table)} states")
            
        except Exception as e:
            print(f"⚠️ Failed to save Q-table: {e}")
    
    def _load_q_table(self):
        """Load Q-table from JSON"""
        try:
            with open('simple_q_table.json', 'r') as f:
                data = json.load(f)
            
            self.q_table.update(data.get('q_table', {}))
            self.stats = data.get('stats', self.stats)
            self.exploration_rate = data.get('exploration_rate', 0.3)
            self.created_patterns = set(data.get('created_patterns', []))
            
            print(f"📂 Loaded Q-table: {len(self.q_table)} states")
            
        except FileNotFoundError:
            print("📂 No saved Q-table, starting fresh")
        except Exception as e:
            print(f"⚠️ Failed to load Q-table: {e}")
    
    # ==================== STATUS ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            'decisions_made': self.stats['decisions'],
            'episodes_learned': self.stats['learned_episodes'],
            'success_rate': round(self.stats['success_rate'] * 100, 1),
            'total_reward': round(self.stats['total_reward'], 2),
            'patterns_created': self.stats['patterns_created'],
            'states_learned': len(self.q_table),
            'exploration_rate': round(self.exploration_rate, 3),
            'top_strategies': self._get_top_strategies(5)
        }
    
    def _get_top_strategies(self, limit: int = 5) -> List[Dict]:
        """Get top learned strategies"""
        strategies = []
        
        for state_key, q_values in self.q_table.items():
            best_action = max(q_values, key=q_values.get)
            best_q = q_values[best_action]
            
            if best_q > 0:
                strategies.append({
                    'state': state_key,
                    'action': best_action,
                    'q_value': round(best_q, 2)
                })
        
        strategies.sort(key=lambda x: x['q_value'], reverse=True)
        return strategies[:limit]


# Global instance
simple_ai_optimizer = SimpleAIOptimizer()

def init_simple_ai(app):
    """Initialize simple AI system"""
    simple_ai_optimizer.init_app(app)
    print("🤖 Simple AI System initialized (clean architecture)")
    return simple_ai_optimizer