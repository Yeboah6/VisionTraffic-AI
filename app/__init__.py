from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User  # Import here to avoid circular imports
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Login manager configuration
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'


    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.locations import loc_bp
    from app.routes.signals import signal_bp
    from app.routes.cameras import camera_bp
    from app.routes.incidents import incident_bp
    from app.routes.sensor import sensor_bp
    
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(loc_bp)
    app.register_blueprint(signal_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(incident_bp)
    app.register_blueprint(sensor_bp)

    return app
