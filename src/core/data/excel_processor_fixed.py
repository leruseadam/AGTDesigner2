import os
import re
import logging
import traceback
from typing import List, Optional, Dict, Any
from pathlib import Path
import pandas as pd
import datetime
from flask import send_file
from src.core.formatting.markers import wrap_with_marker, unwrap_marker
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from src.core.generation.text_processing import (
    format_cannabinoid_content,
    safe_get,
    safe_get_text,
    format_ratio_multiline,
    make_nonbreaking_hyphens,
)
from collections import OrderedDict
from src.core.constants import CLASSIC_TYPES, EXCLUDED_PRODUCT_TYPES, EXCLUDED_PRODUCT_PATTERNS
from src.core.utils.common import calculate_text_complexity

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add at the top of the file (after imports)
VALID_LINEAGES = [
    "SATIVA", "INDICA", "HYBRID", "HYBRID/SATIVA", "HYBRID/INDICA", "CBD", "MIXED", "PARAPHERNALIA"
]

# Performance optimization flags
ENABLE_STRAIN_SIMILARITY_PROCESSING = False  # Disable expensive strain similarity processing by default
ENABLE_FAST_LOADING = True

def get_default_upload_file() -> Optional[str]:
    """
    Returns the path to the default Excel file.
    Consistent across all platforms (Mac, PC, PythonAnywhere).
    Priority order:
    1. data/default_inventory.xlsx (project default)
    2. uploads/default_inventory.xlsx (project uploads)
    3. Most recent "A Greener Today" file in uploads directory
    4. Most recent "A Greener Today" file in Downloads (if accessible)
    """
    import os
    from pathlib import Path
    
    # Get the current working directory (should be the project root)
    current_dir = os.getcwd()
    logger.info(f"Current working directory: {current_dir}")
    
    # 1. First, look for the default inventory file in project directories
    default_inventory_paths = [
        os.path.join(current_dir, "data", "default_inventory.xlsx"),
        os.path.join(current_dir, "uploads", "default_inventory.xlsx"),
    ]
    
    for default_path in default_inventory_paths:
        if os.path.exists(default_path):
            logger.info(f"Found default inventory file: {default_path}")
            return default_path
    
    # 2. Look for "A Greener Today" files in uploads directory (consistent across platforms)
    uploads_dir = os.path.join(current_dir, "uploads")
    logger.info(f"Looking in uploads directory: {uploads_dir}")
    
    if os.path.exists(uploads_dir):
        logger.info(f"Uploads directory exists: {uploads_dir}")
        matching_files = []
        for filename in os.listdir(uploads_dir):
            if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                file_path = os.path.join(uploads_dir, filename)
                try:
                    mod_time = os.path.getmtime(file_path)
                    matching_files.append((file_path, mod_time))
                    logger.info(f"Found A Greener Today file: {filename} (modified: {mod_time})")
                except OSError as e:
                    logger.warning(f"Could not get modification time for {file_path}: {e}")
        
        if matching_files:
            # Sort by modification time (most recent first)
            matching_files.sort(key=lambda x: x[1], reverse=True)
            most_recent_file = matching_files[0][0]
            logger.info(f"Using most recent A Greener Today file from uploads: {most_recent_file}")
            return most_recent_file
    
    # 3. Look in Downloads directory (if accessible and not on PythonAnywhere)
    # Check if we're on PythonAnywhere by looking for specific paths
    is_pythonanywhere = (
        os.path.exists("/home/adamcordova") or 
        "pythonanywhere" in os.getcwd().lower() or
        os.path.exists("/var/www")
    )
    
    if not is_pythonanywhere:
        downloads_dir = os.path.join(str(Path.home()), "Downloads")
        logger.info(f"Looking in Downloads directory: {downloads_dir}")
        
        if os.path.exists(downloads_dir):
            matching_files = []
            try:
                for filename in os.listdir(downloads_dir):
                    if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                        file_path = os.path.join(downloads_dir, filename)
                        try:
                            mod_time = os.path.getmtime(file_path)
                            matching_files.append((file_path, mod_time))
                            logger.info(f"Found A Greener Today file in Downloads: {filename} (modified: {mod_time})")
                        except OSError as e:
                            logger.warning(f"Could not get modification time for {file_path}: {e}")
                
                if matching_files:
                    # Sort by modification time (most recent first)
                    matching_files.sort(key=lambda x: x[1], reverse=True)
                    most_recent_file = matching_files[0][0]
                    logger.info(f"Using most recent A Greener Today file from Downloads: {most_recent_file}")
                    return most_recent_file
            except PermissionError:
                logger.warning(f"Permission denied accessing Downloads directory: {downloads_dir}")
            except Exception as e:
                logger.warning(f"Error accessing Downloads directory: {e}")
    else:
        logger.info("Skipping Downloads directory check on PythonAnywhere")
    
    # 4. PythonAnywhere specific paths (fallback)
    pythonanywhere_paths = [
        "/home/adamcordova/uploads",
        "/home/adamcordova/AGTDesigner/uploads",
        "/home/adamcordova/AGTDesigner/AGTDesigner/uploads",
    ]
    
    for uploads_dir in pythonanywhere_paths:
        logger.info(f"Looking in PythonAnywhere uploads directory: {uploads_dir}")
        if os.path.exists(uploads_dir):
            logger.info(f"PythonAnywhere uploads directory exists: {uploads_dir}")
            matching_files = []
            try:
                for filename in os.listdir(uploads_dir):
                    if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                        file_path = os.path.join(uploads_dir, filename)
                        try:
                            mod_time = os.path.getmtime(file_path)
                            matching_files.append((file_path, mod_time))
                            logger.info(f"Found A Greener Today file in PythonAnywhere: {filename} (modified: {mod_time})")
                        except OSError as e:
                            logger.warning(f"Could not get modification time for {file_path}: {e}")
                
                if matching_files:
                    # Sort by modification time (most recent first)
                    matching_files.sort(key=lambda x: x[1], reverse=True)
                    most_recent_file = matching_files[0][0]
                    logger.info(f"Using most recent A Greener Today file from PythonAnywhere: {most_recent_file}")
                    return most_recent_file
            except PermissionError:
                logger.warning(f"Permission denied accessing PythonAnywhere directory: {uploads_dir}")
            except Exception as e:
                logger.warning(f"Error accessing PythonAnywhere directory: {e}")
    
    logger.warning("No default 'A Greener Today' file found in any location")
    return None 