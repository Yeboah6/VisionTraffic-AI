from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    
# Register the template filter for datetime formatting
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    """Format datetime objects for templates."""
    return value.strftime(format) if value else ''

if __name__ == '__main__':
    app.run(debug = True)