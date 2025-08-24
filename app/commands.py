# app/commands.py
from app import db
from app.models.user import User
from werkzeug.security import generate_password_hash

def seed_admin_user():
    """Seed an admin user if it doesn't exist"""
    admin_email = "admin@visiontraffic.com"
    admin_user = User.query.filter_by(email=admin_email).first()
    
    if not admin_user:
        admin = User(
            username="admin",
            email=admin_email,
            is_admin=True
        )
        # Set password (change this to a secure password)
        admin.set_password("admin123")  # Change this in production!
        
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")
        print(f"Email: {admin_email}")
        print("Password: admin123")  # Remove this in production
    else:
        print("Admin user already exists.")