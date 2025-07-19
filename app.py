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
    current_app,
    g  # Add this for per-request globals
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
import hashlib
import glob
import subprocess
from collections import defaultdict
import shutil

current_dir = os.path.dirname(os.path.abspath(__file__))

# Global variables for lazy loading
_initial_data_cache = None
_cache_timestamp = None
CACHE_DURATION = 300  # Cache for 5 minutes

# Global ExcelProcessor instance
_excel_processor = None
_excel_processor_reset_flag = False  # Flag to track when processor has been explicitly reset

# Global ProductDatabase instance
_product_database = None

# Global JSONMatcher instance
_json_matcher = None

# Global processing status with better state management
processing_status = {}  # filename -> status
processing_timestamps = {}  # filename -> timestamp
processing_lock = threading.Lock()  # Add thread lock for status updates

# Thread lock for ExcelProcessor initialization
excel_processor_lock = threading.Lock()  # Add thread lock for ExcelProcessor initialization

# Cache will be initialized after app creation
cache = None

# Rate limiting for API endpoints
RATE_LIMIT_WINDOW = 60  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 30  # Max requests per minute per IP

# Simple in-memory rate limiter
rate_limit_data = defaultdict(list)

def reset_excel_processor():
    """Reset the global ExcelProcessor to force reloading of the default file."""
    global _excel_processor, _excel_processor_reset_flag
    
    logging.info("Resetting Excel processor - clearing all data")
    
    if _excel_processor is not None:
        # Explicitly clear all data
        if hasattr(_excel_processor, 'df') and _excel_processor.df is not None:
            del _excel_processor.df
            logging.info("Cleared DataFrame from ExcelProcessor")
        
        if hasattr(_excel_processor, 'selected_tags'):
            _excel_processor.selected_tags = []
            logging.info("Cleared selected tags from ExcelProcessor")
        
        if hasattr(_excel_processor, 'dropdown_cache'):
            _excel_processor.dropdown_cache = {}
            logging.info("Cleared dropdown cache from ExcelProcessor")
        
        # Force garbage collection
        import gc
        gc.collect()
        logging.info("Forced garbage collection")
    
    # Set to None to force recreation
    _excel_processor = None
    
    # Set reset flag to prevent automatic default file loading
    _excel_processor_reset_flag = True
    logging.info("Set reset flag to prevent automatic default file loading")
    
    # Clear all caches
    clear_initial_data_cache()
    
    # Clear Flask cache for available tags
    try:
        cache_key = get_session_cache_key('available_tags')
        cache.delete(cache_key)
        logging.info(f"Cleared cache for key: {cache_key}")
    except Exception as cache_error:
        logging.warning(f"Error clearing cache: {cache_error}")
    
    logging.info("Excel processor reset complete")

def force_reload_excel_processor(new_file_path):
    """Force reload the Excel processor with a new file. ALWAYS clears old data completely."""
    global _excel_processor, _excel_processor_reset_flag
    
    logging.info(f"Force reloading Excel processor with new file: {new_file_path}")
    
    # ALWAYS create a completely new ExcelProcessor instance to ensure clean slate
    logging.info("Creating new ExcelProcessor instance to ensure complete data replacement")
    
    # Clear the old processor completely
    if _excel_processor is not None:
        # Explicitly clear all data from old processor
        if hasattr(_excel_processor, 'df') and _excel_processor.df is not None:
            del _excel_processor.df
            logging.info("Cleared old DataFrame from ExcelProcessor")
        
        if hasattr(_excel_processor, 'selected_tags'):
            _excel_processor.selected_tags = []
            logging.info("Cleared selected tags from ExcelProcessor")
        
        if hasattr(_excel_processor, 'dropdown_cache'):
            _excel_processor.dropdown_cache = {}
            logging.info("Cleared dropdown cache from ExcelProcessor")
        
        # Force garbage collection
        import gc
        gc.collect()
        logging.info("Forced garbage collection to free memory")
    
    # Create a completely new instance
    _excel_processor = ExcelProcessor()
    
    # Disable product database integration for better performance
    if hasattr(_excel_processor, 'enable_product_db_integration'):
        _excel_processor.enable_product_db_integration(False)
        logging.info("Product database integration disabled for upload performance")
    
    # Clear the reset flag since we're loading a new file
    _excel_processor_reset_flag = False
    logging.info("Cleared reset flag - loading new file")
    
    # Load the new file with full processing rules
    success = _excel_processor.load_file(new_file_path)
    if success:
        _excel_processor._last_loaded_file = new_file_path
        logging.info(f"Excel processor successfully loaded new file with full processing rules: {new_file_path}")
        logging.info(f"New DataFrame shape: {_excel_processor.df.shape if _excel_processor.df is not None else 'None'}")
    else:
        logging.error(f"Failed to load new file in Excel processor: {new_file_path}")
        # Create empty DataFrame as fallback
        _excel_processor.df = pd.DataFrame()
        _excel_processor.selected_tags = []

def cleanup_old_processing_status():
    """Clean up old processing status entries to prevent memory leaks."""
    with processing_lock:
        current_time = time.time()
        # Keep entries for at least 15 minutes to give frontend time to poll
        cutoff_time = current_time - 900  # 15 minutes
        
        old_entries = []
        for filename, status in processing_status.items():
            timestamp = processing_timestamps.get(filename, 0)
            age = current_time - timestamp
            
            # Only remove entries that are older than 15 minutes AND not currently processing
            # Also, be more conservative with 'ready' status to prevent race conditions
            if age > cutoff_time and status != 'processing':
                # For 'ready' status, wait a bit longer to ensure frontend has completed
                if status == 'ready' and age < 1800:  # 30 minutes for ready status
                    continue
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
    global _excel_processor, _excel_processor_reset_flag
    
    try:
        # Use thread lock to prevent race conditions
        with excel_processor_lock:
            if _excel_processor is None:
                _excel_processor = ExcelProcessor()
                
                # Disable product database integration by default for better performance
                if hasattr(_excel_processor, 'enable_product_db_integration'):
                    _excel_processor.enable_product_db_integration(False)
                    logging.info("Product database integration disabled by default for performance")
                
                # Only load default file if not explicitly reset
                if not _excel_processor_reset_flag:
                    # Try to load the default file
                    default_file = get_default_upload_file()
                    if default_file and os.path.exists(default_file):
                        logging.info(f"Loading default file in get_excel_processor: {default_file}")
                        # Use fast loading mode for better performance
                        success = _excel_processor.load_file(default_file)
                        if success:
                            _excel_processor._last_loaded_file = default_file
                            # Optimize DataFrame
                            if _excel_processor.df is not None:
                                for col in ['Product Type*', 'Lineage', 'Product Brand', 'Vendor', 'Product Strain']:
                                    if col in _excel_processor.df.columns:
                                        _excel_processor.df[col] = _excel_processor.df[col].astype('category')
                        else:
                            logging.error("Failed to load default file in get_excel_processor")
                            # Ensure df attribute exists even if loading failed
                            if not hasattr(_excel_processor, 'df'):
                                _excel_processor.df = pd.DataFrame()
                    else:
                        logging.warning("No default file found in get_excel_processor")
                        # Ensure df attribute exists even if no default file
                        if not hasattr(_excel_processor, 'df'):
                            _excel_processor.df = pd.DataFrame()
                else:
                    logging.info("Excel processor was reset - not loading default file automatically")
                    # Always ensure df attribute exists for reset processor
                    _excel_processor.df = pd.DataFrame()
                    # Clear the reset flag since we've handled it
                    _excel_processor_reset_flag = False
            
            # Ensure df attribute exists
            if not hasattr(_excel_processor, 'df'):
                logging.error("ExcelProcessor missing df attribute - creating empty DataFrame")
                _excel_processor.df = pd.DataFrame()
            
            # Ensure selected_tags attribute exists
            if not hasattr(_excel_processor, 'selected_tags'):
                _excel_processor.selected_tags = []
            
            return _excel_processor
        
    except Exception as e:
        logging.error(f"Error in get_excel_processor: {str(e)}")
        logging.error(traceback.format_exc())
        # Return a safe fallback ExcelProcessor
        try:
            fallback_processor = ExcelProcessor()
            fallback_processor.df = pd.DataFrame()  # Empty DataFrame
            fallback_processor.selected_tags = []
            return fallback_processor
        except Exception as fallback_error:
            logging.error(f"Failed to create fallback ExcelProcessor: {fallback_error}")
            # Return None and let the calling code handle it
            return None

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
    
    # Enable CORS for specific origins only (security fix)
    allowed_origins = [
        'https://yourdomain.com',  # Replace with your actual domain
        'https://www.yourdomain.com',
        'http://localhost:9090',  # For local development
        'http://127.0.0.1:9090'
    ]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})
    
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
    
    app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max file size
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
        
        # Disable product database integration for better performance
        if hasattr(excel_processor, 'enable_product_db_integration'):
            excel_processor.enable_product_db_integration(False)
            logging.info("Product database integration disabled for startup performance")
        
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
        
        logging.info(f"Starting Label Maker application on {host}:{port}")
        self.app.run(
            host=host, 
            port=port, 
            debug=development_mode, 
            use_reloader=development_mode
        )

# === SESSION-BASED HELPERS ===
def get_session_excel_processor():
    """Get ExcelProcessor instance for the current session with proper error handling."""
    try:
        if 'excel_processor' not in g:
            # Use the global Excel processor instead of creating a new one
            # This ensures we always have the most up-to-date data
            g.excel_processor = get_excel_processor()
            
            # Disable product database integration for better performance
            if hasattr(g.excel_processor, 'enable_product_db_integration'):
                g.excel_processor.enable_product_db_integration(False)
            
            # Ensure the DataFrame is properly initialized
            if not hasattr(g.excel_processor, 'df') or g.excel_processor.df is None or g.excel_processor.df.empty:
                from src.core.data.excel_processor import get_default_upload_file
                default_file = get_default_upload_file()
                if default_file and os.path.exists(default_file):
                    logging.info(f"Loading default file for session: {default_file}")
                    success = g.excel_processor.load_file(default_file)
                    if not success:
                        logging.error("Failed to load default file for session")
                        # Create a minimal DataFrame to prevent errors
                        import pandas as pd
                        g.excel_processor.df = pd.DataFrame()
                else:
                    logging.warning("No default file found for session")
                    # Create a minimal DataFrame to prevent errors
                    import pandas as pd
                    g.excel_processor.df = pd.DataFrame()
            
            # Ensure selected_tags attribute exists
            if not hasattr(g.excel_processor, 'selected_tags'):
                g.excel_processor.selected_tags = []
            
            # Restore selected tags from session
            g.excel_processor.selected_tags = session.get('selected_tags', [])
            logging.info(f"Restored {len(g.excel_processor.selected_tags)} selected tags from session")
            logging.info(f"Session selected_tags: {session.get('selected_tags', [])}")
        
        # Final safety check - ensure df attribute exists
        if not hasattr(g.excel_processor, 'df'):
            logging.error("ExcelProcessor missing df attribute - creating empty DataFrame")
            import pandas as pd
            g.excel_processor.df = pd.DataFrame()
        
        return g.excel_processor
        
    except Exception as e:
        logging.error(f"Error in get_session_excel_processor: {str(e)}")
        logging.error(traceback.format_exc())
        # Return a safe fallback ExcelProcessor
        try:
            from src.core.data.excel_processor import ExcelProcessor
            import pandas as pd
            fallback_processor = ExcelProcessor()
            fallback_processor.df = pd.DataFrame()  # Empty DataFrame
            fallback_processor.selected_tags = []
            return fallback_processor
        except Exception as fallback_error:
            logging.error(f"Failed to create fallback ExcelProcessor: {fallback_error}")
            # Return None and let the calling code handle it
            return None

def get_session_json_matcher():
    from src.core.data.json_matcher import JSONMatcher
    excel_processor = get_session_excel_processor()
    if excel_processor is None:
        logging.error("Cannot create JSONMatcher: ExcelProcessor is None")
        return None
    
    # Use a global JSON matcher instance to persist the cache
    if not hasattr(app, '_json_matcher'):
        app._json_matcher = JSONMatcher(excel_processor)
    else:
        # Update the Excel processor reference in case it changed
        app._json_matcher.excel_processor = excel_processor
    
    return app._json_matcher

@app.route('/api/status', methods=['GET'])
def api_status():
    """Check API server status and data loading status."""
    try:
        excel_processor = get_session_excel_processor()
        if excel_processor is None:
            return jsonify({
                'server': 'running',
                'data_loaded': False,
                'data_shape': None,
                'last_loaded_file': None,
                'selected_tags_count': 0,
                'error': 'Unable to initialize data processor'
            })
        
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
        # --- LIGHTWEIGHT PAGE LOAD (minimal work) ---
        cache_bust = str(int(time.time()))
        
        # Only clear session data, don't reset global state
        uploaded_file = session.pop('file_path', None)
        # Don't clear selected_tags - they should persist across page loads
        
        # Remove uploaded file if it exists and is not the default file
        if uploaded_file:
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if uploaded_file != default_file and os.path.exists(uploaded_file):
                try:
                    os.remove(uploaded_file)
                except Exception:
                    pass
        
        # Periodic cleanup (less frequent - every 50th page load)
        import random
        if random.random() < 0.02:  # 2% chance to run cleanup
            try:
                cleanup_result = cleanup_old_files()
                if cleanup_result['success'] and cleanup_result['removed_count'] > 0:
                    logging.info(f"Auto-cleanup removed {cleanup_result['removed_count']} files")
            except Exception as cleanup_error:
                logging.warning(f"Auto-cleanup failed: {cleanup_error}")
        
        # Don't load data here - let frontend load via API calls
        # This makes page loads much faster
        initial_data = None
        
        return render_template('index.html', initial_data=initial_data, cache_bust=cache_bust)
        
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', error=str(e), cache_bust=str(int(time.time())))

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
        # Check disk space before processing upload
        disk_ok, disk_message = check_disk_space()
        if not disk_ok:
            # Perform emergency cleanup
            emergency_cleanup()
            # Check again after cleanup
            disk_ok, disk_message = check_disk_space()
            if not disk_ok:
                return jsonify({'error': f'Insufficient disk space: {disk_message}. Please free up some space and try again.'}), 507
        
        # Rate limiting for uploads (more restrictive)
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({'error': 'Rate limit exceeded. Please wait before uploading another file.'}), 429
        
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
        
        # Sanitize filename to prevent path traversal (security fix)
        sanitized_filename = sanitize_filename(file.filename)
        if not sanitized_filename:
            logging.error(f"Invalid filename after sanitization: {file.filename}")
            return jsonify({'error': 'Invalid filename'}), 400
        
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
        
        # Use sanitized filename (security fix)
        temp_path = os.path.join(upload_folder, sanitized_filename)
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
        logging.info(f"[UPLOAD] Setting processing status for: {file.filename}")
        update_processing_status(file.filename, 'processing')
        logging.info(f"[UPLOAD] Processing status set. Current statuses: {dict(processing_status)}")
        
        # ALWAYS reset the Excel processor to ensure complete data replacement
        logging.info(f"[UPLOAD] Resetting Excel processor before loading new file: {sanitized_filename}")
        reset_excel_processor()
        
        # Start background thread with error handling
        try:
            thread = threading.Thread(target=process_excel_background, args=(file.filename, temp_path))
            thread.daemon = True  # Make thread daemon so it doesn't block app shutdown
            thread.start()
            logging.info(f"Background processing thread started for {file.filename}")
        except Exception as thread_error:
            logging.error(f"Failed to start background thread: {thread_error}")
            update_processing_status(file.filename, f'error: Failed to start processing')
            return jsonify({'error': 'Failed to start file processing'}), 500
        
        upload_time = time.time() - start_time
        logging.info(f"=== UPLOAD REQUEST COMPLETE === Time: {upload_time:.2f}s")
        # Store uploaded file path in session
        session['file_path'] = temp_path
        # Clear selected tags in session
        session['selected_tags'] = []
        return jsonify({'message': 'File uploaded, processing in background', 'filename': sanitized_filename})
    except Exception as e:
        logging.error(f"=== UPLOAD REQUEST FAILED ===")
        logging.error(f"Upload error: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        
        # Don't expose internal errors to client (security fix)
        if app.config.get('DEBUG', False):
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Upload failed. Please try again.'}), 500

def process_excel_background(filename, temp_path):
    """Optimized background processing - do minimal work initially, defer heavy processing"""
    try:
        logging.info(f"[BG] Starting optimized file processing: {temp_path}")
        
        # Set a timeout for the entire processing operation
        start_time = time.time()
        max_processing_time = 300  # 5 minutes max
        
        # Verify the file still exists before processing
        if not os.path.exists(temp_path):
            update_processing_status(filename, f'error: File not found at {temp_path}')
            logging.error(f"[BG] File not found: {temp_path}")
            return
        
        # Step 1: Load the file directly without using force_reload_excel_processor
        # This avoids potential race conditions with global variables
        load_start = time.time()
        
        # Add timeout check
        if time.time() - start_time > max_processing_time:
            update_processing_status(filename, f'error: Processing timeout during file load')
            logging.error(f"[BG] Processing timeout for {filename}")
            return
        
        # Create a new ExcelProcessor instance directly
        from src.core.data.excel_processor import ExcelProcessor
        new_processor = ExcelProcessor()
        
        # Disable product database integration for faster loading
        if hasattr(new_processor, 'enable_product_db_integration'):
            new_processor.enable_product_db_integration(False)
            logging.info("[BG] Product database integration disabled for upload performance")
        
        # Load the file
        success = new_processor.load_file(temp_path)
        load_time = time.time() - load_start
        
        if not success:
            update_processing_status(filename, f'error: Failed to load file data')
            logging.error(f"[BG] File load failed for {filename}")
            return
        
        # Verify the load was successful
        if new_processor.df is None or new_processor.df.empty:
            update_processing_status(filename, f'error: Failed to load file data - DataFrame is empty')
            logging.error(f"[BG] File load failed for {filename} - DataFrame is empty")
            return
        
        # Step 2: Update the global processor safely
        global _excel_processor
        with excel_processor_lock:
            # Clear the old processor
            if _excel_processor is not None:
                # Explicitly clear all data from old processor
                if hasattr(_excel_processor, 'df') and _excel_processor.df is not None:
                    del _excel_processor.df
                    logging.info("[BG] Cleared old DataFrame from ExcelProcessor")
                
                if hasattr(_excel_processor, 'selected_tags'):
                    _excel_processor.selected_tags = []
                    logging.info("[BG] Cleared selected tags from ExcelProcessor")
                
                if hasattr(_excel_processor, 'dropdown_cache'):
                    _excel_processor.dropdown_cache = {}
                    logging.info("[BG] Cleared dropdown cache from ExcelProcessor")
                
                # Force garbage collection
                import gc
                gc.collect()
                logging.info("[BG] Forced garbage collection to free memory")
            
            # Replace with the new processor
            _excel_processor = new_processor
            _excel_processor._last_loaded_file = temp_path
            logging.info(f"[BG] Global Excel processor updated with new file: {temp_path}")
        
        # Clear any cached data
        clear_initial_data_cache()
        
        # Clear Flask cache for available tags to force refresh
        try:
            cache_key = get_session_cache_key('available_tags')
            cache.delete(cache_key)
            logging.info(f"[BG] Cleared cache for key: {cache_key}")
        except Exception as cache_error:
            logging.warning(f"[BG] Error clearing cache: {cache_error}")
        
        logging.info(f"[BG] File loaded successfully in {load_time:.2f}s")
        logging.info(f"[BG] DataFrame shape after load: {_excel_processor.df.shape if _excel_processor.df is not None else 'None'}")
        logging.info(f"[BG] DataFrame empty after load: {_excel_processor.df.empty if _excel_processor.df is not None else 'N/A'}")
        logging.info(f"[BG] New file loaded: {temp_path}")
        logging.info(f"[BG] Replaced previous file: {getattr(_excel_processor, '_last_loaded_file', 'None')}")
        
        # Step 3: Add a small delay to ensure frontend has time to start polling
        time.sleep(1)
        
        # Step 4: Mark as ready for basic operations
        logging.info(f"[BG] Marking file as ready: {filename}")
        update_processing_status(filename, 'ready')
        logging.info(f"[BG] File marked as ready: {filename}")
        logging.info(f"[BG] Current processing statuses: {dict(processing_status)}")
        
        # Step 5: Keep the status as 'ready' for a longer period to prevent race conditions
        # Don't immediately clear the status - let the frontend complete its operations
        # The status will be cleaned up by the periodic cleanup function
        
        total_time = time.time() - start_time
        logging.info(f"[BG] Background processing completed successfully in {total_time:.2f}s")
        
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

    # Auto-clear stuck processing statuses (older than 15 minutes) - less aggressive
    # Only run cleanup occasionally to avoid race conditions
    if random.random() < 0.05:  # Only cleanup 5% of the time
        current_time = time.time()
        cutoff_time = current_time - 900  # 15 minutes (increased from 10)
        
        with processing_lock:
            # Check for stuck processing statuses
            stuck_files = []
            for fname, status in list(processing_status.items()):
                timestamp = processing_timestamps.get(fname, 0)
                age = current_time - timestamp
                if age > cutoff_time and status == 'processing':
                    stuck_files.append(fname)
                    del processing_status[fname]
                    if fname in processing_timestamps:
                        del processing_timestamps[fname]
            
            if stuck_files:
                logging.warning(f"Auto-cleared {len(stuck_files)} stuck processing statuses: {stuck_files}")
    
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
    
    # If status is 'ready' and age is less than 30 seconds, don't clear it yet
    # This prevents race conditions where frontend is still polling
    if status == 'ready' and age < 30:
        logging.debug(f"Keeping 'ready' status for {filename} (age: {age:.1f}s)")
    
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
            
        if template_type not in ['horizontal', 'vertical', 'mini', 'double', 'inventory']:
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

        excel_processor = get_session_excel_processor()
        available_tags = excel_processor.get_available_tags()
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
                excel_processor.selected_tags = [tag['Product Name*'] for tag in available_tags]
            else:
                for tag in tags_to_move:
                    if tag not in excel_processor.selected_tags:
                        excel_processor.selected_tags.append(tag)
        else:  # to_available
            if select_all:
                excel_processor.selected_tags.clear()
            else:
                excel_processor.selected_tags = [tag for tag in excel_processor.selected_tags if tag not in tags_to_move]
        # Update session with new selected tags
        session['selected_tags'] = excel_processor.selected_tags.copy()
        updated_available = [tag for tag in available_tags if tag['Product Name*'] not in excel_processor.selected_tags]
        updated_selected = excel_processor.selected_tags.copy()
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
        excel_processor = get_session_excel_processor()
        selected_tags = []
        for tag in last_state['selected_tags']:
            if isinstance(tag, dict):
                selected_tags.append(tag.get('Product Name*', ''))
            elif isinstance(tag, str):
                selected_tags.append(tag)
            else:
                selected_tags.append(str(tag))
        excel_processor.selected_tags = selected_tags
        session['selected_tags'] = selected_tags.copy()
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
        excel_processor = get_session_excel_processor()
        excel_processor.selected_tags.clear()
        session['selected_tags'] = []
        session[UNDO_STACK_KEY] = []
        excel_processor.dropdown_cache = {}
        json_matcher = get_session_json_matcher()
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
    col_width_twips = str(int((3.4/3) * 1440))
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
        row.height = Inches(2.4)
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
        # Rate limiting for label generation
        client_ip = request.remote_addr
        if not check_rate_limit(client_ip):
            return jsonify({'error': 'Rate limit exceeded. Please wait before generating more labels.'}), 429
        
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
            # Validate that all selected tags exist in the loaded Excel data
            # Create case-insensitive lookup map for available product names
            available_product_names_lower = {}
            product_name_column = 'ProductName'  # The actual column name in the DataFrame
            if excel_processor.df is not None and product_name_column in excel_processor.df.columns:
                for _, row in excel_processor.df.iterrows():
                    # Handle pandas Series objects properly
                    product_name_value = row[product_name_column]
                    if isinstance(product_name_value, pd.Series):
                        product_name = str(product_name_value.iloc[0]).strip() if len(product_name_value) > 0 else ''
                    else:
                        product_name = str(product_name_value).strip()
                    if product_name and product_name != 'nan':
                        available_product_names_lower[product_name.lower()] = product_name  # Store original case
                
                logging.debug(f"Available product names count: {len(available_product_names_lower)}")
                logging.debug(f"Sample available product names: {list(available_product_names_lower.values())[:5]}")
                logging.debug(f"Using column: {product_name_column}")
            
            valid_selected_tags = []
            invalid_selected_tags = []
            
            logging.debug(f"Validating {len(selected_tags_from_request)} selected tags")
            for tag in selected_tags_from_request:
                tag_lower = tag.strip().lower()
                if tag_lower in available_product_names_lower:
                    # Use the original case from Excel data
                    original_case_tag = available_product_names_lower[tag_lower]
                    valid_selected_tags.append(original_case_tag)
                    logging.debug(f"Found tag '{tag}' -> using original case: '{original_case_tag}'")
                else:
                    invalid_selected_tags.append(tag.strip())
                    logging.warning(f"Selected tag not found in Excel data: '{tag}' (lowercase: '{tag_lower}')")
            
            if invalid_selected_tags:
                logging.warning(f"Removed {len(invalid_selected_tags)} invalid tags: {invalid_selected_tags}")
                if not valid_selected_tags:
                    return jsonify({'error': f'No valid tags selected. All selected tags ({len(invalid_selected_tags)}) do not exist in the loaded data. Please ensure you have selected tags that exist in the current Excel file.'}), 400
            
            # Store with original case from Excel data
            excel_processor.selected_tags = [tag.strip() for tag in valid_selected_tags]
            logging.debug(f"Updated excel_processor.selected_tags: {excel_processor.selected_tags}")
        else:
            logging.warning("No selected_tags provided in request body")
            return jsonify({'error': 'No tags selected. Please select at least one tag before generating labels.'}), 400
        
        # Get the fully processed records using the dedicated method
        print(f"DEBUG: About to call get_selected_records with selected_tags: {excel_processor.selected_tags}")
        print(f"DEBUG: DataFrame columns: {list(excel_processor.df.columns)}")
        print(f"DEBUG: DataFrame shape: {excel_processor.df.shape}")
        records = excel_processor.get_selected_records(template_type)
        print(f"DEBUG: get_selected_records returned {len(records) if records else 0} records")
        logging.debug(f"Records returned from get_selected_records: {len(records) if records else 0}")

        if not records:
            print(f"DEBUG: No records returned, returning error")
            logging.error("No selected tags found in the data or failed to process records.")
            return jsonify({'error': 'No selected tags found in the data or failed to process records. Please ensure you have selected tags and they exist in the loaded data.'}), 400

        # Use the already imported TemplateProcessor and get_font_scheme
        font_scheme = get_font_scheme(template_type)
        processor = TemplateProcessor(template_type, font_scheme, scale_factor)
        
        # The TemplateProcessor now handles all post-processing internally
        final_doc = processor.process_records(records)
        if final_doc is None:
            return jsonify({'error': 'Failed to generate document.'}), 500

        # Ensure all fonts are Arial Bold for consistency across platforms
        from src.core.generation.docx_formatting import enforce_arial_bold_all_text
        enforce_arial_bold_all_text(final_doc)

        # Save the final document to a buffer
        output_buffer = BytesIO()
        final_doc.save(output_buffer)
        output_buffer.seek(0)

        # Build a comprehensive informative filename
        today_str = datetime.now().strftime('%Y%m%d')
        time_str = datetime.now().strftime('%H%M%S')
        
        # Get template type and tag count
        template_display = {
            'horizontal': 'HORIZ',
            'vertical': 'VERT', 
            'mini': 'MINI',
            'double': 'DOUBLE'
        }.get(template_type, template_type.upper())
        
        tag_count = len(records)
        
        # Get vendor information from the processed records
        vendor_counts = {}
        product_type_counts = {}
        
        # Get most common lineage from processed records
        lineage_counts = {}
        for record in records:
            # Extract lineage from the wrapped marker format
            lineage_text = record.get('Lineage', '')
            if 'LINEAGE_START' in lineage_text and 'LINEAGE_END' in lineage_text:
                # Extract the actual lineage value from between the markers
                start_marker = 'LINEAGE_START'
                end_marker = 'LINEAGE_END'
                start_idx = lineage_text.find(start_marker) + len(start_marker)
                end_idx = lineage_text.find(end_marker)
                if start_idx != -1 and end_idx != -1:
                    lineage = lineage_text[start_idx:end_idx].strip().upper()
                else:
                    lineage = 'MIXED'
            else:
                lineage = str(lineage_text).strip().upper()
            
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
        
        # Count vendors and product types from processed records
        logging.info(f"Processing {len(records)} processed records for filename generation")
        for i, record in enumerate(records):
            logging.info(f"Record {i} keys: {list(record.keys())}")
            
            # Get vendor from ProductBrand field
            vendor = str(record.get('ProductBrand', '')).strip()
            logging.info(f"Record {i} ProductBrand: '{vendor}'")
            
            if vendor and vendor != 'Unknown' and vendor != '':
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
                logging.info(f"Added vendor '{vendor}' to counts")
            else:
                logging.warning(f"Record {i} has no valid ProductBrand found")
            
            # Get product type from ProductType field
            product_type = str(record.get('ProductType', '')).strip()
            logging.info(f"Record {i} ProductType: '{product_type}'")
            
            if product_type and product_type != 'Unknown' and product_type != '':
                product_type_counts[product_type] = product_type_counts.get(product_type, 0) + 1
                logging.info(f"Added product type '{product_type}' to counts")
            else:
                logging.warning(f"Record {i} has no valid ProductType found")
        
        # Get primary vendor and product type
        logging.info(f"Vendor counts: {vendor_counts}")
        logging.info(f"Product type counts: {product_type_counts}")
        
        primary_vendor = max(vendor_counts.items(), key=lambda x: x[1])[0] if vendor_counts else 'Unknown'
        primary_product_type = max(product_type_counts.items(), key=lambda x: x[1])[0] if product_type_counts else 'Unknown'
        
        logging.info(f"Selected primary vendor: '{primary_vendor}'")
        logging.info(f"Selected primary product type: '{primary_product_type}'")
        
        # Clean vendor name for filename
        vendor_clean = primary_vendor.replace(' ', '_').replace('&', 'AND').replace(',', '').replace('.', '')[:15]
        product_type_clean = primary_product_type.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')[:10]
        
        logging.info(f"Cleaned vendor name: '{vendor_clean}'")
        logging.info(f"Cleaned product type: '{product_type_clean}'")
        
        # Create simplified filename
        filename = f"AGT_{vendor_clean}_{template_display}_{tag_count}tags_{today_str}.docx"
        
        # Debug logging
        logging.info(f"Generated filename: {filename}")
        logging.info(f"Template type: {template_type}, Tag count: {tag_count}, Vendor: {primary_vendor}")
        logging.info(f"Available fields in first record: {list(records[0].keys()) if records else 'No records'}")
        logging.info(f"Sample record data: {records[0] if records else 'No records'}")

        # Create response with explicit headers
        response = send_file(
            output_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        # Ensure Content-Disposition header is set correctly
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        logging.info(f"Response headers: {dict(response.headers)}")
        
        return response

    except Exception as e:
        logging.error(f"Error during label generation: {str(e)}")
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
        
        # Get vendor information for filename
        vendor_counts = {}
        for _, row in filtered_df.iterrows():
            vendor = str(row.get('Vendor', 'Unknown')).strip()
            if vendor and vendor != 'Unknown':
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        
        primary_vendor = max(vendor_counts.items(), key=lambda x: x[1])[0] if vendor_counts else 'Unknown'
        vendor_clean = primary_vendor.replace(' ', '_').replace('&', 'AND').replace(',', '').replace('.', '')[:15]
        
        # Get current timestamp for filename
        today_str = datetime.now().strftime('%Y%m%d')
        time_str = datetime.now().strftime('%H%M%S')
        
        filename = f"AGT_{vendor_clean}_Transformed_Data_{len(selected_tags)}TAGS_{today_str}_{time_str}.xlsx"
        
        return send_file(
            output_stream,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logging.error(f"Error in download_transformed_excel: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_session_cache_key(base_key):
    # Use session id and actual loaded file path for cache isolation
    sid = session.get('_id', None) or session.sid if hasattr(session, 'sid') else None
    
    # Get the actual loaded file path from the Excel processor
    excel_processor = get_excel_processor()
    file_path = getattr(excel_processor, '_last_loaded_file', '')
    
    key_str = f"{base_key}:{sid}:{file_path}"
    return hashlib.sha256(key_str.encode()).hexdigest()

@app.route('/api/available-tags', methods=['GET'])
def get_available_tags():
    try:
        logging.info("=== AVAILABLE TAGS DEBUG START ===")
        
        cache_key = get_session_cache_key('available_tags')
        logging.info(f"Cache key: {cache_key}")
        
        cached_tags = cache.get(cache_key)
        if cached_tags is not None:
            logging.info(f"Returning cached tags: {len(cached_tags)} items")
            return jsonify(cached_tags)
        
        logging.info("No cached tags found, getting ExcelProcessor")
        excel_processor = get_session_excel_processor()
        if excel_processor is None:
            logging.error("Failed to get ExcelProcessor instance")
            return jsonify({'error': 'Server error: Unable to initialize data processor'}), 500
        
        logging.info(f"ExcelProcessor obtained: {excel_processor}")
        logging.info(f"DataFrame exists: {excel_processor.df is not None}")
        logging.info(f"DataFrame empty: {excel_processor.df.empty if excel_processor.df is not None else 'N/A'}")
        logging.info(f"DataFrame shape: {excel_processor.df.shape if excel_processor.df is not None else 'N/A'}")
        
        if excel_processor.df is None or excel_processor.df.empty:
            processing_files = [f for f, status in processing_status.items() if status == 'processing']
            logging.info(f"Processing files: {processing_files}")
            if processing_files:
                logging.info("File is still being processed, returning 202")
                return jsonify({'error': 'File is still being processed. Please wait...'}), 202
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
        
        logging.info("Getting available tags from ExcelProcessor")
        tags = excel_processor.get_available_tags()
        logging.info(f"Raw tags obtained: {len(tags)} items")
        
        import math
        def clean_dict(d):
            return {k: ('' if (v is None or (isinstance(v, float) and math.isnan(v))) else v) for k, v in d.items()}
        tags = [clean_dict(tag) for tag in tags]
        logging.info(f"Cleaned tags: {len(tags)} items")
        
        cache.set(cache_key, tags)
        logging.info(f"Cached tags with key: {cache_key}")
        
        try:
            json_matcher = get_session_json_matcher()
            if json_matcher and json_matcher.get_matched_names():
                matched_names = set(json_matcher.get_matched_names())
                original_count = len(tags)
                tags = [tag for tag in tags if tag['Product Name*'] not in matched_names]
                logging.info(f"Filtered out {original_count - len(tags)} tags due to JSON matches, {len(tags)} remaining")
        except Exception as json_error:
            logging.warning(f"Error processing JSON matcher: {json_error}")
        
        logging.info(f"Returning {len(tags)} available tags")
        logging.info("=== AVAILABLE TAGS DEBUG END ===")
        return jsonify(tags)
    except Exception as e:
        logging.error(f"Error getting available tags: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/selected-tags', methods=['GET'])
def get_selected_tags():
    try:
        excel_processor = get_session_excel_processor()
        if excel_processor is None:
            logging.error("Failed to get ExcelProcessor instance")
            return jsonify({'error': 'Server error: Unable to initialize data processor'}), 500
        
        if excel_processor.df is None or excel_processor.df.empty:
            processing_files = [f for f, status in processing_status.items() if status == 'processing']
            if processing_files:
                return jsonify({'error': 'File is still being processed. Please wait...'}), 202
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
        
        # Get the selected tag names
        selected_names = list(excel_processor.selected_tags)
        import math
        selected_names = ['' if (t is None or (isinstance(t, float) and math.isnan(t))) else t for t in selected_names]
        
        # Debug logging
        logging.info(f"Selected tags endpoint - selected_names: {selected_names}")
        logging.info(f"Excel processor selected_tags: {excel_processor.selected_tags}")
        
        # Convert to full tag objects
        tags = []
        for name in selected_names:
            if name:
                # First try to find in current tags (filtered view)
                found_tag = None
                if hasattr(excel_processor, 'df') and excel_processor.df is not None:
                    # Look for the tag in the DataFrame
                    # Try multiple possible column names
                    mask = None
                    possible_columns = ['ProductName', 'Product Name*', 'Product Name']
                    
                    for col in possible_columns:
                        if col in excel_processor.df.columns:
                            mask = excel_processor.df[col] == name
                            if mask.any():
                                break
                    
                    if mask.any():
                        # Convert the row to a dictionary
                        row = excel_processor.df[mask].iloc[0]
                        found_tag = row.to_dict()
                
                # If not found in DataFrame, create a minimal tag object
                if not found_tag:
                    found_tag = {
                        'Product Name*': name,
                        'Product Brand': 'Unknown',
                        'Vendor': 'Unknown',
                        'Product Type*': 'Unknown',
                        'Lineage': 'MIXED'
                    }
                
                tags.append(found_tag)
        
        return jsonify(tags)
    except Exception as e:
        logging.error(f"Error getting selected tags: {str(e)}")
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

        # Generate descriptive filename with vendor and record count
        today_str = datetime.now().strftime('%Y%m%d')
        time_str = datetime.now().strftime('%H%M%S')
        
        # Get vendor information for filename
        vendor_counts = {}
        for _, row in df.iterrows():
            vendor = str(row.get('Vendor', 'Unknown')).strip()
            if vendor and vendor != 'Unknown':
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        
        primary_vendor = max(vendor_counts.items(), key=lambda x: x[1])[0] if vendor_counts else 'Unknown'
        vendor_clean = primary_vendor.replace(' ', '_').replace('&', 'AND').replace(',', '').replace('.', '')[:15]
        
        filename = f"AGT_{vendor_clean}_Processed_Data_{len(df)}RECORDS_{today_str}_{time_str}.xlsx"

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
        logging.info(f"Looking for tag: '{tag_name}'")
        logging.info(f"Available columns: {list(excel_processor.df.columns)}")
        
        # Debug: Show some sample product names
        if 'ProductName' in excel_processor.df.columns:
            sample_names = excel_processor.df['ProductName'].head(10).tolist()
            logging.info(f"Sample ProductName values: {sample_names}")
        
        mask = excel_processor.df['ProductName'] == tag_name
        if not mask.any():
            # Try alternative column names
            logging.info(f"Tag not found in ProductName, trying Product Name*")
            mask = excel_processor.df['Product Name*'] == tag_name
            
        if not mask.any():
            logging.error(f"Tag '{tag_name}' not found in any product name column")
            return jsonify({'error': f'Tag "{tag_name}" not found'}), 404
            
        # Get the original lineage for logging - be explicit about boolean operations
        original_lineage = 'Unknown'
        if mask.any():
            try:
                original_lineage = excel_processor.df.loc[mask, 'Lineage'].iloc[0]
            except (IndexError, KeyError):
                original_lineage = 'Unknown'
        
        # Update the lineage
        excel_processor.df.loc[mask, 'Lineage'] = new_lineage
        
        # Also update the session excel processor if it exists
        session_excel_processor = get_session_excel_processor()
        if session_excel_processor and session_excel_processor.df is not None:
            session_mask = session_excel_processor.df['ProductName'] == tag_name
            if not session_mask.any():
                session_mask = session_excel_processor.df['Product Name*'] == tag_name
            if session_mask.any():
                try:
                    session_excel_processor.df.loc[session_mask, 'Lineage'] = new_lineage
                    logging.info(f"Updated lineage in session excel processor for tag '{tag_name}'")
                except Exception as session_error:
                    logging.warning(f"Failed to update session excel processor: {session_error}")
        
        # Save the changes back to the file
        try:
            # Get the current file path
            current_file = getattr(excel_processor, '_last_loaded_file', None)
            logging.info(f"Attempting to save lineage change. Current file: {current_file}")
            
            if current_file and os.path.exists(current_file):
                logging.info(f"File exists and is accessible: {current_file}")
                
                # Check if file is writable
                if os.access(current_file, os.W_OK):
                    logging.info(f"File is writable: {current_file}")
                    
                    # Save the updated DataFrame back to the file
                    excel_processor.df.to_excel(current_file, index=False)
                    logging.info(f"Successfully saved lineage change to file: {current_file}")
                    
                    # Verify the save by checking file modification time
                    mtime = os.path.getmtime(current_file)
                    logging.info(f"File modification time after save: {mtime}")
                else:
                    logging.error(f"File is NOT writable: {current_file}")
            else:
                logging.warning(f"Cannot save lineage change - no valid file path: {current_file}")
                if current_file:
                    logging.warning(f"File path exists: {os.path.exists(current_file)}")
        except Exception as save_error:
            logging.error(f"Error saving lineage change to file: {save_error}")
            logging.error(f"Full error details: {str(save_error)}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            # Continue anyway - the change is still in memory
        
        # Log the change
        logging.info(f"Updated lineage for tag '{tag_name}' from '{original_lineage}' to '{new_lineage}'")
        
        return jsonify({
            'success': True,
            'message': f'Updated lineage for {tag_name} from {original_lineage} to {new_lineage}'
        })
        
    except Exception as e:
        logging.error(f"Error updating lineage: {str(e)}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/filter-options', methods=['GET', 'POST'])
def get_filter_options():
    try:
        cache_key = get_session_cache_key('filter_options')
        
        # Always clear cache for weight filter to ensure updated formatting
        cache.delete(cache_key)
        
        excel_processor = get_session_excel_processor()
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
        
        # Debug: Log available columns and weight options
        if excel_processor.df is not None:
            logging.info(f"Available columns: {list(excel_processor.df.columns)}")
            if 'Weight*' in excel_processor.df.columns:
                sample_weights = excel_processor.df['Weight*'].head(5).tolist()
                logging.info(f"Sample Weight* values: {sample_weights}")
            if 'Units' in excel_processor.df.columns:
                sample_units = excel_processor.df['Units'].head(5).tolist()
                logging.info(f"Sample Units values: {sample_units}")
        
        # Log weight options for debugging
        if 'weight' in options:
            logging.info(f"Weight filter options: {options['weight'][:10]}...")  # Log first 10 options
        
        # Don't cache filter options to ensure fresh data
        return jsonify(options)
    except Exception as e:
        logging.error(f"Error in filter_options: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-weight-formatting', methods=['GET'])
def debug_weight_formatting():
    """Debug endpoint to test weight formatting directly."""
    try:
        excel_processor = get_session_excel_processor()
        if excel_processor.df is None or excel_processor.df.empty:
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if default_file and os.path.exists(default_file):
                logging.info(f"Attempting to load default file for debug-weight-formatting: {default_file}")
                success = excel_processor.load_file(default_file)
                if not success:
                    return jsonify({'error': 'Failed to load default file'}), 400
            else:
                return jsonify({'error': 'No default file found'}), 400
        
        # Test weight formatting on first few rows
        results = []
        for i, (_, row) in enumerate(excel_processor.df.head(10).iterrows()):
            row_dict = row.to_dict()
            weight_val = row_dict.get('Weight*', None)
            units_val = row_dict.get('Units', '')
            product_type = row_dict.get('Product Type*', '')
            formatted_weight = excel_processor._format_weight_units(row_dict)
            
            results.append({
                'row': i,
                'weight_val': weight_val,
                'units_val': units_val,
                'product_type': product_type,
                'formatted_weight': formatted_weight
            })
        
        return jsonify({
            'results': results,
            'available_columns': list(excel_processor.df.columns)
        })
    except Exception as e:
        logging.error(f"Error in debug_weight_formatting: {str(e)}")
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
            'dtypes': {col: str(dtype) for col, dtype in excel_processor.df.dtypes.to_dict().items()},
            'sample_data': {},
            'current_file': getattr(excel_processor, '_last_loaded_file', 'None'),
            'selected_tags_count': len(excel_processor.selected_tags) if hasattr(excel_processor, 'selected_tags') else 0
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

@app.route('/api/database-vendor-stats', methods=['GET'])
def database_vendor_stats():
    """Get detailed vendor and brand statistics from the product database."""
    try:
        import sqlite3
        
        product_db = get_product_database()
        
        with sqlite3.connect(product_db.db_path) as conn:
            # Get all vendors with their product counts
            vendors_df = pd.read_sql_query('''
                SELECT vendor, COUNT(*) as product_count, 
                       COUNT(DISTINCT brand) as unique_brands,
                       COUNT(DISTINCT product_type) as unique_product_types
                FROM products 
                WHERE vendor IS NOT NULL AND vendor != ''
                GROUP BY vendor
                ORDER BY product_count DESC
            ''', conn)
            
            # Get all brands with their product counts
            brands_df = pd.read_sql_query('''
                SELECT brand, COUNT(*) as product_count,
                       COUNT(DISTINCT vendor) as unique_vendors,
                       COUNT(DISTINCT product_type) as unique_product_types
                FROM products 
                WHERE brand IS NOT NULL AND brand != ''
                GROUP BY brand
                ORDER BY product_count DESC
            ''', conn)
            
            # Get all product types with their counts
            product_types_df = pd.read_sql_query('''
                SELECT product_type, COUNT(*) as product_count,
                       COUNT(DISTINCT vendor) as unique_vendors,
                       COUNT(DISTINCT brand) as unique_brands
                FROM products 
                WHERE product_type IS NOT NULL AND product_type != ''
                GROUP BY product_type
                ORDER BY product_count DESC
            ''', conn)
            
            # Get vendor-brand combinations
            vendor_brands_df = pd.read_sql_query('''
                SELECT vendor, brand, COUNT(*) as product_count,
                       COUNT(DISTINCT product_type) as unique_product_types
                FROM products 
                WHERE vendor IS NOT NULL AND vendor != '' 
                  AND brand IS NOT NULL AND brand != ''
                GROUP BY vendor, brand
                ORDER BY product_count DESC
            ''', conn)
            
            return jsonify({
                'vendors': vendors_df.to_dict('records'),
                'brands': brands_df.to_dict('records'),
                'product_types': product_types_df.to_dict('records'),
                'vendor_brands': vendor_brands_df.to_dict('records'),
                'summary': {
                    'total_vendors': len(vendors_df),
                    'total_brands': len(brands_df),
                    'total_product_types': len(product_types_df),
                    'total_vendor_brand_combinations': len(vendor_brands_df)
                }
            })
    except Exception as e:
        logging.error(f"Error getting vendor stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database-export', methods=['GET'])
def database_export():
    """Export the database to Excel."""
    try:
        # Check disk space before creating temporary files
        disk_ok, disk_message = check_disk_space()
        if not disk_ok:
            emergency_cleanup()
            disk_ok, disk_message = check_disk_space()
            if not disk_ok:
                return jsonify({'error': f'Insufficient disk space for export: {disk_message}'}), 507
        
        import tempfile
        import os
        
        product_db = get_product_database()
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()
        
        # Export database
        product_db.export_database(temp_file.name)
        
        # Send file with proper cleanup
        # Generate descriptive filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        response = send_file(
            temp_file.name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"AGT_Product_Database_{timestamp}.xlsx"
        )
        
        # Clean up the temporary file after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            except Exception as cleanup_error:
                logging.warning(f"Failed to cleanup temp file {temp_file.name}: {cleanup_error}")
        
        return response
        
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
    """Clear the initial data cache."""
    try:
        clear_initial_data_cache()
        
        # Also clear ExcelProcessor cache
        excel_processor = get_excel_processor()
        if hasattr(excel_processor, 'clear_file_cache'):
            excel_processor.clear_file_cache()
        
        return jsonify({'success': True, 'message': 'Cache cleared successfully'})
    except Exception as e:
        logging.error(f"Error clearing cache: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup-temp-files', methods=['POST'])
def cleanup_temp_files():
    """Clean up temporary files and test outputs."""
    try:
        import glob
        import os
        
        removed_count = 0
        removed_files = []
        
        # Files to remove
        files_to_remove = [
            # Database files
            "product_database.db",
            "product_database.db-wal", 
            "product_database.db-shm",
            
            # Test output files
            "test_double_debug_output.docx",
            "final_double_with_doh.docx",
            "fixed_multi_marker_test.docx",
            "test_productstrain_processed.docx",
            "test_productstrain.docx",
            "final_double_test.docx",
            "full_context_test.docx",
            "test_rendered.docx",
            "test_template.docx",
            "fixed_classic_double_test.docx",
            "classic_double_test.docx",
            "fixed_double_test.docx",
            "actual_double_test.docx",
            "smaller_doh_double_test.docx",
            "test_mini_5_records.docx",
            "test_mini_output.docx",
            
            # Log files
            "app.log",
            "error.log", 
            "test_output.log",
            
            # Temporary files
            "tempCodeRunnerFile.py",
            "reload.txt"
        ]
        
        # Remove specific files
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    removed_files.append(file_path)
                    removed_count += 1
                except Exception as e:
                    logging.warning(f"Failed to remove {file_path}: {e}")
        
        # Remove files matching patterns
        patterns_to_remove = [
            "test_*.docx",
            "*_test.docx",
            "test_*.py",
            "*.log"
        ]
        
        for pattern in patterns_to_remove:
            for file_path in glob.glob(pattern):
                if os.path.isfile(file_path) and file_path not in files_to_remove:
                    try:
                        os.remove(file_path)
                        removed_files.append(file_path)
                        removed_count += 1
                    except Exception as e:
                        logging.warning(f"Failed to remove {file_path}: {e}")
        
        # Clean cache directory (keep directory, remove contents)
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                file_path = os.path.join(cache_dir, file)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        removed_files.append(f"cache/{file}")
                        removed_count += 1
                    except Exception as e:
                        logging.warning(f"Failed to remove cache file {file_path}: {e}")
        
        # Clean output directory (keep directory, remove contents)
        output_dir = "output"
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        removed_files.append(f"output/{file}")
                        removed_count += 1
                    except Exception as e:
                        logging.warning(f"Failed to remove output file {file_path}: {e}")
        
        return jsonify({
            'success': True, 
            'message': f'Cleaned up {removed_count} temporary files',
            'removed_count': removed_count,
            'removed_files': removed_files
        })
    except Exception as e:
        logging.error(f"Error cleaning up temp files: {str(e)}")
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

@app.route('/api/temp-files-status', methods=['GET'])
def temp_files_status():
    """Get information about temporary files that can be cleaned up."""
    try:
        import glob
        import os
        
        temp_files = {
            'database_files': [],
            'test_files': [],
            'log_files': [],
            'cache_files': [],
            'output_files': [],
            'upload_files': []
        }
        
        # Check for database files
        db_files = ["product_database.db", "product_database.db-wal", "product_database.db-shm"]
        for file in db_files:
            if os.path.exists(file):
                size = os.path.getsize(file)
                temp_files['database_files'].append({
                    'name': file,
                    'size_bytes': size,
                    'size_mb': round(size / (1024 * 1024), 2)
                })
        
        # Check for test files
        test_patterns = ["test_*.docx", "*_test.docx", "test_*.py"]
        for pattern in test_patterns:
            for file_path in glob.glob(pattern):
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    temp_files['test_files'].append({
                        'name': file_path,
                        'size_bytes': size,
                        'size_mb': round(size / (1024 * 1024), 2)
                    })
        
        # Check for log files
        log_patterns = ["*.log", "app.log", "error.log", "test_output.log"]
        for pattern in log_patterns:
            for file_path in glob.glob(pattern):
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    temp_files['log_files'].append({
                        'name': file_path,
                        'size_bytes': size,
                        'size_mb': round(size / (1024 * 1024), 2)
                    })
        
        # Check cache directory
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                file_path = os.path.join(cache_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    temp_files['cache_files'].append({
                        'name': f"cache/{file}",
                        'size_bytes': size,
                        'size_mb': round(size / (1024 * 1024), 2)
                    })
        
        # Check output directory
        output_dir = "output"
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    temp_files['output_files'].append({
                        'name': f"output/{file}",
                        'size_bytes': size,
                        'size_mb': round(size / (1024 * 1024), 2)
                    })
        
        # Check uploads directory
        uploads_dir = "uploads"
        if os.path.exists(uploads_dir):
            for file in os.listdir(uploads_dir):
                if file.endswith('.xlsx'):
                    file_path = os.path.join(uploads_dir, file)
                    if os.path.isfile(file_path):
                        size = os.path.getsize(file_path)
                        temp_files['upload_files'].append({
                            'name': f"uploads/{file}",
                            'size_bytes': size,
                            'size_mb': round(size / (1024 * 1024), 2)
                        })
        
        # Calculate totals
        total_files = sum(len(files) for files in temp_files.values())
        total_size_bytes = sum(
            sum(file['size_bytes'] for file in files) 
            for files in temp_files.values()
        )
        total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
        
        return jsonify({
            'temp_files': temp_files,
            'summary': {
                'total_files': total_files,
                'total_size_bytes': total_size_bytes,
                'total_size_mb': total_size_mb
            }
        })
    except Exception as e:
        logging.error(f"Error getting temp files status: {str(e)}")
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
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        if not url.lower().startswith('http'):
            return jsonify({'error': 'Please provide a valid HTTP URL'}), 400
            
        excel_processor = get_session_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No Excel data loaded. Please upload an Excel file first.'}), 400
            
        json_matcher = get_session_json_matcher()
        
        # Rebuild cache with better error handling
        try:
            json_matcher.rebuild_sheet_cache()
        except Exception as cache_error:
            logging.error(f"Failed to rebuild sheet cache: {cache_error}")
            return jsonify({'error': f'Failed to build product cache: {str(cache_error)}'}), 500
            
        cache_status = json_matcher.get_sheet_cache_status()
        if cache_status == "Not built" or cache_status == "Empty":
            return jsonify({'error': f'Failed to build product cache: {cache_status}. Please ensure your Excel file has product data.'}), 400
            
        # Perform matching with timeout handling
        try:
            matched_tags = json_matcher.fetch_and_match(url)
        except Exception as match_error:
            logging.error(f"JSON matching failed: {match_error}")
            if "timeout" in str(match_error).lower():
                return jsonify({'error': 'JSON matching timed out. The dataset may be too large or the URL may be slow to respond.'}), 408
            elif "connection" in str(match_error).lower():
                return jsonify({'error': 'Failed to connect to the JSON URL. Please check the URL and try again.'}), 503
            else:
                return jsonify({'error': f'JSON matching failed: {str(match_error)}'}), 500
        
        if matched_tags:
            # Extract product names from the matched tags
            matched_names = []
            for tag in matched_tags:
                if isinstance(tag, dict):
                    name = tag.get("Product Name*") or tag.get("product_name") or tag.get("name")
                    if name and isinstance(name, str):
                        matched_names.append(name)
                elif isinstance(tag, str):
                    matched_names.append(tag)
            
            if matched_names:
                # Store with original case - the validation will handle case-insensitive matching
                excel_processor.selected_tags = [name.strip() for name in matched_names]
                session['selected_tags'] = excel_processor.selected_tags.copy()
                logging.info(f"Stored {len(excel_processor.selected_tags)} selected tags in session")
                logging.info(f"Session selected_tags: {session.get('selected_tags', [])}")
        else:
            matched_names = []
            
        # Get available tags from Excel processor
        available_tags = excel_processor.get_available_tags()
        
        # Add JSON matched tags to available tags if they're not already there
        if matched_tags:
            # Create a set of existing product names for quick lookup
            existing_names = {tag.get('Product Name*', '').lower() for tag in available_tags}
            
            # Process JSON tags - either add new ones or update existing ones
            for json_tag in matched_tags:
                json_name = json_tag.get('Product Name*', '').lower()
                if json_name:
                    # Check if this tag already exists in available_tags
                    existing_tag_index = None
                    for i, tag in enumerate(available_tags):
                        if tag.get('Product Name*', '').lower() == json_name:
                            existing_tag_index = i
                            break
                    
                    if existing_tag_index is not None:
                        # Update existing tag with JSON data (preserve Excel data but add JSON fields)
                        existing_tag = available_tags[existing_tag_index]
                        # Add any missing fields from JSON tag
                        for key, value in json_tag.items():
                            if key not in existing_tag or not existing_tag[key]:
                                existing_tag[key] = value
                        # Mark as JSON matched
                        existing_tag['Source'] = 'JSON Match'
                    else:
                        # Add new JSON tag
                        available_tags.append(json_tag)
                        existing_names.add(json_name)
                        
        # Get full tag objects for selected tags
        selected_tag_objects = []
        if matched_names:
            for name in matched_names:
                # Find the tag in available_tags
                for tag in available_tags:
                    if tag.get('Product Name*', '').lower() == name.lower():
                        selected_tag_objects.append(tag)
                        break
                else:
                    # If not found in available_tags, create a minimal tag object
                    selected_tag_objects.append({
                        'Product Name*': name,
                        'Product Brand': 'Unknown',
                        'Vendor': 'Unknown',
                        'Product Type*': 'Unknown',
                        'Lineage': 'MIXED'
                    })
        
        # Add debug logging for selected tags
        logging.info(f"JSON match response - matched_count: {len(matched_names)}, selected_tags_count: {len(selected_tag_objects)}")
        if selected_tag_objects:
            logging.info(f"Sample selected tags: {[tag.get('Product Name*', 'Unknown') for tag in selected_tag_objects[:3]]}")
        
        return jsonify({
            'success': True,
            'matched_count': len(matched_names),
            'matched_names': matched_names,
            'available_tags': available_tags,
            'selected_tags': selected_tag_objects,
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
            
        # Ensure all fonts are Arial Bold for consistency across platforms
        from src.core.generation.docx_formatting import enforce_arial_bold_all_text
        enforce_arial_bold_all_text(final_doc)
            
        # Save the final document to a buffer
        output_buffer = BytesIO()
        final_doc.save(output_buffer)
        output_buffer.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"AGT_Inventory_Slips_{timestamp}.docx"
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
            'json_matched_names': json_matcher.get_matched_names() or [],
            'performance_optimized': True,  # Indicate that performance optimizations are active
            'optimization_features': [
                'Indexed cache for O(1) lookups',
                'Vendor-based filtering',
                'Key term indexing',
                'Early termination for exact matches',
                'Candidate limiting to prevent O(n²) complexity'
            ]
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
    """Proxy JSON requests to avoid CORS issues and handle authentication."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        headers = data.get('headers', {})  # Allow custom headers for authentication
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.lower().startswith('http'):
            return jsonify({'error': 'Please provide a valid HTTP URL'}), 400
        
        import requests
        import json
        
        # Set default headers if none provided
        if not headers:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        
        # Add any additional headers from the request
        if 'Authorization' in data:
            headers['Authorization'] = data['Authorization']
        if 'X-API-Key' in data:
            headers['X-API-Key'] = data['X-API-Key']
        if 'X-Auth-Token' in data:
            headers['X-Auth-Token'] = data['X-Auth-Token']
        
        # Fetch the JSON from the external URL with custom headers
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        json_data = response.json()
        return jsonify(json_data)
        
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching JSON from {url}: {e.response.status_code}")
        return jsonify({'error': f'HTTP error: {e.response.status_code}', 'details': e.response.text}), e.response.status_code
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching JSON from {url}: {e}")
        return jsonify({'error': f'Request error: {str(e)}'}), 400
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
        
        # Also check if global Excel processor has data
        excel_processor_info = {
            'has_processor': _excel_processor is not None,
            'has_dataframe': _excel_processor.df is not None if _excel_processor else False,
            'dataframe_shape': _excel_processor.df.shape if _excel_processor and _excel_processor.df is not None else None,
            'dataframe_empty': _excel_processor.df.empty if _excel_processor and _excel_processor.df is not None else None,
            'last_loaded_file': getattr(_excel_processor, '_last_loaded_file', None) if _excel_processor else None
        }
        
        return jsonify({
            'current_time': current_time,
            'total_files': len(status_details),
            'statuses': status_details,
            'processing_files': [f for f, s in all_statuses.items() if s == 'processing'],
            'ready_files': [f for f, s in all_statuses.items() if s == 'ready'],
            'error_files': [f for f, s in all_statuses.items() if s.startswith('error')],
            'excel_processor': excel_processor_info
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
                # Clear all stuck processing statuses (older than 10 minutes)
                current_time = time.time()
                cutoff_time = current_time - 600  # 10 minutes
                
                stuck_files = []
                for fname, status in list(processing_status.items()):
                    timestamp = processing_timestamps.get(fname, 0)
                    age = current_time - timestamp
                    if age > cutoff_time and status == 'processing':
                        stuck_files.append(fname)
                        del processing_status[fname]
                        if fname in processing_timestamps:
                            del processing_timestamps[fname]
                
                if stuck_files:
                    logging.info(f"Cleared {len(stuck_files)} stuck processing statuses: {stuck_files}")
                    return jsonify({'message': f'Cleared {len(stuck_files)} stuck processing statuses', 'files': stuck_files})
                else:
                    # Clear all if no stuck files found
                    count = len(processing_status)
                    processing_status.clear()
                    processing_timestamps.clear()
                    logging.info(f"Cleared all upload statuses ({count} files)")
                    return jsonify({'message': f'Cleared all statuses ({count} files)'})
                
    except Exception as e:
        logging.error(f"Error clearing upload status: {e}")
        return jsonify({'error': str(e)}), 500

def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal attacks.
    Only allows alphanumeric characters, dots, hyphens, and underscores.
    """
    if not filename:
        return None
    
    # Remove any path separators and dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure it's not empty after sanitization
    if not sanitized:
        return None
    
    # Limit length to prevent issues
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:255-len(ext)] + ext
    
    return sanitized

def cleanup_old_files():
    """
    Clean up old files to stay within disk limits.
    Removes old uploaded files, output files, and rotates logs.
    """
    try:
        import glob
        import time
        from datetime import datetime, timedelta
        
        current_time = time.time()
        removed_count = 0
        removed_files = []
        
        # Define cleanup policies
        cleanup_policies = {
            'uploads': {
                'max_age_hours': 24,  # Keep uploads for 24 hours
                'max_files': 50,      # Keep max 50 upload files
                'pattern': 'uploads/*.xlsx'
            },
            'output': {
                'max_age_hours': 12,  # Keep outputs for 12 hours
                'max_files': 30,      # Keep max 30 output files
                'pattern': 'output/*.docx'
            },
            'cache': {
                'max_age_hours': 6,   # Keep cache for 6 hours
                'max_files': 100,     # Keep max 100 cache files
                'pattern': 'cache/*'
            },
            'logs': {
                'max_age_hours': 168, # Keep logs for 1 week
                'max_files': 10,      # Keep max 10 log files
                'pattern': 'logs/*.log'
            }
        }
        
        for category, policy in cleanup_policies.items():
            files = glob.glob(policy['pattern'])
            
            # Sort by modification time (oldest first)
            files_with_time = []
            for file_path in files:
                try:
                    mtime = os.path.getmtime(file_path)
                    files_with_time.append((file_path, mtime))
                except OSError:
                    continue
            
            files_with_time.sort(key=lambda x: x[1])  # Sort by modification time
            
            # Remove files based on age
            cutoff_time = current_time - (policy['max_age_hours'] * 3600)
            for file_path, mtime in files_with_time:
                if mtime < cutoff_time:
                    try:
                        os.remove(file_path)
                        removed_files.append(file_path)
                        removed_count += 1
                        logging.info(f"Cleaned up old {category} file: {file_path}")
                    except OSError as e:
                        logging.warning(f"Failed to remove {file_path}: {e}")
            
            # Remove excess files (keep only the newest ones)
            if len(files_with_time) > policy['max_files']:
                files_to_remove = files_with_time[:-policy['max_files']]  # Remove oldest files
                for file_path, _ in files_to_remove:
                    try:
                        os.remove(file_path)
                        removed_files.append(file_path)
                        removed_count += 1
                        logging.info(f"Cleaned up excess {category} file: {file_path}")
                    except OSError as e:
                        logging.warning(f"Failed to remove {file_path}: {e}")
        
        # Clean up temporary files
        temp_patterns = [
            '*.tmp',
            '*.temp',
            'temp_*',
            '*_temp_*'
        ]
        
        for pattern in temp_patterns:
            for file_path in glob.glob(pattern):
                if os.path.isfile(file_path):
                    try:
                        mtime = os.path.getmtime(file_path)
                        if current_time - mtime > 3600:  # Remove temp files older than 1 hour
                            os.remove(file_path)
                            removed_files.append(file_path)
                            removed_count += 1
                            logging.info(f"Cleaned up temp file: {file_path}")
                    except OSError as e:
                        logging.warning(f"Failed to remove temp file {file_path}: {e}")
        
        logging.info(f"Cleanup completed: removed {removed_count} files")
        return {
            'success': True,
            'removed_count': removed_count,
            'removed_files': removed_files
        }
        
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/api/cleanup', methods=['POST'])
def trigger_cleanup():
    """Manually trigger cleanup of old files."""
    try:
        result = cleanup_old_files()
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Cleanup completed: removed {result['removed_count']} files",
                'removed_count': result['removed_count'],
                'removed_files': result['removed_files']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
    except Exception as e:
        logging.error(f"Error triggering cleanup: {str(e)}")
        return jsonify({'error': 'Cleanup failed'}), 500

@app.route('/api/cleanup-status', methods=['GET'])
def cleanup_status():
    """Get information about files that can be cleaned up."""
    try:
        import glob
        
        file_info = {
            'uploads': [],
            'output': [],
            'cache': [],
            'logs': [],
            'temp': []
        }
        
        current_time = time.time()
        
        # Check uploads
        for file_path in glob.glob('uploads/*.xlsx'):
            try:
                mtime = os.path.getmtime(file_path)
                age_hours = (current_time - mtime) / 3600
                size = os.path.getsize(file_path)
                file_info['uploads'].append({
                    'name': os.path.basename(file_path),
                    'age_hours': round(age_hours, 1),
                    'size_mb': round(size / (1024 * 1024), 2)
                })
            except OSError:
                continue
        
        # Check outputs
        for file_path in glob.glob('output/*.docx'):
            try:
                mtime = os.path.getmtime(file_path)
                age_hours = (current_time - mtime) / 3600
                size = os.path.getsize(file_path)
                file_info['output'].append({
                    'name': os.path.basename(file_path),
                    'age_hours': round(age_hours, 1),
                    'size_mb': round(size / (1024 * 1024), 2)
                })
            except OSError:
                continue
        
        # Check cache
        for file_path in glob.glob('cache/*'):
            try:
                mtime = os.path.getmtime(file_path)
                age_hours = (current_time - mtime) / 3600
                size = os.path.getsize(file_path)
                file_info['cache'].append({
                    'name': os.path.basename(file_path),
                    'age_hours': round(age_hours, 1),
                    'size_mb': round(size / (1024 * 1024), 2)
                })
            except OSError:
                continue
        
        # Calculate totals
        total_files = sum(len(files) for files in file_info.values())
        total_size_mb = sum(
            sum(file['size_mb'] for file in files) 
            for files in file_info.values()
        )
        
        return jsonify({
            'file_info': file_info,
            'total_files': total_files,
            'total_size_mb': round(total_size_mb, 2)
        })
        
    except Exception as e:
        logging.error(f"Error getting cleanup status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring system status."""
    try:
        import psutil
        import os
        
        # Get disk usage
        disk_usage = psutil.disk_usage('.')
        disk_percent = (disk_usage.used / disk_usage.total) * 100
        
        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Check if Excel processor is working
        try:
            excel_processor = get_session_excel_processor()
            if excel_processor is None:
                data_loaded = False
                excel_processor_error = "Failed to initialize ExcelProcessor"
            else:
                data_loaded = excel_processor.df is not None and not excel_processor.df.empty
                excel_processor_error = None
        except Exception as e:
            data_loaded = False
            excel_processor_error = str(e)
        
        # Count files in various directories
        file_counts = {}
        for directory in ['uploads', 'output', 'cache', 'logs']:
            if os.path.exists(directory):
                try:
                    file_counts[directory] = len([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])
                except OSError:
                    file_counts[directory] = 0
            else:
                file_counts[directory] = 0
        
        # Calculate total disk usage from files
        total_file_size_mb = 0
        for directory in ['uploads', 'output', 'cache']:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        try:
                            total_file_size_mb += os.path.getsize(file_path) / (1024 * 1024)
                        except OSError:
                            pass
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'system': {
                'disk_usage_percent': round(disk_percent, 1),
                'disk_free_gb': round(disk_usage.free / (1024**3), 1),
                'memory_usage_percent': round(memory_percent, 1),
                'cpu_usage_percent': round(cpu_percent, 1)
            },
            'application': {
                'data_loaded': data_loaded,
                'data_shape': excel_processor.df.shape if data_loaded and excel_processor is not None else None,
                'selected_tags_count': len(excel_processor.selected_tags) if excel_processor is not None and hasattr(excel_processor, 'selected_tags') else 0,
                'excel_processor_error': excel_processor_error
            },
            'files': {
                'counts': file_counts,
                'total_size_mb': round(total_file_size_mb, 2)
            },
            'warnings': []
        }
        
        # Add warnings for potential issues
        if disk_percent > 80:
            health_status['warnings'].append('High disk usage')
            health_status['status'] = 'warning'
        
        if memory_percent > 80:
            health_status['warnings'].append('High memory usage')
            health_status['status'] = 'warning'
        
        if total_file_size_mb > 4000:  # 4GB threshold
            health_status['warnings'].append('Large file storage')
            health_status['status'] = 'warning'
        
        if not data_loaded:
            health_status['warnings'].append('No data loaded')
            health_status['status'] = 'warning'
        
        if excel_processor_error:
            health_status['warnings'].append(f'ExcelProcessor error: {excel_processor_error}')
            health_status['status'] = 'warning'
        
        return jsonify(health_status)
        
    except Exception as e:
        logging.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def check_rate_limit(ip_address):
    """Check if IP address is within rate limits."""
    current_time = time.time()
    
    # Clean old entries
    rate_limit_data[ip_address] = [
        req_time for req_time in rate_limit_data[ip_address]
        if current_time - req_time < RATE_LIMIT_WINDOW
    ]
    
    # Check if limit exceeded
    if len(rate_limit_data[ip_address]) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    # Add current request
    rate_limit_data[ip_address].append(current_time)
    return True

def get_rate_limit_info(ip_address):
    """Get rate limit information for an IP address."""
    current_time = time.time()
    
    # Clean old entries
    rate_limit_data[ip_address] = [
        req_time for req_time in rate_limit_data[ip_address]
        if current_time - req_time < RATE_LIMIT_WINDOW
    ]
    
    return {
        'requests_remaining': max(0, RATE_LIMIT_MAX_REQUESTS - len(rate_limit_data[ip_address])),
        'requests_used': len(rate_limit_data[ip_address]),
        'window_reset': current_time + RATE_LIMIT_WINDOW
    }

@app.route('/api/initial-data', methods=['GET'])
def get_initial_data():
    """Load initial data for the application (called by frontend after page load)."""
    try:
        # Get the default file
        from src.core.data.excel_processor import get_default_upload_file
        default_file = get_default_upload_file()
        
        if not default_file:
            return jsonify({
                'success': False,
                'message': 'No default file found'
            })
        
        # Load the file if not already loaded
        excel_processor = get_excel_processor()
        
        # Only load file if it's not already loaded or if it's a different file
        if (excel_processor.df is None or 
            not hasattr(excel_processor, '_last_loaded_file') or 
            excel_processor._last_loaded_file != default_file):
            
            logging.info(f"Loading default file: {os.path.basename(default_file)}")
            excel_processor.load_file(default_file)
            excel_processor._last_loaded_file = default_file
            
            # Reset state only when loading new file
            excel_processor.selected_tags = []
            excel_processor.dropdown_cache = {}
            # Clear any session-based selected tags
            if 'selected_tags' in session:
                session.pop('selected_tags', None)
        
        if excel_processor.df is not None:
            # Use the same logic as filter-options to get properly formatted weight values
            filters = excel_processor.get_dynamic_filter_options({})
            import math
            def clean_list(lst):
                return ['' if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in lst]
            filters = {k: clean_list(v) for k, v in filters.items()}
            
            initial_data = {
                'success': True,
                'filename': os.path.basename(default_file),
                'filepath': default_file,
                'columns': excel_processor.df.columns.tolist(),
                'filters': filters,  # Use the properly formatted filters
                'available_tags': excel_processor.get_available_tags(),
                'selected_tags': [],  # Don't restore selected tags on page reload
                'total_records': len(excel_processor.df)
            }
            logging.info(f"Initial data loaded: {len(initial_data['available_tags'])} tags, {initial_data['total_records']} records")
            return jsonify(initial_data)
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to load data'
            })
            
    except Exception as e:
        logging.error(f"Error loading initial data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add disk space checking function after the imports
import shutil

def check_disk_space():
    """Check available disk space and return warning if low."""
    try:
        total, used, free = shutil.disk_usage('.')
        free_gb = free / (1024**3)
        used_percent = (used / total) * 100
        
        if free_gb < 2.0:  # Less than 2GB free
            logging.warning(f"Low disk space: {free_gb:.1f}GB free ({used_percent:.1f}% used)")
            return False, f"Low disk space: {free_gb:.1f}GB free"
        elif free_gb < 5.0:  # Less than 5GB free
            logging.warning(f"Disk space getting low: {free_gb:.1f}GB free ({used_percent:.1f}% used)")
            return True, f"Disk space getting low: {free_gb:.1f}GB free"
        else:
            return True, f"Disk space OK: {free_gb:.1f}GB free"
    except Exception as e:
        logging.error(f"Error checking disk space: {e}")
        return True, "Unable to check disk space"

def emergency_cleanup():
    """Perform emergency cleanup when disk space is critically low."""
    try:
        import glob
        import os
        
        # Clean up old log files
        for log_file in glob.glob("*.log"):
            if os.path.getsize(log_file) > 1024 * 1024:  # Larger than 1MB
                with open(log_file, 'w') as f:
                    f.write("")  # Truncate to empty
                logging.info(f"Truncated large log file: {log_file}")
        
        # Clean up uploads directory (keep only recent files)
        uploads_dir = "uploads"
        if os.path.exists(uploads_dir):
            files = []
            for file in os.listdir(uploads_dir):
                if file.endswith('.xlsx'):
                    file_path = os.path.join(uploads_dir, file)
                    mtime = os.path.getmtime(file_path)
                    files.append((file_path, mtime))
            
            # Sort by modification time (oldest first)
            files.sort(key=lambda x: x[1])
            
            # Remove old files if we have more than 10
            if len(files) > 10:
                for file_path, _ in files[:-10]:  # Keep only the 10 most recent
                    try:
                        os.remove(file_path)
                        logging.info(f"Removed old upload file: {file_path}")
                    except Exception as e:
                        logging.warning(f"Failed to remove {file_path}: {e}")
        
        # Clean up any temporary files
        for pattern in ["*.tmp", "*.temp", "*~"]:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    logging.info(f"Removed temp file: {file_path}")
                except Exception as e:
                    logging.warning(f"Failed to remove temp file {file_path}: {e}")
                    
    except Exception as e:
        logging.error(f"Error during emergency cleanup: {e}")

if __name__ == '__main__':
    # Create and run the application
    label_maker = LabelMakerApp()
    label_maker.run()