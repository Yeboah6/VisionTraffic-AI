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
    AI-powered traffic light optimization service for SUMO
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
        Make AI-driven optimization decision for SUMO traffic lights
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
    
    ################# AI Decision Storage #################
    def _store_ai_decision(self, decision_data: Dict, scenario: str):
        """Store AI decision - UPDATED TO USE SCENARIO TIMESTAMP"""
        try:
            action = decision_data['system_decision']['system_action']
            optimized = decision_data['total_tls_optimized']
            scenario_timestamp = decision_data['timestamp']  # SUMO scenario time

            # 1. Always print the decision
            print(f"🎯 AI DECISION MADE: {action} (Optimized: {optimized} TLS) at scenario time: {scenario_timestamp}")
            
            # 2. Generate UNIQUE ID with scenario timestamp + random component
            decision_id = f"decision_{int(scenario_timestamp)}_{random.randint(1000, 9999)}"

            # 3. Simple in-memory storage (always works)
            simple_record = {
                'id': decision_id,
                'timestamp': scenario_timestamp,  # Use scenario timestamp
                'action': action,
                'optimized': optimized,
                'scenario': scenario,
                'stored_at': datetime.utcnow().isoformat()
            }

            self.emergency_storage.append(simple_record)
            if len(self.emergency_storage) > 100:
                self.emergency_storage.pop(0)

            print(f"💾 DECISION STORED IN MEMORY: {len(self.emergency_storage)} total")
            
            # 4. Try database storage using db_queue_service - WITH APP CONTEXT
            if self.app:
                try:
                    with self.app.app_context():
                        # Prepare data for AIDecisionLog model - USING SCENARIO TIMESTAMP
                        db_data = {
                            'decision_id': decision_id,
                            'scenario': scenario,
                            'timestamp': scenario_timestamp,  # SUMO scenario timestamp (float)
                            'ai_mode': decision_data['ai_mode'],
                            'system_action': decision_data['system_decision']['system_action'],
                            'system_recommendation': decision_data['system_decision']['recommendation'],
                            'optimization_ratio': decision_data['system_decision']['optimization_ratio'],
                            'overall_congestion': decision_data['overall_congestion'],
                            'system_health': decision_data['system_health'],
                            'total_decisions': len(decision_data['decisions']),
                            'total_tls_optimized': optimized,
                            'tls_decisions': json.dumps(decision_data['decisions']),
                            'created_at': datetime.utcnow()  # Real-world time for audit
                        }
                        
                        # Use the db_queue_service directly
                        if hasattr(db_queue_service, 'add_ai_decision_log'):
                            db_queue_service.add_ai_decision_log(db_data)
                            print(f"💾 ALSO STORED IN DATABASE via db_queue_service at scenario time: {scenario_timestamp}")
                        else:
                            print(f"⚠️ db_queue_service.add_ai_decision_log not available")
                            
                except Exception as db_error:
                    print(f"⚠️ Database storage failed: {db_error}")
            else:
                print(f"⚠️ No app context available for database storage")

        except Exception as e:
            print(f"❌ Storage completely failed: {e}")
    
    def get_emergency_decisions(self):
        """Get decisions from emergency storage"""
        return self.emergency_storage.copy()
    
    def flush_emergency_storage(self):
        """Try to flush emergency storage to database"""
        if not self.emergency_storage:
            return
            
        print(f"🔄 Flushing {len(self.emergency_storage)} emergency decisions to DB...")
        
        if self.app:
            with self.app.app_context():
                for decision in self.emergency_storage:
                    try:
                        db_data = {
                            'id': decision['id'],
                            'scenario': decision['scenario'],
                            'timestamp': decision['timestamp'],  # Keep original scenario timestamp
                            'ai_mode': 'EMERGENCY_FLUSH',
                            'system_action': decision['action'],
                            'system_recommendation': 'Emergency storage flush',
                            'optimization_ratio': 0,
                            'overall_congestion': 0,
                            'system_health': 0,
                            'total_decisions': 0,
                            'total_tls_optimized': decision['optimized'],
                            'tls_decisions': json.dumps([]),
                            'created_at': datetime.utcnow()
                        }
                        
                        if hasattr(db_queue_service, 'add_ai_decision_log'):
                            db_queue_service.add_ai_decision_log(db_data)
                            
                    except Exception as e:
                        print(f"⚠️ Failed to flush decision {decision['id']}: {e}")
                        
                self.emergency_storage.clear()
                print("✅ Emergency storage flushed to DB")
        else:
            print("⚠️ No app context available for emergency flush")
    
    ############ Single TLS Optimization ############
    def _optimize_single_tls(self, tl_data: Dict, current_time: float) -> Dict[str, Any]:
        """Optimize a single SUMO traffic light using AI"""
        tl_id = tl_data['id']
        performance = tl_data.get('performance', {})
        
        # Extract key metrics for SUMO
        waiting_vehicles = performance.get('waiting_vehicles', 0)
        efficiency = performance.get('efficiency_score', 0)
        current_phase = tl_data.get('phase', 0)
        phase_duration = tl_data.get('phase_duration', 0)
        
        # Get traffic patterns for this TLS
        pattern_key = f"{tl_id}_{self._get_time_period(current_time)}"
        
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
        
        # Update Q-table if learning - WITH UNIQUE CONSTRAINT HANDLING
        if self.is_learning:
            scenario = tl_data.get('scenario', self.get_current_scenario())
            self._update_q_table(tl_id, state, scenario, action, expected_reward, current_time)

        decision = {
            'traffic_light_id': tl_id,
            'action': action['type'],
            'parameters': action['parameters'],
            'expected_reward': expected_reward,
            'congestion_level': self._calculate_congestion_level(waiting_vehicles),
            'confidence': self._calculate_confidence(tl_id, state, action),
            'reasoning': self._generate_reasoning(tl_data, action, expected_reward),
            'timestamp': current_time  # Use scenario timestamp
        }
        
        return decision
    
    ################ Helper Methods #################
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
            'description': 'Maintain current SUMO configuration'
        }
    
    ######## Reward Calculation ########
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

    ######## Q-Table Management ########
    def _update_q_table(self, tl_id: str, state: str, scenario: str, action: Dict, reward: float, current_time: float):
        """Update Q-table and store in database - UPDATED WITH UNIQUE CONSTRAINT HANDLING"""
        action_key = f"{state}_{action['type']}"

        # Q-learning update
        current_q = self.q_tables[tl_id].get(action_key, 0)
        new_q = current_q + self.learning_rate * (reward - current_q)
        self.q_tables[tl_id][action_key] = new_q

        # Update visit count
        visit_count = self.q_tables[tl_id].get(f"{action_key}_count", 0) + 1
        self.q_tables[tl_id][f"{action_key}_count"] = visit_count

        # ✅ Store in database using db_queue_service with scenario timestamp
        # Only store if there's a significant change to avoid duplicates
        if abs(new_q - current_q) > 0.01:  # Only store if meaningful change
            self._persist_q_table_to_db(tl_id, state, scenario, action, new_q, reward, visit_count, current_time)
        
    def _persist_q_table_to_db(self, tl_id: str, state: str, scenario: str, action: Dict, q_value: float, reward: float, visit_count: int, current_time: float):
        """Persist Q-table entry to database using db_queue_service with scenario timestamp"""
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
                    print(f"💾 Q-table updated for {tl_id}: {state} -> {action['type']} (Q: {q_value:.2f}) at scenario time: {current_time}")
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
            'scenario_timestamp': current_time,  # SUMO scenario timestamp
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
                    # 'last_updated': datetime.utcnow()
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
    
    ###### SUMO Business Rules and Constraints ######
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
    
    ##### Congestion and Confidence Calculation #####
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
    
    ############## Human Reasoning Generation ##############
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
    
    ################ System-Level Decision Making ################
    def _make_system_decision(self, decisions: List[Dict], avg_congestion: float, system_health: float) -> Dict[str, Any]:
        """Make system-level optimization decision for SUMO"""
        # Count optimization actions
        optimization_actions = len([d for d in decisions if d['action'] != 'MAINTAIN'])
        total_decisions = len(decisions)
        
        optimization_ratio = optimization_actions / total_decisions if total_decisions > 0 else 0
        
        # Determine system action based on metrics
        if avg_congestion > 7 and system_health < 0.6:
            system_action = 'AGGRESSIVE_OPTIMIZATION'
            recommendation = 'Apply aggressive optimization to reduce SUMO congestion'
        elif avg_congestion > 5 or optimization_ratio > 0.3:
            system_action = 'BALANCED_OPTIMIZATION'
            recommendation = 'Continue balanced SUMO optimization approach'
        else:
            system_action = 'MINIMAL_INTERVENTION'
            recommendation = 'SUMO system performing well - minimal intervention needed'
        
        return {
            'system_action': system_action,
            'recommendation': recommendation,
            'optimization_ratio': round(optimization_ratio, 2),
            'avg_congestion': round(avg_congestion, 2),
            'system_health': round(system_health, 2)
        }
    
    ################ System Health Calculation ################
    def _calculate_system_health(self, decisions: List[Dict]) -> float:
        """Calculate overall SUMO system health (0-1 scale)"""
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
        """Convert SUMO simulation time to time period"""
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
        """Set the current scenario for all SUMO operations"""
        self.current_scenario = scenario
        print(f"🎯 SUMO Scenario set to: {scenario}")
    
    def _is_peak_hour(self, current_time: float) -> bool:
        """Check if current time is peak hour in SUMO"""
        hour = (current_time // 3600) % 24
        return (7 <= hour < 10) or (16 <= hour < 19)
    
    def _get_default_decision(self) -> Dict[str, Any]:
        """Return default decision when optimization fails"""
        return {
            'timestamp': time.time(),
            'decisions': [],
            'system_decision': {
                'system_action': 'MAINTAIN',
                'recommendation': 'No optimization - default behavior',
                'optimization_ratio': 0,
                'avg_congestion': 0,
                'system_health': 1.0
            },
            'overall_congestion': 0,
            'system_health': 1.0,
            'ai_mode': 'DEFAULT',
            'total_tls_optimized': 0
        }
    
    ############################# Performance Tracking ########################
    def track_performance(self, decision_data: Dict, actual_outcome: Dict):
        """Track performance of AI decisions for SUMO"""
        expected_health = decision_data['system_health']
        actual_health = actual_outcome.get('system_health', 0)
        
        performance_diff = actual_health - expected_health
        
        performance_record = {
            'timestamp': time.time(),
            'expected_health': expected_health,
            'actual_health': actual_health,
            'performance_diff': performance_diff,
            'total_decisions': len(decision_data['decisions']),
            'optimized_tls': decision_data['total_tls_optimized'],
            'ai_mode': decision_data['ai_mode']
        }
        
        self.performance_history.append(performance_record)
        
        # Store performance in database using db_queue_service
        self._store_performance_metric(performance_record)
    
    def _store_performance_metric(self, performance_record: Dict):
        """Store performance metric using db_queue_service"""
        try:
            # Prepare data for performance tracking
            metric_data = {
                'timestamp': datetime.utcnow(),
                'expected_health': performance_record['expected_health'],
                'actual_health': performance_record['actual_health'],
                'performance_diff': performance_record['performance_diff'],
                'total_decisions': performance_record['total_decisions'],
                'optimized_tls': performance_record['optimized_tls'],
                'ai_mode': performance_record['ai_mode'],
                'scenario': self.get_current_scenario()
            }
            
            # Use db_queue_service if available
            if hasattr(db_queue_service, 'add_performance_metric'):
                db_queue_service.add_performance_metric(metric_data)
            else:
                print(f"⚠️ db_queue_service.add_performance_metric not available")
                
        except Exception as e:
            print(f"⚠️ Failed to store SUMO performance metric: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for SUMO AI optimization"""
        if not self.performance_history:
            return {
                'avg_performance_diff': 0,
                'success_rate': 0,
                'total_decisions_tracked': 0,
                'avg_optimization_ratio': 0
            }
        
        performance_diffs = [p['performance_diff'] for p in self.performance_history]
        successful_decisions = len([p for p in performance_diffs if p >= 0])
        
        return {
            'avg_performance_diff': sum(performance_diffs) / len(performance_diffs),
            'success_rate': successful_decisions / len(performance_diffs),
            'total_decisions_tracked': len(self.performance_history),
            'avg_optimization_ratio': sum(p['optimized_tls'] for p in self.performance_history) / len(self.performance_history)
        }
    
    ############################# Configuration Management ########################
    def set_learning_mode(self, enabled: bool):
        """Enable or disable AI learning mode for SUMO"""
        self.is_learning = enabled
        mode = "ENABLED" if enabled else "DISABLED"
        print(f"🎛️ SUMO AI Learning mode: {mode}")
    
    def set_optimization_mode(self, mode: str):
        """Set optimization mode for SUMO"""
        if mode in self.optimization_modes:
            self.current_mode = mode
            print(f"🎛️ SUMO Optimization mode set to: {mode}")
        else:
            print(f"⚠️ Invalid SUMO optimization mode: {mode}")
    
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
    
    ############################# System Maintenance ########################
    def flush_all_pending_data(self):
        """Flush all pending data to database using db_queue_service"""
        print("🔄 Flushing ALL pending SUMO AI data to database...")
        
        self.flush_emergency_storage()
        self.flush_pending_q_updates()
        # self.flush_pending_patterns()
        
        print("✅ All pending SUMO AI data flushed to database")
    
    def reset_learning(self):
        """Reset AI learning for SUMO (clear Q-tables)"""
        self.q_tables.clear()
        self.performance_history.clear()
        self.optimization_decisions.clear()
        self.traffic_patterns.clear()
        
        print("🔄 SUMO AI Learning reset - all Q-tables and history cleared")

# Global instance
ai_traffic_service = AITrafficService()