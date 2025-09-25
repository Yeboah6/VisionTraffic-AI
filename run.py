from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    from app.commands import seed_admin_user
    seed_admin_user()
    print("Database tables created successfully")

if __name__ == '__main__':
    app.run(debug = True)