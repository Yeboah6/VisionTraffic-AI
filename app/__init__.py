from flask import Flask
from flask_migrate import Migrate
from app.extensions import db, login_manager
from config import Config
import humanize
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import logging
import os

# Services
# from app.services.camera_service import camera_service
# from app.services.ai_traffic_service import ai_traffic_service
from app.services.db_queue import init_db_queue

# Models
from app.models.incident import Incident
from app.models.location import Location
from app.models.camera import Camera, CameraMetrics
from app.models.user import User
from app.models.traffic_light import TrafficLightLog, TrafficLightConfig, TrafficPattern
from app.models.ai import AIDecisionLog, AIQTable, AIPerformance

migrate = Migrate()

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User  # Import here to avoid circular imports
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    init_db_queue(app)
    
    # Initialize the SumoService with app context
    # 
    
    # Register services with app
    # app.camera_service = camera_service
    # app.ai_traffic_service = ai_traffic_service
    
    # Services
    # from app.services.sumo_service import sumo_service
    # sumo_service.init_app(app)
    
    from app.services.tls_data_service import init_tls_data_service
    init_tls_data_service(app)
    
    from app.services.optimized_sumo_service import init_optimized_sumo_service
    init_optimized_sumo_service(app)
    
    from app.services.tls_config_service import init_tls_config_service
    init_tls_config_service(app)
    
    from app.services.ai_traffic_service import init_ai_traffic_service
    init_ai_traffic_service(app)
    
    from app.services.performance_monitor import performance_monitor
    
    
    # Register blueprints / Routes
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.incident import incident_bp
    from app.routes.location import location_bp
    from app.routes.settings import settings_bp
    from app.routes.user import user_bp
    
    # Api
    from app.routes.api.tls_routes import tls_bp
    from app.routes.api.sumo import sumo_bp
    from app.routes.api.ai_routes import ai_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(incident_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(user_bp)
    
    app.register_blueprint(sumo_bp)
    app.register_blueprint(tls_bp)
    app.register_blueprint(ai_bp)
    
    # Custom Jinja2 filter for humanizing time
    @app.template_filter('time_ago')
    def time_ago_filter(value):
        if not value:
            return "Just now"
        # Convert to timezone-aware datetime if needed
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return humanize.naturaltime(now - value)
    
    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/ai_traffic.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('AI Traffic Management System startup')
    
    return app