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
from app.models.emergency_veh import EmergencyVehicleLog, EmergencySchedule, GreenWaveSchedule

report_bp = Blueprint('report', __name__)


# def parse_date_range(date_start, date_end):
#     """Parse date range with proper time boundaries"""
#     if date_start and date_end:
#         start = datetime.strptime(date_start, '%Y-%m-%d')
#         end = datetime.strptime(date_end, '%Y-%m-%d')
        
#         # Set end to end of day to capture all records
#         end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
#     else:
#         end = datetime.now()
#         start = end - timedelta(days=30)
    
#     return start, end


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
        emergency_scenarios = db.session.query(EmergencyVehicleLog.scenario).distinct().all()
        pattern_scenarios = db.session.query(TrafficPattern.scenario).distinct().all()
        
        # Combine all scenarios
        all_scenarios = set()
        for (scenario,) in tl_scenarios:
            if scenario:
                all_scenarios.add(scenario)
        for (scenario,) in emergency_scenarios:
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
        
        # Query emergency logs
        emergency_logs = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario,
            EmergencyVehicleLog.detected_at >= start_date,
            EmergencyVehicleLog.detected_at <= end_date
        ).all()
        
        if not logs:
            return jsonify({
                "success": True,
                "data": {
                    "total_vehicle_count": 0,
                    "average_speed": "0 mph",
                    "peak_hours": "N/A",
                    "congestion_level": "Low",
                    "emergency_count": len(emergency_logs),
                    "trend": {
                        "vehicle_count": 0,
                        "speed": 0,
                        "congestion": 0,
                        "emergency": 0
                    }
                }
            })
        
        # Calculate metrics
        total_vehicles = sum(log.vehicle_count for log in logs if log.vehicle_count)
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
        
        prev_emergency = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario,
            EmergencyVehicleLog.detected_at >= prev_start,
            EmergencyVehicleLog.detected_at < start_date
        ).count()
        
        trend = {"vehicle_count": 0, "speed": 0, "congestion": 0, "emergency": 0}
        if prev_logs:
            prev_vehicles = sum(log.vehicle_count for log in prev_logs if log.vehicle_count)
            prev_efficiency = sum(log.efficiency_score for log in prev_logs if log.efficiency_score) / len(prev_logs)
            prev_speed = 38.5 + (prev_efficiency - 50) * 0.1
            
            trend["vehicle_count"] = round(((total_vehicles - prev_vehicles) / prev_vehicles * 100), 1) if prev_vehicles else 0
            trend["speed"] = round(((avg_speed - prev_speed) / prev_speed * 100), 1) if prev_speed else 0
            trend["congestion"] = round(((avg_efficiency - prev_efficiency) / prev_efficiency * 100), 1) if prev_efficiency else 0
            trend["emergency"] = round(((len(emergency_logs) - prev_emergency) / prev_emergency * 100), 1) if prev_emergency else 0
        
        return jsonify({
            "success": True,
            "data": {
                "total_vehicle_count": total_vehicles,
                "average_speed": f"{avg_speed} mph",
                "peak_hours": peak_hours_str,
                "congestion_level": congestion_level,
                "congestion_percentage": round(avg_efficiency, 1),
                "emergency_count": len(emergency_logs),
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
    """Get vehicle type distribution"""
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
        
        total_vehicles = sum(log.vehicle_count for log in logs if log.vehicle_count)
        
        distribution = {
            "Cars": round(total_vehicles * 0.68),
            "Trucks": round(total_vehicles * 0.15),
            "Buses": round(total_vehicles * 0.12),
            "Motorcycles": round(total_vehicles * 0.05)
        }
        
        return jsonify({
            "success": True,
            "data": distribution
        })
        
    except Exception as e:
        print(f"Error in vehicle distribution: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/api/reports/emergency-activity', methods=['GET'])
def get_emergency_activity():
    """Get emergency vehicle activity over time"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        print(f"🚨 Fetching emergency activity for scenario: {scenario}, dates: {date_start} to {date_end}")
        
        start_date, end_date = parse_date_range(date_start, date_end)
        
        # Query emergency logs
        logs = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario,
            EmergencyVehicleLog.detected_at >= start_date,
            EmergencyVehicleLog.detected_at <= end_date
        ).all()
        
        print(f"✅ Found {len(logs)} emergency logs in date range")
        
        # Group by hour and type
        time_data = {}
        
        for log in logs:
            # Group by hour of day
            time_key = log.detected_at.strftime('%H:00')
            
            if time_key not in time_data:
                time_data[time_key] = {'ambulance': 0, 'fire_truck': 0, 'police': 0}
            
            # Classify vehicle type from original_type field
            vtype = (log.original_type or '').lower()
            if 'ambulance' in vtype or 'emergency' in vtype:
                time_data[time_key]['ambulance'] += 1
            elif 'fire' in vtype:
                time_data[time_key]['fire_truck'] += 1
            elif 'police' in vtype:
                time_data[time_key]['police'] += 1
        
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
        
        # Parse date range - this gives us datetime objects for filtering created_at
        start_date, end_date = parse_date_range(date_start, date_end)
        # Extend end_date to include the full day
        end_date = end_date.replace(hour=23, minute=59, second=59)
        
        print(f"📅 Parsed date range: {start_date} to {end_date}")
        
        # Query patterns - FIXED: Filter by created_at (when pattern was created)
        # NOT by interval_start (which is simulation time in seconds: 0, 500, 1000, etc.)
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
        
        # Format results
        pattern_data = []
        for pattern in patterns:
            # FIXED: Handle both float/int (simulation time) and datetime objects
            interval_start = pattern.interval_start
            interval_end = pattern.interval_end
            
            # Format interval display based on type
            if isinstance(interval_start, (int, float)):
                # Simulation time in seconds (0, 500, 1000, etc.)
                interval_start_display = f"{int(interval_start)}s"
                interval_end_display = f"{int(interval_end)}s"
                interval_range = f"Sim Time: {int(interval_start)}-{int(interval_end)}s"
            else:
                # Datetime object (legacy format)
                try:
                    interval_start_display = interval_start.strftime('%b %d, %H:%M') if interval_start else "N/A"
                    interval_end_display = interval_end.strftime('%b %d, %H:%M') if interval_end else "N/A"
                    interval_range = f"{interval_start_display} - {interval_end_display}"
                except:
                    interval_start_display = "N/A"
                    interval_end_display = "N/A"
                    interval_range = "N/A"
            
            # Convert confidence and success rate to percentages
            confidence = round((pattern.confidence_score or 0) * 100, 1)
            success_rate = round((pattern.action_success_rate or 0.5) * 100, 1)
            
            # Get metrics safely
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
    
    # Ensure end_date is not before start_date
    if end_date < start_date:
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start_date, end_date


@report_bp.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """Generate downloadable report (PDF/Excel/CSV)"""
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
        
        # Collect report data
        report_data = _collect_report_data(scenario, start, end, metrics)
        
        # Generate file based on format
        if format_type == 'PDF':
            file_buffer = _generate_pdf_report(report_data, template, scenario, start, end)
            mimetype = 'application/pdf'
            filename = f'traffic_report_{scenario}_{date_start}.pdf'
            
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
            
            # Add traffic data
            if 'traffic_volume' in report_data:
                writer.writerow(['Traffic Volume'])
                writer.writerow(['Total Vehicles', report_data['traffic_volume']['total']])
                writer.writerow(['Average Daily', round(report_data['traffic_volume']['average_daily'], 1)])
                writer.writerow([])
            
            if 'average_speed' in report_data:
                writer.writerow(['Average Speed', f"{report_data['average_speed']} mph"])
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
    """Collect all data needed for report"""
    data = {}
    
    # Traffic volume
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
        
        # Congestion
        data['congestion'] = round(avg_efficiency, 1) if efficiencies else 0
    
    # Emergency vehicles
    emergency_logs = EmergencyVehicleLog.query.filter(
        EmergencyVehicleLog.scenario == scenario,
        EmergencyVehicleLog.detected_at >= start_date,
        EmergencyVehicleLog.detected_at <= end_date
    ).all()
    
    data['emergency'] = {
        'total': len(emergency_logs),
        'by_type': {
            'ambulance': len([l for l in emergency_logs if 'ambulance' in (l.original_type or '').lower() or 'emergency' in (l.original_type or '').lower()]),
            'fire_truck': len([l for l in emergency_logs if 'fire' in (l.original_type or '').lower()]),
            'police': len([l for l in emergency_logs if 'police' in (l.original_type or '').lower()])
        }
    }
    
    # Traffic patterns
    patterns = TrafficPattern.query.filter(
        TrafficPattern.scenario == scenario,
        TrafficPattern.interval_start >= start_date,
        TrafficPattern.interval_start <= end_date
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
    """Generate PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
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
    
    # Title
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
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Traffic Volume Section
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
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(volume_table)
        story.append(Spacer(1, 0.25*inch))
    
    # Speed & Congestion Section
    if 'average_speed' in report_data or 'congestion' in report_data:
        story.append(Paragraph("Performance Metrics", heading_style))
        
        perf_data = [['Metric', 'Value']]
        
        if 'average_speed' in report_data:
            perf_data.append(['Average Speed', f"{report_data['average_speed']} mph"])
        
        if 'congestion' in report_data:
            perf_data.append(['Congestion Level', f"{report_data['congestion']}%"])
        
        perf_table = Table(perf_data, colWidths=[3*inch, 3*inch])
        perf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(perf_table)
        story.append(Spacer(1, 0.25*inch))
    
    # Emergency Section
    if 'emergency' in report_data:
        story.append(Paragraph("Emergency Vehicle Activity", heading_style))
        
        emergency_data = [
            ['Type', 'Count'],
            ['Total Emergency Responses', str(report_data['emergency']['total'])],
            ['Ambulance', str(report_data['emergency']['by_type']['ambulance'])],
            ['Fire Truck', str(report_data['emergency']['by_type']['fire_truck'])],
            ['Police', str(report_data['emergency']['by_type']['police'])]
        ]
        
        emergency_table = Table(emergency_data, colWidths=[3*inch, 3*inch])
        emergency_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef2f2')])
        ]))
        story.append(emergency_table)
        story.append(Spacer(1, 0.25*inch))
    
    # Traffic Patterns Section
    if 'patterns' in report_data and report_data['patterns']:
        story.append(Paragraph("Traffic Patterns Detected", heading_style))
        
        pattern_data = [['Pattern Type', 'Traffic Light', 'Confidence', 'Best Action', 'Success Rate']]
        
        for pattern in report_data['patterns'][:10]:  # Limit to 10 patterns
            pattern_data.append([
                pattern['type'],
                pattern['traffic_light'],
                f"{pattern['confidence']}%",
                pattern.get('best_action', 'N/A'),
                f"{pattern.get('success_rate', 0)}%"
            ])
        
        pattern_table = Table(pattern_data, colWidths=[1.8*inch, 1.5*inch, 1*inch, 1.2*inch, 1*inch])
        pattern_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#faf5ff')])
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
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer