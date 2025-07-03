from flask import Flask

def create_app(config_class = 'config'):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Register blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    
    return app