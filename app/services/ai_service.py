import numpy as np
import json
from datetime import datetime
import threading
from flask import current_app

class AIService:
    def __init__(self, app=None):
        self.models = {}
        self.is_trained = False
        self.prediction_cache = {}
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        self.config = app.config
        # Load pre-trained models or initialize them
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize AI models"""
        # Placeholder for model initialization
        # In a real implementation, this would load pre-trained models
        self.models = {
            'traffic_predictor': None,
            'signal_optimizer': None,
            'incident_detector': None,
            'route_planner': None
        }
        self.is_trained = True  # Assuming we have pre-trained models
    
    def make_decisions(self, simulation_state):
        """Make AI decisions based on current simulation state"""
        decisions = []
        
        # 1. Optimize traffic signals
        signal_decisions = self.optimize_traffic_signals(simulation_state)
        decisions.extend(signal_decisions)
        
        # 2. Detect and handle incidents
        incident_decisions = self.detect_incidents(simulation_state)
        decisions.extend(incident_decisions)
        
        # 3. Plan optimal routes
        route_decisions = self.plan_routes(simulation_state)
        decisions.extend(route_decisions)
        
        return decisions
    
    def optimize_traffic_signals(self, simulation_state):
        """Optimize traffic signals using AI"""
        decisions = []
        traffic_lights = simulation_state.get('traffic_lights', {})
        vehicles = simulation_state.get('vehicles', {})
        
        # Simple rule-based optimization (replace with ML model)
        for tl_id, tl_data in traffic_lights.items():
            current_state = tl_data.get('state', '')
            phase = tl_data.get('phase', 0)
            
            # Count vehicles approaching this traffic light
            approaching_vehicles = self._count_approaching_vehicles(tl_id, vehicles)
            
            # Simple optimization logic
            if approaching_vehicles['north'] > 5 and 'r' in current_state[0:2]:
                # More than 5 vehicles waiting in north direction, change light
                new_state = 'G' + current_state[1:]  # Set north to green
                decisions.append({
                    'type': 'traffic_light_control',
                    'tl_id': tl_id,
                    'state': new_state,
                    'duration': 30  # 30 seconds
                })
            elif approaching_vehicles['east'] > 5 and 'r' in current_state[2:4]:
                new_state = current_state[0:2] + 'G' + current_state[3:]  # Set east to green
                decisions.append({
                    'type': 'traffic_light_control',
                    'tl_id': tl_id,
                    'state': new_state,
                    'duration': 30
                })
        
        return decisions
    
    def _count_approaching_vehicles(self, tl_id, vehicles):
        """Count vehicles approaching a traffic light"""
        # Simplified implementation
        # In a real system, this would use precise position data
        counts = {'north': 0, 'south': 0, 'east': 0, 'west': 0}
        
        for veh_id, veh_data in vehicles.items():
            position = veh_data.get('position', (0, 0))
            # Simple heuristic based on position
            if position[0] < 100:  # West of intersection
                counts['west'] += 1
            elif position[0] > 300:  # East of intersection
                counts['east'] += 1
            elif position[1] < 100:  # South of intersection
                counts['south'] += 1
            elif position[1] > 300:  # North of intersection
                counts['north'] += 1
        
        return counts
    
    def detect_incidents(self, simulation_state):
        """Detect traffic incidents using AI"""
        decisions = []
        vehicles = simulation_state.get('vehicles', {})
        
        # Check for stopped vehicles (potential incidents)
        for veh_id, veh_data in vehicles.items():
            speed = veh_data.get('speed', 0)
            waiting_time = veh_data.get('waiting_time', 0)
            
            if speed < 1.0 and waiting_time > 30:  # Stopped for more than 30 seconds
                # Potential incident detected
                decisions.append({
                    'type': 'incident',
                    'vehicle_id': veh_id,
                    'location': veh_data.get('position', (0, 0)),
                    'severity': 'medium',
                    'action': 'alert'
                })
        
        return decisions
    
    def plan_routes(self, simulation_state):
        """Plan optimal routes using AI"""
        decisions = []
        vehicles = simulation_state.get('vehicles', {})
        
        # Simple route planning (replace with ML model)
        for veh_id, veh_data in vehicles.items():
            current_route = veh_data.get('route', [])
            if len(current_route) > 2:
                # Check if vehicle is in congestion
                if veh_data.get('speed', 0) < 5.0:  # Slow moving
                    # Suggest alternative route (simplified)
                    new_route = self._find_alternative_route(current_route)
                    if new_route and new_route != current_route:
                        decisions.append({
                            'type': 'vehicle_reroute',
                            'vehicle_id': veh_id,
                            'new_route': new_route
                        })
        
        return decisions
    
    def _find_alternative_route(self, current_route):
        """Find an alternative route (simplified)"""
        # In a real implementation, this would use graph algorithms
        # with real-time traffic data
        if len(current_route) < 2:
            return current_route
        
        # Simple example: just reverse the route for demonstration
        return list(reversed(current_route))
    
    def predict_traffic(self, history_data, steps=4):
        """Predict future traffic conditions"""
        # Placeholder for traffic prediction
        # In a real implementation, this would use a time series model
        
        predictions = []
        current_time = datetime.now()
        
        for i in range(steps):
            # Simple linear prediction based on history
            if history_data and len(history_data) > 1:
                last_value = history_data[-1].get('congestion_level', 1)
                trend = last_value - history_data[-2].get('congestion_level', 1) if len(history_data) > 2 else 0
                predicted_value = max(0, min(3, last_value + trend * 0.5))
            else:
                predicted_value = 1  # Default medium congestion
            
            predictions.append({
                'time_step': i + 1,
                'predicted_congestion': predicted_value,
                'timestamp': (current_time.replace(second=0, microsecond=0) + 
                             timedelta(minutes=15 * i)).isoformat()
            })
        
        return predictions
    
    def get_performance_metrics(self):
        """Get AI performance metrics"""
        # Placeholder for performance tracking
        return {
            'accuracy': 0.85,
            'precision': 0.82,
            'recall': 0.87,
            'f1_score': 0.84,
            'response_time': '0.2s'
        }

# Create a global instance
ai_service = AIService()