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
    send_from_directory
)
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
from src.core.data.excel_processor import process_record
import time
from src.core.generation.mini_font_sizing import (
    get_mini_font_size_by_marker,
    set_mini_run_font_size
)

# Local imports - moved to lazy loading to speed up startup
# from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file, process_record
# from src.core.data.product_database import ProductDatabase
# from src.core.constants import DOCUMENT_CONSTANTS
# from src.core.generation.context_builders import (
#     process_chunk,
#     build_label_context,
# )
# from src.core.generation.docx_formatting import (
#     apply_lineage_colors,
#     enforce_ratio_formatting,
#     enforce_arial_bold_all_text,
#     create_3x3_grid,
#     enforce_fixed_cell_dimensions,
# )
# from src.core.generation.text_processing import (
#     format_ratio_multiline,
# )
# from src.core.generation.font_sizing import (
#     get_thresholded_font_size,
#     get_thresholded_font_size_ratio,
# )
# from src.core.formatting.markers import wrap_with_marker, FIELD_MARKERS, unwrap_marker, is_already_wrapped, MARKER_MAP
# from src.core.generation.template_processor import TemplateProcessor, get_font_scheme
# from src.core.generation.tag_generator import get_template_path

current_dir = os.path.dirname(os.path.abspath(__file__))

# Global variables for lazy loading
_excel_processor = None
_product_database = None
_json_matcher = None
_initial_data_cache = None
_cache_timestamp = None
CACHE_DURATION = 300  # Cache for 5 minutes

def get_excel_processor():
    """Lazy load ExcelProcessor to avoid startup delay."""
    global _excel_processor
    if _excel_processor is None:
        from src.core.data.excel_processor import ExcelProcessor
        _excel_processor = ExcelProcessor()
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

# Remove global get_excel_processor() initialization - now lazy loaded
# get_excel_processor() = ExcelProcessor()

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
        # Remove duplicate ExcelProcessor initialization - use lazy loading
        # self.get_excel_processor() = ExcelProcessor()
        self._configure_logging()
        
        # Load default Excel file if available - but do it lazily
        # default_file = get_default_upload_file()
        # if default_file:
        #     self.logger.info(f"Loading default file: {default_file}")
        excel_processor = get_excel_processor()
        #     if self.excel_processor.load_file(default_file):
        excel_processor = get_excel_processor()
        #         self.logger.info(f"Successfully loaded default file with {len(self.excel_processor.df)} tags")
        excel_processor = get_excel_processor()
        #         self.excel_processor.df["Product Brand"] = self.excel_processor.df["Product Brand"].str.strip().str.upper()
        excel_processor = get_excel_processor()
        #         print(self.excel_processor.df[self.excel_processor.df["Product Brand"].str.contains("incredibulk", case=False, na=False)])
        #     else:
        #         self.logger.warning("Failed to load default file")
        
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
        port = int(os.environ.get('FLASK_PORT', 5001))
        development_mode = self.app.config.get('DEVELOPMENT_MODE', False)
        
        logging.info(f"Starting Label Maker application on {host}:{port}")
        self.app.run(
            host=host, 
            port=port, 
            debug=development_mode, 
            use_reloader=development_mode
        )

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon."""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    try:
        # Check cache first
        cached_data = get_cached_initial_data()
        if cached_data:
            return render_template('index.html', initial_data=cached_data)
        
        # Lazy load the required modules
        from src.core.data.excel_processor import get_default_upload_file
        
        default_file = get_default_upload_file()
        initial_data = None
        if default_file:
            logging.info(f"Loading default file: {default_file}")
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
                    logging.info(f"Loaded default file with {len(initial_data['available_tags'])} tags")
            except Exception as e:
                logging.error(f"Error processing default file: {str(e)}")
        
        set_cached_initial_data(initial_data)
        return render_template('index.html', initial_data=initial_data)
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', error=str(e))

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
        if 'file' not in request.files:
            logging.error("No file uploaded")
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            logging.error("No file selected")
            return jsonify({'error': 'No file selected'}), 400
        if not file.filename.lower().endswith('.xlsx'):
            logging.error("Invalid file type")
            return jsonify({'error': 'Only .xlsx files are allowed'}), 400
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(temp_path)
        logging.info(f"File saved to {temp_path}")
        
        # Clear cache when new file is uploaded
        clear_initial_data_cache()
        
        try:
            excel_processor = get_excel_processor()
            prev_selected = set(excel_processor.selected_tags)
            excel_processor.load_file(temp_path)
            excel_processor._last_loaded_file = temp_path
            available_tags = excel_processor.get_available_tags()
            valid_selected = prev_selected.intersection(set(available_tags))
            excel_processor.selected_tags = valid_selected
            return jsonify({
                'message': 'File uploaded successfully',
                'filename': file.filename,
                'available_tags': available_tags,
                'selected_tags': list(valid_selected),
                'columns': excel_processor.df.columns.tolist(),
                'filters': excel_processor.dropdown_cache,
                'tag_count': len(available_tags)
            })
        finally:
            pass  # Do not delete the temp file here; keep it loaded in memory
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        selected_tags = excel_processor.selected_tags.copy()

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
        excel_processor.selected_tags = last_state['selected_tags'].copy()
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
    col_width_twips = str(int((3.5/3) * 1440))
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
    Get font size using the original font-sizing functions based on template type.
    """
    from src.core.generation.font_sizing import (
        get_thresholded_font_size,
        get_thresholded_font_size_ratio,
        get_thresholded_font_size_brand,
        get_thresholded_font_size_price,
        get_thresholded_font_size_lineage,
        get_thresholded_font_size_description,
        get_thresholded_font_size_strain
    )
    
    # Map marker names to field types for the original font-sizing functions
    marker_to_field_type = {
        'DESC': 'description',
        'PRODUCTBRAND_CENTER': 'brand',
        'PRICE': 'price',
        'LINEAGE': 'lineage',
        'THC_CBD': 'ratio',
        'RATIO': 'ratio',
        'PRODUCTSTRAIN': 'strain',
        'DOH': 'default'
    }
    
    field_type = marker_to_field_type.get(marker_name, 'default')
    
    # Use the appropriate original font-sizing function based on template type
    if orientation == 'mini':
        # For mini templates, use the original get_thresholded_font_size with 'mini' orientation
        if field_type == 'description':
            return get_thresholded_font_size_description(content, 'mini', scale_factor)
        elif field_type == 'brand':
            return get_thresholded_font_size_brand(content, 'mini', scale_factor)
        elif field_type == 'price':
            return get_thresholded_font_size_price(content, 'mini', scale_factor)
        elif field_type == 'lineage':
            return get_thresholded_font_size_lineage(content, 'mini', scale_factor)
        elif field_type == 'ratio':
            return get_thresholded_font_size_ratio(content, 'mini', scale_factor)
        elif field_type == 'strain':
            return get_thresholded_font_size_strain(content, 'mini', scale_factor)
        else:
            return get_thresholded_font_size(content, 'mini', scale_factor, field_type)
    
    elif orientation == 'vertical':
        # For vertical templates, use the original get_thresholded_font_size with 'vertical' orientation
        if field_type == 'description':
            return get_thresholded_font_size_description(content, 'vertical', scale_factor)
        elif field_type == 'brand':
            return get_thresholded_font_size_brand(content, 'vertical', scale_factor)
        elif field_type == 'price':
            return get_thresholded_font_size_price(content, 'vertical', scale_factor)
        elif field_type == 'lineage':
            return get_thresholded_font_size_lineage(content, 'vertical', scale_factor)
        elif field_type == 'ratio':
            return get_thresholded_font_size_ratio(content, 'vertical', scale_factor)
        elif field_type == 'strain':
            return get_thresholded_font_size_strain(content, 'vertical', scale_factor)
        else:
            return get_thresholded_font_size(content, 'vertical', scale_factor, field_type)
    
    else:  # horizontal
        # For horizontal templates, use the original get_thresholded_font_size with 'horizontal' orientation
        if field_type == 'description':
            return get_thresholded_font_size_description(content, 'horizontal', scale_factor)
        elif field_type == 'brand':
            return get_thresholded_font_size_brand(content, 'horizontal', scale_factor)
        elif field_type == 'price':
            return get_thresholded_font_size_price(content, 'horizontal', scale_factor)
        elif field_type == 'lineage':
            return get_thresholded_font_size_lineage(content, 'horizontal', scale_factor)
        elif field_type == 'ratio':
            return get_thresholded_font_size_ratio(content, 'horizontal', scale_factor)
        elif field_type == 'strain':
            return get_thresholded_font_size_strain(content, 'horizontal', scale_factor)
        else:
            return get_thresholded_font_size(content, 'horizontal', scale_factor, field_type)

@app.route('/api/generate', methods=['POST'])
def generate_labels():
    try:
        data = request.get_json()
        template_type = data.get('template_type', 'vertical')
        scale_factor = float(data.get('scale_factor', 1.0))
        selected_tags_from_request = data.get('selected_tags', [])
        
        logging.debug(f"Generation request - template_type: {template_type}, scale_factor: {scale_factor}")
        logging.debug(f"Selected tags from request: {selected_tags_from_request}")

        # Ensure data is loaded - try to reload default file if needed
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if default_file:
                excel_processor.load_file(default_file)
        
        excel_processor = get_excel_processor()
        if excel_processor.df is None or excel_processor.df.empty:
            logging.error("No data loaded in Excel processor")
            return jsonify({'error': 'No data loaded. Please upload an Excel file.'}), 400

        # Use selected tags from request body, this updates the processor's internal state
        if selected_tags_from_request:
            excel_processor.selected_tags = [tag.strip().lower() for tag in selected_tags_from_request]
            logging.debug(f"Updated excel_processor.selected_tags: {excel_processor.selected_tags}")
        
        # Get the fully processed records using the dedicated method
        excel_processor = get_excel_processor()
        print(f"DEBUG: About to call get_selected_records with selected_tags: {excel_processor.selected_tags}")
        excel_processor = get_excel_processor()
        records = excel_processor.get_selected_records(template_type)
        print(f"DEBUG: get_selected_records returned {len(records) if records else 0} records")
        logging.debug(f"Records returned from get_selected_records: {len(records) if records else 0}")

        if not records:
            print(f"DEBUG: No records returned, returning error")
            logging.error("No records returned from get_selected_records")
            return jsonify({'error': 'No selected tags found in the data or failed to process records.'}), 400

        font_scheme = get_font_scheme(template_type)
        processor = TemplateProcessor(template_type, font_scheme, scale_factor)
        
        # The TemplateProcessor now handles all post-processing internally
        final_doc = processor.process_records(records)
        if final_doc is None:
            return jsonify({'error': 'Failed to generate document.'}), 500

        # --- END CORE LOGIC ---

        # Save the final document to a buffer
        output_buffer = BytesIO()
        final_doc.save(output_buffer)
        output_buffer.seek(0)

        filename = f"generated_labels-{datetime.now().strftime('%Y-%m-%d_T%H%M%S%f')}.docx"
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
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            # Try to reload the default file if available
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if default_file:
                excel_processor.load_file(default_file)
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No Excel data loaded'}), 400
        excel_processor = get_excel_processor()
        tags = excel_processor.get_available_tags()
        
        # Check if there are JSON matches that should override the available tags
        json_matcher = get_json_matcher()
        if json_matcher.get_matched_names():
            # Filter out matched names from available tags
            matched_names = set(json_matcher.get_matched_names())
            tags = [tag for tag in tags if tag['Product Name*'] not in matched_names]
            
        return jsonify(tags)
    except Exception as e:
        logging.error(f"Error getting available tags: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/selected-tags', methods=['GET'])
def get_selected_tags():
    try:
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({'error': 'No Excel data loaded'}), 400
        excel_processor = get_excel_processor()
        tags = list(excel_processor.selected_tags)
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
        mask = excel_processor.df['ProductName'] == tag_name
        if not mask.any():
            # Try alternative column names
            mask = excel_processor.df['Product Name*'] == tag_name
            
        if not mask.any():
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
    """Get available filter options for dropdowns"""
    try:
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            # Try to reload the default file if available
            from src.core.data.excel_processor import get_default_upload_file
            default_file = get_default_upload_file()
            if default_file:
                excel_processor.load_file(default_file)
        
        excel_processor = get_excel_processor()
        if excel_processor.df is None:
            return jsonify({
                'vendor': [],
                'brand': [],
                'productType': [],
                'lineage': [],
                'weight': [],
                'strain': []
            })
        
        # Get current filters from request if it's a POST request
        current_filters = {}
        if request.method == 'POST':
            data = request.get_json()
            current_filters = data.get('filters', {})
        
        # Get filter options from the Excel processor
        excel_processor = get_excel_processor()
        options = excel_processor.get_dynamic_filter_options(current_filters)
        
        return jsonify(options)
        
    except Exception as e:
        logging.error(f"Error getting filter options: {str(e)}")
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
                columns_info['sample_data'][col] = excel_processor.df[col].head(3).tolist()
        
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
            
        # Get updated available tags (excluding matched ones)
        available_tags = excel_processor.get_available_tags()
        updated_available = [tag for tag in available_tags if tag['Product Name*'] not in matched_names]
        
        return jsonify({
            'success': True,
            'matched_count': len(matched_names),
            'matched_names': matched_names,
            'available_tags': updated_available,
            'selected_tags': matched_names,
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
        from src.core.generation.template_processor import TemplateProcessor
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

if __name__ == '__main__':
    # Create and run the application
    label_maker = LabelMakerApp()
    label_maker.run()