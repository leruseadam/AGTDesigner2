import os
import sys
import logging
import threading
import pandas as pd
from pathlib import Path
from flask import (
    Flask, 
    request, 
    jsonify, 
    send_file, 
    render_template,
    session,
    send_from_directory,
    current_app
)
from flask_cors import CORS
from docx import Document
from docxtpl import DocxTemplate, InlineImage
from io import BytesIO
from datetime import datetime, timezone
from functools import lru_cache
import json
from copy import deepcopy
from docx.shared import Pt, RGBColor, Mm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
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

# Import cross-platform utilities
from src.core.utils.cross_platform import get_platform, platform_manager

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
    """Lazy load ExcelProcessor to avoid startup delay. Optimize DataFrame after loading."""
    global _excel_processor
    if _excel_processor is None:
        _excel_processor = ExcelProcessor()
        # Try to load the default file
        default_file = get_default_upload_file()
        if default_file and os.path.exists(default_file):
            try:
                # Use fast loading mode for better performance
                success = _excel_processor.load_file(default_file)
                if success:
                    _excel_processor._last_loaded_file = default_file
                    # Optimize DataFrame
                    if _excel_processor.df is not None:
                        for col in ['Product Type*', 'Lineage', 'Product Brand', 'Vendor', 'Product Strain']:
                            if col in _excel_processor.df.columns:
                                _excel_processor.df[col] = _excel_processor.df[col].astype('category')
                    logging.info(f"Excel processor initialized with {len(_excel_processor.df) if _excel_processor.df is not None else 0} records")
                else:
                    logging.warning("Failed to load default file in get_excel_processor")
            except Exception as e:
                logging.error(f"Error loading default file in get_excel_processor: {e}")
                # Ensure df is initialized even if loading fails
                if _excel_processor.df is None:
                    _excel_processor.df = pd.DataFrame()
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
    app.config.from_object('config.Config')
    
    # Enable CORS for all routes
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Check if we're in development mode
    development_mode = app.config.get('DEVELOPMENT_MODE', False)
    
    if development_mode:
        # Development settings for hot reloading
        app.config['TEMPLATES_AUTO_RELOAD'] = True  # Enable template auto-reload for development
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable static file caching for development
        app.config['DEBUG'] = True  # Enable debug mode for development
        app.config['PROPAGATE_EXCEPTIONS'] = True  # Enable exception propagation for debugging
        logging.info("Running in DEVELOPMENT mode with hot reloading enabled")
    else:
        # Production settings
        app.config['TEMPLATES_AUTO_RELOAD'] = False  # Disable template auto-reload in production
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # Cache static files for 1 year
        app.config['DEBUG'] = False  # Disable debug mode for better performance
        app.config['PROPAGATE_EXCEPTIONS'] = False
        logging.info("Running in PRODUCTION mode")
    
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['TESTING'] = False
    app.config['SESSION_REFRESH_EACH_REQUEST'] = False  # Don't refresh session on every request
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session lifetime
    
    upload_folder = os.path.join(current_dir, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.secret_key = os.urandom(24)  # This is required for session
    return app

app = create_app()

# Initialize Flask-Caching after app creation
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})

# Initialize Excel processor and load default data on startup
def initialize_excel_processor():
    """Initialize Excel processor and load default data."""
    try:
        excel_processor = get_excel_processor()
        excel_processor.logger.setLevel(logging.WARNING)
        
        # Try to load default file
        from src.core.data.excel_processor import get_default_upload_file
        default_file = get_default_upload_file()
        
        if default_file and os.path.exists(default_file):
            logging.info(f"Loading default file on startup: {default_file}")
            try:
                success = excel_processor.load_file(default_file)
                if success:
                    excel_processor._last_loaded_file = default_file
                    logging.info(f"Default file loaded successfully with {len(excel_processor.df)} records")
                else:
                    logging.warning("Failed to load default file")
            except Exception as load_error:
                logging.error(f"Error loading default file: {load_error}")
                logging.error(f"Traceback: {traceback.format_exc()}")
        else:
            logging.info("No default file found, waiting for user upload")
            if default_file:
                logging.info(f"Default file path was found but file doesn't exist: {default_file}")
            
    except Exception as e:
        logging.error(f"Error initializing Excel processor: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")

# Initialize on startup
initialize_excel_processor()

# Add missing function
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
        
        # Try to find an available port
        import socket
        def is_port_in_use(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex((host, port)) == 0
        
        # Try ports 9090, 9091, 9092, etc.
        original_port = port
        while is_port_in_use(port):
            logging.warning(f"Port {port} is in use, trying next port...")
            port += 1
            if port > original_port + 10:  # Don't try more than 10 ports
                logging.error("Could not find an available port")
                return
        
        if port != original_port:
            logging.info(f"Using port {port} instead of {original_port}")
        
        logging.info(f"Starting Label Maker application on {host}:{port}")
        try:
            self.app.run(
                host=host, 
                port=port, 
                debug=development_mode, 
                use_reloader=development_mode
            )
        except OSError as e:
            if "Address already in use" in str(e):
                logging.error(f"Port {port} is still in use. Please stop the other application or use a different port.")
            else:
                logging.error(f"Error starting application: {e}")
        except Exception as e:
            logging.error(f"Unexpected error starting application: {e}")

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

def auto_check_downloads():
    """Automatically check Downloads for new AGT files and copy them to uploads."""
    try:
        from pathlib import Path
        import shutil
        
        current_dir = os.getcwd()
        
        # Check if we're running on PythonAnywhere
        is_pythonanywhere = os.path.exists("/home/adamcordova") and "pythonanywhere" in current_dir.lower()
        
        # PythonAnywhere specific paths
        pythonanywhere_uploads = "/home/adamcordova/uploads"
        uploads_dir = pythonanywhere_uploads if os.path.exists(pythonanywhere_uploads) else os.path.join(current_dir, "uploads")
        
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Skip Downloads check on PythonAnywhere
        if is_pythonanywhere:
            logging.info("Skipping Downloads check on PythonAnywhere")
            return
        
        downloads_dir = os.path.join(str(Path.home()), "Downloads")
        
        # Find AGT files in Downloads
        agt_files = []
        if os.path.exists(downloads_dir):
            for filename in os.listdir(downloads_dir):
                if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                    file_path = os.path.join(downloads_dir, filename)
                    mod_time = os.path.getmtime(file_path)
                    agt_files.append((file_path, filename, mod_time))
        
        if not agt_files:
            logging.info("No AGT files found in Downloads")
            return None
        
        # Sort by modification time (most recent first)
        agt_files.sort(key=lambda x: x[2], reverse=True)
        
        # Copy the most recent file to uploads if it doesn't exist or is newer
        most_recent_file_path, most_recent_filename, most_recent_mod_time = agt_files[0]
        upload_path = os.path.join(uploads_dir, most_recent_filename)
        
        if not os.path.exists(upload_path) or os.path.getmtime(most_recent_file_path) > os.path.getmtime(upload_path):
            shutil.copy2(most_recent_file_path, upload_path)
            logging.info(f"Auto-copied new file from Downloads: {most_recent_filename}")
        else:
            logging.info(f"Most recent file already exists in uploads: {most_recent_filename}")
        
        # Always return the upload path if we found a file
        return upload_path
            
    except Exception as e:
        logging.error(f"Error in auto_check_downloads: {str(e)}")
        return None

@app.route('/')
def index():
    try:
        # Check cache first
        cached_data = get_cached_initial_data()
        cache_bust = str(int(time.time()))
        if cached_data:
            return render_template('index.html', initial_data=cached_data, cache_bust=cache_bust)
        
        # Auto-check Downloads for new files and get the file path
        copied_file_path = auto_check_downloads()
        
        # Lazy load the required modules
        from src.core.data.excel_processor import get_default_upload_file
        
        # Use the copied file path if available, otherwise fall back to get_default_upload_file
        default_file = copied_file_path if copied_file_path else get_default_upload_file()
        initial_data = None
        
        if default_file:
            if copied_file_path:
                logging.info(f"Auto-loading file from Downloads: {os.path.basename(default_file)}")
            else:
                logging.info(f"Loading existing file: {os.path.basename(default_file)}")
            
            try:
                excel_processor = get_excel_processor()
                
                # Only load file if it's not already loaded or if it's a different file
                if (excel_processor.df is None or 
                    not hasattr(excel_processor, '_last_loaded_file') or 
                    excel_processor._last_loaded_file != default_file):
                    
                    excel_processor.load_file(default_file)
                    excel_processor._last_loaded_file = default_file
                    
                    # Reset state only when loading new file
                    excel_processor.selected_tags = []
                    excel_processor.dropdown_cache = {}
                
                if excel_processor.df is not None:
                    initial_data = {
                        'filename': os.path.basename(default_file),
                        'filepath': default_file,
                        'columns': excel_processor.df.columns.tolist(),
                        'filters': excel_processor.dropdown_cache,
                        'available_tags': excel_processor.get_available_tags(),
                        'selected_tags': list(excel_processor.selected_tags)
                    }
                    logging.info(f"Successfully loaded file with {len(initial_data['available_tags'])} tags")
            except Exception as e:
                logging.error(f"Error processing default file: {str(e)}")
        else:
            logging.info("No default file found to load")
        
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

def clean_dataframe(df):
    df.dropna(how='all', inplace=True)
    df.columns = [str(col).strip() for col in df.columns]
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
    return df

@app.route('/upload', methods=['POST'])
def upload():
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
        
        # Ensure upload folder exists
        upload_folder = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        logging.info(f"Upload folder: {upload_folder}")
        
        temp_path = os.path.join(upload_folder, file.filename)
        logging.info(f"Saving file to: {temp_path}")
        
        save_start = time.time()
        try:
            file.save(temp_path)
            save_time = time.time() - save_start
            logging.info(f"File saved successfully to {temp_path} in {save_time:.2f}s")
        except Exception as save_error:
            logging.error(f"Error saving file: {save_error}")
            return jsonify({'error': f'Failed to save file: {str(save_error)}'}), 500
        
        # Clear any existing status for this filename and mark as processing
        update_processing_status(file.filename, 'processing')
        
        # Start background thread with error handling
        try:
            thread = threading.Thread(target=process_excel_background, args=(file.filename, temp_path))
            thread.daemon = True  # Make thread daemon so it doesn't block app shutdown
            thread.start()
            logging.info(f"Background processing thread started for {file.filename}")

            # --- PATCH: Immediately load the new file as current after upload ---
            excel_processor = get_excel_processor()
            excel_processor.load_file(temp_path)
            excel_processor._last_loaded_file = temp_path
            excel_processor.selected_tags = []
            excel_processor.dropdown_cache = {}
            logging.info(f"Patched: Set {temp_path} as current inventory file after upload.")
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

def process_excel_background(filename, temp_path):
    """Optimized background processing - do minimal work initially, defer heavy processing"""
    try:
        excel_processor = get_excel_processor()
        logging.info(f"[BG] Starting optimized file processing: {temp_path}")
        
        # Verify the file still exists before processing
        if not os.path.exists(temp_path):
            update_processing_status(filename, f'error: File not found at {temp_path}')
            logging.error(f"[BG] File not found: {temp_path}")
            return
        
        # Step 1: Fast load with minimal processing
        load_start = time.time()
        success = excel_processor.fast_load_file(temp_path)
        load_time = time.time() - load_start
        
        if not success:
            update_processing_status(filename, f'error: Failed to load file')
            logging.error(f"[BG] Fast load failed for {filename}")
            return
            
        excel_processor._last_loaded_file = temp_path
        logging.info(f"[BG] File fast-loaded successfully in {load_time:.2f}s")
        logging.info(f"[BG] DataFrame shape after fast load: {excel_processor.df.shape if excel_processor.df is not None else 'None'}")
        logging.info(f"[BG] DataFrame empty after fast load: {excel_processor.df.empty if excel_processor.df is not None else 'N/A'}")
        
        # Step 2: Quick initialization (minimal work)
        excel_processor.selected_tags = []
        
        # Step 3: Add a small delay to ensure frontend has time to start polling
        time.sleep(1)
        
        # Step 4: Mark as ready for basic operations
        update_processing_status(filename, 'ready')
        logging.info(f"[BG] File marked as ready: {filename}")
        logging.info(f"[BG] Current processing statuses: {dict(processing_status)}")
        
        # Step 5: Defer heavy processing (dropdowns, etc.) to when actually needed
        # This will be done on-demand when user accesses filters or other features
        
    except Exception as e:
        logging.error(f"[BG] Error processing uploaded file: {e}")
        logging.error(f"[BG] Traceback: {traceback.format_exc()}")
        update_processing_status(filename, f'error: {str(e)}')
        
        # Clean up the temporary file if it exists
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logging.info(f"[BG] Cleaned up temporary file: {temp_path}")
        except Exception as cleanup_error:
            logging.error(f"[BG] Error cleaning up temporary file: {cleanup_error}")

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

def rebuild_3x3_grid_from_template(doc, template_path, template_type='horizontal'):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches
    from docx.enum.table import WD_ROW_HEIGHT_RULE
    from src.core.constants import CELL_DIMENSIONS

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
    
    # Get cell dimensions based on template type
    if template_type == 'double':
        cell_width = CELL_DIMENSIONS['double']['width']
        cell_height = CELL_DIMENSIONS['double']['height']
    elif template_type == 'vertical':
        cell_width = CELL_DIMENSIONS['vertical']['width']
        cell_height = CELL_DIMENSIONS['vertical']['height']
    else:  # horizontal or default
        cell_width = CELL_DIMENSIONS['horizontal']['width']
        cell_height = CELL_DIMENSIONS['horizontal']['height']
    
    col_width_twips = str(int(cell_width * 1440))
    tblGrid = OxmlElement('w:tblGrid')
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
        row.height = Inches(cell_height)
        row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    
    # Enforce fixed cell dimensions to prevent any growth
    enforce_fixed_cell_dimensions(table, template_type)
    
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

        # DEBUG: Log the template type received from frontend
        print(f"DEBUG: generate_labels - template_type received: '{template_type}'")

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
        
        # DEBUG: Log the template type being passed to TemplateProcessor
        print(f"DEBUG: About to create TemplateProcessor with template_type: '{template_type}'")
        
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
        cache_key = 'available_tags'
        cached_tags = cache.get(cache_key)
        if cached_tags is not None:
            return jsonify(cached_tags)
        
        excel_processor = get_excel_processor()
        
        # Ensure DataFrame is properly initialized
        if not hasattr(excel_processor, 'df') or excel_processor.df is None:
            excel_processor.df = pd.DataFrame()
        
        # Check if data is loaded
        if excel_processor.df.empty:
            # Check if there's a file being processed in the background
            processing_files = [f for f, status in processing_status.items() if status == 'processing']
            if processing_files:
                return jsonify({'error': 'File is still being processed. Please wait...'}), 202
            # Try to reload the default file if available
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if default_file and os.path.exists(default_file):
                logging.info(f"Attempting to load default file: {default_file}")
                success = excel_processor.load_file(default_file)
                if not success:
                    logging.warning("Failed to load default data file, returning empty array")
                    return jsonify([])
            else:
                logging.info("No default file found, returning empty array")
                return jsonify([])
        
        # Get available tags
        tags = excel_processor.get_available_tags()
        # Convert any NaN in tags to ''
        import math
        def clean_dict(d):
            return {k: ('' if (v is None or (isinstance(v, float) and math.isnan(v))) else v) for k, v in d.items()}
        tags = [clean_dict(tag) for tag in tags]
        cache.set(cache_key, tags)
        # Check if there are JSON matches that should override the available tags
        json_matcher = get_json_matcher()
        if json_matcher.get_matched_names():
            matched_names = set(json_matcher.get_matched_names())
            original_count = len(tags)
            tags = [tag for tag in tags if tag['Product Name*'] not in matched_names]
            logging.info(f"Filtered out {original_count - len(tags)} tags due to JSON matches, {len(tags)} remaining")
        logging.info(f"Returning {len(tags)} available tags")
        return jsonify(tags)
    except Exception as e:
        logging.error(f"Error getting available tags: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/selected-tags', methods=['GET'])
def get_selected_tags():
    try:
        excel_processor = get_excel_processor()
        
        # Ensure DataFrame is properly initialized
        if not hasattr(excel_processor, 'df') or excel_processor.df is None:
            excel_processor.df = pd.DataFrame()
        
        # Add debugging information
        logging.info(f"Selected tags request - DataFrame exists: {excel_processor.df is not None}")
        if excel_processor.df is not None:
            logging.info(f"DataFrame shape: {excel_processor.df.shape}")
            logging.info(f"DataFrame empty: {excel_processor.df.empty}")
            logging.info(f"Selected tags count: {len(excel_processor.selected_tags)}")
        
        # Check if data is loaded
        if excel_processor.df.empty:
            # Check if there's a file being processed in the background
            processing_files = [f for f, status in processing_status.items() if status == 'processing']
            if processing_files:
                return jsonify({'error': 'File is still being processed. Please wait...'}), 202
            
            # Try to reload the default file if available
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            
            if default_file and os.path.exists(default_file):
                logging.info(f"Attempting to load default file for selected tags: {default_file}")
                success = excel_processor.load_file(default_file)
                if not success:
                    logging.warning("Failed to load default data file for selected tags, returning empty array")
                    return jsonify([])
            else:
                logging.info("No default file found for selected tags, returning empty array")
                return jsonify([])
        
        # Get selected tags
        tags = list(excel_processor.selected_tags)
        # Clean NaN from tags
        import math
        def clean_tag(tag):
            if isinstance(tag, dict):
                return {k: ('' if (v is None or (isinstance(v, float) and math.isnan(v))) else v) for k, v in tag.items()}
            return '' if (tag is None or (isinstance(tag, float) and math.isnan(tag))) else tag
        tags = [clean_tag(tag) for tag in tags]
        logging.debug(f"Returning {len(tags)} selected tags")
        return jsonify(tags)
        
    except Exception as e:
        logging.error(f"Error getting selected tags: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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
            if 'ProductName' not in df.columns:
                logging.error(f"'ProductName' column not found. Available columns: {list(df.columns)}")
                return jsonify({'error': 'ProductName column not found in data'}), 500
            df = df[df['ProductName'].isin(selected_tags)]
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
            
        # Find the tag in the DataFrame and update its lineage
        excel_processor = get_excel_processor()
        mask = excel_processor.df['ProductName'] == tag_name if 'ProductName' in excel_processor.df.columns else None
        if mask is None or not mask.any():
            mask = excel_processor.df['Product Name*'] == tag_name if 'Product Name*' in excel_processor.df.columns else None
        if mask is None or not mask.any():
            return jsonify({'error': f'Tag "{tag_name}" not found'}), 404
            
        # Update the lineage
        excel_processor = get_excel_processor()
        excel_processor.df.loc[mask, 'Lineage'] = new_lineage
        
        # Log the change
        logging.info(f"Updated lineage for tag '{tag_name}' to '{new_lineage}'")
        
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
        cache_key = 'filter_options'
        cached_options = cache.get(cache_key)
        if cached_options is not None:
            return jsonify(cached_options)
        excel_processor = get_excel_processor()
        # Check if data is loaded
        if excel_processor.df is None or excel_processor.df.empty:
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if default_file and os.path.exists(default_file):
                logging.info(f"Attempting to load default file for filter options: {default_file}")
                success = excel_processor.load_file(default_file)
                if not success:
                    return jsonify({
                        'vendor': [],
                        'brand': [],
                        'productType': [],
                        'lineage': [],
                        'weight': [],
                        'strain': []
                    })
            else:
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
    """Clear all caches and force fresh data loading."""
    try:
        clear_all_caches()
        
        # Force reload of the most recent file
        excel_processor = get_excel_processor()
        from src.core.data.excel_processor import get_default_upload_file
        default_file = get_default_upload_file()
        
        if default_file and os.path.exists(default_file):
            logging.info(f"Force reloading file after cache clear: {default_file}")
            success = excel_processor.load_file(default_file)
            if success:
                logging.info(f"File reloaded successfully with {len(excel_processor.df)} records")
                return jsonify({
                    'success': True, 
                    'message': f'Cache cleared and file reloaded with {len(excel_processor.df)} records',
                    'record_count': len(excel_processor.df)
                })
            else:
                return jsonify({'error': 'Failed to reload file after cache clear'}), 500
        else:
            return jsonify({'success': True, 'message': 'Cache cleared, no file to reload'})
            
    except Exception as e:
        logging.error(f"Error clearing cache: {str(e)}")
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

@app.route('/mobile')
def mobile():
    """Mobile-optimized version of the label maker."""
    return render_template('mobile.html', cache_bust=int(time.time()))

def clear_all_caches():
    """Clear all caches and force fresh data loading."""
    global _initial_data_cache, _cache_timestamp, _excel_processor
    
    # Clear initial data cache
    _initial_data_cache = None
    _cache_timestamp = None
    
    # Clear Flask cache
    if cache:
        cache.clear()
    
    # Clear ExcelProcessor cache and reset
    if _excel_processor:
        if hasattr(_excel_processor, 'clear_file_cache'):
            _excel_processor.clear_file_cache()
        if hasattr(_excel_processor, '_file_cache'):
            _excel_processor._file_cache.clear()
        # Reset the processor to force fresh loading
        _excel_processor.df = None
        _excel_processor._last_loaded_file = None
        _excel_processor.dropdown_cache = {}
        _excel_processor.selected_tags = []
    
    # Clear processing status
    global processing_status, processing_timestamps
    processing_status.clear()
    processing_timestamps.clear()
    
    logging.info("All caches cleared successfully")

@app.route('/api/force-reload', methods=['POST'])
def force_reload():
    """Force reload the current file and return record count."""
    try:
        # Clear all caches first
        clear_all_caches()
        
        # Get the most recent file
        from src.core.data.excel_processor import get_default_upload_file
        default_file = get_default_upload_file()
        
        if not default_file or not os.path.exists(default_file):
            return jsonify({'error': 'No file found to reload'}), 404
        
        # Force reload
        excel_processor = get_excel_processor()
        logging.info(f"Force reloading file: {default_file}")
        
        success = excel_processor.load_file(default_file)
        if success:
            record_count = len(excel_processor.df) if excel_processor.df is not None else 0
            logging.info(f"File reloaded successfully with {record_count} records")
            
            return jsonify({
                'success': True,
                'filename': os.path.basename(default_file),
                'filepath': default_file,
                'record_count': record_count,
                'message': f'File reloaded with {record_count} records'
            })
        else:
            return jsonify({'error': 'Failed to reload file'}), 500
            
    except Exception as e:
        logging.error(f"Error in force reload: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create and run the application
    label_maker = LabelMakerApp()
    label_maker.run()