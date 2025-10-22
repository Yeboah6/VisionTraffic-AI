import time
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
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig, TrafficPattern
from app.models.ai import AIDecisionLog, AIQTable

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
        self.emergency_storage = []  # In-memory fallback
        self.max_emergency_storage = 1000
        
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
        
        self.current_scenario = 'default_simulation'
        
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
            scenario = tls_snapshot.get('scenario', self.get_current_scenario())
            self._store_ai_decision(decision_data, scenario)

            return decision_data
            
        except Exception as e:
            print(f"❌ AI decision error: {e}")
            return self._get_default_decision()
    
    def _store_emergency(self, decision_log):
        """Emergency in-memory storage"""
        self.emergency_storage.append(decision_log)
        if len(self.emergency_storage) > self.max_emergency_storage:
            self.emergency_storage.pop(0)

        print(f"📦 AI Decision in EMERGENCY storage: {decision_log['system_action']}")
        print(f"   Emergency count: {len(self.emergency_storage)}")
    
    ################# AI Decison Storage #################
    def _store_ai_decision(self, decision_data: Dict, scenario: str):
        """Store AI decision - GUARANTEED WORKING VERSION"""
        try:
            action = decision_data['system_decision']['system_action']
            optimized = decision_data['total_tls_optimized']

            # 1. Always print the decision
            print(f"🎯 AI DECISION MADE: {action} (Optimized: {optimized} TLS)")
            
            # 2. Generate UNIQUE ID with timestamp + random component
            decision_id = f"decision_{int(time.time())}_{random.randint(1000, 9999)}"

            # 3. Simple in-memory storage (always works)
            simple_record = {
                'id': decision_id,
                'timestamp': decision_data['timestamp'],
                'action': action,
                'optimized': optimized,
                'scenario': scenario,
                'stored_at': datetime.utcnow().isoformat()
            }

            self.emergency_storage.append(simple_record)
            if len(self.emergency_storage) > 100:
                self.emergency_storage.pop(0)

            print(f"💾 DECISION STORED IN MEMORY: {len(self.emergency_storage)} total")
            # 3. Try database storage (optional)
            try:
                from app.services.db_queue import get_db_queue
                queue = get_db_queue()
                if queue:
                    # Prepare minimal data for DB
                    db_data = {
                        'decision_id': decision_id,
                        'scenario': scenario,
                        'timestamp': decision_data['timestamp'],
                        'ai_mode': decision_data['ai_mode'],
                        'system_action': decision_data['system_decision']['system_action'],
                        'system_recommendation': decision_data['system_decision']['recommendation'],
                        'optimization_ratio': decision_data['system_decision']['optimization_ratio'],
                        'overall_congestion': decision_data['overall_congestion'],
                        'system_health': decision_data['system_health'],
                        'system_action': action,
                        'total_decisions': len(decision_data['decisions']),
                        'total_tls_optimized': optimized,
                        'tls_decisions': json.dumps(decision_data['decisions']),
                        'created_at': datetime.utcnow()
                    }
                    # Check if decision_id already exists before inserting
                    if not self._decision_exists_in_db(decision_id):
                        queue.add_ai_decision_log(db_data)
                        print(f"💾 ALSO STORED IN DATABASE")
                    else:
                        print(f"⚠️ Decision {decision_id} already exists in DB, skipping duplicate")
            except Exception as db_error:
                print(f"⚠️ Database storage failed: {db_error}")

        except Exception as e:
            print(f"❌ Storage completely failed: {e}")
    
    def _decision_exists_in_db(self, decision_id: str) -> bool:
        """Check if a decision_id already exists in the database"""
        try:
            from app.services.db_queue import get_db_queue
            queue = get_db_queue()
            if queue and hasattr(queue, 'check_decision_exists'):
                return queue.check_decision_exists(decision_id)
            return False
        except:
            return False
    
    def get_emergency_decisions(self):
        """Get decisions from emergency storage"""
        return self.emergency_storage.copy()
    
    def flush_emergency_storage(self):
        """Try to flush emergency storage to database"""
        if not self.emergency_storage:
            return
            
        print(f"🔄 Flushing {len(self.emergency_storage)} emergency decisions to DB...")
        from app.services.db_queue import get_db_queue
        queue = get_db_queue()
        
        if queue:
            for decision in self.emergency_storage:
                queue.add_ai_decision_log(decision)
            self.emergency_storage.clear()
            print("✅ Emergency storage flushed to DB")
    
    ############ Single TLS Optimization ############
    def _optimize_single_tls(self, tl_data: Dict, current_time: float) -> Dict[str, Any]:
        """Optimize a single traffic light using AI"""
        tl_id = tl_data['id']
        performance = tl_data.get('performance', {})
        # lane_data = tl_data.get('lane_data', {})
        
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
            scenario = tl_data.get('scenario', 'current')
            self._update_q_table(tl_id, scenario, state, action, expected_reward)

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
    
    ################ Helper Methods #################
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

    ################# AI Decision Making #################
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
    
    ################## Action Definitions #################
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

    #### Get random action ####
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
    
    ######## Reward Calculation ########
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

    ######## Q-Table Management ########
    def _update_q_table(self, tl_id: str, state: str, scenario: str, action: Dict, reward: float):
        """Update Q-table and store in database - PROPERLY PERSISTED"""
        action_key = f"{state}_{action['type']}"

        # Q-learning update
        current_q = self.q_tables[tl_id].get(action_key, 0)
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_tables[tl_id][action_key] = new_q

        # Update visit count
        visit_count = self.q_tables[tl_id].get(f"{action_key}_count", 0) + 1
        self.q_tables[tl_id][f"{action_key}_count"] = visit_count

        # ✅ ALWAYS try to store in database with proper error handling
        self._persist_q_table_to_db(tl_id, state, scenario, action, new_q, reward, visit_count)
        
    def _persist_q_table_to_db(self, tl_id: str, scenario: str, state: str, action: Dict, q_value: float, reward: float, visit_count: int):
        """Persist Q-table entry to database"""
        try:
            from app.services.db_queue import get_db_queue
            db_queue = get_db_queue()

            if db_queue and hasattr(db_queue, 'add_q_table_update'):
                q_table_data = {
                    'traffic_light_id': tl_id,
                    'scenario': scenario,  # Fallback scenario
                    'state': state,
                    'action': action['type'],
                    'q_value': q_value,
                    'visit_count': visit_count,
                    'last_reward': reward,
                    'last_updated': datetime.utcnow()
                }

                db_queue.add_q_table_update(q_table_data)
                print(f"💾 Q-table updated for {tl_id}: {state} -> {action['type']} (Q: {q_value:.2f})")

        except Exception as e:
            print(f"⚠️ Failed to persist Q-table to DB: {e}")
            # Fallback: Store in memory for later batch persistence
            self._store_q_table_fallback(tl_id, scenario, state, action, q_value, reward, visit_count)

    def _store_q_table_fallback(self, tl_id: str, scenario: str, state: str, action: Dict, q_value: float, reward: float, visit_count: int):
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
            'timestamp': datetime.utcnow().isoformat()
        }

        self._q_table_pending_updates.append(update_record)

        # Keep only recent updates to avoid memory issues
        if len(self._q_table_pending_updates) > 1000:
            self._q_table_pending_updates = self._q_table_pending_updates[-500:]

    def _store_q_in_decision_log(self, tl_id: str, scenario: str, state: str, action: Dict, q_value: float, reward: float):
        """Fallback: Store Q-table data in AI decision logs"""
        try:
            from app.services.db_queue import get_db_queue
            db_queue = get_db_queue()

            if db_queue and hasattr(db_queue, 'add_ai_decision_log'):
                q_decision_data = {
                    'decision_id': f"qtable_{int(time.time())}_{random.randint(1000,9999)}",
                    'scenario': scenario,
                    'timestamp': datetime.utcnow().timestamp(),
                    'ai_mode': 'Q_LEARNING',
                    'system_action': f"Q_UPDATE_{tl_id}",
                    'system_recommendation': f"State: {state}, Action: {action['type']}, Q: {q_value:.2f}",
                    'overall_congestion': 0,
                    'system_health': 0,
                    'total_tls_optimized': 0,
                    'tls_decisions': json.dumps([{
                        'traffic_light_id': tl_id,
                        'state': state,
                        'action': action['type'],
                        'q_value': q_value,
                        'reward': reward
                    }]),
                    'created_at': datetime.utcnow()
                }
                db_queue.add_ai_decision_log(q_decision_data)

        except Exception as e:
            print(f"⚠️ Failed to store Q-data in decision log: {e}")
    
    def flush_pending_q_updates(self):
        """Flush pending Q-table updates using individual inserts"""
        if not hasattr(self, '_q_table_pending_updates') or not self._q_table_pending_updates:
            return

        print(f"🔄 Flushing {len(self._q_table_pending_updates)} pending Q-table updates...")

        success_count = 0
        from app.services.db_queue import get_db_queue
        db_queue = get_db_queue()

        if not db_queue:
            print("⚠️ No database queue available")
            return

        for update in self._q_table_pending_updates[:]:  # Iterate over copy
            try:
                # Try to insert each update individually
                q_data = {
                    'traffic_light_id': update['traffic_light_id'],
                    'scenario': update['scenario'],  # Fallback scenario
                    'state': update['state'],
                    'action': update['action'],
                    'q_value': update['q_value'],
                    'visit_count': update['visit_count'],
                    'last_reward': update['reward'],
                    'last_updated': datetime.utcnow()
                }

                # Try different method names
                if hasattr(db_queue, 'add_q_table_entry'):
                    db_queue.add_q_table_entry(q_data)
                    success_count += 1
                    self._q_table_pending_updates.remove(update)
                elif hasattr(db_queue, 'add_ai_q_table'):
                    db_queue.add_ai_q_table(q_data)
                    success_count += 1
                    self._q_table_pending_updates.remove(update)

            except Exception as e:
                print(f"⚠️ Failed to flush Q-update for {update['traffic_light_id']}: {e}")

        print(f"✅ Flushed {success_count} Q-table updates to database")
        print(f"📊 Remaining in queue: {len(self._q_table_pending_updates)}")
    
    ###### Business Rules and Constraints ######
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
    
    #####Congestion and Confidence Calculation #####
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
    
    ############## Human Reasoning Generation ##############
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
    
    ################ System-Level Decision Making ################
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
    
    ################ System Health Calculation ################
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

    ##### Get Time Period #####
    def _get_time_period(self, current_time: float) -> str:
        """Convert simulation time to time period - ENHANCED"""
        hour = (current_time // 3600) % 24
        minute = (current_time // 60) % 60

        if 6 <= hour < 9:
            return 'MORNING_PEAK'
        elif 9 <= hour < 12:
            return 'LATE_MORNING'
        elif 12 <= hour < 14:
            return 'LUNCH_TIME'
        elif 14 <= hour < 16:
            return 'AFTERNOON'
        elif 16 <= hour < 19:
            return 'EVENING_PEAK'
        elif 19 <= hour < 22:
            return 'EVENING'
        else:
            return 'NIGHT'
    
    def get_current_scenario(self) -> str:
        """Safely get the current scenario with fallback"""
        if hasattr(self, 'current_scenario'):
            return self.current_scenario
        else:
            # Initialize if missing
            self.current_scenario = 'default_simulation'
            print(f"⚠️ current_scenario was missing - initialized to: {self.current_scenario}")
            return self.current_scenario
    
    def set_current_scenario(self, scenario: str):
        """Set the current scenario for all operations"""
        self.current_scenario = scenario
        print(f"🎯 Scenario set to: {scenario}")
    
    ############################# Traffic Pattern Analysis ########################
    def _analyze_current_pattern(self, tl_data: Dict, current_time: float) -> Dict[str, Any]:
        """Enhanced traffic pattern analysis with proper numeric values"""
        performance = tl_data.get('performance', {})
        waiting = performance.get('avg_waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)  # This should be a number
        tl_id = tl_data['id']

        # Enhanced pattern analysis
        time_period = self._get_time_period(current_time)
        pattern_key = f"{tl_id}_{time_period}"

        # Detect trends from recent patterns
        trend_analysis = self._detect_pattern_trends(pattern_key, waiting, efficiency)

        pattern_data = {
            'traffic_light_id': tl_id,
            'waiting_trend': trend_analysis['waiting_trend'],
            'avg_efficiency': trend_analysis['avg_efficiency'],  # String trend
            'avg_efficiency': float(efficiency),  # ← NUMERIC VALUE, not string
            'time_period': time_period,
            'congestion_probability': self._calculate_congestion_level(waiting),
            'avg_waiting_vehicles': waiting,
            'efficiency_score': float(efficiency),  # ← NUMERIC VALUE
            'created_at': datetime.utcnow(),
            'pattern_strength': trend_analysis['pattern_strength']
        }

        # Store in memory patterns
        scenario = self.get_current_scenario()
        self.traffic_patterns[pattern_key].append(pattern_data)

        # Store in database using existing methods
        self._store_traffic_pattern(tl_id, scenario, pattern_data)

        return pattern_data
    
    def _store_traffic_pattern(self, tl_id: str, scenario: str, pattern_data: Dict):
        """Store traffic pattern in database"""
        try:
            from app.services.db_queue import get_db_queue
            db_queue = get_db_queue()
            
            current_time = datetime.utcnow()

            if db_queue and hasattr(db_queue, 'add_traffic_pattern'):
                pattern_db_data = {
                    'traffic_light_id': tl_id,
                    'scenario': scenario,
                    'pattern_type': pattern_data.get('pattern_type', 'UNKNOWN'),
                    'time_period': pattern_data['time_period'],
                    'day_of_week': current_time.weekday(),
                    'hour_of_day': current_time.hour,
                    'avg_vehicle_count': pattern_data.get('avg_vehicle_count', 0),
                    'avg_waiting_vehicles': pattern_data.get('avg_waiting_vehicles', 0),
                    'avg_efficiency': pattern_data['avg_efficiency'],
                    'congestion_probability': pattern_data['congestion_probability'],
                    'recommended_phase_duration': pattern_data.get('recommended_phase_duration', 0),
                    'recommended_cycle_time': pattern_data.get('recommended_cycle_time'),
                    "optimal_actions": pattern_data.get("optimal_actions"),
                    'confidence_score': pattern_data.get('confidence_score'),
                    'pattern_strength': pattern_data.get('pattern_strength'),
                    'sample_size': pattern_data.get('sample_size'),
                    'last_observed': pattern_data.get('last_observed', current_time),
                    'waiting_trend': pattern_data['waiting_trend'],
                    'created_at': current_time
                }
                db_queue.add_traffic_pattern(pattern_db_data)
                print(f"📊 Traffic pattern stored: {tl_id} - {pattern_data['time_period']}")

        except Exception as e:
            print(f"⚠️ Failed to store traffic pattern: {e}")
            # Fallback: Store in memory
            self._store_pattern_fallback(tl_id, scenario, pattern_data)

    def _store_pattern_fallback(self, tl_id: str, scenario: str, pattern_data: Dict):
        """Fallback storage for traffic patterns"""
        if not hasattr(self, '_pending_patterns'):
            self._pending_patterns = []

        pending_pattern = {
            'traffic_light_id': tl_id,
            'scenario': scenario,
            **pattern_data,
            'stored_at': datetime.utcnow().isoformat()
        }

        self._pending_patterns.append(pending_pattern)

        # Keep only recent patterns
        if len(self._pending_patterns) > 500:
            self._pending_patterns = self._pending_patterns[-250:]

    def flush_pending_patterns(self):
        """Flush pending traffic patterns to database"""
        if not hasattr(self, '_pending_patterns') or not self._pending_patterns:
            return
        
        print(f"🔄 Flushing {len(self._pending_patterns)} pending traffic patterns...")
        
        success_count = 0
        from app.services.db_queue import get_db_queue
        db_queue = get_db_queue()
        
        if not db_queue:
            print("⚠️ No database queue available for patterns")
            return
            
        for pattern in self._pending_patterns[:]:
            try:
                # Extract the separate parameters
                tl_id = pattern['traffic_light_id']
                scenario = pattern['scenario']
                pattern_data = {k: v for k, v in pattern.items() if k not in ['traffic_light_id', 'scenario', 'stored_at']}

                # Use the updated _store_traffic_pattern method
                self._store_traffic_pattern(tl_id, scenario, pattern_data)
                success_count += 1
                self._pending_patterns.remove(pattern)

            except Exception as e:
                print(f"⚠️ Failed to flush pattern for {pattern['traffic_light_id']}: {e}")
        
        print(f"✅ Flushed {success_count} traffic patterns to database")
    
    def get_pattern_analysis(self, tl_id: str = None) -> Dict[str, Any]:
        """Get traffic pattern analysis summary"""
        patterns_to_analyze = {}

        if tl_id:
            # Analyze specific TLS
            for pattern_key, pattern_list in self.traffic_patterns.items():
                if pattern_key.startswith(tl_id):
                    patterns_to_analyze[pattern_key] = pattern_list
        else:
            # Analyze all patterns
            patterns_to_analyze = dict(self.traffic_patterns)

        analysis = {}
        for pattern_key, patterns in patterns_to_analyze.items():
            if not patterns:
                continue

            recent_patterns = list(patterns)[-50:]  # Last 50 patterns

            analysis[pattern_key] = {
                'total_patterns': len(recent_patterns),
                'avg_congestion': sum(p['congestion_probability'] for p in recent_patterns) / len(recent_patterns),
                'common_waiting_trend': max(set(p['waiting_trend'] for p in recent_patterns), 
                                          key=lambda x: list(p['waiting_trend'] for p in recent_patterns).count(x)),
                'common_avg_efficiency': max(set(p['avg_efficiency'] for p in recent_patterns), 
                                             key=lambda x: list(p['avg_efficiency'] for p in recent_patterns).count(x)),
                'last_updated': recent_patterns[-1]['created_at'] if recent_patterns else None
            }

        return analysis
    
    def _detect_pattern_trends(self, pattern_key: str, current_waiting: int, current_efficiency: float) -> Dict[str, Any]:
        """Detect trends from recent pattern history"""
        recent_patterns = list(self.traffic_patterns[pattern_key])[-5:]  # Last 5 patterns

        if len(recent_patterns) < 3:
            # Not enough data, use current state
            waiting_trend = 'INCREASING' if current_waiting > 5 else 'STABLE' if current_waiting > 2 else 'DECREASING'

            # Convert numeric efficiency to string trend
            if current_efficiency > 80:
                avg_efficiency = 'HIGH'
            elif current_efficiency > 60:
                avg_efficiency = 'MEDIUM'
            else:
                avg_efficiency = 'LOW'

            pattern_strength = 'WEAK'
        else:
            # Analyze trends from history
            waiting_values = [p.get('waiting_vehicles', 0) for p in recent_patterns]
            efficiency_values = [p.get('efficiency_score', 0) for p in recent_patterns]

            # Calculate trends
            waiting_change = waiting_values[-1] - waiting_values[0]
            efficiency_change = efficiency_values[-1] - efficiency_values[0]

            # Determine waiting trends
            if waiting_change > 2:
                waiting_trend = 'INCREASING'
            elif waiting_change < -2:
                waiting_trend = 'DECREASING'
            else:
                waiting_trend = 'STABLE'

            # Determine efficiency trends
            if efficiency_change > 10:
                avg_efficiency = 'IMPROVING'
            elif efficiency_change < -10:
                avg_efficiency = 'DECLINING'
            else:
                # Convert current efficiency to trend category
                current_eff = efficiency_values[-1] if efficiency_values else current_efficiency
                if current_eff > 80:
                    avg_efficiency = 'HIGH'
                elif current_eff > 60:
                    avg_efficiency = 'MEDIUM'
                else:
                    avg_efficiency = 'LOW'

            pattern_strength = 'STRONG' if abs(waiting_change) > 3 or abs(efficiency_change) > 15 else 'MODERATE'

        return {
            'waiting_trend': waiting_trend,
            'avg_efficiency': avg_efficiency,
            'pattern_strength': pattern_strength
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
    
    # def train_on_historical_data(self, days: int = 7):
    #     """Train AI on historical data"""
    #     if not self.app:
    #         return {"success": False, "error": "No app context"}
        
    #     try:
    #         with self.app.app_context():
    #             # Get historical data
    #             since_time = datetime.utcnow() - timedelta(days=days)
    #             historical_logs = TrafficLightLog.query.filter(
    #                 TrafficLightLog.created_at >= since_time
    #             ).order_by(TrafficLightLog.created_at).all()
                
    #             print(f"🤖 Training AI on {len(historical_logs)} historical records...")
                
    #             # Group logs by TLS and time
    #             tls_groups = defaultdict(list)
    #             for log in historical_logs:
    #                 tls_groups[log.traffic_light_id].append(log)
                
    #             # Train on each TLS
    #             trained_count = 0
    #             for tl_id, logs in tls_groups.items():
    #                 if self._train_on_tls_history(tl_id, logs):
    #                     trained_count += 1
                
    #             return {
    #                 "success": True,
    #                 "trained_tls_count": trained_count,
    #                 "total_logs_processed": len(historical_logs),
    #                 "message": f"AI trained on {trained_count} traffic lights"
    #             }
                
    #     except Exception as e:
    #         return {"success": False, "error": str(e)}
    
    # def _train_on_tls_history(self, tl_id: str, logs: List[TrafficLightLog]) -> bool:
    #     """Train Q-learning on historical data for a TLS"""
    #     try:
    #         # Sort logs by time
    #         logs.sort(key=lambda x: x.created_at)
            
    #         # Process in sequences
    #         for i in range(len(logs) - 1):
    #             current_log = logs[i]
    #             next_log = logs[i + 1]
                
    #             # Create state representation
    #             state = self._get_state_from_log(current_log)
                
    #             # Infer action (simplified - in reality would need action history)
    #             action = self._infer_action_from_logs(current_log, next_log)
                
    #             # Calculate reward
    #             reward = self._calculate_reward_from_logs(current_log, next_log)
                
    #             # Update Q-table
    #             if state and action:
    #                 action_key = f"{state}_{action['type']}"
    #                 current_q = self.q_tables[tl_id].get(action_key, 0)
    #                 new_q = current_q + self.learning_rate * (reward - current_q)
    #                 self.q_tables[tl_id][action_key] = new_q
            
    #         return True
            
    #     except Exception as e:
    #         print(f"❌ Training error for {tl_id}: {e}")
    #         return False
    
    # def _get_state_from_log(self, log: TrafficLightLog) -> str:
    #     """Get state representation from log"""
    #     waiting_level = 'LOW' if log.waiting_vehicles < 3 else 'MEDIUM' if log.waiting_vehicles < 8 else 'HIGH'
    #     efficiency_level = 'LOW' if (log.efficiency_score or 0) < 60 else 'MEDIUM' if (log.efficiency_score or 0) < 80 else 'HIGH'
        
    #     return f"{waiting_level}_{efficiency_level}_{log.phase_name}"
    
    # def _infer_action_from_logs(self, current_log: TrafficLightLog, next_log: TrafficLightLog) -> Optional[Dict]:
    #     """Infer action from consecutive logs (simplified)"""
    #     # This is a simplified inference - real implementation would need action logs
    #     phase_change = next_log.phase - current_log.phase
        
    #     if phase_change != 0:
    #         return {'type': 'SKIP_PHASE', 'parameters': {'phases_to_skip': phase_change}}
    #     else:
    #         return self._get_default_action()
    
    # def _calculate_reward_from_logs(self, current_log: TrafficLightLog, next_log: TrafficLightLog) -> float:
    #     """Calculate reward from consecutive logs"""
    #     waiting_improvement = (current_log.waiting_vehicles or 0) - (next_log.waiting_vehicles or 0)
    #     efficiency_improvement = (next_log.efficiency_score or 0) - (current_log.efficiency_score or 0)
        
    #     return waiting_improvement * 2 + efficiency_improvement * 0.5

# Global instance
ai_traffic_service = AITrafficService()

def init_ai_traffic_service(app):
    """Initialize AI traffic service"""
    ai_traffic_service.init_app(app)