#!/usr/bin/env python3
"""
WSGI entry point for the Label Maker application - Python 3.10 compatible.
This file is specifically configured for PythonAnywhere Python 3.10.12.
"""

import sys
import os

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set production environment variables for Python 3.10
os.environ.setdefault('DEVELOPMENT_MODE', 'false')
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('PYTHON_VERSION', '3.10')

# Configure logging for PythonAnywhere
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the Flask app from app.py
try:
    from app import app
    # For PythonAnywhere, we need to expose the app object
    application = app
    
    # Log successful import
    logging.info("Successfully imported Flask app")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")
    
except ImportError as e:
    # Log the error for debugging
    logging.error(f"Error importing app: {e}")
    print(f"Error importing app: {e}")
    raise

if __name__ == "__main__":
    app.run() 