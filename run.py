from app import create_app, db
from app.models.traffic_light import TrafficLightLog

app = create_app()

with app.app_context():
    db.create_all()
    from app.commands import seed_admin_user
    seed_admin_user()
    print("Database tables created successfully")
    
    # Test basic database operations
    test_log = TrafficLightLog(
        traffic_light_id='test_tls',
        scenario='test',
        simulation_time=100.0,
        state='GGGrrr',
        phase=0,
        phase_name='TEST'
    )

if __name__ == '__main__':
    app.run(debug = True)