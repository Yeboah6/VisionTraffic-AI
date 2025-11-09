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
from app.services.ai_decision import ai_decision_service
from app.services.green_wave_service import green_wave_service

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
        
        # Use the decision service for core AI functions
        self.decision_service = ai_decision_service
        
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
        
        # Add green wave service
        self.green_wave_service = green_wave_service
        self.green_wave_enabled = True
        
        self.current_scenario = 'default_simulation'
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        # Also initialize the decision service
        self.decision_service.init_app(app)
    
    def make_traffic_decision(self, tls_snapshot: Dict, current_time: float) -> Dict[str, Any]:
        """
        Make AI-driven optimization decision with green wave integration
        """
        if not tls_snapshot or not tls_snapshot.get('traffic_lights'):
            return self._get_default_decision()
        
        try:
            # First, check for green wave opportunities
            green_wave_result = None
            if self.green_wave_enabled:
                green_wave_result = self.green_wave_service.integrate_with_ai_decision(
                    tls_snapshot, current_time
                )
            
            decisions = []
            overall_congestion = 0
            total_tls = len(tls_snapshot['traffic_lights'])
            
            # Use green wave decisions if available, otherwise use standard AI
            if green_wave_result and green_wave_result['primary_strategy'] == 'GREEN_WAVE':
                wave_decision = green_wave_result['wave_decision']
                decisions = wave_decision['coordinated_decisions']
            
                # Mark these as green wave decisions
                for decision in decisions:
                    decision['strategy'] = 'GREEN_WAVE'
                    decision['wave_id'] = wave_decision['wave_id']
                
                overall_congestion = self._calculate_wave_congestion(decisions)
            
            else:
            # Standard AI optimization
                for tl_id, tl_data in tls_snapshot['traffic_lights'].items():
                    # Use the decision service for single TLS optimization
                    tl_decision = self.decision_service.optimize_single_tls(tl_data, current_time)
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
                'total_tls_optimized': len([d for d in decisions if d['action'] != 'MAINTAIN']),
                'green_wave_active': green_wave_result['primary_strategy'] == 'GREEN_WAVE' if green_wave_result else False,
                'green_wave_analysis': green_wave_result['analysis'] if green_wave_result else None
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
    
    def _calculate_wave_congestion(self, wave_decisions: List[Dict]) -> float:
        """Calculate congestion level for green wave decisions"""
        if not wave_decisions:
            return 0
        
        total_congestion = 0
        for decision in wave_decisions:
            # Green wave decisions might not have congestion_level, estimate it
            if 'congestion_level' in decision:
                total_congestion += decision['congestion_level']
            else:
                # Estimate based on action type
                if decision['action'] in ['EXTEND_GREEN_WAVE', 'SYNCHRONIZE_GREEN']:
                    total_congestion += 3  # Low congestion for coordinated actions
                else:
                    total_congestion += 5  # Medium congestion for others
        
        return total_congestion / len(wave_decisions)
    
    def set_green_wave_mode(self, enabled: bool):
        """Enable or disable green wave coordination"""
        self.green_wave_enabled = enabled
        mode = "ENABLED" if enabled else "DISABLED"
        print(f"🌊 Green Wave coordination: {mode}")
    
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
        # Also update the decision service
        self.decision_service.set_learning_mode(enabled)
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
        
        # Also update the decision service parameters
        self.decision_service.update_parameters(learning_rate, discount_factor, exploration_rate)
        
        print(f"🔄 SUMO AI Parameters updated - LR: {self.learning_rate}, DF: {self.discount_factor}, ER: {self.exploration_rate}")
    
    ############################# System Maintenance ########################
    def flush_all_pending_data(self):
        """Flush all pending data to database using db_queue_service"""
        print("🔄 Flushing ALL pending SUMO AI data to database...")
        
        # Flush emergency storage
        self.flush_emergency_storage()
        
        # Flush pending Q-table updates from decision service
        self.decision_service.flush_pending_q_updates()
        
        print("✅ All pending SUMO AI data flushed")
    
    def reset_learning(self):
        """Reset AI learning for SUMO (clear Q-tables and history)"""
        self.performance_history.clear()
        self.optimization_decisions.clear()
        self.traffic_patterns.clear()
        self.time_based_profiles.clear()
        
        # Also reset the decision service
        self.decision_service.reset_learning()
        
        print("🔄 SUMO AI Learning reset - all Q-tables and history cleared")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status for SUMO AI"""
        performance_stats = self.get_performance_stats()
        
        return {
            'ai_mode': self.current_mode,
            'learning_enabled': self.is_learning,
            'learning_rate': self.learning_rate,
            'discount_factor': self.discount_factor,
            'exploration_rate': self.exploration_rate,
            'performance_stats': performance_stats,
            'emergency_storage_count': len(self.emergency_storage),
            'decision_history_count': len(self.optimization_decisions),
            'performance_history_count': len(self.performance_history),
            'current_scenario': self.get_current_scenario(),
            'decision_service_status': 'ACTIVE' if self.decision_service else 'INACTIVE'
        }

# Global instance
ai_traffic_service = AITrafficService()