from flask import Blueprint, jsonify

traffic_analysis_bp = Blueprint('traffic_analysis', __name__)

@traffic_analysis_bp.route('/api/analyze-traffic-patterns', methods=['POST'])
def trigger_analysis():
    """Manual trigger for traffic pattern analysis"""
    try:
        result = traffic_pattern_analyzer.analyze_traffic_patterns()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@traffic_analysis_bp.route('/api/analysis-status', methods=['GET'])
def analysis_status():
    """Check analysis status and scheduler"""
    try:
        summary = traffic_pattern_analyzer.get_pattern_summary()
        return jsonify({
            "status": "active",
            "scheduler_interval": traffic_pattern_analyzer.analysis_interval,
            "patterns_summary": summary
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500