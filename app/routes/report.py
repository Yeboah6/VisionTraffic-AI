from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.extensions import db
from sqlalchemy import func, and_, or_
import io
import json
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import xlsxwriter

# models
from app.models.user import User
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig, TrafficPattern
from app.models.ai import AIDecisionLog, AIPerformance, AIQTable

report_bp = Blueprint('report', __name__)

@report_bp.route('/report')
@login_required
def report():
    now = datetime.now()
    user = current_user
    return render_template('report/report.html',
                           user=user,
                           current_date=now.strftime("%B %d, %Y"), 
                           current_time=now.strftime("%I:%M %p")
                           )


@report_bp.route('/api/reports/scenarios', methods=['GET'])
def get_scenarios():
    """Get all available scenarios from database"""
    try:
        # Get unique scenarios from all relevant tables
        tl_scenarios = db.session.query(TrafficLightLog.scenario).distinct().all()
        pattern_scenarios = db.session.query(TrafficPattern.scenario).distinct().all()
        
        # Combine all scenarios
        all_scenarios = set()
        for (scenario,) in tl_scenarios:
            if scenario:
                all_scenarios.add(scenario)
        for (scenario,) in pattern_scenarios:
            if scenario:
                all_scenarios.add(scenario)
        
        scenarios_list = sorted(list(all_scenarios))
        
        # Format for display
        formatted_scenarios = []
        for scenario in scenarios_list:
            formatted_scenarios.append({
                'value': scenario,
                'label': scenario.replace('_', ' ').title()
            })
        
        return jsonify({
            "success": True,
            "scenarios": formatted_scenarios
        })
        
    except Exception as e:
        print(f"Error fetching scenarios: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "scenarios": [
                {"value": "accra", "label": "Accra Network"}
            ]
        }), 200


@report_bp.route('/api/reports/traffic-overview', methods=['GET'])
def get_traffic_overview():
    """Get traffic overview metrics for report"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        print(f"📊 Traffic overview: {start_date} to {end_date}")
        
        # Query traffic logs
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        if not logs:
            return jsonify({
                "success": True,
                "data": {
                    "total_vehicle_count": 0,
                    "average_speed": "0 mph",
                    "peak_hours": "N/A",
                    "congestion_level": "Low",
                    "emergency_count": 0,
                    "trend": {
                        "vehicle_count": 0,
                        "speed": 0,
                        "congestion": 0,
                        "emergency": 0
                    }
                }
            })
        
        # Calculate metrics using NEW vehicle type fields
        total_vehicles = sum(log.vehicle_count for log in logs if log.vehicle_count)
        
        # NEW: Calculate emergency count from emergency_count field
        emergency_count = sum(log.emergency_count or 0 for log in logs)
        
        avg_efficiency = sum(log.efficiency_score for log in logs if log.efficiency_score) / len(logs)
        avg_speed = round(38.5 + (avg_efficiency - 50) * 0.1, 1)
        
        # Peak hours detection
        hourly_counts = {}
        for log in logs:
            hour = log.created_at.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + (log.vehicle_count or 0)
        
        peak_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        peak_times = [f"{h}:00" for h, _ in peak_hours]
        peak_hours_str = ", ".join(peak_times) if peak_times else "N/A"
        
        # Congestion level
        if avg_efficiency >= 70:
            congestion_level = "High"
        elif avg_efficiency >= 40:
            congestion_level = "Medium"
        else:
            congestion_level = "Low"
        
        # Calculate trends
        period_length = end_date - start_date
        prev_start = start_date - period_length
        
        prev_logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= prev_start,
            TrafficLightLog.created_at < start_date
        ).all()
        
        trend = {"vehicle_count": 0, "speed": 0, "congestion": 0, "emergency": 0}
        if prev_logs:
            prev_vehicles = sum(log.vehicle_count for log in prev_logs if log.vehicle_count)
            prev_emergency = sum(log.emergency_count or 0 for log in prev_logs)
            prev_efficiency = sum(log.efficiency_score for log in prev_logs if log.efficiency_score) / len(prev_logs)
            prev_speed = 38.5 + (prev_efficiency - 50) * 0.1
            
            trend["vehicle_count"] = round(((total_vehicles - prev_vehicles) / prev_vehicles * 100), 1) if prev_vehicles else 0
            trend["speed"] = round(((avg_speed - prev_speed) / prev_speed * 100), 1) if prev_speed else 0
            trend["congestion"] = round(((avg_efficiency - prev_efficiency) / prev_efficiency * 100), 1) if prev_efficiency else 0
            trend["emergency"] = round(((emergency_count - prev_emergency) / prev_emergency * 100), 1) if prev_emergency else 0
        
        return jsonify({
            "success": True,
            "data": {
                "total_vehicle_count": total_vehicles,
                "average_speed": f"{avg_speed} mph",
                "peak_hours": peak_hours_str,
                "congestion_level": congestion_level,
                "congestion_percentage": round(avg_efficiency, 1),
                "emergency_count": emergency_count,
                "trend": trend
            }
        })
        
    except Exception as e:
        print(f"Error in traffic overview: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/traffic-volume-trends', methods=['GET'])
def get_traffic_volume_trends():
    """Get traffic volume trends over time"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        period = request.args.get('period', 'daily')
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).order_by(TrafficLightLog.created_at).all()
        
        # Group by time period
        time_data = {}
        for log in logs:
            if period == 'hourly':
                time_key = log.created_at.strftime('%H:00')
            elif period == 'daily':
                time_key = log.created_at.strftime('%b %d')
            else:
                time_key = log.created_at.strftime('Week %W')
            
            if time_key not in time_data:
                time_data[time_key] = {'cars': 0, 'trucks': 0, 'buses': 0}
            
            total = log.vehicle_count or 0
            time_data[time_key]['cars'] += int(total * 0.68)
            time_data[time_key]['trucks'] += int(total * 0.15)
            time_data[time_key]['buses'] += int(total * 0.12)
        
        labels = sorted(time_data.keys())
        cars = [time_data[label]['cars'] for label in labels]
        trucks = [time_data[label]['trucks'] for label in labels]
        buses = [time_data[label]['buses'] for label in labels]
        
        return jsonify({
            "success": True,
            "data": {
                "labels": labels,
                "datasets": {
                    "cars": cars,
                    "trucks": trucks,
                    "buses": buses
                }
            }
        })
        
    except Exception as e:
        print(f"Error in traffic volume trends: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/congestion-analysis', methods=['GET'])
def get_congestion_analysis():
    """Get congestion heatmap data"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        # Build heatmap
        heatmap_data = []
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hours = [f'{i}{"a" if i < 12 else "p"}' for i in ([12] + list(range(1, 12))) * 2]
        
        congestion_matrix = [[0 for _ in range(24)] for _ in range(7)]
        count_matrix = [[0 for _ in range(24)] for _ in range(7)]
        
        for log in logs:
            day = log.created_at.weekday()
            hour = log.created_at.hour
            if log.efficiency_score:
                congestion_matrix[day][hour] += log.efficiency_score
                count_matrix[day][hour] += 1
        
        for day in range(7):
            for hour in range(24):
                if count_matrix[day][hour] > 0:
                    avg_congestion = congestion_matrix[day][hour] / count_matrix[day][hour]
                    heatmap_data.append([hour, day, round(avg_congestion, 1)])
                else:
                    heatmap_data.append([hour, day, 0])
        
        return jsonify({
            "success": True,
            "data": {
                "hours": hours,
                "days": days,
                "heatmap": heatmap_data
            }
        })
        
    except Exception as e:
        print(f"Error in congestion analysis: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/vehicle-distribution', methods=['GET'])
def get_vehicle_distribution():
    """Get vehicle type distribution with actual data from database"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        # Aggregate vehicle types from NEW fields in logs
        total_passenger = sum(log.passenger_count or 0 for log in logs)
        total_truck = sum(log.truck_count or 0 for log in logs)
        total_bus = sum(log.bus_count or 0 for log in logs)
        total_motorcycle = sum(log.motorcycle_count or 0 for log in logs)
        total_bicycle = sum(log.bicycle_count or 0 for log in logs)
        total_emergency = sum(log.emergency_count or 0 for log in logs)
        
        total_vehicles = (total_passenger + total_truck + total_bus + 
                         total_motorcycle + total_bicycle + total_emergency)
        
        # If no data collected yet, use default distribution
        if total_vehicles == 0:
            # Fallback to estimated distribution
            total_vehicles = sum(log.vehicle_count for log in logs if log.vehicle_count)
            distribution = {
                "Passenger Cars": round(total_vehicles * 0.68),
                "Trucks": round(total_vehicles * 0.15),
                "Buses": round(total_vehicles * 0.12),
                "Motorcycles": round(total_vehicles * 0.05),
                "Bicycles": 0,
                "Emergency": 0
            }
            data_source = "estimated"
        else:
            # Use actual collected data
            distribution = {
                "Passenger Cars": total_passenger,
                "Trucks": total_truck,
                "Buses": total_bus,
                "Motorcycles": total_motorcycle,
                "Bicycles": total_bicycle,
                "Emergency": total_emergency
            }
            data_source = "actual"
        
        # Calculate percentages
        distribution_with_percentages = {}
        for vehicle_type, count in distribution.items():
            percentage = round((count / total_vehicles * 100), 1) if total_vehicles > 0 else 0
            distribution_with_percentages[vehicle_type] = {
                'count': count,
                'percentage': percentage
            }
        
        return jsonify({
            "success": True,
            "data": distribution,
            "detailed": distribution_with_percentages,
            "total_vehicles": total_vehicles,
            "data_source": data_source
        })
        
    except Exception as e:
        print(f"Error in vehicle distribution: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/vehicle-type-distribution', methods=['GET'])
def get_vehicle_type_distribution():
    """NEW: Get detailed vehicle type distribution for visualization"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        if not logs:
            return jsonify({
                "success": True,
                "data": {
                    "passenger": 0,
                    "truck": 0,
                    "bus": 0,
                    "motorcycle": 0,
                    "bicycle": 0,
                    "emergency": 0
                },
                "message": "No data available for selected period"
            })
        
        # Aggregate vehicle types
        vehicle_types = {
            "passenger": sum(log.passenger_count or 0 for log in logs),
            "truck": sum(log.truck_count or 0 for log in logs),
            "bus": sum(log.bus_count or 0 for log in logs),
            "motorcycle": sum(log.motorcycle_count or 0 for log in logs),
            "bicycle": sum(log.bicycle_count or 0 for log in logs),
            "emergency": sum(log.emergency_count or 0 for log in logs)
        }
        
        total = sum(vehicle_types.values())
        
        # If no type data but we have vehicle counts, use estimation
        if total == 0:
            total_vehicles = sum(log.vehicle_count for log in logs if log.vehicle_count)
            vehicle_types = {
                "passenger": round(total_vehicles * 0.68),
                "truck": round(total_vehicles * 0.15),
                "bus": round(total_vehicles * 0.12),
                "motorcycle": round(total_vehicles * 0.05),
                "bicycle": 0,
                "emergency": 0
            }
            data_source = "estimated"
        else:
            data_source = "actual"
        
        return jsonify({
            "success": True,
            "data": vehicle_types,
            "total_vehicles": sum(vehicle_types.values()),
            "data_source": data_source,
            "period": {
                "start": start_date.strftime('%Y-%m-%d'),
                "end": end_date.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        print(f"Error in vehicle type distribution: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/vehicle-type-trends', methods=['GET'])
def get_vehicle_type_trends():
    """Get vehicle type trends over time"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        period = request.args.get('period', 'hourly')
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).order_by(TrafficLightLog.created_at).all()
        
        # Group by time period
        time_data = {}
        
        for log in logs:
            if period == 'hourly':
                time_key = log.created_at.strftime('%H:00')
            elif period == 'daily':
                time_key = log.created_at.strftime('%b %d')
            else:
                time_key = log.created_at.strftime('Week %W')
            
            if time_key not in time_data:
                time_data[time_key] = {
                    'passenger': 0,
                    'truck': 0,
                    'bus': 0,
                    'motorcycle': 0,
                    'bicycle': 0,
                    'emergency': 0
                }
            
            time_data[time_key]['passenger'] += log.passenger_count or 0
            time_data[time_key]['truck'] += log.truck_count or 0
            time_data[time_key]['bus'] += log.bus_count or 0
            time_data[time_key]['motorcycle'] += log.motorcycle_count or 0
            time_data[time_key]['bicycle'] += log.bicycle_count or 0
            time_data[time_key]['emergency'] += log.emergency_count or 0
        
        labels = sorted(time_data.keys())
        
        return jsonify({
            "success": True,
            "data": {
                "labels": labels,
                "datasets": {
                    "passenger": [time_data[label]['passenger'] for label in labels],
                    "truck": [time_data[label]['truck'] for label in labels],
                    "bus": [time_data[label]['bus'] for label in labels],
                    "motorcycle": [time_data[label]['motorcycle'] for label in labels],
                    "bicycle": [time_data[label]['bicycle'] for label in labels],
                    "emergency": [time_data[label]['emergency'] for label in labels]
                }
            }
        })
        
    except Exception as e:
        print(f"Error in vehicle type trends: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/emergency-activity', methods=['GET'])
def get_emergency_activity():
    """Get emergency vehicle activity over time from TrafficLightLog"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        print(f"🚨 Fetching emergency activity for scenario: {scenario}, dates: {date_start} to {date_end}")
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        # Query traffic logs and aggregate emergency counts
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        print(f"✅ Found {len(logs)} traffic logs in date range")
        
        # Group by hour
        time_data = {}
        
        for log in logs:
            time_key = log.created_at.strftime('%H:00')
            
            if time_key not in time_data:
                time_data[time_key] = {'ambulance': 0, 'fire_truck': 0, 'police': 0}
            
            # Distribute emergency count (simplified - in real scenario, you'd track types separately)
            emergency_total = log.emergency_count or 0
            if emergency_total > 0:
                # Simple distribution (you can make this more sophisticated)
                time_data[time_key]['ambulance'] += emergency_total // 3
                time_data[time_key]['fire_truck'] += emergency_total // 3
                time_data[time_key]['police'] += emergency_total - (2 * (emergency_total // 3))
        
        if not time_data:
            print("⚠️ No emergency data, returning empty")
            return jsonify({
                "success": True,
                "data": {
                    "labels": ['No Data'],
                    "datasets": {
                        "ambulance": [0],
                        "fire_truck": [0],
                        "police": [0]
                    }
                },
                "message": f"No emergency activity found ({start_date.strftime('%b %d')} to {end_date.strftime('%b %d')})"
            })
        
        # Sort by time
        labels = sorted(time_data.keys())
        ambulance = [time_data[label]['ambulance'] for label in labels]
        fire_truck = [time_data[label]['fire_truck'] for label in labels]
        police = [time_data[label]['police'] for label in labels]
        
        total = sum(ambulance) + sum(fire_truck) + sum(police)
        print(f"📊 Emergency totals - Ambulance: {sum(ambulance)}, Fire: {sum(fire_truck)}, Police: {sum(police)}")
        
        return jsonify({
            "success": True,
            "data": {
                "labels": labels,
                "datasets": {
                    "ambulance": ambulance,
                    "fire_truck": fire_truck,
                    "police": police
                }
            },
            "total_emergencies": total
        })
        
    except Exception as e:
        print(f"❌ Error fetching emergency activity: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "data": {
                "labels": [],
                "datasets": {
                    "ambulance": [],
                    "fire_truck": [],
                    "police": []
                }
            }
        }), 500


@report_bp.route('/api/reports/traffic-patterns', methods=['GET'])
def get_traffic_patterns():
    """Get detected traffic patterns from database"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        print(f"📊 Fetching patterns for scenario: {scenario}, dates: {date_start} to {date_end}")
        
        start_date, end_date = parse_date_range(date_start, date_end)
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
        print(f"📅 Parsed date range: {start_date} to {end_date}")
        
        patterns = TrafficPattern.query.filter(
            TrafficPattern.scenario == scenario,
            TrafficPattern.created_at >= start_date,
            TrafficPattern.created_at <= end_date
        ).order_by(
            TrafficPattern.confidence_score.desc(),
            TrafficPattern.updated_at.desc()
        ).limit(20).all()
        
        print(f"✅ Found {len(patterns)} traffic patterns in date range")
        
        if not patterns:
            return jsonify({
                "success": True,
                "data": [],
                "message": f"No patterns found between {start_date.strftime('%b %d')} and {end_date.strftime('%b %d')}"
            })
        
        pattern_data = []
        for pattern in patterns:
            interval_start = pattern.interval_start
            interval_end = pattern.interval_end
            
            if isinstance(interval_start, (int, float)):
                interval_start_display = f"{int(interval_start)}s"
                interval_end_display = f"{int(interval_end)}s"
                interval_range = f"Sim Time: {int(interval_start)}-{int(interval_end)}s"
            else:
                try:
                    interval_start_display = interval_start.strftime('%b %d, %H:%M') if interval_start else "N/A"
                    interval_end_display = interval_end.strftime('%b %d, %H:%M') if interval_end else "N/A"
                    interval_range = f"{interval_start_display} - {interval_end_display}"
                except:
                    interval_start_display = "N/A"
                    interval_end_display = "N/A"
                    interval_range = "N/A"
            
            confidence = round((pattern.confidence_score or 0) * 100, 1)
            success_rate = round((pattern.action_success_rate or 0.5) * 100, 1)
            metrics = pattern.pattern_metrics or {}
            
            pattern_data.append({
                "id": pattern.id,
                "traffic_light_id": pattern.traffic_light_id,
                "pattern_type": pattern.pattern_type or "UNKNOWN",
                "confidence_score": confidence,
                "interval_start": interval_start_display,
                "interval_end": interval_end_display,
                "interval_range": interval_range,
                "simulation_interval": f"{int(interval_start)}-{int(interval_end)}" if isinstance(interval_start, (int, float)) else None,
                "recommendations": pattern.recommendations if pattern.recommendations else [],
                "best_action": pattern.best_action or "MAINTAIN",
                "action_success_rate": success_rate,
                "sample_size": pattern.sample_size or 0,
                "pattern_metrics": metrics,
                "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
                "updated_at": pattern.updated_at.isoformat() if pattern.updated_at else None
            })
        
        print(f"📊 Returning {len(pattern_data)} formatted patterns")
        
        return jsonify({
            "success": True,
            "data": pattern_data,
            "message": f"Found {len(pattern_data)} patterns",
            "total_patterns": len(pattern_data),
            "scenario": scenario,
            "date_range": {
                "start": start_date.strftime('%Y-%m-%d'),
                "end": end_date.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        print(f"❌ Error fetching traffic patterns: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "data": [],
            "message": "Failed to fetch traffic patterns"
        }), 500


def parse_date_range(date_start, date_end):
    """Parse and validate date range"""
    from datetime import datetime, timedelta
    
    if date_start:
        try:
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        except ValueError:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if date_end:
        try:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
        except ValueError:
            end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if end_date < start_date:
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start_date, end_date


@report_bp.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """Generate downloadable report (PDF/Excel/CSV) with vehicle type data"""
    try:
        data = request.get_json()
        
        template = data.get('template', 'comprehensive')
        date_start = data.get('date_start')
        date_end = data.get('date_end')
        format_type = data.get('format', 'PDF')
        metrics = data.get('metrics', [])
        scenario = data.get('scenario', 'accra')
        
        if not date_start or not date_end:
            return jsonify({
                "success": False,
                "error": "Start and end dates are required"
            }), 400
        
        start, end = parse_date_range(date_start, date_end)
        
        # Collect report data (now includes vehicle types)
        report_data = _collect_report_data(scenario, start, end, metrics)
        
        # Generate file based on format
        if format_type == 'PDF':
            file_buffer = _generate_pdf_report(report_data, template, scenario, start, end)
            mimetype = 'application/pdf'
            filename = f'traffic_report_{scenario}_{date_start}.pdf'
            
            file_buffer.seek(0)
            
            return send_file(
                file_buffer,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename
            )
            
        elif format_type == 'CSV':
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(['Traffic Management Report'])
            writer.writerow([f'Scenario: {scenario}'])
            writer.writerow([f'Period: {start.strftime("%Y-%m-%d")} to {end.strftime("%Y-%m-%d")}'])
            writer.writerow([])
            
            # Traffic data
            if 'traffic_volume' in report_data:
                writer.writerow(['Traffic Volume'])
                writer.writerow(['Total Vehicles', report_data['traffic_volume']['total']])
                writer.writerow(['Average Daily', round(report_data['traffic_volume']['average_daily'], 1)])
                writer.writerow([])
            
            # NEW: Vehicle Type Distribution
            if 'vehicle_types' in report_data:
                writer.writerow(['Vehicle Type Distribution'])
                writer.writerow(['Type', 'Count', 'Percentage'])
                for vtype, data in report_data['vehicle_types'].items():
                    writer.writerow([vtype, data['count'], f"{data['percentage']}%"])
                writer.writerow([])
            
            if 'average_speed' in report_data:
                writer.writerow(['Average Speed', f"{report_data['average_speed']} mph"])
                writer.writerow([])
            
            # Emergency vehicles
            if 'emergency' in report_data:
                writer.writerow(['Emergency Vehicle Activity'])
                writer.writerow(['Total Emergencies', report_data['emergency']['total']])
                writer.writerow([])
            
            if 'patterns' in report_data and report_data['patterns']:
                writer.writerow(['Traffic Patterns'])
                writer.writerow(['Pattern Type', 'Traffic Light', 'Confidence', 'Best Action'])
                for pattern in report_data['patterns']:
                    writer.writerow([
                        pattern['type'],
                        pattern['traffic_light'],
                        f"{pattern['confidence']}%",
                        pattern.get('best_action', 'N/A')
                    ])
            
            output = io.BytesIO()
            output.write(buffer.getvalue().encode('utf-8'))
            output.seek(0)
            
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'traffic_report_{scenario}_{date_start}.csv'
            )
        
        elif format_type == 'EXCEL':
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Traffic Report')
            
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#3b82f6',
                'font_color': 'white',
                'border': 1
            })
            
            row = 0
            worksheet.write(row, 0, 'Traffic Management Report', header_format)
            row += 2
            
            worksheet.write(row, 0, 'Scenario:', header_format)
            worksheet.write(row, 1, scenario)
            row += 1
            
            worksheet.write(row, 0, 'Period:', header_format)
            worksheet.write(row, 1, f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
            row += 2
            
            if 'traffic_volume' in report_data:
                worksheet.write(row, 0, 'Total Vehicles:', header_format)
                worksheet.write(row, 1, report_data['traffic_volume']['total'])
                row += 1
            
            # NEW: Vehicle Types
            if 'vehicle_types' in report_data:
                row += 1
                worksheet.write(row, 0, 'Vehicle Type Distribution', header_format)
                row += 1
                worksheet.write(row, 0, 'Type', header_format)
                worksheet.write(row, 1, 'Count', header_format)
                worksheet.write(row, 2, 'Percentage', header_format)
                row += 1
                
                for vtype, data in report_data['vehicle_types'].items():
                    worksheet.write(row, 0, vtype)
                    worksheet.write(row, 1, data['count'])
                    worksheet.write(row, 2, f"{data['percentage']}%")
                    row += 1
            
            workbook.close()
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'traffic_report_{scenario}_{date_start}.xlsx'
            )
        
        return jsonify({
            "success": False,
            "error": f"Format {format_type} not supported"
        }), 400
        
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def _collect_report_data(scenario, start_date, end_date, metrics):
    """Collect all data needed for report including vehicle types"""
    data = {}
    
    logs = TrafficLightLog.query.filter(
        TrafficLightLog.scenario == scenario,
        TrafficLightLog.created_at >= start_date,
        TrafficLightLog.created_at <= end_date
    ).all()
    
    if logs:
        data['traffic_volume'] = {
            'total': sum(log.vehicle_count for log in logs if log.vehicle_count),
            'average_daily': sum(log.vehicle_count for log in logs if log.vehicle_count) / max(1, (end_date - start_date).days)
        }
        
        # Average speed
        efficiencies = [log.efficiency_score for log in logs if log.efficiency_score]
        if efficiencies:
            avg_efficiency = sum(efficiencies) / len(efficiencies)
            data['average_speed'] = round(38.5 + (avg_efficiency - 50) * 0.1, 1)
            data['congestion'] = round(avg_efficiency, 1)
        
        # NEW: Vehicle Type Distribution
        total_passenger = sum(log.passenger_count or 0 for log in logs)
        total_truck = sum(log.truck_count or 0 for log in logs)
        total_bus = sum(log.bus_count or 0 for log in logs)
        total_motorcycle = sum(log.motorcycle_count or 0 for log in logs)
        total_bicycle = sum(log.bicycle_count or 0 for log in logs)
        total_emergency = sum(log.emergency_count or 0 for log in logs)
        
        total_by_type = total_passenger + total_truck + total_bus + total_motorcycle + total_bicycle + total_emergency
        
        if total_by_type > 0:
            data['vehicle_types'] = {
                'Passenger Cars': {
                    'count': total_passenger,
                    'percentage': round((total_passenger / total_by_type) * 100, 1)
                },
                'Trucks': {
                    'count': total_truck,
                    'percentage': round((total_truck / total_by_type) * 100, 1)
                },
                'Buses': {
                    'count': total_bus,
                    'percentage': round((total_bus / total_by_type) * 100, 1)
                },
                'Motorcycles': {
                    'count': total_motorcycle,
                    'percentage': round((total_motorcycle / total_by_type) * 100, 1)
                },
                'Bicycles': {
                    'count': total_bicycle,
                    'percentage': round((total_bicycle / total_by_type) * 100, 1)
                },
                'Emergency': {
                    'count': total_emergency,
                    'percentage': round((total_emergency / total_by_type) * 100, 1)
                }
            }
    
    # Emergency vehicles total
    data['emergency'] = {
        'total': sum(log.emergency_count or 0 for log in logs)
    }
    
    # Traffic patterns
    patterns = TrafficPattern.query.filter(
        TrafficPattern.scenario == scenario,
        TrafficPattern.created_at >= start_date,
        TrafficPattern.created_at <= end_date
    ).order_by(TrafficPattern.confidence_score.desc()).limit(10).all()
    
    data['patterns'] = [{
        'type': p.pattern_type,
        'confidence': round((p.confidence_score or 0) * 100, 1),
        'traffic_light': p.traffic_light_id,
        'best_action': p.best_action,
        'success_rate': round((p.action_success_rate or 0.5) * 100, 1)
    } for p in patterns]
    
    return data


def _generate_pdf_report(report_data, template, scenario, start_date, end_date):
    """Generate PDF report with vehicle type data"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#334155'),
        spaceBefore=15,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("Traffic Management Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Report Info
    info_data = [
        ['Scenario:', scenario.upper()],
        ['Period:', f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"],
        ['Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
        ['Template:', template.replace('_', ' ').title()]
    ]
    
    info_table = Table(info_data, colWidths=[1.5*inch, 4.5*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Traffic Volume
    if 'traffic_volume' in report_data:
        story.append(Paragraph("Traffic Volume Summary", heading_style))
        
        volume_data = [
            ['Metric', 'Value'],
            ['Total Vehicles', f"{report_data['traffic_volume']['total']:,}"],
            ['Average Daily', f"{report_data['traffic_volume']['average_daily']:.1f}"]
        ]
        
        volume_table = Table(volume_data, colWidths=[3*inch, 3*inch])
        volume_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(volume_table)
        story.append(Spacer(1, 0.25*inch))
    
    # NEW: Vehicle Type Distribution
    if 'vehicle_types' in report_data:
        story.append(Paragraph("Vehicle Type Distribution", heading_style))
        
        vtype_data = [['Vehicle Type', 'Count', 'Percentage']]
        for vtype, data in report_data['vehicle_types'].items():
            vtype_data.append([vtype, f"{data['count']:,}", f"{data['percentage']}%"])
        
        vtype_table = Table(vtype_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        vtype_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')])
        ]))
        story.append(vtype_table)
        story.append(Spacer(1, 0.25*inch))
    
    # Performance Metrics
    if 'average_speed' in report_data or 'congestion' in report_data:
        story.append(Paragraph("Performance Metrics", heading_style))
        
        perf_data = [['Metric', 'Value']]
        if 'average_speed' in report_data:
            perf_data.append(['Average Speed', f"{report_data['average_speed']} mph"])
        if 'congestion' in report_data:
            perf_data.append(['Congestion Level', f"{report_data['congestion']}%"])
        
        perf_table = Table(perf_data, colWidths=[3*inch, 3*inch])
        perf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f97316')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ]))
        story.append(perf_table)
        story.append(Spacer(1, 0.25*inch))
    
    # Emergency Activity
    if 'emergency' in report_data:
        story.append(Paragraph("Emergency Vehicle Activity", heading_style))
        
        emergency_data = [
            ['Metric', 'Value'],
            ['Total Emergency Responses', str(report_data['emergency']['total'])]
        ]
        
        emergency_table = Table(emergency_data, colWidths=[3*inch, 3*inch])
        emergency_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ]))
        story.append(emergency_table)
        story.append(Spacer(1, 0.25*inch))
    
    # Traffic Patterns
    if 'patterns' in report_data and report_data['patterns']:
        story.append(Paragraph("Traffic Patterns Detected", heading_style))
        
        pattern_data = [['Pattern Type', 'Traffic Light', 'Confidence', 'Best Action']]
        for pattern in report_data['patterns'][:10]:
            pattern_data.append([
                pattern['type'],
                pattern['traffic_light'],
                f"{pattern['confidence']}%",
                pattern.get('best_action', 'N/A')
            ])
        
        pattern_table = Table(pattern_data, colWidths=[2*inch, 1.8*inch, 1.2*inch, 1.5*inch])
        pattern_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ]))
        story.append(pattern_table)
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    footer_text = f"Generated by Traffic Management System | {datetime.now().strftime('%Y')}"
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#94a3b8'),
        alignment=TA_CENTER
    )
    story.append(Paragraph(footer_text, footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer
