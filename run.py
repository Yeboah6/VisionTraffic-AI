from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    
    # from sqlalchemy import text
    # try:
    #     db.session.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
    #     db.session.commit()
    # except Exception as e:
    #     app.logger.error(f"Failed to enable PostGIS: {str(e)}")

if __name__ == '__main__':
    app.run(debug = True)