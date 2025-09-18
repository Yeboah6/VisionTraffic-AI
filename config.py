import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ECHO = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    
    # JWT_TOKEN_LOCATION = ['cookies']
    # JWT_COOKIE_SECURE = False  # True in production with HTTPS
    # JWT_COOKIE_CSRF_PROTECT = False  # Recommended for security
    # JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)  # Short-lived access token
    # JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    
    # SQLALCHEMY_ENGINE_OPTIONS = {
    #     'pool_size': 10,
    #     'max_overflow': 20,
    #     'pool_pre_ping': True,
    #     'pool_recycle': 3600,
    # }
    
    # Flask-Login settings
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_PROTECTION = 'strong'
    
    UPLOAD_FOLDER = 'app/static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'pdf'}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    
    # SUMO Configuration
    SUMO_BINARY = os.environ.get('SUMO_BINARY')
    SUMO_CONFIG = os.environ.get('SUMO_CONFIG')
    SUMO_SIMULATION_DELAY = float(os.environ.get('SUMO_SIMULATION_DELAY'))