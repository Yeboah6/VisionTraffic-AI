from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from .middleware.jwt_middleware import jwt_required_redirect
from config import Config
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    # Register middleware as decorator
    app.jwt_required_redirect = jwt_required_redirect

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

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
