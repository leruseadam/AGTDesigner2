import os

import sys  # Add this import
import logging
import threading
import pandas as pd  # Add this import
from pathlib import Path
from flask import (
    Flask, 
    request, 
    jsonify, 
    send_file, 
    render_template,
    session,  # Add this
    send_from_directory,
    current_app
)
from flask_cors import CORS
from docx import Document
from docxtpl import DocxTemplate, InlineImage
from io import BytesIO
from datetime import datetime, timezone
from functools import lru_cache
import json  # Add this import
from copy import deepcopy
from docx.shared import Pt, RGBColor, Mm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH  # Add this import
import pprint
import re
import traceback
from docxcompose.composer import Composer
from openpyxl import load_workbook
from PIL import Image as PILImage
import copy
from docx.enum.section import WD_ORIENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn
from docx.enum.table import WD_ROW_HEIGHT_RULE
from src.core.generation.template_processor import get_font_scheme, TemplateProcessor
from src.core.generation.tag_generator import get_template_path
import time
from src.core.generation.mini_font_sizing import (
    get_mini_font_size_by_marker,
    set_mini_run_font_size
)
from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file
import random
from flask_caching import Cache
import pickle

current_dir = os.path.dirname(os.path.abspath(__file__))

# Global variables for lazy loading
_excel_processor = None
_product_database = None
_json_matcher = None
_initial_data_cache = None
_cache_timestamp = None
CACHE_DURATION = 300  # Cache for 5 minutes

# Global processing status with better state management
processing_status = {}  # filename -> status
processing_timestamps = {}  # filename -> timestamp
processing_lock = threading.Lock()  # Add thread lock for status updates

# Cache will be initialized after app creation
cache = None

# Global shared data store for cross-worker communication
shared_data_lock = threading.Lock()

# Shared data file for cross-worker communication
SHARED_DATA_FILE = '/tmp/excel_processor_shared_data.pkl'

def cleanup_old_processing_status():
    """Clean up old processing status entries to prevent memory leaks."""
    with processing_lock:
        current_time = time.time()
        # Keep entries for at least 10 minutes to give frontend time to poll
        cutoff_time = current_time - 600  # 10 minutes
        
        old_entries = []
        for filename, status in processing_status.items():
            timestamp = processing_timestamps.get(filename, 0)
            age = current_time - timestamp
            
            # Only remove entries that are older than 10 minutes AND not currently processing
            if age > cutoff_time and status != 'processing':
                old_entries.append(filename)
        
        for filename in old_entries:
            del processing_status[filename]
            if filename in processing_timestamps:
                del processing_timestamps[filename]
            logging.debug(f"Cleaned up old processing status for: {filename}")

def update_processing_status(filename, status):
    """Update processing status with timestamp."""
    with processing_lock:
        processing_status[filename] = status
        processing_timestamps[filename] = time.time()
        logging.info(f"Updated processing status for {filename}: {status}")
        logging.debug(f"Current processing statuses: {dict(processing_status)}")

def get_excel_processor():
    """Lazy load ExcelProcessor to avoid startup delay. Don't auto-load default file."""
    global _excel_processor
    if _excel_processor is None:
        _excel_processor = ExcelProcessor()
        # Don't auto-load default file - let it be loaded explicitly when needed
        logging.info("Excel processor initialized (no auto-load)")
    return _excel_processor

def get_product_database():
    """Lazy load ProductDatabase to avoid startup delay."""
    global _product_database
    if _product_database is None:
        from src.core.data.product_database import ProductDatabase
        _product_database = ProductDatabase()
    return _product_database

def get_json_matcher():
    """Lazy load JSONMatcher to avoid startup delay."""
    global _json_matcher
    if _json_matcher is None:
        from src.core.data.json_matcher import JSONMatcher
        _json_matcher = JSONMatcher(get_excel_processor())
    return _json_matcher

def disable_product_db_integration():
    """Disable product database integration to improve load times."""
    try:
        excel_processor = get_excel_processor()
        if hasattr(excel_processor, 'enable_product_db_integration'):
            excel_processor.enable_product_db_integration(False)
            logging.info("Product database integration disabled")
    except Exception as e:
        logging.error(f"Error disabling product DB integration: {e}")

def get_cached_initial_data():
    """Get cached initial data if it's still valid."""
    global _initial_data_cache, _cache_timestamp
    if (_initial_data_cache is not None and 
        _cache_timestamp is not None and 
        time.time() - _cache_timestamp < CACHE_DURATION):
        return _initial_data_cache
    return None

def set_cached_initial_data(data):
    """Cache initial data with timestamp."""
    global _initial_data_cache, _cache_timestamp
    _initial_data_cache = data
    _cache_timestamp = time.time()

def clear_initial_data_cache():
    """Clear the initial data cache."""
    global _initial_data_cache, _cache_timestamp
    _initial_data_cache = None
    _cache_timestamp = None

def set_landscape(doc):
    section = doc.sections[-1]
    section.orientation = WD_ORIENT.LANDSCAPE
    # Set minimal margins
    section.left_margin = Inches(0.25)
    section.right_margin = Inches(0.25)
    section.top_margin = Inches(0.25)
    section.bottom_margin = Inches(0.25)
    # Swap width and height for landscape
    new_width, new_height = section.page_height, section.page_width
    section.page_width = new_width
    section.page_height = new_height
 
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = current_dir
    return os.path.join(base_path, relative_path)

def create_app():
    app = Flask(__name__, static_url_path='/static', static_folder='static')
    
    # Detect environment and load appropriate config
    current_dir = os.getcwd()
    
    # More reliable PythonAnywhere detection
    is_pythonanywhere = (
        os.path.exists("/home/adamcordova") or
        'PYTHONANYWHERE_SITE' in os.environ or
        'PYTHONANYWHERE_DOMAIN' in os.environ or
        'pythonanywhere.com' in os.environ.get('HTTP_HOST', '') or
        os.path.exists('/var/log/pythonanywhere') or
        current_dir.startswith('/home/adamcordova') or
        'agtpricetags.com' in os.environ.get('HTTP_HOST', '') or
        'www.agtpricetags.com' in os.environ.get('HTTP_HOST', '')
    )
    
    # Force PythonAnywhere detection if we're on the production domain
    if 'agtpricetags.com' in os.environ.get('HTTP_HOST', '') or 'www.agtpricetags.com' in os.environ.get('HTTP_HOST', ''):
        is_pythonanywhere = True
    
    if is_pythonanywhere:
        # Use production config for PythonAnywhere
        app.config.from_object('config_production.Config')
        logging.info("PythonAnywhere detected - using PRODUCTION configuration")
    else:
        # Use development config for local
        app.config.from_object('config.Config')
        logging.info("Local development detected - using DEVELOPMENT configuration")
    
    # Enable CORS for all routes
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Check if we're in development mode
    development_mode = app.config.get('DEVELOPMENT_MODE', False)
    
    if development_mode:
        # Development settings for hot reloading
        app.config['TEMPLATES_AUTO_RELOAD'] = True  # Enable template auto-reload for development
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file caching for development
        app.config['DEBUG'] = True  # Enable debug mode for development
        app.config['PROPAGATE_EXCEPTIONS'] = True  # Enable exception propagation for development
        logging.info("Running in DEVELOPMENT mode with hot reloading enabled")
    else:
        # Production settings
        app.config['TEMPLATES_AUTO_RELOAD'] = False  # Disable template auto-reload for production
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # Enable static file caching for production (1 year)
        app.config['DEBUG'] = False  # Disable debug mode for production
        app.config['PROPAGATE_EXCEPTIONS'] = False  # Disable exception propagation for production
        logging.info("Running in PRODUCTION mode")
    
    # Set up upload folder
    if is_pythonanywhere:
        # PythonAnywhere specific upload folder
        upload_folder = '/home/adamcordova/uploads'
        logging.info(f"PythonAnywhere detected, using upload folder: {upload_folder}")
    else:
        # Local development upload folder
        upload_folder = os.path.join(current_dir, 'uploads')
        logging.info(f"Local development, using upload folder: {upload_folder}")
    
    # Ensure upload folder exists and is writable
    try:
        os.makedirs(upload_folder, exist_ok=True)
        # Test write permissions
        test_file = os.path.join(upload_folder, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logging.info(f"Upload folder {upload_folder} is writable")
    except Exception as e:
        logging.error(f"Upload folder {upload_folder} is not writable: {e}")
        # Fallback to current directory
        upload_folder = current_dir
        logging.warning(f"Falling back to current directory: {upload_folder}")
    
    app.config['UPLOAD_FOLDER'] = upload_folder
    
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['TESTING'] = False
    app.config['SESSION_REFRESH_EACH_REQUEST'] = False  # Don't refresh session on every request
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session lifetime
    
    app.secret_key = os.urandom(24)  # This is required for session
    return app

app = create_app()

# Initialize Flask-Caching after app creation
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

# Initialize Excel processor and load default data on startup
# REMOVED: No longer auto-loading default files

# Initialize Excel processor function removed - no default file loading

# No default file loading on startup
def save_template_settings(template_type, font_settings):
    """Save template settings to a configuration file."""
    try:
        config_dir = Path(__file__).parent / 'config'
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / f'{template_type}_settings.json'
        
        with open(config_file, 'w') as f:
            json.dump(font_settings, f, indent=2)
        
        logging.info(f"Saved template settings for {template_type}")
    except Exception as e:
        logging.error(f"Error saving template settings: {str(e)}")
        raise

# --- LabelMakerApp Class ---
class LabelMakerApp:
    def __init__(self):
        self.app = app
        self._configure_logging()
        
    def _configure_logging(self):
        # Configure logging only once
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            # Create logs directory if it doesn't exist
            log_dir = Path(__file__).parent / 'logs'
            log_dir.mkdir(exist_ok=True)
            
            # Set up logging format
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            formatter = logging.Formatter(log_format)
            
            # Configure console handler - reduce verbosity in production
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)  # Only show warnings and errors
            console_handler.setFormatter(formatter)
            
            # Configure file handler
            log_file = log_dir / 'label_maker.log'
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            
            # Configure root logger
            logging.basicConfig(
                level=logging.WARNING,
                format=log_format,
                handlers=[console_handler, file_handler]
            )
            
            # Suppress verbose logging from third-party libraries
            logging.getLogger('watchdog').setLevel(logging.WARNING)
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            logging.getLogger('requests').setLevel(logging.WARNING)
            
            # Add handlers to application logger
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.INFO)
            
            self.logger.debug("Logging configured for Label Maker application")
            self.logger.debug(f"Log file location: {log_file}")
            
    def run(self):
        host = os.environ.get('HOST', '127.0.0.1')
        port = int(os.environ.get('FLASK_PORT', 9090))  # Changed to 9090 to avoid conflicts
        development_mode = self.app.config.get('DEVELOPMENT_MODE', False)
        
        logging.info(f"Starting Label Maker application on {host}:{port}")
        self.app.run(
            host=host, 
            port=port, 
            debug=development_mode, 
            use_reloader=development_mode
        )

@app.route('/api/status', methods=['GET'])
def api_status():
    """Check API server status and data loading status."""
    try:
        excel_processor = get_excel_processor()
        
        status = {
            'server': 'running',
            'data_loaded': excel_processor.df is not None and not excel_processor.df.empty,
            'data_shape': excel_processor.df.shape if excel_processor.df is not None else None,
            'last_loaded_file': getattr(excel_processor, '_last_loaded_file', None),
            'selected_tags_count': len(excel_processor.selected_tags) if hasattr(excel_processor, 'selected_tags') else 0
        }
        
        return jsonify(status)
    except Exception as e:
        logging.error(f"Error in status endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon."""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Auto-check downloads function removed - no default file loading

@app.route('/')
def index():
    try:
        # Check cache first
        cached_data = get_cached_initial_data()
        cache_bust = str(int(time.time()))
        if cached_data:
            return render_template('index.html', initial_data=cached_data, cache_bust=cache_bust)
        
        # No default file loading - start completely empty
        initial_data = None
        logging.info("No default file loading - waiting for user upload")
        
        set_cached_initial_data(initial_data)
        return render_template('index.html', initial_data=initial_data, cache_bust=cache_bust)
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', error=str(e), cache_bust=str(int(time.time())) )

@app.route('/splash')
def splash():
    """Serve the splash screen."""
    return render_template('splash.html')

@app.route('/generation-splash')
def generation_splash():
    """Serve the generation splash screen."""
    return render_template('generation-splash.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        logging.info("=== UPLOAD REQUEST START ===")
        start_time = time.time()
        
        # Log request details
        logging.info(f"Request method: {request.method}")
        logging.info(f"Request headers: {dict(request.headers)}")
        logging.info(f"Request files: {list(request.files.keys()) if request.files else 'None'}")
        
        if 'file' not in request.files:
            logging.error("No file uploaded - 'file' not in request.files")
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        logging.info(f"File received: {file.filename}, Content-Type: {file.content_type}")
        
        if file.filename == '':
            logging.error("No file selected - filename is empty")
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.xlsx'):
            logging.error(f"Invalid file type: {file.filename}")
            return jsonify({'error': 'Only .xlsx files are allowed'}), 400
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        logging.info(f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            logging.error(f"File too large: {file_size} bytes (max: {app.config['MAX_CONTENT_LENGTH']})")
            return jsonify({'error': f'File too large. Maximum size is {app.config["MAX_CONTENT_LENGTH"] / (1024*1024):.1f} MB'}), 400
        
        # Ensure upload folder exists and is writable
        upload_folder = app.config['UPLOAD_FOLDER']
        logging.info(f"Using upload folder: {upload_folder}")
        
        try:
            os.makedirs(upload_folder, exist_ok=True)
            logging.info(f"Upload folder created/verified: {upload_folder}")
        except Exception as folder_error:
            logging.error(f"Error creating upload folder {upload_folder}: {folder_error}")
            return jsonify({'error': f'Failed to create upload folder: {str(folder_error)}'}), 500
        
        # Check if folder is writable
        if not os.access(upload_folder, os.W_OK):
            logging.error(f"Upload folder {upload_folder} is not writable")
            return jsonify({'error': 'Upload folder is not writable. Please contact administrator.'}), 500
        
        temp_path = os.path.join(upload_folder, file.filename)
        logging.info(f"Saving file to: {temp_path}")
        
        save_start = time.time()
        try:
            file.save(temp_path)
            save_time = time.time() - save_start
            logging.info(f"File saved successfully to {temp_path} in {save_time:.2f}s")
            
            # Verify file was actually saved
            if not os.path.exists(temp_path):
                raise Exception("File was not saved despite no error")
            
            file_size_on_disk = os.path.getsize(temp_path)
            logging.info(f"File size on disk: {file_size_on_disk} bytes")
            
        except Exception as save_error:
            logging.error(f"Error saving file: {save_error}")
            logging.error(f"Upload folder permissions: {oct(os.stat(upload_folder).st_mode)[-3:]}")
            logging.error(f"Current working directory: {os.getcwd()}")
            return jsonify({'error': f'Failed to save file: {str(save_error)}'}), 500
        
        # Clear any existing status for this filename and mark as processing
        update_processing_status(file.filename, 'processing')
        
        # Start background thread with error handling
        try:
            thread = threading.Thread(target=process_file_background, args=(temp_path,))
            thread.daemon = True  # Make thread daemon so it doesn't block app shutdown
            thread.start()
            logging.info(f"Background processing thread started for {file.filename}")
        except Exception as thread_error:
            logging.error(f"Failed to start background thread: {thread_error}")
            update_processing_status(file.filename, f'error: Failed to start processing')
            return jsonify({'error': 'Failed to start file processing'}), 500
        
        upload_time = time.time() - start_time
        logging.info(f"=== UPLOAD REQUEST COMPLETE === Time: {upload_time:.2f}s")
        return jsonify({'message': 'File uploaded, processing in background', 'filename': file.filename})
    except Exception as e:
        logging.error(f"=== UPLOAD REQUEST FAILED ===")
        logging.error(f"Upload error: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

def process_file_background(file_path: str):
    """Background processing function that saves data to shared file"""
    start_time = time.time()
    try:
        logging.info(f"[BG] Starting optimized file processing: {file_path}")
        
        # Get the Excel processor instance
        excel_processor = get_excel_processor()
        
        # Process the file
        if excel_processor.fast_load_file(file_path):
            logging.info(f"[BG] File fast-loaded successfully in {time.time() - start_time:.2f}s")
            logging.info(f"[BG] DataFrame shape after fast load: {excel_processor.df.shape}")
            logging.info(f"[BG] DataFrame empty after fast load: {excel_processor.df.empty}")
            
            # Save the processed DataFrame to shared file
            if excel_processor.df is not None and not excel_processor.df.empty:
                save_shared_data(excel_processor.df)
                logging.info(f"[BG] DataFrame saved to shared file: {excel_processor.df.shape}")
            
            # Mark as ready
            processing_status[os.path.basename(file_path)] = 'ready'
            logging.info(f"[BG] File marked as ready: {os.path.basename(file_path)}")
            logging.info(f"[BG] Current processing statuses: {processing_status}")
        else:
            logging.error(f"[BG] Fast load failed for {os.path.basename(file_path)}")
            processing_status[os.path.basename(file_path)] = 'error: Failed to load file'
            
    except Exception as e:
        logging.error(f"[BG] Error processing file {file_path}: {e}")
        processing_status[os.path.basename(file_path)] = f'error: {str(e)}'

@app.route('/api/upload-status', methods=['GET'])
def upload_status():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    
    # Clean up old entries periodically (but not on every request to reduce overhead)
    if random.random() < 0.1:  # Only cleanup 10% of the time
        cleanup_old_processing_status()
    
    with processing_lock:
        status = processing_status.get(filename, 'not_found')
        all_statuses = dict(processing_status)  # Copy for debugging
        timestamp = processing_timestamps.get(filename, 0)
        age = time.time() - timestamp if timestamp > 0 else 0
    
    logging.info(f"Upload status request for {filename}: {status} (age: {age:.1f}s)")
    logging.debug(f"All processing statuses: {all_statuses}")
    
    # Add more detailed response for debugging
    response_data = {
        'status': status,
        'filename': filename,
        'age_seconds': round(age, 1),
        'total_processing_files': len(all_statuses)
    }
    
    return jsonify(response_data)

@app.route('/api/template', methods=['POST'])
def edit_template():
    """
    Edit template settings and apply changes to template file. 
    Expected JSON payload:
    {
        "type": "horizontal|vertical|mini|inventory",
        "font_settings": {
            "base_size": 12,
            "title_size": 14,
            "body_size": 11
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate template type
        template_type = data.get('type')
        if not template_type:
            return jsonify({'error': 'Template type is required'}), 400
            
        if template_type not in ['horizontal', 'vertical', 'mini', 'inventory']:
            return jsonify({'error': 'Invalid template type'}), 400

        # Validate font settings
        font_settings = data.get('font_settings', {})
        if not isinstance(font_settings, dict):
            return jsonify({'error': 'Font settings must be an object'}), 400

        # Get and validate template path
        try:
            template_path = get_template_path(template_type)
        except Exception as e:
            logging.error(f"Failed to get template path: {str(e)}")
            return jsonify({'error': 'Template path error'}), 500

        if not template_path or not os.path.exists(template_path):
            return jsonify({'error': 'Template not found'}), 404

        # Apply template fixes and save settings
        try:

            # Save font settings
            save_template_settings(template_type, font_settings)
            
            # Clear font scheme cache if it exists
            if hasattr(get_cached_font_scheme, 'cache_clear'):
                get_cached_font_scheme.cache_clear()

            return jsonify({
                'success': True,
                'message': 'Template updated successfully'
            })

        except Exception as e:
            logging.error(f"Failed to update template: {str(e)}")
            return jsonify({
                'error': 'Failed to update template',
                'details': str(e)
            }), 500

    except Exception as e:
        logging.error(f"Error in edit_template: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add undo/clear support for tag moves and filters
from flask import session

# Helper: maintain an undo stack in session
UNDO_STACK_KEY = 'undo_stack'

@app.route('/api/move-tags', methods=['POST'])
def move_tags():
    try:
        data = request.get_json()
        tags_to_move = data.get('tags', [])
        direction = data.get('direction', 'to_selected')
        select_all = data.get('selectAll', False)

        excel_processor = get_excel_processor()
        # Get current state from excel_processor instead of session
        available_tags = excel_processor.get_available_tags()
        
        # Ensure selected_tags contains only strings
        selected_tags = []
        for tag in excel_processor.selected_tags:
            if isinstance(tag, dict):
                selected_tags.append(tag.get('Product Name*', ''))
            elif isinstance(tag, str):
                selected_tags.append(tag)
            else:
                selected_tags.append(str(tag))

        # Save current state for undo
        undo_stack = session.get(UNDO_STACK_KEY, [])
        undo_stack.append({
            'available_tags': available_tags.copy(),
            'selected_tags': selected_tags.copy(),
        })
        session[UNDO_STACK_KEY] = undo_stack

        if direction == 'to_selected':
            if select_all:
                # For select all, preserve the order from available tags
                excel_processor.selected_tags = [tag['Product Name*'] for tag in available_tags]
            else:
                # For individual moves, add tags in the order they were moved
                for tag in tags_to_move:
                    if tag not in excel_processor.selected_tags:
                        excel_processor.selected_tags.append(tag)
        else:  # to_available
            if select_all:
                excel_processor.selected_tags.clear()
            else:
                excel_processor.selected_tags = [tag for tag in excel_processor.selected_tags if tag not in tags_to_move]

        updated_available = [tag for tag in available_tags if tag['Product Name*'] not in excel_processor.selected_tags]
        updated_selected = excel_processor.selected_tags.copy()

        logging.info(f"Updated available tags count: {len(updated_available)}")
        logging.info(f"Updated selected tags count: {len(updated_selected)}")

        return jsonify({
            'success': True,
            'available_tags': updated_available,
            'selected_tags': updated_selected
        })

    except Exception as e:
        logging.error(f"Error moving tags: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/undo-move', methods=['POST'])
def undo_move():
    try:
        undo_stack = session.get(UNDO_STACK_KEY, [])
        if not undo_stack:
            return jsonify({'error': 'Nothing to undo'}), 400
        last_state = undo_stack.pop()
        session[UNDO_STACK_KEY] = undo_stack
        excel_processor = get_excel_processor()
        
        # Ensure selected_tags contains only strings
        selected_tags = []
        for tag in last_state['selected_tags']:
            if isinstance(tag, dict):
                selected_tags.append(tag.get('Product Name*', ''))
            elif isinstance(tag, str):
                selected_tags.append(tag)
            else:
                selected_tags.append(str(tag))
        
        excel_processor.selected_tags = selected_tags
        available_tags = excel_processor.get_available_tags()
        updated_available = [tag for tag in available_tags if tag['Product Name*'] not in excel_processor.selected_tags]
        updated_selected = excel_processor.selected_tags.copy()
        return jsonify({
            'success': True,
            'available_tags': updated_available,
            'selected_tags': updated_selected
        })
    except Exception as e:
        logging.error(f"Error undoing move: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-filters', methods=['POST'])
def clear_filters():
    try:
        excel_processor = get_excel_processor()
        excel_processor.selected_tags.clear()
        session[UNDO_STACK_KEY] = []
        # Optionally reset dropdown_cache or filters if needed
        excel_processor.dropdown_cache = {}
        
        # Clear JSON matches if any
        json_matcher = get_json_matcher()
        json_matcher.clear_matches()
        
        available_tags = excel_processor.get_available_tags()
        return jsonify({
            'success': True,
            'available_tags': available_tags,
            'selected_tags': [],
            'filters': excel_processor.dropdown_cache
        })
    except Exception as e:
        logging.error(f"Error clearing filters: {str(e)}")
        return jsonify({'error': str(e)}), 500

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@lru_cache(maxsize=32)
def get_cached_font_scheme(template_type, base_size=12):
    from src.core.generation.template_processor import get_font_scheme
    return get_font_scheme(template_type, base_size)

def copy_cell_content(src_cell, dst_cell):
    dst_cell._element.clear_content()
    # Set cell alignment to center
    dst_cell.vertical_alignment = WD_ALIGN_PARAGRAPH.CENTER
    for child in src_cell._element:
        dst_cell._element.append(copy.deepcopy(child))
    # Center all paragraphs in the cell
    for paragraph in dst_cell.paragraphs:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # Center all runs in the paragraph
        for run in paragraph.runs:
            run.font.name = "Arial"
            run.font.bold = True

def rebuild_3x3_grid_from_template(doc, template_path):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches
    from docx.enum.table import WD_ROW_HEIGHT_RULE

    # Load the template and get the first table/cell
    template_doc = Document(template_path)
    old_table = template_doc.tables[0]
    source_cell_xml = deepcopy(old_table.cell(0, 0)._tc)

    # Remove all existing tables in doc
    for table in doc.tables:
        table._element.getparent().remove(table._element)

    # Add new fixed 3x3 table
    table = doc.add_table(rows=3, cols=3)
    table.autofit = False
    table.allow_autofit = False
    tblPr = table._element.find(qn('w:tblPr')) or OxmlElement('w:tblPr')
    tblLayout = OxmlElement('w:tblLayout')
    tblLayout.set(qn('w:type'), 'fixed')
    tblPr.append(tblLayout)
    table._element.insert(0, tblPr)
    tblGrid = OxmlElement('w:tblGrid')
    col_width_twips = str(int((3.3/3) * 1440))
    for _ in range(3):
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), col_width_twips)
        tblGrid.append(gridCol)
    table._element.insert(0, tblGrid)
    for i in range(3):
        for j in range(3):
            cell = table.cell(i, j)
            cell._tc.clear_content()
            new_tc = deepcopy(source_cell_xml)
            # Replace Label1 with LabelN in the XML
            label_num = i * 3 + j + 1
            for text_el in new_tc.iter():
                if text_el.tag == qn('w:t') and text_el.text:
                    logging.debug(f"Processing text element: {text_el.text}")
                    if "Label1" in text_el.text:
                        text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
                        logging.info(f"Replaced Label1 with Label{label_num} in text element.")
            cell._tc.extend(new_tc.xpath('./*'))
        row = table.rows[i]
        row.height = Inches(2.25)
        row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    
    # Enforce fixed cell dimensions to prevent any growth
    enforce_fixed_cell_dimensions(table)
    
    return table

def post_process_document(doc, font_scheme, orientation, scale_factor):
    """
    Main post-processing function, inspired by the old MAIN.py logic.
    This function finds and formats all marked fields in the document.
    Uses template-type-specific font sizing based on the original font-sizing utilities.
    """
    from src.core.generation.font_sizing import (
        get_thresholded_font_size,
        get_thresholded_font_size_ratio,
        get_thresholded_font_size_thc_cbd,
        get_thresholded_font_size_brand,
        get_thresholded_font_size_price,
        get_thresholded_font_size_lineage,
        get_thresholded_font_size_description,
        get_thresholded_font_size_strain,
        set_run_font_size
    )

    # Define marker processing for all template types
    markers = [
        'DESC', 'PRODUCTBRAND_CENTER', 'PRICE', 'LINEAGE', 
        'THC_CBD', 'RATIO', 'PRODUCTSTRAIN', 'DOH'
    ]

    # Process each marker type recursively through the document using template-specific font sizing
    for marker_name in markers:
        _autosize_recursive_template_specific(doc, marker_name, orientation, scale_factor)

    # Apply final conditional formatting for colors, etc.
    apply_lineage_colors(doc)
    return doc

def _autosize_recursive_template_specific(element, marker_name, orientation, scale_factor):
    """
    Recursively search for and format a specific marked field within a document element using template-specific font sizing.
    """
    from src.core.generation.font_sizing import (
        get_thresholded_font_size,
        get_thresholded_font_size_ratio,
        get_thresholded_font_size_thc_cbd,
        get_thresholded_font_size_brand,
        get_thresholded_font_size_price,
        get_thresholded_font_size_lineage,
        get_thresholded_font_size_description,
        get_thresholded_font_size_strain,
        set_run_font_size
    )
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    start_marker = f'{marker_name}_START'
    end_marker = f'{marker_name}_END'

    if hasattr(element, 'paragraphs'):
        for p in element.paragraphs:
            # Reassemble full text from runs to handle split markers
            full_text = "".join(run.text for run in p.runs)

            if start_marker in full_text and end_marker in full_text:
                # Extract content
                start_idx = full_text.find(start_marker) + len(start_marker)
                end_idx = full_text.find(end_marker)
                content = full_text[start_idx:end_idx].strip()

                if content:
                    # Calculate font size using template-specific sizing
                    font_size = _get_template_specific_font_size(content, marker_name, orientation, scale_factor)
                    
                    # Rewrite the paragraph with clean content and new font size
                    p.clear()
                    
                    # Handle line breaks for THC/CBD content
                    if marker_name in ['THC_CBD', 'RATIO'] and '\n' in content:
                        parts = content.split('\n')
                        for i, part in enumerate(parts):
                            if i > 0:
                                run = p.add_run()
                                run.add_break()
                            run = p.add_run(part)
                            run.font.name = "Arial"
                            run.font.bold = True
                            run.font.size = font_size
                            set_run_font_size(run, font_size)
                    else:
                        run = p.add_run(content)
                        run.font.name = "Arial"
                        run.font.bold = True
                        run.font.size = font_size
                        set_run_font_size(run, font_size)
                    
                    # Handle special paragraph properties
                    if marker_name == 'PRODUCTBRAND_CENTER':
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    if marker_name == 'THC_CBD':
                        p.paragraph_format.line_spacing = 1.5
                else:
                    # If there's no content, just remove the markers
                    p.clear()

    if hasattr(element, 'tables'):
        for table in element.tables:
            for row in table.rows:
                for cell in row.cells:
                    # Continue the recursion into cells
                    _autosize_recursive_template_specific(cell, marker_name, orientation, scale_factor)

def _get_template_specific_font_size(content, marker_name, orientation, scale_factor):
    """
    Get font size using the unified font sizing system.
    """
    from src.core.generation.unified_font_sizing import get_font_size
    
    # Map marker names to field types
    marker_to_field_type = {
        'DESC': 'description',
        'PRODUCTBRAND_CENTER': 'brand',
        'PRICE': 'price',
        'LINEAGE': 'lineage',
        'THC_CBD': 'thc_cbd',
        'RATIO': 'ratio',
        'PRODUCTSTRAIN': 'strain',
        'DOH': 'doh'
    }
    
    field_type = marker_to_field_type.get(marker_name, 'default')
    
    # Use unified font sizing with appropriate complexity type
    complexity_type = 'mini' if orientation == 'mini' else 'standard'
    return get_font_size(content, field_type, orientation, scale_factor, complexity_type)

@app.route('/api/generate', methods=['POST'])
def generate_labels():
    try:
        data = request.get_json()
        template_type = data.get('template_type', 'vertical')
        scale_factor = float(data.get('scale_factor', 1.0))
        selected_tags_from_request = data.get('selected_tags', [])
        file_path = data.get('file_path')
        filters = data.get('filters', None)

        logging.debug(f"Generation request - template_type: {template_type}, scale_factor: {scale_factor}")
        logging.debug(f"Selected tags from request: {selected_tags_from_request}")

        # Disable product DB integration for faster loads
        excel_processor = get_excel_processor()
        excel_processor.enable_product_db_integration(False)

        # Only load file if not already loaded
        if file_path:
            if excel_processor._last_loaded_file != file_path or excel_processor.df is None or excel_processor.df.empty:
                excel_processor.load_file(file_path)
        else:
            # Ensure data is loaded - try to reload default file if needed
            if excel_processor.df is None:
                from src.core.data.excel_processor import get_default_upload_file
                default_file = get_default_upload_file()
                if default_file:
                    excel_processor.load_file(default_file)

        if excel_processor.df is None or excel_processor.df.empty:
            logging.error("No data loaded in Excel processor")
            return jsonify({'error': 'No data loaded. Please upload an Excel file.'}), 400

        # Apply filters early
        filtered_df = excel_processor.apply_filters(filters) if filters else excel_processor.df

        # Use cached dropdowns for UI (if needed elsewhere)
        dropdowns = excel_processor.dropdown_cache

        # Use selected tags from request body, this updates the processor's internal state
        if selected_tags_from_request:
            excel_processor.selected_tags = [tag.strip().lower() for tag in selected_tags_from_request]
            logging.debug(f"Updated excel_processor.selected_tags: {excel_processor.selected_tags}")
        
        # Get the fully processed records using the dedicated method
        print(f"DEBUG: About to call get_selected_records with selected_tags: {excel_processor.selected_tags}")
        records = excel_processor.get_selected_records(template_type)
        print(f"DEBUG: get_selected_records returned {len(records) if records else 0} records")
        logging.debug(f"Records returned from get_selected_records: {len(records) if records else 0}")

        if not records:
            print(f"DEBUG: No records returned, returning error")
            logging.error("No selected tags found in the data or failed to process records.")
            return jsonify({'error': 'No selected tags found in the data or failed to process records.'}), 400

        # Use the already imported TemplateProcessor and get_font_scheme
        font_scheme = get_font_scheme(template_type)
        processor = TemplateProcessor(template_type, font_scheme, scale_factor)
        
        # The TemplateProcessor now handles all post-processing internally
        final_doc = processor.process_records(records)
        if final_doc is None:
            return jsonify({'error': 'Failed to generate document.'}), 500

        # Save the final document to a buffer
        output_buffer = BytesIO()
        final_doc.save(output_buffer)
        output_buffer.seek(0)

        # Build a simple informative filename
        today_str = datetime.now().strftime('%Y%m%d')
        time_str = datetime.now().strftime('%H%M%S')
        
        # Get template type and tag count
        template_display = {
            'horizontal': 'HORIZ',
            'vertical': 'VERT', 
            'mini': 'MINI'
        }.get(template_type, template_type.upper())
        
        tag_count = len(records)
        
        # Get most common lineage
        lineage_counts = {}
        for record in records:
            lineage = str(record.get('Lineage', 'MIXED')).upper()
            lineage_counts[lineage] = lineage_counts.get(lineage, 0) + 1
        
        main_lineage = max(lineage_counts.items(), key=lambda x: x[1])[0] if lineage_counts else 'MIXED'
        lineage_abbr = {
            'SATIVA': 'S',
            'INDICA': 'I', 
            'HYBRID': 'H',
            'HYBRID/SATIVA': 'HS',
            'HYBRID/INDICA': 'HI',
            'CBD': 'CBD',
            'MIXED': 'MIX',
            'PARAPHERNALIA': 'PARA'
        }.get(main_lineage, main_lineage[:3])
        
        filename = f"{template_display}_{tag_count}TAGS_{lineage_abbr}_{today_str}_{time_str}.docx"

        return send_file(
            output_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logging.error(f"Error during label generation: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf_labels():
    """Generate PDF labels by first creating DOCX, then converting to PDF with LibreOffice."""
    import subprocess
    import tempfile
    try:
        data = request.get_json()
        template_type = data.get('template_type', 'vertical')
        scale_factor = float(data.get('scale_factor', 1.0))
        selected_tags_from_request = data.get('selected_tags', [])
        file_path = data.get('file_path')
        filters = data.get('filters', None)

        # Usual Excel/data loading logic...
        excel_processor = get_excel_processor()
        excel_processor.enable_product_db_integration(False)
        if file_path:
            if excel_processor._last_loaded_file != file_path or excel_processor.df is None or excel_processor.df.empty:
                excel_processor.load_file(file_path)
        else:
            if excel_processor.df is None:
                from src.core.data.excel_processor import get_default_upload_file
                default_file = get_default_upload_file()
                if default_file:
                    excel_processor.load_file(default_file)
        if excel_processor.df is None or excel_processor.df.empty:
            return jsonify({'error': 'No data loaded. Please upload an Excel file.'}), 400
        filtered_df = excel_processor.apply_filters(filters) if filters else excel_processor.df
        if selected_tags_from_request:
            excel_processor.selected_tags = [tag.strip().lower() for tag in selected_tags_from_request]
        records = excel_processor.get_selected_records(template_type)
        if not records:
            return jsonify({'error': 'No selected tags found in the data or failed to process records.'}), 400

        # Generate DOCX using your template logic
        font_scheme = get_font_scheme(template_type)
        processor = TemplateProcessor(template_type, font_scheme, scale_factor)
        final_doc = processor.process_records(records)
        if final_doc is None:
            return jsonify({'error': 'Failed to generate document.'}), 500

        # Save DOCX to a temp file
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as docx_tmp:
            final_doc.save(docx_tmp)
            docx_path = docx_tmp.name

        # Convert DOCX to PDF using LibreOffice
        pdf_path = docx_path.replace('.docx', '.pdf')
        subprocess.run([
            'libreoffice', '--headless', '--convert-to', 'pdf', '--outdir',
            os.path.dirname(docx_path), docx_path
        ], check=True)

        # Send the PDF file
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name='labels.pdf',
            mimetype='application/pdf'
        )

    except Exception as e:
        logging.error(f"Error during PDF label generation: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

# Example route for dropdowns
@app.route('/api/dropdowns', methods=['GET'])
def get_dropdowns():
    # Use cached dropdowns for UI
    dropdowns = excel_processor.dropdown_cache
    return jsonify(dropdowns)

@app.route('/api/download-transformed-excel', methods=['POST'])
def download_transformed_excel():
    """Generate and return an Excel file containing the processed records."""
    try:
        data = request.get_json()
        # Ensure that the Excel processor has loaded data
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No data loaded'}), 400
            
        selected_tags = list(data.get('selected_tags', []))
        if not selected_tags:
            return jsonify({'error': 'No records selected'}), 400
        
        excel_processor = get_excel_processor()
        filtered_df = excel_processor.df[excel_processor.df['ProductName'].isin(selected_tags)]
        processed_records = []
        for _, row in filtered_df.iterrows():
            processed_records.append(process_record(row, data.get('template_type', ''), get_excel_processor()))
        
        output_df = pd.DataFrame(processed_records)
        output_stream = BytesIO()
        output_df.to_excel(output_stream, index=False)
        output_stream.seek(0)
        
        return send_file(
            output_stream,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name="transformed.xlsx"
        )
        
    except Exception as e:
        logging.error(f"Error in download_transformed_excel: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/available-tags', methods=['GET'])
def get_available_tags():
    try:
        # Check if cache is available (it might be None during initialization)
        cache_key = 'available_tags'
        if cache is not None:
            cached_tags = cache.get(cache_key)
            if cached_tags is not None:
                return jsonify(cached_tags)
            
        excel_processor = get_excel_processor()
        
        # Check if local Excel processor has data
        if excel_processor.df is None or excel_processor.df.empty:
            # Try to load from shared file
            shared_df = load_shared_data()
            if shared_df is not None:
                logging.info(f"Loaded DataFrame from shared file: {shared_df.shape}")
                excel_processor.df = shared_df
            else:
                # Check if there's a file being processed in the background
                processing_files = [f for f, status in processing_status.items() if status == 'processing']
                if processing_files:
                    return jsonify({'error': 'File is still being processed. Please wait...'}), 202
                
                # No data available
                logging.info("No data loaded - returning empty array")
                return jsonify([])
        
        # Add debugging information
        logging.info(f"get_available_tags: DataFrame shape {excel_processor.df.shape if excel_processor.df is not None else 'None'}, filtered shape {excel_processor.df.shape if excel_processor.df is not None else 'None'}")
        
        # Get available tags from the DataFrame
        if excel_processor.df is not None and not excel_processor.df.empty:
            # Debug: Print available columns
            logging.info(f"Available DataFrame columns: {list(excel_processor.df.columns)}")
            
            # Try multiple possible column names for Product
            product_columns = ['Product Name*', 'Product', 'ProductName', 'Product Name', 'product', 'productname']
            product_col = None
            
            for col in product_columns:
                if col in excel_processor.df.columns:
                    product_col = col
                    logging.info(f"Found product column: {product_col}")
                    break
            
            if product_col is None:
                logging.error(f"No product column found. Available columns: {list(excel_processor.df.columns)}")
                return jsonify({'error': 'Product column not found in data'}), 500

            # Log the first 10 product names for debugging
            sample_products = excel_processor.df[product_col].dropna().astype(str).head(10).tolist()
            logging.info(f"Sample product names from '{product_col}': {sample_products}")

            # Get unique product names for tags
            available_tags = excel_processor.df[product_col].dropna().unique().tolist()
            available_tags.sort()
            
            # Convert to proper tag objects with all required properties
            tag_objects = []
            for product_name in available_tags:
                # Find the row with this product name
                product_row = excel_processor.df[excel_processor.df[product_col] == product_name].iloc[0]
                
                # Create tag object with all required properties
                tag_obj = {
                    'Product Name*': convert_to_json_serializable(product_name),
                    'Description': convert_to_json_serializable(product_row.get('Description', '')),
                    'Product Type*': convert_to_json_serializable(product_row.get('Product Type*', 'Unknown Type')),
                    'Product Brand': convert_to_json_serializable(product_row.get('Product Brand', '')),
                    'Product Strain': convert_to_json_serializable(product_row.get('Product Strain', '')),
                    'Lineage': convert_to_json_serializable(product_row.get('Lineage', 'MIXED')),
                    'Concentrate Type': convert_to_json_serializable(product_row.get('Concentrate Type', '')),
                    'Quantity*': convert_to_json_serializable(product_row.get('Quantity*', '')),
                    'Weight*': convert_to_json_serializable(product_row.get('Weight*', '')),
                    'Weight Unit* (grams/gm or ounces/oz)': convert_to_json_serializable(product_row.get('Weight Unit* (grams/gm or ounces/oz)', '')),
                    'THC test result': convert_to_json_serializable(product_row.get('THC test result', '')),
                    'CBD test result': convert_to_json_serializable(product_row.get('CBD test result', '')),
                    'Test result unit (% or mg)': convert_to_json_serializable(product_row.get('Test result unit (% or mg)', '')),
                    'Vendor/Supplier*': convert_to_json_serializable(product_row.get('Vendor/Supplier*', 'Unknown Vendor')),
                    'Price* (Tier Name for Bulk)': convert_to_json_serializable(product_row.get('Price* (Tier Name for Bulk)', '')),
                    'Cost*': convert_to_json_serializable(product_row.get('Cost*', '')),
                    'Lot Number': convert_to_json_serializable(product_row.get('Lot Number', '')),
                    'Barcode*': convert_to_json_serializable(product_row.get('Barcode*', '')),
                    'State': convert_to_json_serializable(product_row.get('State', '')),
                    'Is Sample? (yes/no)': convert_to_json_serializable(product_row.get('Is Sample? (yes/no)', '')),
                    'Is MJ product?(yes/no)': convert_to_json_serializable(product_row.get('Is MJ product?(yes/no)', '')),
                    'Discountable? (yes/no)': convert_to_json_serializable(product_row.get('Discountable? (yes/no)', '')),
                    'Room*': convert_to_json_serializable(product_row.get('Room*', '')),
                    'Batch Number': convert_to_json_serializable(product_row.get('Batch Number', '')),
                    'Product Tags (comma separated)': convert_to_json_serializable(product_row.get('Product Tags (comma separated)', '')),
                    'Internal Product Identifier': convert_to_json_serializable(product_row.get('Internal Product Identifier', '')),
                    'Expiration Date(YYYY-MM-DD)': convert_to_json_serializable(product_row.get('Expiration Date(YYYY-MM-DD)', '')),
                    'Is Archived? (yes/no)': convert_to_json_serializable(product_row.get('Is Archived? (yes/no)', '')),
                    'THC Per Serving': convert_to_json_serializable(product_row.get('THC Per Serving', '')),
                    'Allergens': convert_to_json_serializable(product_row.get('Allergens', '')),
                    'Solvent': convert_to_json_serializable(product_row.get('Solvent', '')),
                    'Accepted Date': convert_to_json_serializable(product_row.get('Accepted Date', '')),
                    'Medical Only (Yes/No)': convert_to_json_serializable(product_row.get('Medical Only (Yes/No)', '')),
                    'Med Price': convert_to_json_serializable(product_row.get('Med Price', '')),
                    'Total THC': convert_to_json_serializable(product_row.get('Total THC', '')),
                    'THCA': convert_to_json_serializable(product_row.get('THCA', '')),
                    'CBDA': convert_to_json_serializable(product_row.get('CBDA', '')),
                    'CBN': convert_to_json_serializable(product_row.get('CBN', '')),
                    'Image URL': convert_to_json_serializable(product_row.get('Image URL', '')),
                    'Ingredients': convert_to_json_serializable(product_row.get('Ingredients', '')),
                    'DOH Compliant (Yes/No)': convert_to_json_serializable(product_row.get('DOH Compliant (Yes/No)', '')),
                    # Add frontend-expected properties
                    'vendor': convert_to_json_serializable(product_row.get('Vendor/Supplier*', 'Unknown Vendor')),
                    'brand': convert_to_json_serializable(product_row.get('Product Brand', '')),
                    'productType': convert_to_json_serializable(product_row.get('Product Type*', 'Unknown Type')),
                    'lineage': convert_to_json_serializable(product_row.get('Lineage', 'MIXED')),
                    'weight': convert_to_json_serializable(product_row.get('Weight*', '')),
                    'weightWithUnits': f"{convert_to_json_serializable(product_row.get('Weight*', ''))} {convert_to_json_serializable(product_row.get('Weight Unit* (grams/gm or ounces/oz)', ''))}".strip(),
                    'displayName': convert_to_json_serializable(product_name)
                }
                tag_objects.append(tag_obj)
            
            # Cache the result if cache is available
            if cache is not None:
                cache.set(cache_key, tag_objects, timeout=300)
            
            logging.info(f"get_available_tags: Returning {len(tag_objects)} tags")
            return jsonify(tag_objects)
        else:
            logging.info("No data loaded - returning empty array")
            return jsonify([])
            
    except Exception as e:
        logging.error(f"Error in available-tags: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/selected-tags', methods=['GET'])
def get_selected_tags():
    try:
        excel_processor = get_excel_processor()
        
        # Add debugging information
        logging.info(f"Selected tags request - DataFrame exists: {excel_processor.df is not None}")
        if excel_processor.df is not None:
            logging.info(f"DataFrame shape: {excel_processor.df.shape}")
            logging.info(f"DataFrame empty: {excel_processor.df.empty}")
            logging.info(f"Selected tags count: {len(excel_processor.selected_tags)}")
        
        # Check if data is loaded
        if excel_processor.df is None or excel_processor.df.empty:
            # Check if there's a file being processed in the background
            processing_files = [f for f, status in processing_status.items() if status == 'processing']
            if processing_files:
                return jsonify({'error': 'File is still being processed. Please wait...'}), 202
            
            # No default file loading - return empty array
            logging.info("No data loaded - returning empty array")
            return jsonify([])
        
        # Get selected tags
        tags = list(excel_processor.selected_tags)
        # Clean NaN from tags
        import math
        def clean_list(lst):
            return ['' if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in lst]
        tags = clean_list(tags)
        return jsonify(tags)
    except Exception as e:
        logging.error(f"Error in selected-tags: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-processed-excel', methods=['POST'])
def download_processed_excel():
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        selected_tags = data.get('selected_tags', [])

        # Check if DataFrame exists
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No data loaded'}), 400

        # Log DataFrame info for debugging
        excel_processor = get_excel_processor()
        logging.debug(f"DataFrame columns: {list(excel_processor.df.columns)}")
        excel_processor = get_excel_processor()
        logging.debug(f"DataFrame shape: {excel_processor.df.shape}")
        logging.debug(f"Filters received: {filters}")
        logging.debug(f"Selected tags: {selected_tags}")

        # Map frontend filter keys to DataFrame column names
        column_mapping = {
            'vendor': 'Vendor',
            'brand': 'Product Brand',
            'productType': 'Product Type*',
            'lineage': 'Lineage',
            'weight': 'Weight*',
            'strain': 'Product Strain'
        }

        # Apply filters if provided
        excel_processor = get_excel_processor()
        df = excel_processor.df.copy()  # Create a copy to avoid modifying the original
        logging.debug(f"Initial DataFrame shape: {df.shape}")
        
        if filters:
            for col, val in filters.items():
                if val is None or val == 'All':
                    continue
                    
                df_col = column_mapping.get(col, col)
                logging.debug(f"Processing filter: {col} -> {df_col}, value: {val}")
                
                # Try multiple possible column names for robustness
                possible_columns = [df_col]
                if col == 'vendor':
                    possible_columns = ['Vendor', 'Vendor/Supplier*', 'vendor', 'Vendor/Supplier']
                elif col == 'brand':
                    possible_columns = ['Product Brand', 'ProductBrand', 'Brand', 'brand']
                elif col == 'productType':
                    possible_columns = ['Product Type*', 'ProductType', 'Product Type', 'productType']
                elif col == 'lineage':
                    possible_columns = ['Lineage', 'lineage']
                elif col == 'weight':
                    possible_columns = ['Weight*', 'Weight', 'weight']
                elif col == 'strain':
                    possible_columns = ['Product Strain', 'ProductStrain', 'Strain', 'strain']
                
                # Find the first available column
                actual_col = None
                for possible_col in possible_columns:
                    if possible_col in df.columns:
                        actual_col = possible_col
                        break
                
                if actual_col is None:
                    logging.warning(f"Column '{df_col}' not found in DataFrame. Available columns: {list(df.columns)}")
                    continue  # skip if column doesn't exist
                    
                try:
                    if isinstance(val, list):
                        logging.debug(f"Applying list filter: {actual_col} in {val}")
                        df = df[df[actual_col].isin(val)]
                    else:
                        logging.debug(f"Applying string filter: {actual_col} == {val}")
                        # Handle potential NaN values in the column
                        df = df[df[actual_col].astype(str).str.lower() == str(val).lower()]
                    
                    logging.debug(f"After filter '{col}': DataFrame shape: {df.shape}")
                except Exception as filter_error:
                    logging.error(f"Error applying filter {col} ({actual_col}): {str(filter_error)}")
                    logging.error(f"Column data type: {df[actual_col].dtype}")
                    logging.error(f"Column sample values: {df[actual_col].head().tolist()}")
                    raise

        # Further filter by selected tags if provided
        if selected_tags:
            logging.debug(f"Filtering by selected tags: {selected_tags}")
            # Try to find the product column
            product_columns = ['Product Name*', 'ProductName', 'Product Name', 'Product', 'product', 'productname']
            product_col = None
            
            for col in product_columns:
                if col in df.columns:
                    product_col = col
                    logging.debug(f"Found product column for tag filtering: {product_col}")
                    break
            
            if product_col is None:
                logging.error(f"No product column found for tag filtering. Available columns: {list(df.columns)}")
                return jsonify({'error': 'Product column not found in data'}), 500
            
            df = df[df[product_col].isin(selected_tags)]
            logging.debug(f"After tag filtering: DataFrame shape: {df.shape}")

        if df is None or df.empty:
            return jsonify({'error': 'No data available after filtering'}), 400

        # Create output buffer
        output_buffer = BytesIO()
        logging.debug(f"Creating Excel file with {df.shape[0]} rows and {df.shape[1]} columns")
        df.to_excel(output_buffer, index=False, engine='openpyxl')
        output_buffer.seek(0)

        # Generate filename with date
        filename = f"processed_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return send_file(
            output_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logging.error(f"Error in download_processed_excel: {str(e)}")
        logging.error(f"Exception type: {type(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-lineage', methods=['POST'])
def update_lineage():
    """Update the lineage for a specific tag."""
    try:
        data = request.get_json()
        tag_name = data.get('tag_name')
        new_lineage = data.get('lineage')
        
        if not tag_name or not new_lineage:
            return jsonify({'error': 'Missing tag_name or lineage'}), 400
            
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No data loaded'}), 400
            
        # --- Robust product name column handling ---
        df = excel_processor.df
        product_name_col = None
        for col in ['ProductName', 'Product Name*', 'Product Name']:
            if col in df.columns:
                product_name_col = col
                break
        if not product_name_col:
            return jsonify({'error': 'No product name column found in data'}), 500
        # Case-insensitive, whitespace-insensitive match
        norm_tag = tag_name.strip().lower()
        norm_col = df[product_name_col].astype(str).str.strip().str.lower()
        mask = norm_col == norm_tag
        if not mask.any():
            return jsonify({'error': f'Tag "{tag_name}" not found'}), 404
        # Update the lineage in the Excel data
        df.loc[mask, 'Lineage'] = new_lineage
        # --- NEW: Update the product database as well ---
        product_db = get_product_database()
        vendor = None
        brand = None
        try:
            row = df.loc[mask].iloc[0]
            vendor = row.get('Vendor') or row.get('Vendor/Supplier*')
            brand = row.get('Product Brand')
        except Exception as e:
            logging.warning(f"Could not extract vendor/brand for DB update: {e}")
        db_success = product_db.update_product_lineage(tag_name, new_lineage, vendor, brand)
        if not db_success:
            logging.error(f"Failed to update product database for {tag_name} (vendor={vendor}, brand={brand})")
            return jsonify({'error': f'Failed to update product database for {tag_name}'}), 500
        # --- END NEW ---
        # Log the change
        logging.info(f"Updated lineage for tag '{tag_name}' to '{new_lineage}' (vendor={vendor}, brand={brand})")
        return jsonify({
            'success': True,
            'message': f'Updated lineage for {tag_name} to {new_lineage}'
        })
    except Exception as e:
        logging.error(f"Error updating lineage: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/filter-options', methods=['GET', 'POST'])
def get_filter_options():
    try:
        # Ensure cache is available
        if cache is None:
            logging.error("Cache is None in filter-options endpoint")
            return jsonify({'error': 'Cache not initialized'}), 500
            
        cache_key = 'filter_options'
        cached_options = cache.get(cache_key)
        if cached_options is not None:
            return jsonify(cached_options)
        excel_processor = get_excel_processor()
        # Check if data is loaded
        if excel_processor.df is None or excel_processor.df.empty:
            # No default file loading - return empty filter options
            logging.info("No data loaded - returning empty filter options")
            return jsonify({
                'vendor': [],
                'brand': [],
                'productType': [],
                'lineage': [],
                'weight': [],
                'strain': []
            })
        current_filters = {}
        if request.method == 'POST':
            data = request.get_json()
            current_filters = data.get('filters', {})
        options = excel_processor.get_dynamic_filter_options(current_filters)
        import math
        def clean_list(lst):
            return ['' if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in lst]
        options = {k: clean_list(v) for k, v in options.items()}
        cache.set(cache_key, options)
        return jsonify(options)
    except Exception as e:
        logging.error(f"Error in filter_options: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-columns', methods=['GET'])
def debug_columns():
    """Debug endpoint to show available columns in the DataFrame."""
    try:
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No data loaded'}), 400
        columns_info = {
            'columns': list(excel_processor.df.columns),
            'shape': excel_processor.df.shape,
            'dtypes': excel_processor.df.dtypes.to_dict(),
            'sample_data': {}
        }
        # Add sample data for key columns
        for col in ['Vendor', 'Product Brand', 'Product Type*', 'Lineage', 'ProductName']:
            if col in excel_processor.df.columns:
                # Clean NaN from sample data
                sample = excel_processor.df[col].head(3).tolist()
                import math
                sample = ['' if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in sample]
                columns_info['sample_data'][col] = sample
        return jsonify(columns_info)
    except Exception as e:
        logging.error(f"Error in debug_columns: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database-stats', methods=['GET'])
def database_stats():
    """Get statistics about the product database."""
    try:
        product_db = get_product_database()
        stats = product_db.get_strain_statistics()
        return jsonify(stats)
    except Exception as e:
        logging.error(f"Error getting database stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database-export', methods=['GET'])
def database_export():
    """Export the database to Excel."""
    try:
        import tempfile
        import os
        
        product_db = get_product_database()
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()
        
        # Export database
        product_db.export_database(temp_file.name)
        
        # Send file
        return send_file(
            temp_file.name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"product_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
    except Exception as e:
        logging.error(f"Error exporting database: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database-view', methods=['GET'])
def database_view():
    """View database contents in JSON format."""
    try:
        import sqlite3
        
        product_db = get_product_database()
        
        with sqlite3.connect(product_db.db_path) as conn:
            # Get strains
            strains_df = pd.read_sql_query('''
                SELECT strain_name, canonical_lineage, total_occurrences, first_seen_date, last_seen_date
                FROM strains
                ORDER BY total_occurrences DESC
                LIMIT 50
            ''', conn)
            
            # Get products
            products_df = pd.read_sql_query('''
                SELECT p.product_name, p.product_type, p.vendor, p.brand, p.lineage,
                       s.strain_name, p.total_occurrences, p.first_seen_date, p.last_seen_date
                FROM products p
                LEFT JOIN strains s ON p.strain_id = s.id
                ORDER BY p.total_occurrences DESC
                LIMIT 50
            ''', conn)
            
            return jsonify({
                'strains': strains_df.to_dict('records'),
                'products': products_df.to_dict('records'),
                'total_strains': len(strains_df),
                'total_products': len(products_df)
            })
    except Exception as e:
        logging.error(f"Error viewing database: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear all caches and reset data"""
    start_time = time.time()
    try:
        logging.info("=== CACHE CLEAR REQUEST ===")
        
        # Clear Excel processor cache
        excel_processor = get_excel_processor()
        if hasattr(excel_processor, 'clear_cache'):
            excel_processor.clear_cache()
            logging.info("Excel processor cache cleared and reset")
        else:
            # Reset the DataFrame if clear_cache method doesn't exist
            excel_processor.df = None
            logging.info("Excel processor DataFrame reset (no clear_cache method)")
        
        # Clear product database cache
        product_db = get_product_database()
        product_db.clear_cache()
        logging.info("Product database cache cleared")
        
        # Reinitialize product database if method exists
        if hasattr(product_db, "initialize"):
            logging.info("Initializing product database...")
            product_db.initialize()
            logging.info(f"Product database initialized successfully in {time.time() - start_time:.3f}s")
        else:
            logging.info("Product database does not have an initialize() method, skipping reinitialization.")
        
        # Clear JSON matcher cache
        json_matcher = get_json_matcher()
        json_matcher.clear_cache()
        logging.info("JSON matcher cache cleared")
        
        # Clear Flask cache
        if cache is not None:
            cache.clear()
            logging.info("Flask cache cleared")
        
        # Clear shared data file
        clear_shared_data()
        
        return jsonify({'message': 'All caches cleared successfully'})
        
    except Exception as e:
        logging.error(f"Error clearing cache: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache-status', methods=['GET'])
def cache_status():
    """Get cache status information."""
    try:
        global _initial_data_cache, _cache_timestamp
        if _initial_data_cache is not None and _cache_timestamp is not None:
            age = time.time() - _cache_timestamp
            return jsonify({
                'cached': True,
                'age_seconds': age,
                'max_age_seconds': CACHE_DURATION,
                'expires_in_seconds': max(0, CACHE_DURATION - age)
            })
        else:
            return jsonify({'cached': False})
    except Exception as e:
        logging.error(f"Error getting cache status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/performance', methods=['GET'])
def performance_stats():
    """Get performance statistics."""
    try:
        import psutil
        import time
        
        # Get system stats
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Get cache stats
        global _initial_data_cache, _cache_timestamp
        cache_info = {
            'cached': _initial_data_cache is not None,
            'age_seconds': time.time() - _cache_timestamp if _cache_timestamp else None,
            'cache_size': len(_initial_data_cache) if _initial_data_cache else 0
        }
        
        # Get ExcelProcessor stats
        excel_processor = get_excel_processor()
        excel_stats = {
            'file_loaded': excel_processor.df is not None,
            'dataframe_shape': excel_processor.df.shape if excel_processor.df is not None else None,
            'cache_size': len(excel_processor._file_cache) if hasattr(excel_processor, '_file_cache') else 0
        }
        
        # Get product database stats
        product_db_stats = {}
        if hasattr(excel_processor, 'get_product_db_stats'):
            product_db_stats = excel_processor.get_product_db_stats()
        
        return jsonify({
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': memory.available / (1024**3)
            },
            'cache': cache_info,
            'excel_processor': excel_stats,
            'product_database': product_db_stats
        })
    except Exception as e:
        logging.error(f"Error getting performance stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/product-db/disable', methods=['POST'])
def disable_product_db():
    """Disable product database integration to improve performance."""
    try:
        disable_product_db_integration()
        return jsonify({'success': True, 'message': 'Product database integration disabled'})
    except Exception as e:
        logging.error(f"Error disabling product DB: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/product-db/enable', methods=['POST'])
def enable_product_db():
    """Enable product database integration."""
    try:
        excel_processor = get_excel_processor()
        if hasattr(excel_processor, 'enable_product_db_integration'):
            excel_processor.enable_product_db_integration(True)
            logging.info("Product database integration enabled")
        return jsonify({'success': True, 'message': 'Product database integration enabled'})
    except Exception as e:
        logging.error(f"Error enabling product DB: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/product-db/status', methods=['GET'])
def product_db_status():
    """Get product database integration status."""
    try:
        excel_processor = get_excel_processor()
        enabled = getattr(excel_processor, '_product_db_enabled', True)
        stats = excel_processor.get_product_db_stats() if hasattr(excel_processor, 'get_product_db_stats') else {}
        
        return jsonify({
            'enabled': enabled,
            'stats': stats
        })
    except Exception as e:
        logging.error(f"Error getting product DB status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/json-match', methods=['POST'])
def json_match():
    """Fetch JSON from URL and match products against loaded Excel data."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.lower().startswith('http'):
            return jsonify({'error': 'Please provide a valid HTTP URL'}), 400
            
        # Get Excel processor and ensure data is loaded
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No Excel data loaded. Please upload an Excel file first.'}), 400
            
        # Get JSON matcher and ensure sheet cache is built
        json_matcher = get_json_matcher()
        
        # Force rebuild sheet cache to ensure it's up to date
        json_matcher.rebuild_sheet_cache()
        
        # Check if sheet cache was built successfully
        cache_status = json_matcher.get_sheet_cache_status()
        if cache_status == "Not built" or cache_status == "Empty":
            return jsonify({'error': f'Failed to build product cache: {cache_status}. Please ensure your Excel file has product data.'}), 400
            
        # Perform matching
        matched_names = json_matcher.fetch_and_match(url)
        
        # Update the Excel processor's selected tags with matched names
        if matched_names:
            excel_processor.selected_tags = [name.lower() for name in matched_names]
            
        # Get all available tags (don't filter out matched ones - they stay in Available)
        available_tags = excel_processor.get_available_tags()
        
        return jsonify({
            'success': True,
            'matched_count': len(matched_names),
            'matched_names': matched_names,
            'available_tags': available_tags,  # Keep all available tags unchanged
            'selected_tags': matched_names,    # Only update selected tags
            'cache_status': cache_status
        })
        
    except Exception as e:
        logging.error(f"Error in JSON matching: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/json-inventory', methods=['POST'])
def json_inventory():
    """Process JSON inventory data and generate inventory slips."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.lower().startswith('http'):
            return jsonify({'error': 'Please provide a valid HTTP URL'}), 400
            
        # Process JSON inventory data
        json_matcher = get_json_matcher()
        inventory_df = json_matcher.process_json_inventory(url)
        
        if inventory_df.empty:
            return jsonify({'error': 'No inventory items found in JSON'}), 400
            
        # Generate inventory slips using the existing template processor
        from src.core.generation.template_processor import TemplateProcessor, get_font_scheme
        from src.core.generation.tag_generator import get_template_path
        
        template_type = 'inventory'
        template_path = get_template_path(template_type)
        font_scheme = get_font_scheme(template_type)
        processor = TemplateProcessor(template_type, font_scheme, 1.0)
        
        # Convert DataFrame to records format expected by processor
        records = []
        for _, row in inventory_df.iterrows():
            record = {}
            for col in inventory_df.columns:
                record[col] = str(row[col]) if pd.notna(row[col]) else ""
            records.append(record)
            
        # Generate the document
        final_doc = processor.process_records(records)
        if final_doc is None:
            return jsonify({'error': 'Failed to generate inventory document'}), 500
            
        # Save the final document to a buffer
        output_buffer = BytesIO()
        final_doc.save(output_buffer)
        output_buffer.seek(0)
        
        filename = f"inventory_slips-{datetime.now().strftime('%Y-%m-%d_T%H%M%S%f')}.docx"
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        logging.error(f"Error processing JSON inventory: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/json-clear', methods=['POST'])
def json_clear():
    """Clear JSON matches and reset to original state."""
    try:
        json_matcher = get_json_matcher()
        json_matcher.clear_matches()
        
        # Reset Excel processor selected tags
        excel_processor = get_excel_processor()
        excel_processor.selected_tags = []
        
        # Get all available tags
        available_tags = excel_processor.get_available_tags()
        
        return jsonify({
            'success': True,
            'message': 'JSON matches cleared',
            'available_tags': available_tags,
            'selected_tags': []
        })
        
    except Exception as e:
        logging.error(f"Error clearing JSON matches: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/json-status', methods=['GET'])
def json_status():
    """Get JSON matcher status for debugging."""
    try:
        excel_processor = get_excel_processor()
        json_matcher = get_json_matcher()
        
        status = {
            'excel_loaded': excel_processor.df is not None,
            'excel_columns': list(excel_processor.df.columns) if excel_processor.df is not None else [],
            'excel_row_count': len(excel_processor.df) if excel_processor.df is not None else 0,
            'sheet_cache_status': json_matcher.get_sheet_cache_status(),
            'json_matched_names': json_matcher.get_matched_names() or []
        }
        
        return jsonify(status)
        
    except Exception as e:
        logging.error(f"Error getting JSON status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match-json-tags', methods=['POST'])
def match_json_tags():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'matched': [], 'unmatched': [], 'error': 'No JSON data provided.'}), 400
            
        # Accept array of names/IDs, array of objects, or object with 'products' array
        names = []
        if isinstance(data, list):
            if data and isinstance(data[0], str):
                names = data
            elif data and isinstance(data[0], dict):
                names = [obj.get('Product Name*') or obj.get('name') or obj.get('product_name') or obj.get('id') or obj.get('ID') for obj in data if obj]
        elif isinstance(data, dict):
            if 'products' in data and isinstance(data['products'], list):
                names = [obj.get('Product Name*') or obj.get('name') or obj.get('product_name') or obj.get('id') or obj.get('ID') for obj in data['products'] if obj]
            elif 'inventory_transfer_items' in data and isinstance(data['inventory_transfer_items'], list):
                # Cultivera format
                names = []
                for item in data['inventory_transfer_items']:
                    if isinstance(item, dict):
                        name = item.get('product_name') or item.get('name') or item.get('Product Name*') or item.get('id') or item.get('ID')
                        if name:
                            names.append(name)
            else:
                # Try to extract names from any array in the object
                for key, value in data.items():
                    if isinstance(value, list) and value:
                        if isinstance(value[0], str):
                            names = value
                            break
                        elif isinstance(value[0], dict):
                            names = [obj.get('Product Name*') or obj.get('name') or obj.get('product_name') or obj.get('id') or obj.get('ID') for obj in value if obj]
                            if names:
                                break
        
        # Clean and validate names
        names = [str(n).strip() for n in names if n and str(n).strip()]
        if not names:
            return jsonify({'matched': [], 'unmatched': [], 'error': 'No valid product names or IDs found in JSON.'}), 400
            
        # Get Excel processor and available tags
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'matched': [], 'unmatched': names, 'error': 'No Excel data loaded. Please upload an Excel file first.'}), 400
            
        available_tags = excel_processor.get_available_tags()
        if not available_tags:
            return jsonify({'matched': [], 'unmatched': names, 'error': 'No available tags found in Excel data.'}), 400
        
        matched = []
        unmatched = []
        
        # Use the improved matching logic from JSONMatcher
        json_matcher = get_json_matcher()
        
        # Build cache if needed
        if json_matcher._sheet_cache is None:
            json_matcher._build_sheet_cache()
            
        if not json_matcher._sheet_cache:
            return jsonify({'matched': [], 'unmatched': names, 'error': 'Failed to build product cache. Please ensure your Excel file has product data.'}), 400
        
        # For each JSON name, find the best match using the improved scoring system
        for name in names:
            best_score = 0.0
            best_match = None
            
            # Create a mock JSON item for scoring
            json_item = {"product_name": name}
            
            # Try to match against all available tags
            for tag in available_tags:
                tag_name = tag.get('Product Name*', '')
                if not tag_name:
                    continue
                    
                # Create a mock cache item for scoring
                cache_item = {
                    "original_name": tag_name,
                    "key_terms": json_matcher._extract_key_terms(tag_name),
                    "norm": json_matcher._normalize(tag_name)
                }
                
                # Calculate match score
                score = json_matcher._calculate_match_score(json_item, cache_item)
                
                if score > best_score:
                    best_score = score
                    best_match = tag
                    
            # Accept matches with reasonable confidence
            if best_score >= 0.3:  # Lowered threshold for better matching
                matched.append(best_match)
                logging.info(f"Matched '{name}' to '{best_match.get('Product Name*', '')}' (score: {best_score:.2f})")
            else:
                unmatched.append(name)
                logging.info(f"No match found for '{name}' (best score: {best_score:.2f})")
        
        logging.info(f"JSON matching: {len(matched)} matched, {len(unmatched)} unmatched out of {len(names)} total")
        
        # Add debugging information for the first few unmatched items
        if unmatched and len(unmatched) > 0:
            logging.info(f"Sample unmatched names: {unmatched[:5]}")
            logging.info(f"Sample available tags: {[tag.get('Product Name*', '') for tag in available_tags[:5]]}")
        
        return jsonify({
            'matched': matched, 
            'unmatched': unmatched,
            'debug_info': {
                'total_names': len(names),
                'total_available_tags': len(available_tags),
                'sample_unmatched': unmatched[:5] if unmatched else [],
                'matching_threshold': 0.3
            }
        })
        
    except Exception as e:
        logging.error(f"Error in match_json_tags: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'matched': [], 'unmatched': [], 'error': f'Internal error: {str(e)}'}), 500

@app.route('/api/proxy-json', methods=['POST'])
def proxy_json():
    """Proxy JSON requests to avoid CORS issues."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.lower().startswith('http'):
            return jsonify({'error': 'Please provide a valid HTTP URL'}), 400
        
        import urllib.request
        import json
        
        # Fetch the JSON from the external URL
        with urllib.request.urlopen(url) as response:
            json_data = json.loads(response.read().decode())
            
        return jsonify(json_data)
        
    except urllib.error.HTTPError as e:
        logging.error(f"HTTP error fetching JSON from {url}: {e.code}")
        return jsonify({'error': f'HTTP error: {e.code}'}), e.code
    except urllib.error.URLError as e:
        logging.error(f"URL error fetching JSON from {url}: {e.reason}")
        return jsonify({'error': f'URL error: {e.reason}'}), 400
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error from {url}: {e}")
        return jsonify({'error': f'Invalid JSON: {e}'}), 400
    except Exception as e:
        logging.error(f"Error proxying JSON from {url}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-upload-status', methods=['GET'])
def debug_upload_status():
    """Debug endpoint to show all upload processing statuses."""
    try:
        with processing_lock:
            all_statuses = dict(processing_status)
            all_timestamps = dict(processing_timestamps)
        
        current_time = time.time()
        status_details = []
        
        for filename, status in all_statuses.items():
            timestamp = all_timestamps.get(filename, 0)
            age = current_time - timestamp if timestamp > 0 else 0
            status_details.append({
                'filename': filename,
                'status': status,
                'age_seconds': round(age, 1),
                'timestamp': timestamp
            })
        
        # Sort by age (oldest first)
        status_details.sort(key=lambda x: x['age_seconds'], reverse=True)
        
        return jsonify({
            'current_time': current_time,
            'total_files': len(status_details),
            'statuses': status_details
        })
        
    except Exception as e:
        logging.error(f"Error in debug upload status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-upload-status', methods=['POST'])
def clear_upload_status():
    """Clear all upload processing statuses (for debugging)."""
    try:
        data = request.get_json() or {}
        filename = data.get('filename')
        
        with processing_lock:
            if filename:
                # Clear specific filename
                if filename in processing_status:
                    del processing_status[filename]
                if filename in processing_timestamps:
                    del processing_timestamps[filename]
                logging.info(f"Cleared upload status for: {filename}")
                return jsonify({'message': f'Cleared status for {filename}'})
            else:
                # Clear all
                count = len(processing_status)
                processing_status.clear()
                processing_timestamps.clear()
                logging.info(f"Cleared all upload statuses ({count} files)")
                return jsonify({'message': f'Cleared all statuses ({count} files)'})
                
    except Exception as e:
        logging.error(f"Error clearing upload status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-environment', methods=['GET'])
def debug_environment():
    """Debug endpoint to show environment information for troubleshooting."""
    try:
        current_dir = os.getcwd()
        
        # Use the same detection logic as create_app()
        is_pythonanywhere = (
            os.path.exists("/home/adamcordova") or
            'PYTHONANYWHERE_SITE' in os.environ or
            'PYTHONANYWHERE_DOMAIN' in os.environ or
            'pythonanywhere.com' in os.environ.get('HTTP_HOST', '') or
            os.path.exists('/var/log/pythonanywhere') or
            current_dir.startswith('/home/adamcordova') or
            'agtpricetags.com' in os.environ.get('HTTP_HOST', '') or
            'www.agtpricetags.com' in os.environ.get('HTTP_HOST', '')
        )
        
        # Check upload folder
        upload_folder = app.config.get('UPLOAD_FOLDER', 'Not set')
        upload_folder_exists = os.path.exists(upload_folder) if upload_folder != 'Not set' else False
        upload_folder_writable = os.access(upload_folder, os.W_OK) if upload_folder_exists else False
        
        # Check current directory permissions
        current_dir_writable = os.access(current_dir, os.W_OK)
        
        # Get environment variables
        env_vars = {
            'PYTHONANYWHERE_SITE': os.environ.get('PYTHONANYWHERE_SITE', 'Not set'),
            'PYTHONANYWHERE_DOMAIN': os.environ.get('PYTHONANYWHERE_DOMAIN', 'Not set'),
            'HTTP_HOST': os.environ.get('HTTP_HOST', 'Not set'),
            'DEVELOPMENT_MODE': os.environ.get('DEVELOPMENT_MODE', 'Not set'),
            'PWD': os.environ.get('PWD', 'Not set'),
            'HOME': os.environ.get('HOME', 'Not set')
        }
        
        # Check if /home/adamcordova exists
        adamcordova_exists = os.path.exists("/home/adamcordova")
        adamcordova_writable = os.access("/home/adamcordova", os.W_OK) if adamcordova_exists else False
        
        # Check if /home/adamcordova/uploads exists
        uploads_exists = os.path.exists("/home/adamcordova/uploads") if adamcordova_exists else False
        uploads_writable = os.access("/home/adamcordova/uploads", os.W_OK) if uploads_exists else False
        
        debug_info = {
            'environment': {
                'is_pythonanywhere': is_pythonanywhere,
                'current_directory': current_dir,
                'current_directory_writable': current_dir_writable,
                'adamcordova_exists': adamcordova_exists,
                'adamcordova_writable': adamcordova_writable,
                'uploads_exists': uploads_exists,
                'uploads_writable': uploads_writable
            },
            'app_config': {
                'upload_folder': upload_folder,
                'upload_folder_exists': upload_folder_exists,
                'upload_folder_writable': upload_folder_writable,
                'development_mode': app.config.get('DEVELOPMENT_MODE', 'Not set'),
                'debug_mode': app.config.get('DEBUG', 'Not set'),
                'max_content_length': app.config.get('MAX_CONTENT_LENGTH', 'Not set')
            },
            'environment_variables': env_vars,
            'file_permissions': {
                'current_dir_perms': oct(os.stat(current_dir).st_mode)[-3:] if os.path.exists(current_dir) else 'N/A',
                'upload_folder_perms': oct(os.stat(upload_folder).st_mode)[-3:] if upload_folder_exists else 'N/A',
                'adamcordova_perms': oct(os.stat("/home/adamcordova").st_mode)[-3:] if adamcordova_exists else 'N/A'
            }
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        logging.error(f"Error in debug environment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-upload', methods=['GET'])
def test_upload():
    """Test endpoint to verify upload functionality by creating a test file."""
    try:
        upload_folder = app.config.get('UPLOAD_FOLDER', 'Not set')
        
        if upload_folder == 'Not set':
            return jsonify({'error': 'Upload folder not configured'}), 500
        
        # Create test file
        test_file_path = os.path.join(upload_folder, 'test_upload.txt')
        test_content = f"Test upload file created at {datetime.now().isoformat()}"
        
        try:
            with open(test_file_path, 'w') as f:
                f.write(test_content)
            
            # Verify file was created
            if os.path.exists(test_file_path):
                file_size = os.path.getsize(test_file_path)
                return jsonify({
                    'success': True,
                    'message': 'Test file created successfully',
                    'file_path': test_file_path,
                    'file_size': file_size,
                    'upload_folder': upload_folder,
                    'upload_folder_writable': os.access(upload_folder, os.W_OK)
                })
            else:
                return jsonify({'error': 'Test file was not created'}), 500
                
        except Exception as write_error:
            return jsonify({
                'error': f'Failed to create test file: {str(write_error)}',
                'upload_folder': upload_folder,
                'upload_folder_exists': os.path.exists(upload_folder),
                'upload_folder_writable': os.access(upload_folder, os.W_OK) if os.path.exists(upload_folder) else False
            }), 500
            
    except Exception as e:
        logging.error(f"Error in test upload: {e}")
        return jsonify({'error': str(e)}), 500

def save_shared_data(data):
    """Save data to shared file that persists across worker processes"""
    try:
        with shared_data_lock:
            with open(SHARED_DATA_FILE, 'wb') as f:
                pickle.dump(data, f)
        logging.info(f"Shared data saved: {len(data) if isinstance(data, list) else 'DataFrame'}")
    except Exception as e:
        logging.error(f"Error saving shared data: {e}")

def load_shared_data():
    """Load data from shared file"""
    try:
        if os.path.exists(SHARED_DATA_FILE):
            with shared_data_lock:
                with open(SHARED_DATA_FILE, 'rb') as f:
                    data = pickle.load(f)
            logging.info(f"Shared data loaded: {len(data) if isinstance(data, list) else 'DataFrame'}")
            return data
        else:
            logging.info("No shared data file found")
            return None
    except Exception as e:
        logging.error(f"Error loading shared data: {e}")
        return None

def clear_shared_data():
    """Clear shared data file"""
    try:
        with shared_data_lock:
            if os.path.exists(SHARED_DATA_FILE):
                os.remove(SHARED_DATA_FILE)
        logging.info("Shared data file cleared")
    except Exception as e:
        logging.error(f"Error clearing shared data: {e}")

def convert_to_json_serializable(value):
    """Convert pandas/numpy values to JSON serializable types."""
    import numpy as np
    import pandas as pd
    
    if value is None or pd.isna(value):
        return ''
    elif isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    elif isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    elif isinstance(value, (np.bool_)):
        return bool(value)
    elif isinstance(value, (pd.Timestamp)):
        return value.isoformat()
    else:
        return str(value)

if __name__ == '__main__':
    # Create and run the application
    label_maker = LabelMakerApp()
    label_maker.run()