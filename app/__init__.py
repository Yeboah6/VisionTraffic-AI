from flask import Flask
from flask_migrate import Migrate
from app.extensions import db, login_manager
from config import Config
import humanize
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import logging
import os
from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.sumo import sumo_bp
# from app.routes.api import api_bp  # Uncomment if API routes are needed

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
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.sumo import sumo_bp
    # from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(sumo_bp)
    # app.register_blueprint(api_bp, url_prefix='/api')
    
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