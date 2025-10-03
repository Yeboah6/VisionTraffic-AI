import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ECHO = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask-Login settings
    REMEMBER_COOKIE_DURATION = timedelta(days=2)
    SESSION_PROTECTION = 'strong'
    
    UPLOAD_FOLDER = 'app/static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'pdf'}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # SUMO Configuration
    SUMO_BINARY = os.environ.get('SUMO_BINARY')
    SUMO_CONFIG = os.environ.get('SUMO_CONFIG')
    SUMO_SIMULATION_DELAY = float(os.environ.get('SUMO_SIMULATION_DELAY'))