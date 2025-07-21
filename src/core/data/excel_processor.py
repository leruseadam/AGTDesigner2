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
from src.core.constants import CLASSIC_TYPES, EXCLUDED_PRODUCT_TYPES, EXCLUDED_PRODUCT_PATTERNS, TYPE_OVERRIDES
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
ENABLE_FAST_LOADING = True  # Enable fast loading mode by default

# Add this function after the imports at the top of the file
def handle_duplicate_columns(df):
    """Handle duplicate column names by adding suffixes to make them unique."""
    if df.columns.duplicated().any():
        # Get duplicate column names
        duplicated_cols = df.columns[df.columns.duplicated()].unique()
        for col in duplicated_cols:
            # Find all occurrences of this column
            col_indices = df.columns.get_loc(col)
            if isinstance(col_indices, slice):
                # Multiple columns with same name
                start, stop = col_indices.start, col_indices.stop
                for i in range(start, stop):
                    if i > start:  # Keep the first one as is
                        new_name = f"{col}_{i-start+1}"
                        df.columns.values[i] = new_name
            else:
                # Single column, but duplicated elsewhere
                pass
        
        # Reset index to ensure no duplicate labels
        df.reset_index(drop=True, inplace=True)
        
        # Log the changes
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Handled duplicate columns. Final columns: {df.columns.tolist()}")
    
    return df

def get_default_upload_file() -> Optional[str]:
    """
    Returns the path to the most recent "A Greener Today" Excel file.
    Searches multiple locations and returns the most recently modified file.
    """
    import os
    from pathlib import Path
    
    # Get the current working directory (should be the project root)
    current_dir = os.getcwd()
    print(f"Current working directory: {current_dir}")
    
    # Check if we're running on PythonAnywhere
    is_pythonanywhere = os.path.exists("/home/adamcordova") and "pythonanywhere" in current_dir.lower()
    
    # Define search locations
    search_locations = [
        os.path.join(current_dir, "uploads"),  # Local uploads directory
        os.path.join(str(Path.home()), "Downloads"),  # Downloads folder (local only)
    ]
    
    # Add PythonAnywhere specific paths
    if is_pythonanywhere:
        pythonanywhere_paths = [
            "/home/adamcordova/uploads",  # PythonAnywhere uploads directory
            "/home/adamcordova/AGTDesigner/uploads",  # Project-specific uploads
            "/home/adamcordova/AGTDesigner/AGTDesigner/uploads",  # Nested project structure
        ]
        search_locations.extend(pythonanywhere_paths)
    
    # Find all "A Greener Today" files
    agt_files = []
    
    for location in search_locations:
        if os.path.exists(location):
            print(f"Searching in: {location}")
            try:
                for filename in os.listdir(location):
                    if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                        file_path = os.path.join(location, filename)
                        if os.path.isfile(file_path):
                            mod_time = os.path.getmtime(file_path)
                            agt_files.append((file_path, filename, mod_time))
                            print(f"Found AGT file: {filename} (modified: {mod_time})")
            except Exception as e:
                print(f"Error searching {location}: {e}")
    
    if not agt_files:
        logger.warning("No 'A Greener Today' files found in any search location")
        return None
    
    # Sort by modification time (most recent first)
    agt_files.sort(key=lambda x: x[2], reverse=True)
    
    # Return the most recent file
    most_recent_file_path, most_recent_filename, most_recent_mod_time = agt_files[0]
    logger.info(f"Found most recent AGT file: {most_recent_filename} (modified: {most_recent_mod_time})")
    return most_recent_file_path

def _complexity(text):
    """Legacy complexity function - use calculate_text_complexity from common.py instead."""
    return calculate_text_complexity(text, 'standard')


def normalize_name(name):
    """Normalize product names for robust matching."""
    if not isinstance(name, str):
        return ""
    # Lowercase, strip, replace multiple spaces/hyphens, remove non-breaking hyphens, etc.
    name = name.lower().strip()
    name = name.replace('\u2011', '-')  # non-breaking hyphen to normal
    name = re.sub(r'[-\s]+', ' ', name)  # collapse hyphens and spaces
    name = re.sub(r'[^\w\s-]', '', name)  # remove non-alphanumeric except hyphen/space
    return name


def is_real_ratio(text: str) -> bool:
    """Check if a string represents a valid ratio format."""
    if not text or not isinstance(text, str):
        return False
    
    # Clean the text
    text = text.strip()
    
    # Check for common invalid values
    if text in ["", "CBD", "THC", "CBD:", "THC:", "CBD:\n", "THC:\n"]:
        return False
    
    # Check for mg values (e.g., "100mg", "500mg THC", "10mg CBD")
    if 'mg' in text.lower():
        return True
    
    # Check for ratio format with numbers and separators
    if any(c.isdigit() for c in text) and any(sep in text for sep in [":", "/", "-"]):
        return True
    
    # Check for specific cannabinoid patterns
    cannabinoid_patterns = [
        r'\b(?:THC|CBD|CBC|CBG|CBN)\b',
        r'\d+mg',
        r'\d+:\d+',
        r'\d+:\d+:\d+'
    ]
    
    for pattern in cannabinoid_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def is_weight_with_unit(text: str) -> bool:
    """Check if a string represents a weight with unit format (e.g., '1g', '3.5g', '1oz')."""
    if not text or not isinstance(text, str):
        return False
    
    # Clean the text
    text = text.strip()
    
    # Check for weight + unit patterns
    weight_patterns = [
        r'^\d+(?:\.\d+)?\s*(?:g|gram|grams|gm|oz|ounce|ounces)$',  # 1g, 3.5g, 1oz, etc.
        r'^\d+(?:\.\d+)?\s*(?:g|gram|grams|gm|oz|ounce|ounces)\s*$',  # with trailing space
    ]
    
    for pattern in weight_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False


def normalize_strain_name(strain):
    """Normalize strain names for accurate matching."""
    if not isinstance(strain, str):
        return ""
    
    # Convert to string and clean
    strain = str(strain).strip()
    
    # Skip invalid strains
    if not strain or strain.lower() in ['mixed', 'unknown', 'n/a', 'none', '']:
        return ""
    
    # Normalize the strain name
    strain = strain.lower()
    
    # Remove common prefixes/suffixes that don't affect strain identity
    strain = re.sub(r'^(strain|variety|cultivar)\s+', '', strain)
    strain = re.sub(r'\s+(strain|variety|cultivar)$', '', strain)
    
    # Normalize common abbreviations and variations
    strain = re.sub(r'\bog\b', 'og kush', strain)  # "OG" -> "OG Kush"
    strain = re.sub(r'\bblue\s*dream\b', 'blue dream', strain)
    strain = re.sub(r'\bwhite\s*widow\b', 'white widow', strain)
    strain = re.sub(r'\bpurple\s*haze\b', 'purple haze', strain)
    strain = re.sub(r'\bjack\s*herer\b', 'jack herer', strain)
    strain = re.sub(r'\bnorthern\s*lights\b', 'northern lights', strain)
    strain = re.sub(r'\bsour\s*diesel\b', 'sour diesel', strain)
    strain = re.sub(r'\bafghan\s*kush\b', 'afghan kush', strain)
    strain = re.sub(r'\bcheese\b', 'uk cheese', strain)
    strain = re.sub(r'\bamnesia\s*haze\b', 'amnesia haze', strain)
    
    # Remove extra spaces and normalize punctuation
    strain = re.sub(r'\s+', ' ', strain)
    strain = re.sub(r'[^\w\s-]', '', strain)  # Keep only alphanumeric, spaces, and hyphens
    
    return strain.strip()


def get_strain_similarity(strain1, strain2):
    """Calculate similarity between two strain names. Optimized for performance."""
    if not strain1 or not strain2:
        return 0.0
    
    # Fast exact match check first
    if strain1 == strain2:
        return 1.0
    
    norm1 = normalize_strain_name(strain1)
    norm2 = normalize_strain_name(strain2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Exact match after normalization
    if norm1 == norm2:
        return 1.0
    
    # Fast substring check (most common case)
    if norm1 in norm2 or norm2 in norm1:
        return 0.9
    
    # Only do expensive similarity calculation for very similar strings
    if abs(len(norm1) - len(norm2)) <= 3:  # Only compare strings of similar length
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, norm1, norm2).ratio()
        return similarity if similarity > 0.8 else 0.0  # Only return high similarity
    
    return 0.0


def group_similar_strains(strains, similarity_threshold=0.8):
    """Group similar strain names together. Optimized for performance."""
    if not strains:
        return {}
    
    # Fast path: if similarity processing is disabled, return empty groups
    if not ENABLE_STRAIN_SIMILARITY_PROCESSING:
        return {}
    
    # Limit the number of strains to process to avoid O(n²) complexity
    max_strains = 100  # Only process first 100 strains to avoid performance issues
    if len(strains) > max_strains:
        strains = list(strains)[:max_strains]
    
    # Normalize all strains
    normalized_strains = {}
    for strain in strains:
        norm = normalize_strain_name(strain)
        if norm:
            normalized_strains[strain] = norm
    
    # Group similar strains (optimized algorithm)
    groups = {}
    processed = set()
    
    # Sort strains by length to process shorter ones first (better for substring matching)
    sorted_strains = sorted(normalized_strains.items(), key=lambda x: len(x[1]))
    
    for strain1, norm1 in sorted_strains:
        if strain1 in processed:
            continue
            
        # Start a new group
        group_key = strain1
        groups[group_key] = [strain1]
        processed.add(strain1)
        
        # Find similar strains (only check unprocessed strains)
        for strain2, norm2 in sorted_strains:
            if strain2 in processed:
                continue
                
            # Fast similarity check
            similarity = get_strain_similarity(strain1, strain2)
            if similarity >= similarity_threshold:
                groups[group_key].append(strain2)
                processed.add(strain2)
    
    return groups


class ExcelProcessor:
    """Processes Excel files containing product data."""

    def __init__(self):
        self.df = None
        self.dropdown_cache = {}
        self.selected_tags = []
        self.logger = logger
        self._last_loaded_file = None
        self._file_cache = {}
        self._max_cache_size = 5  # Keep only 5 files in cache
        self._product_db_enabled = True  # Enable product database integration by default
        self._debug_count = 0  # Initialize debug count

    def clear_file_cache(self):
        """Clear the file cache to free memory."""
        self._file_cache.clear()
        self.logger.debug("File cache cleared")

    def _manage_cache_size(self):
        """Keep cache size under control."""
        if len(self._file_cache) > self._max_cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_keys = list(self._file_cache.keys())[:len(self._file_cache) - self._max_cache_size]
            for key in oldest_keys:
                del self._file_cache[key]
    
    def _schedule_product_db_integration(self):
        """Schedule product database integration in background to avoid blocking file load."""
        # Check if integration is enabled
        if not getattr(self, '_product_db_enabled', True):
            self.logger.debug("[ProductDB] Integration disabled, skipping background processing")
            return
            
        try:
            import threading
            import time
            
            def background_integration():
                """Background task for product database integration."""
                try:
                    # Add a small delay to ensure main file load completes first
                    time.sleep(0.1)
                    
                    from .product_database import ProductDatabase
                    product_db = ProductDatabase()
                    
                    # Process in batches for better performance
                    batch_size = 50
                    total_rows = len(self.df)
                    product_count = 0
                    strain_count = 0
                    
                    # Count classic types for logging
                    classic_types_count = sum(1 for _, row in self.df.iterrows() 
                                            if row.get('Product Type*', '').strip().lower() in [c.lower() for c in CLASSIC_TYPES])
                    self.logger.info(f"[ProductDB] Starting background integration for {total_rows} records ({classic_types_count} classic types for strain processing)...")
                    
                    for i in range(0, total_rows, batch_size):
                        batch_end = min(i + batch_size, total_rows)
                        batch_df = self.df.iloc[i:batch_end]
                        
                        # Process batch
                        for _, row in batch_df.iterrows():
                            row_dict = row.to_dict()
                            
                            # Only process classic types through the strain database
                            product_type = row_dict.get('Product Type*', '').strip().lower()
                            if product_type in [c.lower() for c in CLASSIC_TYPES]:
                                # Add or update strain (only if strain name exists)
                                strain_name = row_dict.get('Product Strain', '')
                                if strain_name and str(strain_name).strip():
                                    strain_id = product_db.add_or_update_strain(strain_name, row_dict.get('Lineage', ''))
                                    if strain_id:
                                        strain_count += 1
                                
                                # Add or update product
                                product_id = product_db.add_or_update_product(row_dict)
                                if product_id:
                                    product_count += 1
                            else:
                                # For non-classic types, only add/update the product (no strain processing)
                                product_id = product_db.add_or_update_product(row_dict)
                                if product_id:
                                    product_count += 1
                        
                        # Log progress for large files
                        if total_rows > 100:
                            progress = (batch_end / total_rows) * 100
                            self.logger.debug(f"[ProductDB] Progress: {progress:.1f}% ({batch_end}/{total_rows})")
                    
                    self.logger.info(f"[ProductDB] Background integration complete: {strain_count} strains processed, {product_count} products added/updated")
                    
                except Exception as e:
                    self.logger.error(f"[ProductDB] Background integration error: {e}")
            
            # Start background thread
            thread = threading.Thread(target=background_integration, daemon=True)
            thread.start()
            
        except Exception as e:
            self.logger.error(f"[ProductDB] Failed to schedule background integration: {e}")
    
    def enable_product_db_integration(self, enable: bool = True):
        """Enable or disable product database integration."""
        self._product_db_enabled = enable
        self.logger.info(f"[ProductDB] Integration {'enabled' if enable else 'disabled'}")
    
    def get_product_db_stats(self):
        """Get product database statistics."""
        try:
            from .product_database import ProductDatabase
            product_db = ProductDatabase()
            return product_db.get_performance_stats()
        except Exception as e:
            self.logger.error(f"[ProductDB] Error getting stats: {e}")
            return {}

    def fast_load_file(self, file_path: str) -> bool:
        """Fast file loading with minimal processing for uploads."""
        try:
            self.logger.debug(f"Fast loading file: {file_path}")
            
            # Validate file exists and is accessible
            import os
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                return False
            
            if not os.access(file_path, os.R_OK):
                self.logger.error(f"File not readable: {file_path}")
                return False
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                self.logger.error("File is empty")
                return False
            
            self.logger.info(f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
            
            # Clear previous data
            if hasattr(self, 'df') and self.df is not None:
                del self.df
                import gc
                gc.collect()
            
            # Try different Excel engines for better compatibility
            excel_engines = ['openpyxl']  # Start with openpyxl only for now
            df = None
            
            # First, try to read the file as bytes to see if it's accessible
            try:
                with open(file_path, 'rb') as f:
                    first_bytes = f.read(100)
                    self.logger.debug(f"File first 100 bytes: {first_bytes[:50]}...")
            except Exception as file_error:
                self.logger.error(f"Cannot read file as bytes: {file_error}")
                return False
            
            for engine in excel_engines:
                try:
                    self.logger.debug(f"Attempting to read with engine: {engine}")
                    df = pd.read_excel(file_path, engine=engine)
                    self.logger.info(f"Successfully read file with {engine} engine: {len(df)} rows, {len(df.columns)} columns")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to read with {engine} engine: {e}")
                    if engine == excel_engines[-1]:  # Last engine
                        self.logger.error(f"All Excel engines failed to read file: {file_path}")
                        return False
                    continue
            
            if df is None or df.empty:
                self.logger.error("No data found in Excel file")
                return False
            
            # Remove duplicates and reset index to avoid duplicate labels
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            df.reset_index(drop=True, inplace=True)  # Reset index to avoid duplicate labels
            final_count = len(df)
            if initial_count != final_count:
                self.logger.info(f"Removed {initial_count - final_count} duplicate rows")

            # Log all available columns for debugging
            self.logger.info(f"All columns in uploaded file: {df.columns.tolist()}")
            
            # Keep all columns but ensure required ones exist
            required_columns = [
                'Product Name*', 'ProductName', 'Description',
                'Product Type*', 'Lineage', 'Product Brand', 'Vendor/Supplier*',
                'Weight*', 'Weight Unit* (grams/gm or ounces/oz)', 'Units',
                'Price* (Tier Name for Bulk)', 'Price',
                'DOH Compliant (Yes/No)', 'DOH',
                'Concentrate Type', 'Ratio',
                'Joint Ratio', 'JointRatio',
                'Product Strain',
                'Quantity*', 'Quantity Received*', 'Quantity', 'qty'
            ]
            
            # Check which required columns are missing
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.warning(f"Missing required columns: {missing_columns}")
            
            # Keep all columns - don't filter them out
            # df = df[existing_required]  # REMOVED - this was causing column loss

            self.df = df
            self.logger.debug(f"Original columns: {self.df.columns.tolist()}")
            
            self._last_loaded_file = file_path
            self.logger.info(f"Fast load successful: {len(self.df)} rows, {len(self.df.columns)} columns")
            return True
                
        except Exception as e:
            self.logger.error(f"Error in fast_load_file: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Try to provide more specific error information
            if "No module named" in str(e):
                self.logger.error("Missing required module - this might be a dependency issue")
            elif "Permission denied" in str(e):
                self.logger.error("File permission issue - check file permissions")
            elif "Memory" in str(e):
                self.logger.error("Memory issue - file might be too large")
            return False

    def load_file(self, file_path: str) -> bool:
        """Load Excel file and prepare data exactly like MAIN.py. Enhanced for PythonAnywhere compatibility."""
        try:
            # Check if we've already loaded this exact file
            if (self._last_loaded_file == file_path and 
                self.df is not None and 
                not self.df.empty):
                self.logger.debug(f"File {file_path} already loaded, skipping reload")
                return True
            
            self.logger.debug(f"Loading file: {file_path}")
            
            # Validate file exists and is accessible
            import os
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                return False
            
            if not os.access(file_path, os.R_OK):
                self.logger.error(f"File not readable: {file_path}")
                return False
            
            # Check file size (PythonAnywhere has memory limits)
            file_size = os.path.getsize(file_path)
            max_size = 50 * 1024 * 1024  # 50MB limit for PythonAnywhere
            if file_size > max_size:
                self.logger.error(f"File too large for PythonAnywhere: {file_size} bytes (max: {max_size})")
                return False
            
            self.logger.info(f"File size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
            
            # Check file modification time for cache invalidation
            file_mtime = os.path.getmtime(file_path)
            cache_key = f"{file_path}_{file_mtime}"
            
            if cache_key in self._file_cache:
                self.logger.debug(f"Using cached data for {file_path}")
                self.df = self._file_cache[cache_key].copy()
                self._last_loaded_file = file_path
                return True
            
            # Clear previous data to free memory
            if hasattr(self, 'df') and self.df is not None:
                del self.df
                import gc
                gc.collect()
            
            # 1) Read & dedupe, force-key columns to string for .str ops
            # Use more conservative settings for PythonAnywhere
            dtype_dict = {
                "Product Type*": "string",
                "Lineage": "string",
                "Product Brand": "string",
                "Vendor": "string",
                "Weight Unit* (grams/gm or ounces/oz)": "string",
                "Product Name*": "string"
            }
            
            # Try different Excel engines for better compatibility
            excel_engines = ['openpyxl', 'xlrd']
            df = None
            
            for engine in excel_engines:
                try:
                    self.logger.debug(f"Attempting to read with engine: {engine}")
                    
                    # Use chunking for large files on PythonAnywhere
                    if file_size > 10 * 1024 * 1024:  # 10MB
                        self.logger.info("Large file detected, using chunked reading")
                        # Read in chunks to manage memory
                        chunk_size = 1000
                        chunks = []
                        
                        for chunk in pd.read_excel(file_path, engine=engine, dtype=dtype_dict, chunksize=chunk_size):
                            chunks.append(chunk)
                            self.logger.debug(f"Read chunk {len(chunks)} with {len(chunk)} rows")
                        
                        if chunks:
                            df = pd.concat(chunks, ignore_index=True)
                            self.logger.info(f"Successfully read {len(df)} rows in {len(chunks)} chunks")
                        else:
                            self.logger.error("No data found in file")
                            return False
                    else:
                        # For smaller files, read normally
                        df = pd.read_excel(file_path, engine=engine, dtype=dtype_dict)
                    
                    self.logger.info(f"Successfully read file with {engine} engine: {len(df)} rows, {len(df.columns)} columns")
                    break
                    
                except Exception as e:
                    self.logger.warning(f"Failed to read with {engine} engine: {e}")
                    if engine == excel_engines[-1]:  # Last engine
                        self.logger.error(f"All Excel engines failed to read file: {file_path}")
                        return False
                    continue
            
            if df is None or df.empty:
                self.logger.error("No data found in Excel file")
                return False
            
            # Handle duplicate columns before processing
            df = handle_duplicate_columns(df)
            
            # Remove duplicates and reset index to avoid duplicate labels
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            df.reset_index(drop=True, inplace=True)  # Reset index to avoid duplicate labels
            final_count = len(df)
            if initial_count != final_count:
                self.logger.info(f"Removed {initial_count - final_count} duplicate rows")

            # Log all available columns for debugging
            self.logger.info(f"All columns in uploaded file: {df.columns.tolist()}")
            
            # Keep all columns but ensure required ones exist
            required_columns = [
                'Product Name*', 'ProductName', 'Description',
                'Product Type*', 'Lineage', 'Product Brand', 'Vendor/Supplier*',
                'Weight*', 'Weight Unit* (grams/gm or ounces/oz)', 'Units',
                'Price* (Tier Name for Bulk)', 'Price',
                'DOH Compliant (Yes/No)', 'DOH',
                'Concentrate Type', 'Ratio',
                'Joint Ratio', 'JointRatio',
                'Product Strain',
                'Quantity*', 'Quantity Received*', 'Quantity', 'qty'
            ]
            
            # Check which required columns are missing
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.warning(f"Missing required columns: {missing_columns}")
            
            # Keep all columns - don't filter them out
            # df = df[existing_required]  # REMOVED - this was causing column loss

            self.df = df
            # Handle duplicate columns before any operations
            self.df = handle_duplicate_columns(self.df)
            # Reset index immediately after assignment to prevent duplicate labels
            self.df.reset_index(drop=True, inplace=True)
            self.logger.debug(f"Original columns: {self.df.columns.tolist()}")
            
            # 2) Trim product names
            if "Product Name*" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name*"].str.lstrip()
            elif "Product Name" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name"].str.lstrip()
            elif "ProductName" in self.df.columns:
                self.df["Product Name*"] = self.df["ProductName"].str.lstrip()
            else:
                self.logger.error("No product name column found")
                self.df["Product Name*"] = "Unknown"

            # 3) Ensure required columns exist
            for col in ["Product Type*", "Lineage", "Product Brand"]:
                if col not in self.df.columns:
                    self.df[col] = "Unknown"

            # 3.5) Determine product name column early (needed for lineage processing)
            product_name_col = 'Product Name*'
            if product_name_col not in self.df.columns:
                product_name_col = 'ProductName' if 'ProductName' in self.df.columns else None

            # 4) Exclude sample rows and deactivated products
            initial_count = len(self.df)
            excluded_by_type = self.df[self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            self.df = self.df[~self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            # Reset index after filtering to prevent duplicate labels
            self.df.reset_index(drop=True, inplace=True)
            self.logger.info(f"Excluded {len(excluded_by_type)} products by product type: {excluded_by_type['Product Type*'].unique().tolist()}")
            
            # Also exclude products with excluded patterns in the name
            for pattern in EXCLUDED_PRODUCT_PATTERNS:
                pattern_mask = self.df["Product Name*"].str.contains(pattern, case=False, na=False)
                excluded_by_pattern = self.df[pattern_mask]
                self.df = self.df[~pattern_mask]
                if len(excluded_by_pattern) > 0:
                    self.logger.info(f"Excluded {len(excluded_by_pattern)} products containing pattern '{pattern}': {excluded_by_pattern['Product Name*'].tolist()}")
            
            # Reset index after all filtering to prevent duplicate labels
            self.df.reset_index(drop=True, inplace=True)
            final_count = len(self.df)
            self.logger.info(f"Product filtering complete: {initial_count} -> {final_count} products (excluded {initial_count - final_count})")

            # 5) Rename for convenience (only if target columns don't already exist)
            rename_mapping = {}
            if "Product Name*" in self.df.columns and "ProductName" not in self.df.columns:
                rename_mapping["Product Name*"] = "ProductName"
            if "Weight Unit* (grams/gm or ounces/oz)" in self.df.columns and "Units" not in self.df.columns:
                rename_mapping["Weight Unit* (grams/gm or ounces/oz)"] = "Units"
            if "Price* (Tier Name for Bulk)" in self.df.columns and "Price" not in self.df.columns:
                rename_mapping["Price* (Tier Name for Bulk)"] = "Price"
            if "Vendor/Supplier*" in self.df.columns and "Vendor" not in self.df.columns:
                rename_mapping["Vendor/Supplier*"] = "Vendor"
            if "DOH Compliant (Yes/No)" in self.df.columns and "DOH" not in self.df.columns:
                rename_mapping["DOH Compliant (Yes/No)"] = "DOH"
            if "Concentrate Type" in self.df.columns and "Ratio" not in self.df.columns:
                rename_mapping["Concentrate Type"] = "Ratio"
            
            if rename_mapping:
                self.df.rename(columns=rename_mapping, inplace=True)

            # Handle duplicate columns after renaming
            self.df = handle_duplicate_columns(self.df)

            # 5.5) Normalize product types using TYPE_OVERRIDES
            if "Product Type*" in self.df.columns:
                self.logger.info("Applying product type normalization...")
                # First trim whitespace from product types
                self.df["Product Type*"] = self.df["Product Type*"].str.strip()
                # Apply TYPE_OVERRIDES to normalize product types
                self.df["Product Type*"] = self.df["Product Type*"].replace(TYPE_OVERRIDES)
                self.logger.info(f"Product type normalization complete. Sample types: {self.df['Product Type*'].unique()[:10].tolist()}")

            # Update product_name_col after renaming
            if product_name_col == 'Product Name*':
                product_name_col = 'ProductName'

            # 6) Normalize units
            if "Units" in self.df.columns:
                self.df["Units"] = self.df["Units"].str.lower().replace(
                    {"ounces": "oz", "grams": "g"}, regex=True
                )

            # 7) Standardize Lineage
            # Reset index before lineage processing to prevent duplicate labels
            self.df.reset_index(drop=True, inplace=True)
            if "Lineage" in self.df.columns:
                self.logger.info("Starting lineage standardization process...")
                # First, standardize existing values
                self.df["Lineage"] = (
                    self.df["Lineage"]
                    .str.lower()
                    .replace({
                        "indica_hybrid": "HYBRID/INDICA",
                        "sativa_hybrid": "HYBRID/SATIVA",
                        "sativa": "SATIVA",
                        "hybrid": "HYBRID",
                        "indica": "INDICA",
                        "cbd": "CBD"
                    })
                    .str.upper()
                )
                
                # For classic types, set empty lineage to HYBRID
                # For non-classic types, set empty lineage to MIXED or CBD based on content
                from src.core.constants import CLASSIC_TYPES
                
                # Create mask for classic types
                classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(CLASSIC_TYPES)
                
                # Set empty lineage values based on product type
                empty_lineage_mask = self.df["Lineage"].isnull() | (self.df["Lineage"].astype(str).str.strip() == "")
                
                # For classic types, set to HYBRID
                classic_empty_mask = classic_mask & empty_lineage_mask
                if classic_empty_mask.any():
                    self.df.loc[classic_empty_mask, "Lineage"] = "HYBRID"
                
                # For non-classic types, check for CBD content first
                non_classic_empty_mask = ~classic_mask & empty_lineage_mask
                if non_classic_empty_mask.any():
                    # Define edible types
                    edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                    
                    # Create mask for edible products
                    edible_mask = self.df["Product Type*"].str.strip().str.lower().isin(edible_types)
                    
                    # For edibles, be more conservative about CBD lineage assignment
                    if edible_mask.any():
                        # Only assign CBD lineage to edibles if they are explicitly CBD-focused
                        cbd_edible_mask = (
                            (self.df["Product Type*"].str.strip().str.lower() == "high cbd edible liquid") |
                            (self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend") |
                            (self.df[product_name_col].str.contains(r"\bCBD\b", case=False, na=False) if product_name_col else False)
                        )
                        
                        # Edibles with explicit CBD focus get CBD lineage
                        cbd_edible_empty = non_classic_empty_mask & edible_mask & cbd_edible_mask
                        if cbd_edible_empty.any():
                            self.df.loc[cbd_edible_empty, "Lineage"] = "CBD"
                            self.logger.info(f"Assigned CBD lineage to {cbd_edible_empty.sum()} CBD-focused edible products")
                        
                        # All other edibles get MIXED lineage
                        non_cbd_edible_empty = non_classic_empty_mask & edible_mask & ~cbd_edible_mask
                        if non_cbd_edible_empty.any():
                            self.df.loc[non_cbd_edible_empty, "Lineage"] = "MIXED"
                            self.logger.info(f"Assigned MIXED lineage to {non_cbd_edible_empty.sum()} edible products")
                    
                    # For non-edible non-classic types, use the original logic
                    non_edible_mask = ~edible_mask
                    non_edible_empty = non_classic_empty_mask & non_edible_mask
                    if non_edible_empty.any():
                        # Check if non-edible non-classic products contain CBD-related content
                        cbd_content_mask = (
                            self.df["Description"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) |
                            (self.df[product_name_col].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) if product_name_col else False) |
                            (self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend")
                        )
                        
                        # Non-edible non-classic products with CBD content get CBD lineage
                        cbd_non_edible_empty = non_edible_empty & cbd_content_mask
                        if cbd_non_edible_empty.any():
                            self.df.loc[cbd_non_edible_empty, "Lineage"] = "CBD"
                        
                        # Non-edible non-classic products without CBD content get MIXED lineage
                        non_cbd_non_edible_empty = non_edible_empty & ~cbd_content_mask
                        if non_cbd_non_edible_empty.any():
                            self.df.loc[non_cbd_non_edible_empty, "Lineage"] = "MIXED"

            # 8) Build Description & Ratio & Strain
            if "ProductName" in self.df.columns:
                self.logger.debug("Building Description and Ratio columns")

                def get_description(name):
                    # Handle pandas Series and other non-string types
                    if name is None:
                        return ""
                    if isinstance(name, pd.Series):
                        if pd.isna(name).any():
                            return ""
                        name = name.iloc[0] if len(name) > 0 else ""
                    elif pd.isna(name):
                        return ""
                    name = str(name).strip()
                    if not name:
                        return ""
                    if ' by ' in name:
                        return name.split(' by ')[0].strip()
                    if ' - ' in name:
                        # Take all parts before the last hyphen
                        return name.rsplit(' - ', 1)[0].strip()
                    return name.strip()

                # Ensure Product Name* is string type before applying
                if product_name_col:
                    # Reset index to avoid duplicate labels before applying operations
                    self.df.reset_index(drop=True, inplace=True)
                    
                    # Ensure we get a Series, not a DataFrame
                    if isinstance(product_name_col, list):
                        product_name_col = product_name_col[0] if product_name_col else None
                    
                    if product_name_col and product_name_col in self.df.columns:
                        self.df[product_name_col] = self.df[product_name_col].astype(str)
                        # Ensure we get a Series by using .iloc[:, 0] if it's a DataFrame
                        product_names = self.df[product_name_col]
                        if isinstance(product_names, pd.DataFrame):
                            product_names = product_names.iloc[:, 0]
                        product_names = product_names.astype(str)
                        # Debug: Check if product_names is a Series or DataFrame
                        self.logger.debug(f"product_names type: {type(product_names)}, shape: {getattr(product_names, 'shape', 'N/A')}")
                        
                        # Ensure product_names is a Series before calling .str
                        if isinstance(product_names, pd.Series):
                            # Only overwrite Description if it's empty or null
                            empty_desc_mask = self.df["Description"].isnull() | (self.df["Description"].astype(str).str.strip() == "")
                            self.df.loc[empty_desc_mask, "Description"] = product_names.loc[empty_desc_mask].str.strip()
                        else:
                            # Fallback: convert to string and strip manually
                            empty_desc_mask = self.df["Description"].isnull() | (self.df["Description"].astype(str).str.strip() == "")
                            self.df.loc[empty_desc_mask, "Description"] = product_names.astype(str).str.strip()
                        # Handle ' by ' pattern
                        mask_by = self.df["Description"].str.contains(' by ', na=False)
                        self.df.loc[mask_by, "Description"] = self.df.loc[mask_by, "Description"].str.split(' by ').str[0].str.strip()
                        # Handle ' - ' pattern, but preserve weight for classic types
                        mask_dash = self.df["Description"].str.contains(' - ', na=False)
                        # Don't remove weight for classic types (including rso/co2 tankers)
                        classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"]
                        classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(classic_types)
                        
                        # Only remove weight for non-classic types
                        non_classic_dash_mask = mask_dash & ~classic_mask
                        self.df.loc[non_classic_dash_mask, "Description"] = self.df.loc[non_classic_dash_mask, "Description"].str.rsplit(' - ', n=1).str[0].str.strip()
                    else:
                        # Fallback to empty descriptions
                        self.df["Description"] = ""
                    
                    # Reset index again after operations to prevent duplicate labels
                    self.df.reset_index(drop=True, inplace=True)
                
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
                self.df.loc[mask_para, "Description"] = (
                    self.df.loc[mask_para, "Description"]
                    .str.replace(r"\s*-\s*\d+g$", "", regex=True)
                )

                # Calculate complexity for Description column using vectorized operations
                # Reset index before applying to prevent duplicate labels
                self.df.reset_index(drop=True, inplace=True)
                # Use a safer approach for applying the complexity function
                try:
                    self.df["Description_Complexity"] = self.df["Description"].apply(_complexity)
                except Exception as e:
                    self.logger.warning(f"Error applying complexity function: {e}")
                    # Fallback: create a simple complexity based on length
                    self.df["Description_Complexity"] = self.df["Description"].str.len().fillna(0)
                # Reset index after apply operation to prevent duplicate labels
                self.df.reset_index(drop=True, inplace=True)

                # Build cannabinoid content info
                self.logger.debug("Extracting cannabinoid content from Product Name")
                # Extract text following the FINAL hyphen only, but not for classic types
                if product_name_col:
                    # Ensure we get a Series, not a DataFrame
                    product_names_for_ratio = self.df[product_name_col]
                    if isinstance(product_names_for_ratio, pd.DataFrame):
                        product_names_for_ratio = product_names_for_ratio.iloc[:, 0]
                    
                    # Don't extract weight for classic types (including rso/co2 tankers)
                    # Note: capsules are NOT classic types for ratio extraction - they should extract ratio like edibles
                    classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"]
                    classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(classic_types)
                    
                    # Extract ratio for non-classic types only (including capsules)
                    # For classic types, preserve existing ratio values from the file
                    non_classic_mask = ~classic_mask
                    if non_classic_mask.any():
                        extracted_ratios = product_names_for_ratio.loc[non_classic_mask].str.extract(r".*-\s*(.+)").fillna("")
                        # Ensure we get the first column as a Series
                        if isinstance(extracted_ratios, pd.DataFrame):
                            extracted_ratios = extracted_ratios.iloc[:, 0]
                        self.df.loc[non_classic_mask, "Ratio"] = extracted_ratios
                else:
                    self.df["Ratio"] = ""
                self.logger.debug(f"Sample cannabinoid content values before processing: {self.df['Ratio'].head()}")
                
                # Replace "/" with space to remove backslash formatting
                self.df["Ratio"] = self.df["Ratio"].str.replace(r"/", " ", regex=True)
                
                # Replace "nan" values with empty string to trigger default THC: CBD: formatting
                self.df["Ratio"] = self.df["Ratio"].replace("nan", "")
                
                self.logger.debug(f"Sample cannabinoid content values after processing: {self.df['Ratio'].head()}")

                # Set Ratio_or_THC_CBD based on product type
                def set_ratio_or_thc_cbd(row):
                    product_type = str(row.get("Product Type*", "")).strip().lower()
                    ratio = str(row.get("Ratio", "")).strip()
                    
                    # Handle "nan" values by replacing with empty string
                    if ratio.lower() == "nan":
                        ratio = ""
                    
                    classic_types = [
                        "flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"
                    ]
                    # Note: capsules are NOT classic types for ratio processing - they should be treated as edibles
                    BAD_VALUES = {"", "CBD", "THC", "CBD:", "THC:", "CBD:\n", "THC:\n", "nan"}
                    
                    # For pre-rolls and infused pre-rolls, use JointRatio if available, otherwise default format
                    if product_type in ["pre-roll", "infused pre-roll"]:
                        joint_ratio = str(row.get("JointRatio", "")).strip()
                        if joint_ratio and joint_ratio not in BAD_VALUES:
                            # Remove leading dash if present
                            if joint_ratio.startswith("- "):
                                joint_ratio = joint_ratio[2:]
                            return joint_ratio
                        return "THC:|BR|CBD:"
                    
                    # For solventless concentrate, check if ratio is a weight + unit format
                    if product_type == "solventless concentrate":
                        if not ratio or ratio in BAD_VALUES or not is_weight_with_unit(ratio):
                            return "1g"
                        return ratio
                    
                    if product_type in classic_types:
                        if not ratio or ratio in BAD_VALUES:
                            return "THC:|BR|CBD:"
                        # If ratio contains THC/CBD values, use it directly
                        if any(cannabinoid in ratio.upper() for cannabinoid in ['THC', 'CBD', 'CBC', 'CBG', 'CBN']):
                            return ratio
                        # If it's a valid ratio format, use it
                        if is_real_ratio(ratio):
                            return ratio
                        # If it's a weight format (like "1g", "28g"), use it
                        if is_weight_with_unit(ratio):
                            return ratio
                        # Otherwise, use default THC:CBD format
                        return "THC:|BR|CBD:"
                    
                    # For Edibles, Topicals, Tinctures, etc., use the ratio if it contains cannabinoid content
                    edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                    if product_type in edible_types:
                        if not ratio or ratio in BAD_VALUES:
                            return "THC:|BR|CBD:"
                        # If ratio contains cannabinoid content, use it
                        if any(cannabinoid in ratio.upper() for cannabinoid in ['THC', 'CBD', 'CBC', 'CBG', 'CBN']):
                            return ratio
                        # If it's a weight format, use it
                        if is_weight_with_unit(ratio):
                            return ratio
                        # Otherwise, use default THC:CBD format
                        return "THC:|BR|CBD:"
                    
                    # For any other product type, return the ratio as-is
                    return ratio

                # Reset index before applying to prevent duplicate labels
                self.df.reset_index(drop=True, inplace=True)
                # Use a safer approach for applying the ratio function
                try:
                    self.df["Ratio_or_THC_CBD"] = self.df.apply(set_ratio_or_thc_cbd, axis=1)
                except Exception as e:
                    self.logger.warning(f"Error applying ratio function: {e}")
                    # Fallback: use default values
                    self.df["Ratio_or_THC_CBD"] = "THC:|BR|CBD:"
                # Reset index after apply operation to prevent duplicate labels
                self.df.reset_index(drop=True, inplace=True)
                self.logger.debug(f"Ratio_or_THC_CBD values: {self.df['Ratio_or_THC_CBD'].head()}")

                # Ensure Product Strain exists and is categorical
                if "Product Strain" not in self.df.columns:
                    self.df["Product Strain"] = ""
                # Fill null values before converting to categorical
                self.df["Product Strain"] = self.df["Product Strain"].fillna("Mixed")
                # Don't convert to categorical yet - wait until after all Product Strain logic is complete

                # Special case: paraphernalia gets Product Strain set to "Paraphernalia"
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
                if mask_para.any():
                    # Only convert to categorical if there's actually paraphernalia
                    if "Product Strain" not in self.df.columns:
                        self.df["Product Strain"] = pd.Categorical([], categories=["Paraphernalia"])
                    else:
                        if isinstance(self.df["Product Strain"].dtype, pd.CategoricalDtype):
                            if "Paraphernalia" not in self.df["Product Strain"].cat.categories:
                                self.df["Product Strain"] = self.df["Product Strain"].cat.add_categories(["Paraphernalia"])
                        else:
                            # Ensure no null values before creating categorical
                            product_strain_clean = self.df["Product Strain"].fillna("Mixed")
                            unique_values = product_strain_clean.unique().tolist()
                            if "Paraphernalia" not in unique_values:
                                unique_values.append("Paraphernalia")
                            self.df["Product Strain"] = pd.Categorical(
                                product_strain_clean,
                                categories=unique_values
                            )
                    # Set paraphernalia products to "Paraphernalia"
                    self.df.loc[mask_para, "Product Strain"] = "Paraphernalia"

                # Force CBD Blend for any ratio containing CBD, CBC, CBN or CBG
                mask_cbd_ratio = self.df["Ratio"].str.contains(
                    r"\b(?:CBD|CBC|CBN|CBG)\b", case=False, na=False
                )
                # Use .any() to avoid Series boolean ambiguity
                if mask_cbd_ratio.any():
                    self.df.loc[mask_cbd_ratio, "Product Strain"] = "CBD Blend"
                    # Debug: Log which products got CBD Blend from ratio
                    cbd_products = self.df[mask_cbd_ratio]
                    for idx, row in cbd_products.iterrows():
                        self.logger.info(f"Assigned CBD Blend from ratio: {row.get('Product Name*', 'NO NAME')} (Type: {row.get('Product Type*', 'NO TYPE')})")
                
                # If Description contains ":" or "CBD", set Product Strain to 'CBD Blend' (excluding edibles which have their own logic)
                edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                non_edible_mask = ~self.df["Product Type*"].str.strip().str.lower().isin(edible_types)
                
                mask_cbd_blend = (self.df["Description"].str.contains(":", na=False) | self.df["Description"].str.contains("CBD", case=False, na=False)) & non_edible_mask
                # Use .any() to avoid Series boolean ambiguity
                if mask_cbd_blend.any():
                    self.df.loc[mask_cbd_blend, "Product Strain"] = "CBD Blend"
                    # Debug: Log which products got CBD Blend from description
                    cbd_desc_products = self.df[mask_cbd_blend]
                    for idx, row in cbd_desc_products.iterrows():
                        self.logger.info(f"Assigned CBD Blend from description: {row.get('Product Name*', 'NO NAME')} (Type: {row.get('Product Type*', 'NO TYPE')})")
                
                # NEW: If no strain in column, check if product contains CBD CBN CBG or CBC, or a ":" in description
                # This applies when Product Strain is empty, null, or "Mixed" (excluding edibles which have their own logic)
                no_strain_mask = (
                    self.df["Product Strain"].isnull() | 
                    (self.df["Product Strain"].astype(str).str.strip() == "") |
                    (self.df["Product Strain"].astype(str).str.lower().str.strip() == "mixed")
                )
                
                # Check if description contains cannabinoids or ":"
                cannabinoid_mask = (
                    self.df["Description"].str.contains(r"\b(?:CBD|CBC|CBN|CBG)\b", case=False, na=False) |
                    self.df["Description"].str.contains(":", na=False)
                )
                
                # Apply CBD Blend to non-edible products with no strain that contain cannabinoids or ":"
                combined_cbd_mask = no_strain_mask & cannabinoid_mask & non_edible_mask
                if combined_cbd_mask.any():
                    self.df.loc[combined_cbd_mask, "Product Strain"] = "CBD Blend"
                    # Debug: Log which products got CBD Blend from combined logic
                    combined_cbd_products = self.df[combined_cbd_mask]
                    for idx, row in combined_cbd_products.iterrows():
                        self.logger.info(f"Assigned CBD Blend from combined logic: {row.get('Product Name*', 'NO NAME')} (Type: {row.get('Product Type*', 'NO TYPE')})")
                
                # Debug: Log final Product Strain values for RSO/CO2 Tankers
                rso_co2_mask = self.df["Product Type*"].str.strip().str.lower() == "rso/co2 tankers"
                if rso_co2_mask.any():
                    rso_co2_products = self.df[rso_co2_mask]
                    self.logger.info(f"=== RSO/CO2 Tankers Product Strain Debug ===")
                    for idx, row in rso_co2_products.iterrows():
                        self.logger.info(f"RSO/CO2 Tanker: {row.get('Product Name*', 'NO NAME')} -> Product Strain: '{row.get('Product Strain', 'NO STRAIN')}'")
                    self.logger.info(f"=== End RSO/CO2 Tankers Debug ===")
                
                # RSO/CO2 Tankers: if Description contains CBD, CBG, CBC, CBN, or ":", then Product Strain is "CBD Blend", otherwise "Mixed"
                rso_co2_mask = self.df["Product Type*"].str.strip().str.lower() == "rso/co2 tankers"
                if rso_co2_mask.any():
                    # Check if Description contains CBD, CBG, CBC, CBN, or ":"
                    cbd_content_mask = (
                        self.df["Description"].str.contains(r"CBD|CBG|CBC|CBN", case=False, na=False) |
                        self.df["Description"].str.contains(":", na=False)
                    )
                    
                    # For RSO/CO2 Tankers with cannabinoid content or ":" in Description, set to "CBD Blend"
                    rso_co2_cbd_mask = rso_co2_mask & cbd_content_mask
                    if rso_co2_cbd_mask.any():
                        self.df.loc[rso_co2_cbd_mask, "Product Strain"] = "CBD Blend"
                        self.logger.info(f"Assigned 'CBD Blend' to {rso_co2_cbd_mask.sum()} RSO/CO2 Tankers with cannabinoid content or ':' in Description")
                    
                    # For RSO/CO2 Tankers without cannabinoid content or ":" in Description, set to "Mixed"
                    rso_co2_mixed_mask = rso_co2_mask & ~cbd_content_mask
                    if rso_co2_mixed_mask.any():
                        self.df.loc[rso_co2_mixed_mask, "Product Strain"] = "Mixed"
                        self.logger.info(f"Assigned 'Mixed' to {rso_co2_mixed_mask.sum()} RSO/CO2 Tankers without cannabinoid content or ':' in Description")

                # Edibles: if ProductName contains CBD, CBG, CBN, or CBC, then Product Strain is "CBD Blend", otherwise "Mixed"
                edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                edible_mask = self.df["Product Type*"].str.strip().str.lower().isin(edible_types)
                if edible_mask.any():
                    # Check if ProductName contains CBD, CBG, CBN, or CBC (same as UI logic)
                    edible_cbd_content_mask = (
                        self.df["ProductName"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False)
                    )
                    
                    # For edibles with cannabinoid content in ProductName, set to "CBD Blend"
                    edible_cbd_mask = edible_mask & edible_cbd_content_mask
                    if edible_cbd_mask.any():
                        self.df.loc[edible_cbd_mask, "Product Strain"] = "CBD Blend"
                        self.logger.info(f"Assigned 'CBD Blend' to {edible_cbd_mask.sum()} edibles with cannabinoid content in ProductName")
                    
                    # For edibles without cannabinoid content in ProductName, set to "Mixed"
                    edible_mixed_mask = edible_mask & ~edible_cbd_content_mask
                    if edible_mixed_mask.any():
                        self.df.loc[edible_mixed_mask, "Product Strain"] = "Mixed"
                        self.logger.info(f"Assigned 'Mixed' to {edible_mixed_mask.sum()} edibles without cannabinoid content in ProductName")

            # 8.5) Convert Product Strain to categorical after all logic is complete
            if "Product Strain" in self.df.columns:
                self.df["Product Strain"] = self.df["Product Strain"].astype("category")

            # 9) Convert key fields to categorical
            for col in ["Product Type*", "Lineage", "Product Brand", "Vendor"]:
                if col in self.df.columns:
                    # Fill null values before converting to categorical
                    self.df[col] = self.df[col].fillna("Unknown")
                    self.df[col] = self.df[col].astype("category")

            # 10) CBD and Mixed overrides (with edible lineage protection)
            if "Lineage" in self.df.columns:
                # Define edible types for protection
                edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                edible_mask = self.df["Product Type*"].str.strip().str.lower().isin(edible_types)
                
                # If Product Strain is 'CBD Blend', set Lineage to 'CBD' (but protect edibles that already have proper lineage)
                if "Product Strain" in self.df.columns:
                    cbd_blend_mask = self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend"
                    # Only apply to non-edibles or edibles that don't already have a proper lineage
                    non_edible_cbd_blend = cbd_blend_mask & ~edible_mask
                    edible_cbd_blend_no_lineage = cbd_blend_mask & edible_mask & (
                        self.df["Lineage"].isnull() | 
                        (self.df["Lineage"].astype(str).str.strip() == "") |
                        (self.df["Lineage"].astype(str).str.strip() == "Unknown")
                    )
                    
                    combined_cbd_blend_mask = non_edible_cbd_blend | edible_cbd_blend_no_lineage
                    
                    if combined_cbd_blend_mask.any():
                        if "CBD" not in self.df["Lineage"].cat.categories:
                            self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["CBD"])
                        self.df.loc[combined_cbd_blend_mask, "Lineage"] = "CBD"
                        self.logger.info(f"Assigned CBD lineage to {combined_cbd_blend_mask.sum()} products with CBD Blend strain")

                # If Description or Product Name* contains CBD, CBG, CBN, CBC, set Lineage to 'CBD' (but protect edibles)
                # Fix: ensure product_name_col is always a Series for .str methods
                if product_name_col:
                    product_names_for_cbd = self.df[product_name_col]
                    if isinstance(product_names_for_cbd, pd.DataFrame):
                        product_names_for_cbd = product_names_for_cbd.iloc[:, 0]
                else:
                    product_names_for_cbd = pd.Series("")
                cbd_mask = (
                    self.df["Description"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) |
                    (product_names_for_cbd.str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) if product_name_col else False)
                )
                # Only apply to non-edibles or edibles that don't already have a proper lineage
                non_edible_cbd = cbd_mask & ~edible_mask
                edible_cbd_no_lineage = cbd_mask & edible_mask & (
                    self.df["Lineage"].isnull() | 
                    (self.df["Lineage"].astype(str).str.strip() == "") |
                    (self.df["Lineage"].astype(str).str.strip() == "Unknown")
                )
                
                combined_cbd_mask = non_edible_cbd | edible_cbd_no_lineage
                
                # Use .any() to avoid Series boolean ambiguity
                if combined_cbd_mask.any():
                    self.df.loc[combined_cbd_mask, "Lineage"] = "CBD"
                    self.logger.info(f"Assigned CBD lineage to {combined_cbd_mask.sum()} products with cannabinoid content")

                # DISABLED: If Lineage is missing or empty, set to 'MIXED'
                # empty_lineage_mask = self.df["Lineage"].isnull() | (self.df["Lineage"].astype(str).str.strip() == "")
                # if "MIXED" not in self.df["Lineage"].cat.categories:
                #     self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                # # Use .any() to avoid Series boolean ambiguity
                # if empty_lineage_mask.any():
                #     self.df.loc[empty_lineage_mask, "Lineage"] = "MIXED"

                # DISABLED: For all edibles, set Lineage to 'MIXED' unless already 'CBD'
                # edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                # if "Product Type*" in self.df.columns:
                #     edible_mask = self.df["Product Type*"].str.strip().str.lower().isin([e.lower() for e in edible_types])
                #     not_cbd_mask = self.df["Lineage"].astype(str).str.upper() != "CBD"
                #     if "MIXED" not in self.df["Lineage"].cat.categories:
                #         self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                #     # Use .any() to avoid Series boolean ambiguity
                #     combined_mask = edible_mask & not_cbd_mask
                #     if combined_mask.any():
                #         self.df.loc[combined_mask, "Lineage"] = "MIXED"

            # 11) Normalize Weight* and CombinedWeight
            if "Weight*" in self.df.columns:
                self.df["Weight*"] = pd.to_numeric(self.df["Weight*"], errors="coerce") \
                    .apply(lambda x: str(int(x)) if pd.notnull(x) and float(x).is_integer() else str(x))
            if "Weight*" in self.df.columns and "Units" in self.df.columns:
                # Fill null values before converting to categorical
                combined_weight = (self.df["Weight*"] + self.df["Units"]).fillna("Unknown")
                self.df["CombinedWeight"] = combined_weight.astype("category")

            # 12) Format Price
            if "Price" in self.df.columns:
                def format_p(p):
                    if pd.isna(p) or p == '':
                        return ""
                    s = str(p).strip().lstrip("$").replace("'", "").strip()
                    try:
                        v = float(s)
                        if v.is_integer():
                            return f"${int(v)}"
                        else:
                            # Round to 2 decimal places and remove trailing zeros
                            return f"${v:.2f}".rstrip('0').rstrip('.')
                    except:
                        return f"${s}"
                self.df["Price"] = self.df["Price"].apply(lambda x: format_p(x) if pd.notnull(x) else "")
                self.df["Price"] = self.df["Price"].astype("string")

            # 13) Special pre-roll Ratio logic
            def process_ratio(row):
                t = str(row.get("Product Type*", "")).strip().lower()
                if t in ["pre-roll", "infused pre-roll"]:
                    # For pre-rolls, extract the weight/quantity part after the last hyphen
                    ratio_str = str(row.get("Ratio", ""))
                    if " - " in ratio_str:
                        parts = ratio_str.split(" - ")
                        if len(parts) >= 2:
                            # Take everything after the last hyphen
                            weight_part = parts[-1].strip()
                            return f" - {weight_part}" if weight_part and not weight_part.startswith(" - ") else weight_part
                    return ratio_str
                return row.get("Ratio", "")
            
            self.logger.debug("Applying special pre-roll ratio logic")
            self.df["Ratio"] = self.df.apply(process_ratio, axis=1)
            self.logger.debug(f"Final Ratio values after pre-roll processing: {self.df['Ratio'].head()}")

            # Create JointRatio column for Pre-Roll and Infused Pre-Roll products
            preroll_mask = self.df["Product Type*"].str.strip().str.lower().isin(["pre-roll", "infused pre-roll"])
            self.df["JointRatio"] = ""
            if "Joint Ratio" in self.df.columns:
                self.df.loc[preroll_mask, "JointRatio"] = self.df.loc[preroll_mask, "Joint Ratio"]
            elif "Ratio" in self.df.columns:
                self.df.loc[preroll_mask, "JointRatio"] = self.df.loc[preroll_mask, "Ratio"]
            # JointRatio: preserve original spacing exactly as in Excel - no normalization
            self.logger.debug(f"Sample JointRatio values after spacing fix: {self.df.loc[preroll_mask, 'JointRatio'].head()}")
            # Add detailed logging for JointRatio values
            if preroll_mask.any():
                sample_values = self.df.loc[preroll_mask, 'JointRatio'].head(10)
                for idx, value in sample_values.items():
                    self.logger.debug(f"JointRatio value '{value}' (length: {len(str(value))}, repr: {repr(str(value))})")

            # Reorder columns to place JointRatio next to Ratio
            if "Ratio" in self.df.columns and "JointRatio" in self.df.columns:
                ratio_col_idx = self.df.columns.get_loc("Ratio")
                cols = self.df.columns.tolist()
                
                # Remove duplicates first
                unique_cols = []
                seen_cols = set()
                for col in cols:
                    if col not in seen_cols:
                        unique_cols.append(col)
                        seen_cols.add(col)
                    else:
                        self.logger.warning(f"Removing duplicate column in JointRatio reorder: {col}")
                
                cols = unique_cols
                cols.remove("JointRatio")
                cols.insert(ratio_col_idx + 1, "JointRatio")
                # Ensure Description_Complexity is preserved
                if "Description_Complexity" not in cols:
                    cols.append("Description_Complexity")
                self.df = self.df[cols]

            # --- Reorder columns: move Description_Complexity, Ratio_or_THC_CBD, CombinedWeight after Lineage ---
            # First, remove any duplicate column names to prevent DataFrame issues
            cols = self.df.columns.tolist()
            unique_cols = []
            seen_cols = set()
            for col in cols:
                if col not in seen_cols:
                    unique_cols.append(col)
                    seen_cols.add(col)
                else:
                    self.logger.warning(f"Removing duplicate column: {col}")
            
            cols = unique_cols
            
            def move_after(col_to_move, after_col):
                if col_to_move in cols and after_col in cols:
                    cols.remove(col_to_move)
                    idx = cols.index(after_col)
                    cols.insert(idx+1, col_to_move)
            move_after('Description_Complexity', 'Lineage')
            move_after('Ratio_or_THC_CBD', 'Lineage')
            move_after('CombinedWeight', 'Lineage')
            self.df = self.df[cols]

            # Normalize Joint Ratio column name for consistency
            if "Joint Ratio" in self.df.columns and "JointRatio" not in self.df.columns:
                self.df.rename(columns={"Joint Ratio": "JointRatio"}, inplace=True)
            self.logger.debug(f"Columns after JointRatio normalization: {self.df.columns.tolist()}")

            # 14) Apply mode lineage for Classic Types based on Product Strain (OPTIMIZED)
            if ENABLE_FAST_LOADING:
                self.logger.debug("Fast loading mode: Skipping expensive strain similarity processing")
            else:
                self.logger.debug("Applying mode lineage for Classic Types based on Product Strain")
                
                # Filter for Classic Types only
                classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(CLASSIC_TYPES)
                classic_df = self.df[classic_mask].copy()
                
                if not classic_df.empty and "Product Strain" in classic_df.columns:
                    # Get all unique strain names from Classic Types
                    unique_strains = classic_df["Product Strain"].dropna().unique()
                    valid_strains = [s for s in unique_strains if normalize_strain_name(s)]
                    
                    if valid_strains:
                        # Group similar strains together (with performance limits)
                        strain_groups = group_similar_strains(valid_strains, similarity_threshold=0.8)
                        self.logger.debug(f"Found {len(strain_groups)} strain groups from {len(valid_strains)} unique strains")
                        
                        # Process each strain group
                        strain_lineage_map = {}
                        
                        for group_key, group_strains in strain_groups.items():
                            # Get all records for this strain group
                            group_mask = classic_df["Product Strain"].isin(group_strains)
                            group_records = classic_df[group_mask]
                            
                            if len(group_records) > 0:
                                # Get lineage values for this strain group (excluding empty/null values)
                                lineage_values = group_records["Lineage"].dropna()
                                lineage_values = lineage_values[lineage_values.astype(str).str.strip() != ""]
                                
                                if not lineage_values.empty:
                                    # Find the mode (most common) lineage
                                    lineage_counts = lineage_values.value_counts()
                                    most_common_lineage = lineage_counts.index[0]
                                    strain_lineage_map[group_key] = most_common_lineage
                                    
                                    # Log the grouping and mode lineage
                                    strain_list = ", ".join(group_strains)
                                    self.logger.debug(f"Strain Group '{group_key}' ({strain_list}) -> Mode Lineage: '{most_common_lineage}'")
                        
                        # Apply the mode lineage to all Classic Type products with matching Product Strain groups
                        if strain_lineage_map:
                            for group_key, mode_lineage in strain_lineage_map.items():
                                # Get the strains in this group
                                group_strains = strain_groups[group_key]
                                
                                # Find all Classic Type products with any of the strains in this group
                                strain_mask = (self.df["Product Type*"].str.strip().str.lower().isin(CLASSIC_TYPES)) & \
                                            (self.df["Product Strain"].isin(group_strains))
                                
                                # Update lineage for these products
                                self.df.loc[strain_mask, "Lineage"] = mode_lineage
                                
                                # Log the changes
                                updated_count = strain_mask.sum()
                                if updated_count > 0:
                                    strain_list = ", ".join(group_strains)
                                    self.logger.debug(f"Updated {updated_count} Classic Type products with strains [{strain_list}] to lineage '{mode_lineage}'")
                        
                        self.logger.debug(f"Mode lineage processing complete. Applied to {len(strain_lineage_map)} strain groups")
                    else:
                        self.logger.debug("No valid strains found for Classic Types")
                else:
                    self.logger.debug("No Classic Types found or Product Strain column missing")

            # Optimize memory usage for PythonAnywhere
            self.logger.debug("Optimizing memory usage for PythonAnywhere")
            
            # Convert string columns to categorical where appropriate to save memory
            categorical_columns = ['Product Type*', 'Lineage', 'Product Brand', 'Vendor', 'Product Strain']
            for col in categorical_columns:
                if col in self.df.columns:
                    # Only convert if the column has reasonable number of unique values
                    unique_count = self.df[col].nunique()
                    if unique_count < len(self.df) * 0.5:  # Less than 50% unique values
                        self.df[col] = self.df[col].astype('category')
                        self.logger.debug(f"Converted {col} to categorical (unique values: {unique_count})")
            
            # Final cleanup: remove any remaining duplicate columns
            cols = self.df.columns.tolist()
            unique_cols = []
            seen_cols = set()
            for col in cols:
                if col not in seen_cols:
                    unique_cols.append(col)
                    seen_cols.add(col)
                else:
                    self.logger.warning(f"Final cleanup: removing duplicate column: {col}")
            
            if len(unique_cols) != len(cols):
                self.df = self.df[unique_cols]
                self.logger.info(f"Final cleanup: removed {len(cols) - len(unique_cols)} duplicate columns")
            
            # Cache dropdown values
            self._cache_dropdown_values()
            self.logger.debug(f"Final columns after all processing: {self.df.columns.tolist()}")
            self.logger.debug(f"Sample data after all processing:\n{self.df[['ProductName', 'Description', 'Ratio', 'Product Strain']].head()}")
            
            # Log memory usage for PythonAnywhere monitoring
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                self.logger.info(f"Memory usage after file load: {memory_info.rss / (1024*1024):.2f} MB")
            except ImportError:
                self.logger.debug("psutil not available for memory monitoring")
            
            # --- Product/Strain Database Integration (Background Processing) ---
            # Move this to background processing to avoid blocking the main file load
            self._schedule_product_db_integration()
            
            # Cache the processed file
            self._file_cache[cache_key] = self.df.copy()
            self._last_loaded_file = file_path
            
            # Manage cache size
            self._manage_cache_size()
            
            # Force garbage collection to free memory
            import gc
            gc.collect()

            # --- After classic type lineage logic, enforce non-classic type rules ---
            if "Product Type*" in self.df.columns and "Lineage" in self.df.columns:
                # Define specific non-classic types that should always use MIXED or CBD Blend
                nonclassic_product_types = [
                    "edible (solid)", "edible (liquid)", "Edible (Solid)", "Edible (Liquid)",
                    "tincture", "Tincture", "topical", "Topical", 
                    "capsule", "Capsule", "suppository", "Suppository", "transdermal", "Transdermal",
                    "beverage", "Beverage", "powder", "Powder",
                    "gummy", "Gummy", "chocolate", "Chocolate", "cookie", "Cookie", 
                    "brownie", "Brownie", "candy", "Candy", "drink", "Drink",
                    "tea", "Tea", "coffee", "Coffee", "soda", "Soda", "juice", "Juice", 
                    "smoothie", "Smoothie", "shot", "Shot"
                ]
                
                # Identify non-classic types - products that are NOT in CLASSIC_TYPES
                nonclassic_mask = ~self.df["Product Type*"].str.strip().str.lower().isin([c.lower() for c in CLASSIC_TYPES])
                
                # Add debugging
                self.logger.info(f"Non-classic type processing: Found {nonclassic_mask.sum()} non-classic products")
                if nonclassic_mask.any():
                    sample_types = self.df.loc[nonclassic_mask, "Product Type*"].unique()
                    self.logger.info(f"Sample non-classic product types: {sample_types}")
                
                # Identify CBD Blend products
                is_cbd_blend = (
                    self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend"
                ) | (
                    self.df["Description"].astype(str).str.lower().str.contains("cbd blend", na=False)
                )
                
                # Set Lineage to 'CBD' for blends (not 'CBD Blend')
                if "CBD" not in self.df["Lineage"].cat.categories:
                    self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["CBD"])
                self.df.loc[nonclassic_mask & is_cbd_blend, "Lineage"] = "CBD"
                
                # For all other non-classic types, set Lineage to 'MIXED' unless already 'CBD'
                if "MIXED" not in self.df["Lineage"].cat.categories:
                    self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                not_cbd = ~self.df["Lineage"].astype(str).str.upper().isin(["CBD"])
                self.df.loc[nonclassic_mask & not_cbd, "Lineage"] = "MIXED"
                
                # Never allow 'HYBRID' for non-classic types
                hybrid_mask = nonclassic_mask & (self.df["Lineage"].astype(str).str.upper() == "HYBRID")
                if hybrid_mask.any():
                    self.logger.info(f"Converting {hybrid_mask.sum()} non-classic products from HYBRID to MIXED")
                    self.df.loc[hybrid_mask, "Lineage"] = "MIXED"

            # --- Set default lineage for classic types if missing ---
            if "Product Type*" in self.df.columns and "Lineage" in self.df.columns:
                classic_mask = self.df["Product Type*"].str.strip().str.lower().isin([c.lower() for c in CLASSIC_TYPES])
                empty_lineage_mask = self.df["Lineage"].isnull() | (self.df["Lineage"].astype(str).str.strip() == "")
                set_hybrid_mask = classic_mask & empty_lineage_mask
                if "HYBRID" not in self.df["Lineage"].cat.categories:
                    self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["HYBRID"])
                if set_hybrid_mask.any():
                    self.df.loc[set_hybrid_mask, "Lineage"] = "HYBRID"

            self.logger.info(f"File loaded successfully: {len(self.df)} rows, {len(self.df.columns)} columns")
            return True
            
        except MemoryError as me:
            self.logger.error(f"Memory error loading file: {str(me)}")
            # Clear any partial data
            if hasattr(self, 'df'):
                del self.df
                self.df = None
            import gc
            gc.collect()
            return False
            
        except Exception as e:
            self.logger.error(f"Error loading file: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Clear any partial data
            if hasattr(self, 'df'):
                del self.df
                self.df = None
            return False

    def apply_filters(self, filters: Optional[Dict[str, str]] = None):
        """Apply filters to the DataFrame."""
        if self.df is None or not filters:
            return self.df

        self.logger.debug(f"apply_filters received filters: {filters}")
        filtered_df = self.df.copy()
        column_mapping = {
            'vendor': 'Vendor',
            'brand': 'Product Brand',
            'productType': 'Product Type*',
            'lineage': 'Lineage',
            'weight': 'Weight*',
            'strain': 'Product Strain'
        }
        for filter_key, value in filters.items():
            if value and value != 'All':
                column = column_mapping.get(filter_key)
                if column and column in filtered_df.columns:
                    # Convert both the column and the filter value to lowercase for case-insensitive comparison
                    filtered_df = filtered_df[
                        filtered_df[column].astype(str).str.lower().str.strip() == value.lower().strip()
                    ]
        return filtered_df

    def _cache_dropdown_values(self):
        """Cache unique values for dropdown filters."""
        if self.df is None:
            logger.warning("No DataFrame loaded, cannot cache dropdown values")
            return

        filter_columns = {
            'vendor': 'Vendor',
            'brand': 'Product Brand',
            'productType': 'Product Type*',
            'lineage': 'Lineage',
            'weight': 'Weight*',
            'strain': 'Product Strain'
        }
        self.dropdown_cache = {}
        for filter_id, column in filter_columns.items():
            if column in self.df.columns:
                values = self.df[column].dropna().unique().tolist()
                values = [str(v) for v in values if str(v).strip()]
                # Exclude unwanted product types from dropdown
                if filter_id == 'productType':
                    filtered_values = []
                    for v in values:
                        v_lower = v.strip().lower()
                        if (('trade sample' in v_lower and 'not for sale' in v_lower) or 'deactivated' in v_lower):
                            continue
                        filtered_values.append(v)
                    values = filtered_values
                self.dropdown_cache[filter_id] = sorted(values)
            else:
                self.dropdown_cache[filter_id] = []

    def get_available_tags(self, filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Return a list of tag objects with all necessary data."""
        if self.df is None:
            logger.warning("DataFrame is None in get_available_tags")
            return []
        
        filtered_df = self.apply_filters(filters) if filters else self.df
        logger.info(f"get_available_tags: DataFrame shape {self.df.shape}, filtered shape {filtered_df.shape}")
        
        tags = []
        for _, row in filtered_df.iterrows():
            # Get quantity from various possible column names
            quantity = row.get('Quantity*', '') or row.get('Quantity Received*', '') or row.get('Quantity', '') or row.get('qty', '') or ''
            
            # Get formatted weight with units
            weight_with_units = self._format_weight_units(row)
            raw_weight = row.get('Weight*', '')
            
            # Helper function to safely get values and handle NaN
            def safe_get_value(value, default=''):
                if value is None:
                    return default
                if isinstance(value, pd.Series):
                    if pd.isna(value).any():
                        return default
                    value = value.iloc[0] if len(value) > 0 else default
                elif pd.isna(value):
                    return default
                return str(value).strip()
            
            # Use the dynamically detected product name column
            product_name_col = 'Product Name*'
            if product_name_col not in self.df.columns:
                possible_cols = ['ProductName', 'Product Name', 'Description']
                product_name_col = next((col for col in possible_cols if col in self.df.columns), None)
                if not product_name_col:
                    product_name_col = 'Description'  # Fallback to Description
            tag = {
                'Product Name*': safe_get_value(row.get(product_name_col, '')) or safe_get_value(row.get('Description', '')) or 'Unnamed Product',
                'Vendor': safe_get_value(row.get('Vendor', '')),
                'Vendor/Supplier*': safe_get_value(row.get('Vendor', '')),
                'Product Brand': safe_get_value(row.get('Product Brand', '')),
                'ProductBrand': safe_get_value(row.get('Product Brand', '')),
                'Lineage': safe_get_value(row.get('Lineage', 'MIXED')),
                'Product Type*': safe_get_value(row.get('Product Type*', '')),
                'Product Type': safe_get_value(row.get('Product Type*', '')),
                'Weight*': safe_get_value(raw_weight),
                'Weight': safe_get_value(raw_weight),
                'WeightWithUnits': safe_get_value(weight_with_units),
                'WeightUnits': safe_get_value(weight_with_units),  # Add WeightUnits for frontend compatibility
                'Quantity*': safe_get_value(quantity),
                'Quantity Received*': safe_get_value(quantity),
                'quantity': safe_get_value(quantity),
                # Also include the lowercase versions for backward compatibility
                'vendor': safe_get_value(row.get('Vendor', '')),
                'productBrand': safe_get_value(row.get('Product Brand', '')),
                'lineage': safe_get_value(row.get('Lineage', 'MIXED')),
                'productType': safe_get_value(row.get('Product Type*', '')),
                'weight': safe_get_value(raw_weight),
                'weightWithUnits': safe_get_value(weight_with_units),
                'displayName': safe_get_value(row.get(product_name_col, '')) or safe_get_value(row.get('Description', '')) or 'Unnamed Product'
            }
            # --- Filtering logic ---
            product_brand = str(tag['productBrand']).strip().lower()
            product_type = str(tag['productType']).strip().lower().replace('  ', ' ')
            weight = str(tag['weight']).strip().lower()

            # Sanitize lineage
            lineage = str(row.get('Lineage', 'MIXED') or '').strip().upper()
            if lineage not in VALID_LINEAGES:
                lineage = "MIXED"
            tag['Lineage'] = lineage
            tag['lineage'] = lineage

            # Only filter out very specific cases, be more permissive
            if (
                weight == '-1g' or  # Invalid weight
                (product_type == 'trade sample' and 'not for sale' in product_type.lower())  # Only filter trade samples that are explicitly not for sale
            ):
                continue  # Skip this tag
            tags.append(tag)
        
        # Sort tags by vendor first, then by brand, then by weight
        def sort_key(tag):
            vendor = str(tag.get('vendor', '')).strip().lower()
            brand = str(tag.get('productBrand', '')).strip().lower()
            weight = ExcelProcessor.parse_weight_str(tag.get('weight', ''), tag.get('weightWithUnits', ''))
            return (vendor, brand, weight)
        
        sorted_tags = sorted(tags, key=sort_key)
        logger.info(f"get_available_tags: Returning {len(sorted_tags)} tags")
        return sorted_tags

    def select_tags(self, tags):
        """Add tags to the selected set, preserving order and avoiding duplicates."""
        if not isinstance(tags, (list, set)):
            tags = [tags]
        for tag in tags:
            if tag not in self.selected_tags:
                self.selected_tags.append(tag)
        logger.debug(f"Selected tags after selection: {self.selected_tags}")

    def unselect_tags(self, tags):
        """Remove tags from the selected set."""
        if not isinstance(tags, (list, set)):
            tags = [tags]
        self.selected_tags = [tag for tag in self.selected_tags if tag not in tags]
        logger.debug(f"Selected tags after unselection: {self.selected_tags}")

    def get_selected_tags(self) -> List[str]:
        """Return the list of selected tag names in order."""
        return self.selected_tags if self.selected_tags else []

    def get_selected_records(self, template_type: str = 'vertical') -> List[Dict[str, Any]]:
        """Get selected records from the DataFrame, ordered by lineage."""
        try:
            # Get selected tags in the order they were selected
            selected_tags = list(self.selected_tags)
            if not selected_tags:
                logger.warning("No tags selected")
                return []
            
            logger.debug(f"Selected tags: {selected_tags}")
            
            # Build a mapping from normalized product names to canonical names
            product_name_col = 'ProductName'  # The actual column name in the DataFrame
            if product_name_col not in self.df.columns:
                possible_cols = ['Product Name*', 'Product Name', 'Description']
                product_name_col = next((col for col in possible_cols if col in self.df.columns), None)
                if not product_name_col:
                    logger.error(f"Product name column not found. Available columns: {list(self.df.columns)}")
                    return []
            
            canonical_map = {normalize_name(name): name for name in self.df[product_name_col]}
            logger.debug(f"Canonical map sample: {dict(list(canonical_map.items())[:5])}")
            
            # Map incoming selected tags to canonical names
            canonical_selected = [canonical_map.get(normalize_name(tag)) for tag in selected_tags if canonical_map.get(normalize_name(tag))]
            logger.debug(f"Selected tags: {selected_tags}")
            logger.debug(f"Canonical selected tags: {canonical_selected}")
            
            # Fallback: try case-insensitive and whitespace-insensitive matching if no canonical matches
            if not canonical_selected:
                logger.warning("No canonical matches for selected tags, trying fallback matching...")
                available_names = list(self.df[product_name_col])
                fallback_selected = []
                for tag in selected_tags:
                    tag_norm = tag.strip().lower().replace(' ', '')
                    for name in available_names:
                        name_norm = str(name).strip().lower().replace(' ', '')
                        if tag_norm == name_norm:
                            fallback_selected.append(name)
                            break
                canonical_selected = fallback_selected
                logger.debug(f"Fallback canonical selected tags: {canonical_selected}")
            
            if not canonical_selected:
                logger.warning("No canonical matches for selected tags after fallback")
                logger.warning(f"Available canonical keys (sample): {list(canonical_map.keys())[:10]}")
                normalized_selected = [normalize_name(tag) for tag in selected_tags]
                logger.warning(f"Normalized selected tags: {normalized_selected}")
                logger.warning(f"Available product names: {list(self.df[product_name_col])[:10]}")
                return []
            
            logger.debug(f"Canonical selected tags: {canonical_selected}")
            
            # Filter DataFrame to only include selected records by canonical ProductName
            filtered_df = self.df[self.df[product_name_col].isin(canonical_selected)]
            logger.debug(f"Found {len(filtered_df)} matching records")
            
            # Convert to list of dictionaries
            records = filtered_df.to_dict('records')
            logger.debug(f"Converted to {len(records)} records")
            
            # Sort records by lineage order, then by the order they appear in selected_tags
            lineage_order = [
                'SATIVA', 'INDICA', 'HYBRID', 'HYBRID/SATIVA',
                'HYBRID/INDICA', 'CBD', 'MIXED', 'PARAPHERNALIA'
            ]
            
            def get_lineage(rec):
                lineage = str(rec.get('Lineage', '')).upper()
                return lineage if lineage in lineage_order else 'MIXED'
            
            def get_selected_order(rec):
                product_name = rec.get(product_name_col, '').strip().lower()
                try:
                    return selected_tags.index(product_name)
                except ValueError:
                    return len(selected_tags)  # Put unknown tags at the end
            
            # Sort by lineage first, then by selected order
            records_sorted = sorted(records, key=lambda r: (
                lineage_order.index(get_lineage(r)),
                get_selected_order(r)
            ))
            
            processed_records = []
            
            for record in records_sorted:
                try:
                    # Use the correct product name column
                    product_name = record.get(product_name_col, '').strip()
                    # Ensure Description is always set
                    description = record.get('Description', '')
                    if not description:
                        description = product_name or record.get(product_name_col, '')
                    product_type = record.get('Product Type*', '').strip().lower()
                    
                    # Get ratio text and ensure it's a string
                    ratio_text = str(record.get('Ratio', '')).strip()
                    
                    # Define classic types
                    classic_types = [
                        "flower", "pre-roll", "infused pre-roll", "concentrate", 
                        "solventless concentrate", "vape cartridge", "rso/co2 tankers"
                    ]
                    
                    # For classic types, ensure proper ratio format
                    if product_type in classic_types:
                        # Check if we have a valid ratio, otherwise use default
                        if not ratio_text or ratio_text in ["", "CBD", "THC", "CBD:", "THC:", "CBD:\n", "THC:\n"]:
                            ratio_text = "THC:|BR|CBD:"
                        # If ratio contains THC/CBD values, use it directly
                        elif any(cannabinoid in ratio_text.upper() for cannabinoid in ['THC', 'CBD', 'CBC', 'CBG', 'CBN']):
                            ratio_text = ratio_text  # Keep as is
                        # If it's a valid ratio format, use it
                        elif is_real_ratio(ratio_text):
                            ratio_text = ratio_text  # Keep as is
                        # Otherwise, use default THC:CBD format
                        else:
                            ratio_text = "THC:|BR|CBD:"
                    
                    # Don't apply ratio formatting here - let the template processor handle it
                    # For classic types (including RSO/CO2 Tankers), the template processor will handle the classic formatting
                    
                    # Ensure we have a valid ratio text
                    if not ratio_text:
                        if product_type in classic_types:
                            ratio_text = "THC:|BR|CBD:"
                        else:
                            ratio_text = ""
                    
                    product_name = make_nonbreaking_hyphens(product_name)
                    description = make_nonbreaking_hyphens(description)
                    
                    # Get DOH value without normalization
                    doh_value = str(record.get('DOH', '')).strip().upper()
                    logger.debug(f"Processing DOH value: {doh_value}")
                    
                    # Get original values
                    product_brand = record.get('Product Brand', '').upper()
                    
                    # If no brand name, try to extract from product name or use vendor
                    if not product_brand or product_brand.strip() == '':
                        product_name = record.get('ProductName', '') or record.get('Product Name*', '')
                        if product_name:
                            # Look for common brand patterns in product name
                            import re
                            # Pattern: product name followed by brand name (e.g., "White Widow CBG Platinum Distillate")
                            brand_patterns = [
                                r'(.+?)\s+(Platinum|Premium|Gold|Silver|Elite|Select|Reserve|Craft|Artisan|Boutique|Signature|Limited|Exclusive|Private|Custom|Special|Deluxe|Ultra|Super|Mega|Max|Pro|Plus|X)\s+(Distillate|Extract|Concentrate|Oil|Tincture|Gel|Capsule|Edible|Gummy|Chocolate|Beverage|Topical|Cream|Lotion|Salve|Balm|Spray|Drops|Syrup|Sauce|Dab|Wax|Shatter|Live|Rosin|Resin|Kief|Hash|Bubble|Ice|Water|Solventless|Full\s+Spectrum|Broad\s+Spectrum|Isolate|Terpene|Terpenes|Terp|Terps)',
                                r'(.+?)\s+(Distillate|Extract|Concentrate|Oil|Tincture|Gel|Capsule|Edible|Gummy|Chocolate|Beverage|Topical|Cream|Lotion|Salve|Balm|Spray|Drops|Syrup|Sauce|Dab|Wax|Shatter|Live|Rosin|Resin|Kief|Hash|Bubble|Ice|Water|Solventless|Full\s+Spectrum|Broad\s+Spectrum|Isolate|Terpene|Terpenes|Terp|Terps)',
                                r'(.+?)\s+(Platinum|Premium|Gold|Silver|Elite|Select|Reserve|Craft|Artisan|Boutique|Signature|Limited|Exclusive|Private|Custom|Special|Deluxe|Ultra|Super|Mega|Max|Pro|Plus|X)',
                            ]
                            
                            for pattern in brand_patterns:
                                match = re.search(pattern, product_name, re.IGNORECASE)
                                if match:
                                    # Extract the brand part (everything after the product name)
                                    full_match = match.group(0)
                                    product_part = match.group(1).strip()
                                    brand_part = full_match[len(product_part):].strip()
                                    if brand_part:
                                        product_brand = brand_part.upper()
                                        break
                        
                        # If still no brand, try vendor as fallback
                        if not product_brand or product_brand.strip() == '':
                            vendor = record.get('Vendor', '') or record.get('Vendor/Supplier*', '')
                            if vendor and vendor.strip() != '':
                                product_brand = vendor.strip().upper()
                    
                    original_lineage = str(record.get('Lineage', '')).upper()
                    original_product_strain = record.get('Product Strain', '')
                    
                    # For RSO/CO2 Tankers and Capsules, use Product Brand in place of Lineage
                    if product_type in ["rso/co2 tankers", "capsule"]:
                        final_lineage = product_brand if product_brand else original_lineage
                        final_product_strain = original_product_strain  # Keep Product Strain for CBD Blend/Mixed values
                    else:
                        # For other product types, use the actual Lineage value
                        final_lineage = original_lineage
                        final_product_strain = original_product_strain
                    
                    lineage_needs_centering = False  # Lineage should not be centered
                    
                    # Debug print for verification
                    print(f"Product: {product_name}, Type: {product_type}, Lineage: '{final_lineage}', ProductStrain: '{final_product_strain}'")
                    
                    # Debug ProductStrain logic
                    include_product_strain = (product_type in ["rso/co2 tankers", "capsule"] or product_type not in classic_types)
                    print(f"  ProductStrain logic: product_type='{product_type}', in special list={product_type in ['rso/co2 tankers', 'capsule']}, not in classic_types={product_type not in classic_types}, include_product_strain={include_product_strain}")
                    
                    # Build the processed record with raw values (no markers)
                    processed = {
                        'ProductName': product_name,  # Keep this for compatibility
                        product_name_col: product_name,  # Also store with original column name
                        'Description': description,
                        'WeightUnits': record.get('JointRatio', '') if product_type in {"pre-roll", "infused pre-roll"} else self._format_weight_units(record),
                        'ProductBrand': product_brand,
                        'Price': str(record.get('Price', '')).strip(),
                        'Lineage': wrap_with_marker(unwrap_marker(str(final_lineage), "LINEAGE"), "LINEAGE"),
                        'DOH': doh_value,  # Keep DOH as raw value
                        'Ratio_or_THC_CBD': ratio_text,  # Use the processed ratio_text for all product types
                        'ProductStrain': wrap_with_marker(final_product_strain, "PRODUCTSTRAIN") if include_product_strain else '',
                        'ProductType': record.get('Product Type*', ''),
                        'Ratio': str(record.get('Ratio', '')).strip(),
                    }
                    # Ensure leading space before hyphen is a non-breaking space to prevent Word from stripping it
                    joint_ratio = record.get('JointRatio', '')
                    if joint_ratio.startswith(' -'):
                        joint_ratio = ' -\u00A0' + joint_ratio[2:]
                    processed['JointRatio'] = joint_ratio
                    
                    logger.info(f"Rendered label for record: {product_name if product_name else '[NO NAME]'}")
                    logger.debug(f"Processed record DOH value: {processed['DOH']}")
                    logger.debug(f"Product Type: {product_type}, Classic: {product_type in classic_types}")
                    logger.debug(f"Original Lineage: {original_lineage}, Final Lineage: {final_lineage}")
                    logger.debug(f"Original Product Strain: {original_product_strain}, Final Product Strain: {final_product_strain}")
                    logger.debug(f"Lineage needs centering: {lineage_needs_centering}")
                    processed_records.append(processed)
                except Exception as e:
                    logger.error(f"Error processing record {product_name}: {str(e)}")
                    continue
                
            # Debug log the final processed records
            logger.debug(f"Processed {len(processed_records)} records")
            for record in processed_records:
                logger.debug(f"Processed record: {record.get('ProductName', 'NO NAME')}")
                logger.debug(f"Record DOH value: {record.get('DOH', 'NO DOH')}")
            
            return processed_records
        except Exception as e:
            logger.error(f"Error in get_selected_records: {str(e)}")
            return []

    def _format_weight_units(self, record):
        # Handle pandas Series and NA values properly
        def safe_get_value(value, default=''):
            if value is None or pd.isna(value):
                return default
            if isinstance(value, pd.Series):
                if pd.isna(value).any():
                    return default
                value = value.iloc[0] if len(value) > 0 else default
            return str(value).strip()
        
        weight_val = safe_get_value(record.get('Weight*', None))
        units_val = safe_get_value(record.get('Units', ''))
        product_type = safe_get_value(record.get('Product Type*', '')).lower()
        
        # Debug: Log first few records
        if hasattr(self, '_debug_count'):
            self._debug_count += 1
        else:
            self._debug_count = 1
            
        if self._debug_count <= 5:  # Log first 5 records for debugging
            self.logger.info(f"Record {self._debug_count}: weight_val={weight_val} (type: {type(weight_val)}), units_val={units_val} (type: {type(units_val)}), product_type={product_type}")
        
        edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
        preroll_types = {"pre-roll", "infused pre-roll"}

        # For pre-rolls and infused pre-rolls, use JointRatio if available
        if product_type in preroll_types:
            joint_ratio = safe_get_value(record.get('JointRatio', ''))
            if joint_ratio:
                result = str(joint_ratio)
            else:
                result = "THC:|BR|CBD:"
        else:
            try:
                weight_val = float(weight_val) if weight_val not in (None, '', 'nan') else None
            except Exception:
                weight_val = None

            if product_type in edible_types and units_val in {"g", "grams"} and weight_val is not None:
                weight_val = weight_val * 0.03527396195
                units_val = "oz"

            # Now we can safely check the values since they've been processed by safe_get_value
            if weight_val is not None and units_val:
                weight_str = f"{weight_val:.2f}".rstrip("0").rstrip(".")
                result = f"{weight_str}{units_val}"
            elif weight_val is not None:
                result = str(weight_val)
            elif units_val:
                result = str(units_val)
            else:
                result = ""
        
        # Debug: Log result for first few records
        if self._debug_count <= 5:
            self.logger.info(f"Record {self._debug_count} result: '{result}'")
            
        return result

    def get_dynamic_filter_options(self, current_filters: Dict[str, str]) -> Dict[str, list]:
        if self.df is None:
            # Return empty options if no data is loaded
            return {
                "vendor": [],
                "brand": [],
                "productType": [],
                "lineage": [],
                "weight": [],
                "strain": []
            }
        df = self.df.copy()
        filter_map = {
            "vendor": "Vendor",
            "brand": "Product Brand",
            "productType": "Product Type*",
            "lineage": "Lineage",
            "weight": "Weight*",  # Changed from "CombinedWeight" to "Weight*"
            "strain": "Product Strain"
        }
        options = {}
        import math
        def clean_list(lst):
            return ['' if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in lst]
        # For each filter type, generate options by applying all other filters except itself
        for filter_key, col in filter_map.items():
            temp_df = df.copy()
            # Apply all other filters except the current one
            for key, value in current_filters.items():
                if key == filter_key:
                    continue  # Skip filtering by itself
                if value and value != "All":
                    filter_col = filter_map.get(key)
                    if filter_col and filter_col in temp_df.columns:
                        temp_df = temp_df[
                            temp_df[filter_col].astype(str).str.lower().str.strip() == value.lower().strip()
                        ]
            # Get unique values for this filter type
            if col in temp_df.columns:
                if filter_key == "weight":
                    # For weight, use the properly formatted weight with units
                    values = []
                    for _, row in temp_df.iterrows():
                        # Convert row to dict for _format_weight_units
                        row_dict = row.to_dict()
                        weight_with_units = self._format_weight_units(row_dict)
                        if weight_with_units and weight_with_units.strip():
                            values.append(weight_with_units.strip())
                    
                    # Debug: Log what weight values are being generated
                    if values:
                        self.logger.info(f"Weight filter values generated: {values[:5]}...")  # Log first 5 values
                    else:
                        self.logger.warning("No weight values generated for filter dropdown")
                else:
                    values = temp_df[col].dropna().unique().tolist()
                    values = [str(v) for v in values if str(v).strip()]
                
                # Exclude unwanted product types from dropdown and apply product type normalization
                if filter_key == "productType":
                    filtered_values = []
                    for v in values:
                        v_lower = v.strip().lower()
                        if ("trade sample" in v_lower or "deactivated" in v_lower):
                            continue
                        # Apply product type normalization (same as TYPE_OVERRIDES)
                        normalized_v = TYPE_OVERRIDES.get(v_lower, v)
                        filtered_values.append(normalized_v)
                    values = filtered_values
                
                # Remove duplicates and sort
                values = list(set(values))
                values.sort()
                options[filter_key] = clean_list(values)
            else:
                options[filter_key] = []
        
        return options

    @staticmethod
    def parse_weight_str(w, u=None):
        import re
        w = str(w).strip() if w is not None else ''
        u = str(u).strip().lower() if u is not None else ''
        # Try to extract numeric value and units from weight or weightWithUnits
        match = re.match(r"([\d.]+)\s*(g|oz)?", w.lower())
        if not match and u:
            match = re.match(r"([\d.]+)\s*(g|oz)?", u)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            if unit == 'oz':
                val = val * 28.3495
            return val
        return float('inf')  # Non-numeric weights go last

