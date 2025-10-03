import json
from typing import Dict, List
from datetime import datetime

class AITrafficService:
    def __init__(self):
        self.decision_history = []
        self.performance_metrics = {}
    
    def make_traffic_decision(self, camera_data: Dict, sumo_state: Dict) -> Dict:
        """Make AI decision based on camera data and SUMO state"""
        
        # Analyze current conditions
        analysis = self._analyze_traffic_conditions(camera_data, sumo_state)
        
        # Make optimization decision
        decision = self._calculate_optimization(analysis)
        
        # Log decision
        decision_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'analysis': analysis,
            'decision': decision,
            'camera_sources': list(camera_data.keys())
        }
        self.decision_history.append(decision_record)
        
        return decision
    
    def _analyze_traffic_conditions(self, camera_data: Dict, sumo_state: Dict) -> Dict:
        """Analyze current traffic conditions from multiple sources"""
        
        total_vehicles = 0
        total_queues = 0
        avg_speed = 0
        camera_count = len(camera_data)
        
        for cam_id, data in camera_data.items():
            total_vehicles += data.get('vehicle_count', 0)
            total_queues += data.get('queue_length', 0)
            avg_speed += data.get('average_speed', 0)
        
        if camera_count > 0:
            avg_speed = avg_speed / camera_count
        
        return {
            'total_vehicles': total_vehicles,
            'total_queues': total_queues,
            'average_speed': avg_speed,
            'congestion_level': self._assess_congestion_level(total_vehicles, total_queues),
            'data_source_count': camera_count,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_optimization(self, analysis: Dict) -> Dict:
        """Calculate traffic light optimization"""
        
        congestion = analysis['congestion_level']
        total_queues = analysis['total_queues']
        
        # Simple rule-based AI (replace with ML model)
        if congestion == 'high' and total_queues > 15:
            return {
                'action': 'extend_green',
                'duration_increase': 20,
                'reason': 'High congestion detected',
                'confidence': 0.85
            }
        elif congestion == 'low' and total_queues < 5:
            return {
                'action': 'reduce_cycle',
                'duration_decrease': 10,
                'reason': 'Light traffic conditions',
                'confidence': 0.75
            }
        else:
            return {
                'action': 'maintain',
                'reason': 'Stable conditions',
                'confidence': 0.90
            }

# Global instance
ai_traffic_service = AITrafficService()