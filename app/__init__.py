from flask import Flask

app = Flask(__name__)

def create_app():
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    
    return app
