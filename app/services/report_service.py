"""
Report Service - Business logic for report generation and data analysis
"""

from datetime import datetime, timedelta
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig
from app.models.ai import AIDecisionLog, AIPerformance
from app.extensions import db
from sqlalchemy import func, and_
from typing import Dict, List, Optional, Tuple
import json

class ReportService:
    """Service class for handling report generation and analytics"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
    
    def get_date_range(self, date_str: Optional[str], period: str) -> Tuple[datetime, datetime]:
        """Calculate date range based on period type"""
        if date_str:
            end_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            end_date = datetime.now()
        
        period_map = {
            'hourly': timedelta(hours=24),
            'daily': timedelta(days=7),
            'weekly': timedelta(weeks=4),
            'monthly': timedelta(days=365)
        }
        
        delta = period_map.get(period, timedelta(days=7))
        start_date = end_date - delta
        
        return start_date, end_date
    
    def calculate_vehicle_count_metrics(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime,
        location: str = 'all'
    ) -> Dict:
        """Calculate vehicle count metrics with trends"""
        
        # Build query
        query = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        )
        
        if location != 'all':
            query = query.filter(TrafficLightLog.traffic_light_id.like(f'%{location}%'))
        
        current_logs = query.all()
        
        if not current_logs:
            return self._empty_metrics()
        
        # Calculate current metrics
        total_vehicles = sum(log.vehicle_count for log in current_logs)
        avg_efficiency = sum(log.efficiency_score for log in current_logs) / len(current_logs)
        
        # Calculate previous period for trends
        period_length = end_date - start_date
        prev_start = start_date - period_length
        
        prev_query = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= prev_start,
            TrafficLightLog.created_at < start_date
        )
        
        if location != 'all':
            prev_query = prev_query.filter(TrafficLightLog.traffic_light_id.like(f'%{location}%'))
        
        prev_logs = prev_query.all()
        
        # Calculate trends
        trends = self._calculate_trends(current_logs, prev_logs)
        
        return {
            'total_vehicles': total_vehicles,
            'avg_efficiency': round(avg_efficiency, 1),
            'trends': trends
        }
    
    def calculate_speed_metrics(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate average speed based on efficiency scores"""
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        if not logs:
            return {'average_speed': 0, 'min_speed': 0, 'max_speed': 0}
        
        avg_efficiency = sum(log.efficiency_score for log in logs) / len(logs)
        
        # Convert efficiency to speed (simulation formula)
        base_speed = 38.5
        avg_speed = base_speed + (avg_efficiency - 50) * 0.1
        
        return {
            'average_speed': round(avg_speed, 1),
            'min_speed': round(avg_speed - 5, 1),
            'max_speed': round(avg_speed + 5, 1),
            'efficiency_score': round(avg_efficiency, 1)
        }
    
    def detect_peak_hours(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Detect peak traffic hours from vehicle patterns"""
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        if not logs:
            return {'peak_hours': 'N/A', 'hourly_distribution': {}}
        
        # Aggregate by hour
        hourly_counts = {}
        for log in logs:
            hour = log.created_at.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + log.vehicle_count
        
        # Find top 2-3 peak hours
        sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Group consecutive hours
        peak_groups = self._group_peak_hours(sorted_hours[:3])
        
        return {
            'peak_hours': ', '.join(peak_groups),
            'hourly_distribution': hourly_counts,
            'peak_values': dict(sorted_hours[:3])
        }
    
    def calculate_congestion_level(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Calculate overall congestion level and classification"""
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        if not logs:
            return {
                'level': 'Low',
                'percentage': 0,
                'classification': 'OPTIMAL'
            }
        
        avg_congestion = sum(log.efficiency_score for log in logs) / len(logs)
        
        # Classify congestion
        if avg_congestion >= 70:
            level = "High"
            classification = "CRITICAL"
        elif avg_congestion >= 40:
            level = "Medium"
            classification = "MODERATE"
        else:
            level = "Low"
            classification = "OPTIMAL"
        
        return {
            'level': level,
            'percentage': round(avg_congestion, 1),
            'classification': classification
        }
    
    def get_traffic_volume_by_type(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime,
        period: str = 'daily'
    ) -> Dict:
        """Get traffic volume trends broken down by vehicle type"""
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).order_by(TrafficLightLog.created_at).all()
        
        if not logs:
            return {'labels': [], 'datasets': {'cars': [], 'trucks': [], 'buses': []}}
        
        # Group by time period
        time_data = {}
        
        for log in logs:
            time_key = self._get_time_key(log.created_at, period)
            
            if time_key not in time_data:
                time_data[time_key] = {'cars': 0, 'trucks': 0, 'buses': 0}
            
            # Simulate vehicle type distribution
            total = log.vehicle_count
            time_data[time_key]['cars'] += int(total * 0.68)
            time_data[time_key]['trucks'] += int(total * 0.15)
            time_data[time_key]['buses'] += int(total * 0.12)
        
        # Format for frontend
        labels = sorted(time_data.keys())
        
        return {
            'labels': labels,
            'datasets': {
                'cars': [time_data[label]['cars'] for label in labels],
                'trucks': [time_data[label]['trucks'] for label in labels],
                'buses': [time_data[label]['buses'] for label in labels]
            }
        }
    
    def get_congestion_heatmap(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Generate congestion heatmap data (day x hour)"""
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        # Initialize matrices
        congestion_matrix = [[0 for _ in range(24)] for _ in range(7)]
        count_matrix = [[0 for _ in range(24)] for _ in range(7)]
        
        # Aggregate data
        for log in logs:
            day = log.created_at.weekday()
            hour = log.created_at.hour
            congestion_matrix[day][hour] += log.efficiency_score
            count_matrix[day][hour] += 1
        
        # Calculate averages and format for heatmap
        heatmap_data = []
        for day in range(7):
            for hour in range(24):
                if count_matrix[day][hour] > 0:
                    avg_congestion = congestion_matrix[day][hour] / count_matrix[day][hour]
                    heatmap_data.append([hour, day, round(avg_congestion, 1)])
                else:
                    heatmap_data.append([hour, day, 0])
        
        return {
            'hours': self._get_hour_labels(),
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
            'heatmap': heatmap_data
        }
    
    def get_vehicle_distribution(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get vehicle type distribution statistics"""
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        if not logs:
            return {
                "Cars": 0,
                "Trucks": 0,
                "Buses": 0,
                "Motorcycles": 0
            }
        
        total_vehicles = sum(log.vehicle_count for log in logs)
        
        # Simulate distribution based on typical traffic patterns
        return {
            "Cars": round(total_vehicles * 0.68),
            "Trucks": round(total_vehicles * 0.15),
            "Buses": round(total_vehicles * 0.12),
            "Motorcycles": round(total_vehicles * 0.05)
        }
    
    def get_ai_performance_metrics(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Get AI optimization performance metrics"""
        
        ai_logs = AIDecisionLog.query.filter(
            AIDecisionLog.scenario == scenario,
            AIDecisionLog.created_at >= start_date,
            AIDecisionLog.created_at <= end_date
        ).all()
        
        if not ai_logs:
            return self._empty_ai_metrics()
        
        # Calculate metrics
        total_decisions = sum(log.total_decisions for log in ai_logs)
        total_optimized = sum(log.total_tls_optimized for log in ai_logs)
        avg_confidence = sum(log.avg_confidence for log in ai_logs) / len(ai_logs)
        avg_congestion = sum(log.overall_congestion for log in ai_logs) / len(ai_logs)
        avg_health = sum(log.system_health for log in ai_logs) / len(ai_logs)
        total_reward = sum(log.total_reward for log in ai_logs)
        
        optimization_rate = (total_optimized / total_decisions * 100) if total_decisions > 0 else 0
        congestion_reduction = max(0, (1 - avg_congestion / 100) * 100)
        
        return {
            'total_decisions': total_decisions,
            'total_optimized': total_optimized,
            'optimization_rate': round(optimization_rate, 1),
            'avg_confidence': round(avg_confidence, 1),
            'congestion_reduction': round(congestion_reduction, 1),
            'system_health': round(avg_health * 100, 1),
            'avg_reward': round(total_reward / len(ai_logs), 2) if ai_logs else 0,
            'performance_grade': self._calculate_ai_grade(optimization_rate, avg_health)
        }
    
    def get_traffic_light_performance(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 20
    ) -> List[Dict]:
        """Get performance metrics for individual traffic lights"""
        
        tl_performance = db.session.query(
            TrafficLightLog.traffic_light_id,
            func.avg(TrafficLightLog.efficiency_score).label('avg_efficiency'),
            func.sum(TrafficLightLog.vehicle_count).label('total_vehicles'),
            func.avg(TrafficLightLog.waiting_vehicles).label('avg_waiting'),
            func.count(TrafficLightLog.id).label('log_count')
        ).filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).group_by(TrafficLightLog.traffic_light_id).all()
        
        # Format and sort results
        performance_data = []
        for tl in tl_performance:
            grade = self._calculate_tl_grade(tl.avg_efficiency)
            status = "Optimized" if tl.avg_efficiency >= 65 else "Needs Attention"
            
            performance_data.append({
                "traffic_light_id": tl.traffic_light_id,
                "avg_efficiency": round(tl.avg_efficiency, 1),
                "total_vehicles": tl.total_vehicles,
                "avg_waiting": round(tl.avg_waiting, 1),
                "grade": grade,
                "status": status,
                "log_count": tl.log_count
            })
        
        # Sort by efficiency and limit
        performance_data.sort(key=lambda x: x['avg_efficiency'], reverse=True)
        return performance_data[:limit]
    
    # Helper methods
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            'total_vehicles': 0,
            'avg_efficiency': 0,
            'trends': {'vehicle_count': 0, 'speed': 0, 'congestion': 0}
        }
    
    def _empty_ai_metrics(self) -> Dict:
        """Return empty AI metrics structure"""
        return {
            'total_decisions': 0,
            'total_optimized': 0,
            'optimization_rate': 0,
            'avg_confidence': 0,
            'congestion_reduction': 0,
            'system_health': 0,
            'avg_reward': 0,
            'performance_grade': 'N/A'
        }
    
    def _calculate_trends(self, current_logs: List, prev_logs: List) -> Dict:
        """Calculate percentage trends between periods"""
        if not prev_logs:
            return {'vehicle_count': 0, 'speed': 0, 'congestion': 0}
        
        current_vehicles = sum(log.vehicle_count for log in current_logs)
        prev_vehicles = sum(log.vehicle_count for log in prev_logs)
        
        current_efficiency = sum(log.efficiency_score for log in current_logs) / len(current_logs)
        prev_efficiency = sum(log.efficiency_score for log in prev_logs) / len(prev_logs)
        
        current_speed = 38.5 + (current_efficiency - 50) * 0.1
        prev_speed = 38.5 + (prev_efficiency - 50) * 0.1
        
        return {
            'vehicle_count': round(((current_vehicles - prev_vehicles) / prev_vehicles * 100), 1) if prev_vehicles else 0,
            'speed': round(((current_speed - prev_speed) / prev_speed * 100), 1) if prev_speed else 0,
            'congestion': round(((current_efficiency - prev_efficiency) / prev_efficiency * 100), 1) if prev_efficiency else 0
        }
    
    def _get_time_key(self, dt: datetime, period: str) -> str:
        """Get time key based on period"""
        if period == 'hourly':
            return dt.strftime('%H:00')
        elif period == 'daily':
            return dt.strftime('%b %d')
        elif period == 'weekly':
            return dt.strftime('Week %W')
        elif period == 'monthly':
            return dt.strftime('%b %Y')
        return dt.strftime('%Y-%m-%d')
    
    def _group_peak_hours(self, sorted_hours: List[Tuple[int, int]]) -> List[str]:
        """Group consecutive peak hours into ranges"""
        if not sorted_hours:
            return []
        
        groups = []
        current_group = [sorted_hours[0][0]]
        
        for i in range(1, len(sorted_hours)):
            hour = sorted_hours[i][0]
            if abs(hour - current_group[-1]) <= 1:
                current_group.append(hour)
            else:
                groups.append(self._format_hour_range(current_group))
                current_group = [hour]
        
        groups.append(self._format_hour_range(current_group))
        return groups
    
    def _format_hour_range(self, hours: List[int]) -> str:
        """Format hour range for display"""
        if len(hours) == 1:
            return self._format_hour(hours[0])
        return f"{self._format_hour(hours[0])}-{self._format_hour(hours[-1])}"
    
    def _format_hour(self, hour: int) -> str:
        """Format hour for 12-hour display"""
        if hour == 0:
            return "12 AM"
        elif hour < 12:
            return f"{hour} AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"
    
    def _get_hour_labels(self) -> List[str]:
        """Get hour labels for heatmap"""
        labels = []
        for i in range(24):
            if i == 0:
                labels.append('12a')
            elif i < 12:
                labels.append(f'{i}a')
            elif i == 12:
                labels.append('12p')
            else:
                labels.append(f'{i-12}p')
        return labels
    
    def _calculate_tl_grade(self, efficiency: float) -> str:
        """Calculate grade based on efficiency score"""
        if efficiency >= 80:
            return "A"
        elif efficiency >= 65:
            return "B"
        elif efficiency >= 50:
            return "C"
        else:
            return "D"
    
    def _calculate_ai_grade(self, optimization_rate: float, health: float) -> str:
        """Calculate AI performance grade"""
        score = (optimization_rate + health * 100) / 2
        
        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 55:
            return "Fair"
        else:
            return "Needs Improvement"

# Create singleton instance
report_service = ReportService()