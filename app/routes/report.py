from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify
from flask_login import login_required,current_user
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


@report_bp.route('/report')
@login_required
def report():
    now = datetime.now()
    user = current_user
    return render_template('report/report.html',
                           user = user,
                           current_date = now.strftime("%B %d, %Y"), 
                           current_time = now.strftime("%I:%M %p")
                           )

@report_bp.route('/api/reports/scenarios', methods=['GET'])
def get_scenarios():
    """Get all available scenarios from database"""
    try:
        # Get unique scenarios from TrafficLightLog
        tl_scenarios = db.session.query(
            TrafficLightLog.scenario
        ).distinct().all()
        
        # Get unique scenarios from EmergencyVehicleLog
        emergency_scenarios = db.session.query(
            EmergencyVehicleLog.scenario
        ).distinct().all()
        
        # Get unique scenarios from TrafficPattern
        pattern_scenarios = db.session.query(
            TrafficPattern.scenario
        ).distinct().all()
        
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
                {"value": "accra", "label": "Accra Network"},
                {"value": "default", "label": "Default Scenario"}
            ]
        }), 200  # Return 200 with default scenarios

@report_bp.route('/api/reports/traffic-overview', methods=['GET'])
def get_traffic_overview():
    """Get traffic overview metrics for report"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        period = request.args.get('period', 'daily')
        
        # Calculate date range
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            if period == 'hourly':
                start_date = end_date - timedelta(hours=24)
            elif period == 'daily':
                start_date = end_date - timedelta(days=7)
            elif period == 'weekly':
                start_date = end_date - timedelta(weeks=4)
            else:
                start_date = end_date - timedelta(days=7)
        
        # Query traffic logs
        query = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        )
        
        logs = query.all()
        
        # Query emergency logs
        emergency_query = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario,
            EmergencyVehicleLog.detected_at >= start_date,
            EmergencyVehicleLog.detected_at <= end_date
        )
        emergency_logs = emergency_query.all()
        
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
        total_vehicles = sum(log.vehicle_count for log in logs)
        avg_efficiency = sum(log.efficiency_score for log in logs) / len(logs)
        avg_speed = round(38.5 + (avg_efficiency - 50) * 0.1, 1)
        
        # Peak hours detection
        hourly_counts = {}
        for log in logs:
            hour = log.created_at.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + log.vehicle_count
        
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
            prev_vehicles = sum(log.vehicle_count for log in prev_logs)
            prev_efficiency = sum(log.efficiency_score for log in prev_logs) / len(prev_logs)
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
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
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
            
            total = log.vehicle_count
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
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        # Build heatmap
        heatmap_data = []
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hours = [f'{i}{"a" if i < 12 else "p"}' for i in [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] * 2]
        
        congestion_matrix = [[0 for _ in range(24)] for _ in range(7)]
        count_matrix = [[0 for _ in range(24)] for _ in range(7)]
        
        for log in logs:
            day = log.created_at.weekday()
            hour = log.created_at.hour
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
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        total_vehicles = sum(log.vehicle_count for log in logs)
        
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
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)  # Extended to 30 days
        
        # Query emergency logs
        logs_query = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario
        )
        
        # Apply date filter
        if hasattr(EmergencyVehicleLog, 'detected_at'):
            logs_query = logs_query.filter(
                EmergencyVehicleLog.detected_at >= start_date,
                EmergencyVehicleLog.detected_at <= end_date
            )
        
        logs = logs_query.all()
        
        print(f"✅ Found {len(logs)} emergency vehicle logs")
        
        if not logs:
            # Try without date filter
            all_logs = EmergencyVehicleLog.query.filter_by(scenario=scenario).limit(10).all()
            print(f"ℹ️  Total emergency logs for scenario without date filter: {len(all_logs)}")
            
            if all_logs:
                print("⚠️  Emergency logs exist but outside date range")
                logs = all_logs
        
        # Group by date and type
        time_data = {}
        
        for log in logs:
            if hasattr(log, 'detected_at') and log.detected_at:
                date_key = log.detected_at.strftime('%b %d')
            else:
                date_key = 'Unknown'
            
            if date_key not in time_data:
                time_data[date_key] = {'ambulance': 0, 'fire_truck': 0, 'police': 0, 'other': 0}
            
            # Classify vehicle type
            vtype = (log.vehicle_type or '').lower()
            if 'ambulance' in vtype or 'medic' in vtype:
                time_data[date_key]['ambulance'] += 1
            elif 'fire' in vtype:
                time_data[date_key]['fire_truck'] += 1
            elif 'police' in vtype or 'patrol' in vtype:
                time_data[date_key]['police'] += 1
            else:
                time_data[date_key]['other'] += 1
        
        # If no data, create dummy structure
        if not time_data:
            print("⚠️  No emergency data found, returning empty structure")
            # Generate date labels for the range
            date_labels = []
            current = start_date
            while current <= end_date:
                date_labels.append(current.strftime('%b %d'))
                current += timedelta(days=1)
            
            return jsonify({
                "success": True,
                "data": {
                    "labels": date_labels[:7],  # Limit to 7 days
                    "datasets": {
                        "ambulance": [0] * min(7, len(date_labels)),
                        "fire_truck": [0] * min(7, len(date_labels)),
                        "police": [0] * min(7, len(date_labels))
                    }
                },
                "message": "No emergency activity in selected period"
            })
        
        # Sort by date and create arrays
        labels = sorted(time_data.keys())
        ambulance = [time_data[label]['ambulance'] for label in labels]
        fire_truck = [time_data[label]['fire_truck'] for label in labels]
        police = [time_data[label]['police'] for label in labels]
        
        print(f"📊 Emergency data - Labels: {len(labels)}, Ambulance: {sum(ambulance)}, Fire: {sum(fire_truck)}, Police: {sum(police)}")
        
        return jsonify({
            "success": True,
            "data": {
                "labels": labels,
                "datasets": {
                    "ambulance": ambulance,
                    "fire_truck": fire_truck,
                    "police": police
                }
            }
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
    """Get detected traffic patterns"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        print(f"🔍 Fetching patterns for scenario: {scenario}, dates: {date_start} to {date_end}")
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)  # Extended to 30 days
        
        # Query with more lenient filters
        patterns_query = TrafficPattern.query.filter(
            TrafficPattern.scenario == scenario
        )
        
        # Only apply date filters if patterns have datetime fields
        if hasattr(TrafficPattern, 'interval_start'):
            patterns_query = patterns_query.filter(
                TrafficPattern.interval_start >= start_date,
                TrafficPattern.interval_end <= end_date
            )
        
        patterns = patterns_query.order_by(
            TrafficPattern.confidence_score.desc()
        ).limit(20).all()  # Increased limit
        
        print(f"✅ Found {len(patterns)} traffic patterns")
        
        if not patterns:
            # Try without date filter to see if any patterns exist
            all_patterns = TrafficPattern.query.filter_by(scenario=scenario).limit(10).all()
            print(f"ℹ️  Total patterns for scenario without date filter: {len(all_patterns)}")
            
            if all_patterns:
                print("⚠️  Patterns exist but outside date range")
                # Return the patterns anyway with a note
                pattern_data = []
                for pattern in all_patterns:
                    pattern_data.append({
                        "traffic_light_id": pattern.traffic_light_id,
                        "pattern_type": pattern.pattern_type,
                        "confidence_score": round(pattern.confidence_score, 1) if pattern.confidence_score else 0,
                        "interval_start": pattern.interval_start.isoformat() if hasattr(pattern, 'interval_start') and pattern.interval_start else "N/A",
                        "interval_end": pattern.interval_end.isoformat() if hasattr(pattern, 'interval_end') and pattern.interval_end else "N/A",
                        "recommendations": pattern.recommendations if pattern.recommendations else [],
                        "note": "Outside selected date range"
                    })
                
                return jsonify({
                    "success": True,
                    "data": pattern_data,
                    "message": "Showing patterns outside date range"
                })
        
        pattern_data = []
        for pattern in patterns:
            pattern_data.append({
                "traffic_light_id": pattern.traffic_light_id,
                "pattern_type": pattern.pattern_type,
                "confidence_score": round(pattern.confidence_score, 1) if pattern.confidence_score else 0,
                "interval_start": pattern.interval_start.isoformat() if hasattr(pattern, 'interval_start') and pattern.interval_start else "N/A",
                "interval_end": pattern.interval_end.isoformat() if hasattr(pattern, 'interval_end') and pattern.interval_end else "N/A",
                "recommendations": pattern.recommendations if pattern.recommendations else []
            })
        
        return jsonify({
            "success": True,
            "data": pattern_data
        })
        
    except Exception as e:
        print(f"❌ Error fetching traffic patterns: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "data": []
        }), 500

@report_bp.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """Generate actual report file (PDF/Excel/CSV)"""
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
        
        start = datetime.strptime(date_start, '%Y-%m-%d')
        end = datetime.strptime(date_end, '%Y-%m-%d')
        
        # Collect report data
        report_data = _collect_report_data(scenario, start, end, metrics)
        
        # Generate file based on format
        if format_type == 'PDF':
            file_buffer = _generate_pdf_report(report_data, template, scenario, start, end)
            mimetype = 'application/pdf'
            filename = f'traffic_report_{scenario}_{date_start}.pdf'
        elif format_type == 'Excel':
            file_buffer = _generate_excel_report(report_data, template, scenario, start, end)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'traffic_report_{scenario}_{date_start}.xlsx'
        elif format_type == 'CSV':
            file_buffer = _generate_csv_report(report_data, scenario, start, end)
            mimetype = 'text/csv'
            filename = f'traffic_report_{scenario}_{date_start}.csv'
        else:
            return jsonify({
                "success": False,
                "error": "Unsupported format"
            }), 400
        
        return send_file(
            file_buffer,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def _collect_report_data(scenario, start_date, end_date, metrics):
    """Collect all data needed for report"""
    data = {}
    
    # Traffic volume
    if "Traffic Volume" in metrics:
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        data['traffic_volume'] = {
            'total': sum(log.vehicle_count for log in logs),
            'average_daily': sum(log.vehicle_count for log in logs) / max(1, (end_date - start_date).days)
        }
    
    # Average speed
    if "Average Speed" in metrics:
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        if logs:
            avg_efficiency = sum(log.efficiency_score for log in logs) / len(logs)
            data['average_speed'] = round(38.5 + (avg_efficiency - 50) * 0.1, 1)
        else:
            data['average_speed'] = 0
    
    # Congestion
    if "Congestion Levels" in metrics:
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        if logs:
            data['congestion'] = round(sum(log.efficiency_score for log in logs) / len(logs), 1)
        else:
            data['congestion'] = 0
    
    # Emergency vehicles
    if "Emergency Vehicles" in metrics:
        emergency_logs = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario,
            EmergencyVehicleLog.detected_at >= start_date,
            EmergencyVehicleLog.detected_at <= end_date
        ).all()
        data['emergency'] = {
            'total': len(emergency_logs),
            'by_type': {
                'ambulance': len([l for l in emergency_logs if 'ambulance' in l.vehicle_type.lower()]),
                'fire_truck': len([l for l in emergency_logs if 'fire' in l.vehicle_type.lower()]),
                'police': len([l for l in emergency_logs if 'police' in l.vehicle_type.lower()])
            }
        }
    
    # Traffic patterns
    if "Traffic Patterns" in metrics:
        patterns = TrafficPattern.query.filter(
            TrafficPattern.scenario == scenario,
            TrafficPattern.interval_start >= start_date,
            TrafficPattern.interval_end <= end_date
        ).all()
        data['patterns'] = [{
            'type': p.pattern_type,
            'confidence': round(p.confidence_score, 1),
            'traffic_light': p.traffic_light_id
        } for p in patterns[:10]]
    
    return data

def _generate_pdf_report(report_data, template, scenario, start_date, end_date):
    """Generate PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    story.append(Paragraph(f"Traffic Management Report", title_style))
    story.append(Paragraph(f"Scenario: {scenario.upper()}", styles['Normal']))
    story.append(Paragraph(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    # Traffic Volume
    if 'traffic_volume' in report_data:
        story.append(Paragraph("Traffic Volume Analysis", styles['Heading2']))
        data = [
            ['Metric', 'Value'],
            ['Total Vehicles', f"{report_data['traffic_volume']['total']:,}"],
            ['Average Daily', f"{report_data['traffic_volume']['average_daily']:.1f}"]
        ]
        t = Table(data, colWidths=[3*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
    
    # Speed
    if 'average_speed' in report_data:
        story.append(Paragraph("Speed Analysis", styles['Heading2']))
        story.append(Paragraph(f"Average Speed: {report_data['average_speed']} mph", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
    
    # Congestion
    if 'congestion' in report_data:
        story.append(Paragraph("Congestion Analysis", styles['Heading2']))
        story.append(Paragraph(f"Average Congestion Level: {report_data['congestion']}%", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
    
    # Emergency
    if 'emergency' in report_data:
        story.append(Paragraph("Emergency Vehicle Activity", styles['Heading2']))
        data = [
            ['Type', 'Count'],
            ['Total Emergency Responses', str(report_data['emergency']['total'])],
            ['Ambulance', str(report_data['emergency']['by_type']['ambulance'])],
            ['Fire Truck', str(report_data['emergency']['by_type']['fire_truck'])],
            ['Police', str(report_data['emergency']['by_type']['police'])]
        ]
        t = Table(data, colWidths=[3*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
    
    # Traffic Patterns
    if 'patterns' in report_data and report_data['patterns']:
        story.append(Paragraph("Traffic Patterns Detected", styles['Heading2']))
        data = [['Pattern Type', 'Traffic Light', 'Confidence']]
        for pattern in report_data['patterns']:
            data.append([
                pattern['type'],
                pattern['traffic_light'],
                f"{pattern['confidence']}%"
            ])
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def _generate_excel_report(report_data, template, scenario, start_date, end_date):
    """Generate Excel report"""
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer)
    
    # Formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#3b82f6',
        'font_color': 'white',
        'align': 'center',
        'valign': 'vcenter',
        'border': 1
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    # Summary sheet
    worksheet = workbook.add_worksheet('Summary')
    worksheet.write('A1', 'Traffic Management Report', workbook.add_format({'bold': True, 'font_size': 16}))
    worksheet.write('A2', f'Scenario: {scenario.upper()}')
    worksheet.write('A3', f'Period: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}')
    worksheet.write('A4', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    
    row = 6
    
    # Traffic Volume
    if 'traffic_volume' in report_data:
        worksheet.write(row, 0, 'Traffic Volume', header_format)
        worksheet.write(row, 1, 'Value', header_format)
        row += 1
        worksheet.write(row, 0, 'Total Vehicles', cell_format)
        worksheet.write(row, 1, report_data['traffic_volume']['total'], cell_format)
        row += 1
        worksheet.write(row, 0, 'Average Daily', cell_format)
        worksheet.write(row, 1, round(report_data['traffic_volume']['average_daily'], 1), cell_format)
        row += 2
    
    # Speed
    if 'average_speed' in report_data:
        worksheet.write(row, 0, 'Average Speed (mph)', header_format)
        worksheet.write(row, 1, report_data['average_speed'], cell_format)
        row += 2
    
    # Congestion
    if 'congestion' in report_data:
        worksheet.write(row, 0, 'Congestion Level (%)', header_format)
        worksheet.write(row, 1, report_data['congestion'], cell_format)
        row += 2
    
    # Emergency
    if 'emergency' in report_data:
        worksheet.write(row, 0, 'Emergency Type', header_format)
        worksheet.write(row, 1, 'Count', header_format)
        row += 1
        worksheet.write(row, 0, 'Total', cell_format)
        worksheet.write(row, 1, report_data['emergency']['total'], cell_format)
        row += 1
        worksheet.write(row, 0, 'Ambulance', cell_format)
        worksheet.write(row, 1, report_data['emergency']['by_type']['ambulance'], cell_format)
        row += 1
        worksheet.write(row, 0, 'Fire Truck', cell_format)
        worksheet.write(row, 1, report_data['emergency']['by_type']['fire_truck'], cell_format)
        row += 1
        worksheet.write(row, 0, 'Police', cell_format)
        worksheet.write(row, 1, report_data['emergency']['by_type']['police'], cell_format)
        row += 2
    
    # Traffic Patterns
    if 'patterns' in report_data and report_data['patterns']:
        patterns_sheet = workbook.add_worksheet('Traffic Patterns')
        patterns_sheet.write(0, 0, 'Pattern Type', header_format)
        patterns_sheet.write(0, 1, 'Traffic Light', header_format)
        patterns_sheet.write(0, 2, 'Confidence (%)', header_format)
        
        for idx, pattern in enumerate(report_data['patterns'], start=1):
            patterns_sheet.write(idx, 0, pattern['type'], cell_format)
            patterns_sheet.write(idx, 1, pattern['traffic_light'], cell_format)
            patterns_sheet.write(idx, 2, pattern['confidence'], cell_format)
    
    workbook.close()
    buffer.seek(0)
    return buffer

def _generate_csv_report(report_data, scenario, start_date, end_date):
    """Generate CSV report"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    
    # Header
    writer.writerow(['Traffic Management Report'])
    writer.writerow([f'Scenario: {scenario.upper()}'])
    writer.writerow([f'Period: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'])
    writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}'])
    writer.writerow([])
    
    # Traffic Volume
    if 'traffic_volume' in report_data:
        writer.writerow(['Traffic Volume'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Vehicles', report_data['traffic_volume']['total']])
        writer.writerow(['Average Daily', round(report_data['traffic_volume']['average_daily'], 1)])
        writer.writerow([])
    
    # Speed
    if 'average_speed' in report_data:
        writer.writerow(['Average Speed'])
        writer.writerow(['Speed (mph)', report_data['average_speed']])
        writer.writerow([])
    
    # Congestion
    if 'congestion' in report_data:
        writer.writerow(['Congestion Level'])
        writer.writerow(['Percentage', report_data['congestion']])
        writer.writerow([])
    
    # Emergency
    if 'emergency' in report_data:
        writer.writerow(['Emergency Vehicle Activity'])
        writer.writerow(['Type', 'Count'])
        writer.writerow(['Total', report_data['emergency']['total']])
        writer.writerow(['Ambulance', report_data['emergency']['by_type']['ambulance']])
        writer.writerow(['Fire Truck', report_data['emergency']['by_type']['fire_truck']])
        writer.writerow(['Police', report_data['emergency']['by_type']['police']])
        writer.writerow([])
    
    # Traffic Patterns
    if 'patterns' in report_data and report_data['patterns']:
        writer.writerow(['Traffic Patterns'])
        writer.writerow(['Pattern Type', 'Traffic Light', 'Confidence (%)'])
        for pattern in report_data['patterns']:
            writer.writerow([pattern['type'], pattern['traffic_light'], pattern['confidence']])
    
    # Convert to BytesIO for send_file
    output = io.BytesIO()
    output.write(buffer.getvalue().encode('utf-8'))
    output.seek(0)
    return output

@report_bp.route('/api/reports/export', methods=['POST'])
def export_report_data():
    """Export current view data as CSV"""
    try:
        data = request.get_json()
        scenario = data.get('scenario', 'accra')
        start_date = datetime.strptime(data.get('startDate', '2025-06-27'), '%Y-%m-%d')
        end_date = datetime.strptime(data.get('endDate', '2025-07-04'), '%Y-%m-%d')
        
        # Collect basic data
        logs = TrafficLightLog.query.filter(
            TrafficLightLog.scenario == scenario,
            TrafficLightLog.created_at >= start_date,
            TrafficLightLog.created_at <= end_date
        ).all()
        
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        # Write headers
        writer.writerow([
            'Date', 'Time', 'Traffic Light', 'Vehicle Count', 
            'Efficiency Score', 'Waiting Vehicles', 'State'
        ])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d'),
                log.created_at.strftime('%H:%M:%S'),
                log.traffic_light_id,
                log.vehicle_count,
                log.efficiency_score,
                log.waiting_vehicles,
                log.state
            ])
        
        output = io.BytesIO()
        output.write(buffer.getvalue().encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'traffic_data_{scenario}_{start_date.strftime("%Y%m%d")}.csv'
        )
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@report_bp.route('/api/reports/ai-performance', methods=['GET'])
def get_ai_performance():
    """Get AI optimization performance metrics"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
        ai_logs = AIDecisionLog.query.filter(
            AIDecisionLog.scenario == scenario,
            AIDecisionLog.created_at >= start_date,
            AIDecisionLog.created_at <= end_date
        ).all()
        
        if not ai_logs:
            return jsonify({
                "success": True,
                "data": {
                    "total_decisions": 0,
                    "optimization_rate": 0,
                    "avg_confidence": 0,
                    "congestion_reduction": 0,
                    "system_health": 0
                }
            })
        
        total_decisions = sum(log.total_decisions for log in ai_logs)
        total_optimized = sum(log.total_tls_optimized for log in ai_logs)
        avg_confidence = sum(log.avg_confidence for log in ai_logs) / len(ai_logs)
        avg_congestion = sum(log.overall_congestion for log in ai_logs) / len(ai_logs)
        avg_health = sum(log.system_health for log in ai_logs) / len(ai_logs)
        
        optimization_rate = (total_optimized / total_decisions * 100) if total_decisions > 0 else 0
        congestion_reduction = max(0, (1 - avg_congestion / 100) * 100)
        
        return jsonify({
            "success": True,
            "data": {
                "total_decisions": total_decisions,
                "total_optimized": total_optimized,
                "optimization_rate": round(optimization_rate, 1),
                "avg_confidence": round(avg_confidence, 1),
                "congestion_reduction": round(congestion_reduction, 1),
                "system_health": round(avg_health * 100, 1),
                "avg_reward": round(sum(log.total_reward for log in ai_logs) / len(ai_logs), 2)
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@report_bp.route('/api/reports/traffic-light-performance', methods=['GET'])
def get_traffic_light_performance():
    """Get individual traffic light performance"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
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
        
        performance_data = []
        for tl in tl_performance:
            if tl.avg_efficiency >= 80:
                grade = "A"
            elif tl.avg_efficiency >= 65:
                grade = "B"
            elif tl.avg_efficiency >= 50:
                grade = "C"
            else:
                grade = "D"
            
            performance_data.append({
                "traffic_light_id": tl.traffic_light_id,
                "avg_efficiency": round(tl.avg_efficiency, 1),
                "total_vehicles": tl.total_vehicles,
                "avg_waiting": round(tl.avg_waiting, 1),
                "grade": grade,
                "status": "Optimized" if tl.avg_efficiency >= 65 else "Needs Attention"
            })
        
        performance_data.sort(key=lambda x: x['avg_efficiency'], reverse=True)
        
        return jsonify({
            "success": True,
            "data": performance_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@report_bp.route('/api/reports/emergency-summary', methods=['GET'])
def get_emergency_summary():
    """Get emergency vehicle summary statistics"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
        # Get emergency logs
        emergency_logs = EmergencyVehicleLog.query.filter(
            EmergencyVehicleLog.scenario == scenario,
            EmergencyVehicleLog.detected_at >= start_date,
            EmergencyVehicleLog.detected_at <= end_date
        ).all()
        
        # Get green wave schedules
        green_waves = GreenWaveSchedule.query.join(
            EmergencySchedule,
            GreenWaveSchedule.emergency_id == EmergencySchedule.id
        ).filter(
            EmergencySchedule.scenario == scenario,
            EmergencySchedule.created_at >= start_date,
            EmergencySchedule.created_at <= end_date
        ).all()
        
        # Calculate statistics
        by_priority = {
            'CRITICAL': len([l for l in emergency_logs if l.priority == 'CRITICAL']),
            'HIGH': len([l for l in emergency_logs if l.priority == 'HIGH']),
            'MEDIUM': len([l for l in emergency_logs if l.priority == 'MEDIUM'])
        }
        
        by_type = {
            'AMBULANCE': len([l for l in emergency_logs if 'ambulance' in l.vehicle_type.lower()]),
            'FIRE_TRUCK': len([l for l in emergency_logs if 'fire' in l.vehicle_type.lower()]),
            'POLICE': len([l for l in emergency_logs if 'police' in l.vehicle_type.lower()])
        }
        
        return jsonify({
            "success": True,
            "data": {
                "total_emergencies": len(emergency_logs),
                "green_waves_activated": len(green_waves),
                "by_priority": by_priority,
                "by_type": by_type,
                "avg_response_time": 0,  # Can be calculated if time data available
                "scheduled_vs_detected": {
                    "scheduled": len([l for l in emergency_logs if l.is_scheduled]),
                    "detected": len([l for l in emergency_logs if not l.is_scheduled])
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@report_bp.route('/api/reports/pattern-insights', methods=['GET'])
def get_pattern_insights():
    """Get insights from traffic patterns"""
    try:
        scenario = request.args.get('scenario', 'accra')
        date_start = request.args.get('date_start')
        date_end = request.args.get('date_end')
        
        if date_start and date_end:
            end_date = datetime.strptime(date_end, '%Y-%m-%d')
            start_date = datetime.strptime(date_start, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
        
        patterns = TrafficPattern.query.filter(
            TrafficPattern.scenario == scenario,
            TrafficPattern.interval_start >= start_date,
            TrafficPattern.interval_end <= end_date
        ).all()
        
        # Analyze patterns
        pattern_types = {}
        high_confidence_patterns = []
        traffic_lights_analyzed = set()
        
        for pattern in patterns:
            pattern_types[pattern.pattern_type] = pattern_types.get(pattern.pattern_type, 0) + 1
            traffic_lights_analyzed.add(pattern.traffic_light_id)
            
            if pattern.confidence_score >= 80:
                high_confidence_patterns.append({
                    'type': pattern.pattern_type,
                    'traffic_light': pattern.traffic_light_id,
                    'confidence': round(pattern.confidence_score, 1)
                })
        
        return jsonify({
            "success": True,
            "data": {
                "total_patterns": len(patterns),
                "pattern_types": pattern_types,
                "high_confidence_count": len(high_confidence_patterns),
                "traffic_lights_analyzed": len(traffic_lights_analyzed),
                "top_patterns": high_confidence_patterns[:5]
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
@report_bp.route('/api/reports/debug/data-availability', methods=['GET'])
def debug_data_availability():
    """Debug endpoint to check data availability"""
    try:
        scenario = request.args.get('scenario', 'accra')
        
        # Check TrafficLightLog
        tl_count = TrafficLightLog.query.filter_by(scenario=scenario).count()
        tl_latest = TrafficLightLog.query.filter_by(scenario=scenario).order_by(
            TrafficLightLog.created_at.desc()
        ).first()
        
        # Check EmergencyVehicleLog
        emergency_count = EmergencyVehicleLog.query.filter_by(scenario=scenario).count()
        emergency_latest = EmergencyVehicleLog.query.filter_by(scenario=scenario).order_by(
            EmergencyVehicleLog.detected_at.desc()
        ).first()
        
        # Check TrafficPattern
        pattern_count = TrafficPattern.query.filter_by(scenario=scenario).count()
        pattern_latest = TrafficPattern.query.filter_by(scenario=scenario).order_by(
            TrafficPattern.id.desc()
        ).first()
        
        # Get all scenarios
        all_scenarios = db.session.query(TrafficLightLog.scenario).distinct().all()
        
        debug_info = {
            "scenario_checked": scenario,
            "available_scenarios": [s[0] for s in all_scenarios],
            "traffic_logs": {
                "count": tl_count,
                "latest_date": tl_latest.created_at.isoformat() if tl_latest else None,
                "sample_id": tl_latest.traffic_light_id if tl_latest else None
            },
            "emergency_logs": {
                "count": emergency_count,
                "latest_date": emergency_latest.detected_at.isoformat() if emergency_latest else None,
                "sample_type": emergency_latest.vehicle_type if emergency_latest else None
            },
            "traffic_patterns": {
                "count": pattern_count,
                "latest_type": pattern_latest.pattern_type if pattern_latest else None,
                "latest_confidence": pattern_latest.confidence_score if pattern_latest else None,
                "sample_tl": pattern_latest.traffic_light_id if pattern_latest else None
            }
        }
        
        return jsonify({
            "success": True,
            "debug_info": debug_info,
            "recommendations": _get_debug_recommendations(debug_info)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def _get_debug_recommendations(debug_info):
    """Generate recommendations based on debug info"""
    recommendations = []
    
    if debug_info['traffic_logs']['count'] == 0:
        recommendations.append("No traffic logs found. Ensure simulation is running and logging data.")
    
    if debug_info['emergency_logs']['count'] == 0:
        recommendations.append("No emergency logs found. Check if emergency vehicles are being detected and logged.")
    
    if debug_info['traffic_patterns']['count'] == 0:
        recommendations.append("No traffic patterns found. Pattern detection may need to run or accumulate more data.")
    
    if not recommendations:
        recommendations.append("All data sources have records. If charts are empty, check date ranges.")
    
    return recommendations