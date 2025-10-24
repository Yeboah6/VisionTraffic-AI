from app import create_app, db
from app.services.traffic_pattern_analyzer import traffic_pattern_analyzer

app = create_app()

with app.app_context():
    db.create_all()
    from app.commands import seed_admin_user
    seed_admin_user()
    print("Database tables created successfully")
    
    # print("🧪 Testing direct pattern storage...")
    
    # Create a simple test pattern
    # test_pattern = {
    #     'traffic_light_id': 'test_tls_01',
    #     'pattern_type': 'TEST_PATTERN'
    # }
    
    # # Test direct storage
    # test_result = traffic_pattern_analyzer.store_patterns_directly([test_pattern])
    # print(f"Test storage result: {test_result}")
    
    # # Now run the full analysis
    # print("🔍 Running full pattern analysis...")
    # result = traffic_pattern_analyzer.analyze_traffic_patterns()
    # print("Analysis result:", result)

if __name__ == '__main__':
    app.run(debug = True)