import time
import threading
from collections import deque
from datetime import datetime

class PerformanceMonitor:
    """
    Real-time performance monitoring for SUMO simulation
    """
    
    def __init__(self, history_size=100):
        self.history_size = history_size
        self.metrics = {
            'steps_per_second': deque(maxlen=history_size),
            'simulation_speed': deque(maxlen=history_size),
            'db_queue_size': deque(maxlen=history_size),
            'traci_call_count': deque(maxlen=history_size),
            'memory_usage': deque(maxlen=history_size)
        }
        
        self.current_stats = {
            'start_time': time.time(),
            'total_steps': 0,
            'last_step_time': time.time(),
            'traci_calls': 0
        }
    
    def record_step(self):
        """Record simulation step performance"""
        current_time = time.time()
        step_duration = current_time - self.current_stats['last_step_time']
        
        if step_duration > 0:
            steps_per_second = 1.0 / step_duration
            self.metrics['steps_per_second'].append(steps_per_second)
            
            # Calculate simulation speed (real-time factor)
            simulation_speed = step_duration / 0.1  # Assuming 0.1s step length
            self.metrics['simulation_speed'].append(simulation_speed)
        
        self.current_stats['total_steps'] += 1
        self.current_stats['last_step_time'] = current_time
    
    def record_traci_call(self):
        """Record TraCI call"""
        self.current_stats['traci_calls'] += 1
        self.metrics['traci_call_count'].append(self.current_stats['traci_calls'])
    
    def record_db_queue_size(self, size):
        """Record database queue size"""
        self.metrics['db_queue_size'].append(size)
    
    def get_current_performance(self):
        """Get current performance metrics"""
        if not self.metrics['steps_per_second']:
            return {}
        
        return {
            'steps_per_second': {
                'current': self.metrics['steps_per_second'][-1],
                'average': sum(self.metrics['steps_per_second']) / len(self.metrics['steps_per_second']),
                'max': max(self.metrics['steps_per_second']),
                'min': min(self.metrics['steps_per_second'])
            },
            'simulation_speed': {
                'current': self.metrics['simulation_speed'][-1],
                'average': sum(self.metrics['simulation_speed']) / len(self.metrics['simulation_speed'])
            },
            'db_queue_size': {
                'current': self.metrics['db_queue_size'][-1] if self.metrics['db_queue_size'] else 0,
                'average': sum(self.metrics['db_queue_size']) / len(self.metrics['db_queue_size']) if self.metrics['db_queue_size'] else 0
            },
            'total_steps': self.current_stats['total_steps'],
            'uptime_seconds': time.time() - self.current_stats['start_time'],
            'traci_calls_total': self.current_stats['traci_calls']
        }
    
    def get_performance_history(self):
        """Get performance history for charts"""
        return {
            'steps_per_second': list(self.metrics['steps_per_second']),
            'simulation_speed': list(self.metrics['simulation_speed']),
            'db_queue_size': list(self.metrics['db_queue_size']),
            'timestamps': [f"{(i*5):.0f}s" for i in range(len(self.metrics['steps_per_second']))]
        }

# Global instance
performance_monitor = PerformanceMonitor()