# WSGI Configuration for PythonAnywhere
# Replace 'yourusername' with your actual PythonAnywhere username

import sys
import os

# Add your project directory to the Python path
path = '/home/yourusername/AGTDesigner'
if path not in sys.path:
    sys.path.append(path)

# Set environment variables for production
os.environ['FLASK_ENV'] = 'production'
os.environ['PYTHONPATH'] = path

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

# Import your Flask app
try:
    from app import create_app
    application = create_app()
    print("✅ Label Maker application loaded successfully")
except Exception as e:
    print(f"❌ Failed to load application: {e}")
    # Create a minimal error app
    from flask import Flask
    application = Flask(__name__)
    
    @application.route('/')
    def error_page():
        return f"Application failed to load: {str(e)}", 500

# For debugging (this won't run in production)
if __name__ == "__main__":
    application.run(debug=True) 