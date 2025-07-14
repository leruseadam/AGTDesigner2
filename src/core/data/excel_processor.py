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

# Import cross-platform utilities
from src.core.utils.cross_platform import get_platform, platform_manager, get_safe_path, ensure_directory

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

def get_default_upload_file() -> Optional[str]:
    """
    Returns None - no files are stored on disk.
    All files are processed in memory and deleted immediately.
    """
    logger.info("No default file loading - files are processed in memory only")
    return None

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
                    
                    self.logger.info(f"[ProductDB] Starting background integration for {total_rows} records...")
                    
                    for i in range(0, total_rows, batch_size):
                        batch_end = min(i + batch_size, total_rows)
                        batch_df = self.df.iloc[i:batch_end]
                        
                        # Process batch
                        for _, row in batch_df.iterrows():
                            row_dict = row.to_dict()
                            
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
                        
                        # Log progress for large files
                        if total_rows > 100:
                            progress = (batch_end / total_rows) * 100
                            self.logger.debug(f"[ProductDB] Progress: {progress:.1f}% ({batch_end}/{total_rows})")
                    
                    self.logger.info(f"[ProductDB] Background integration complete: {strain_count} strains, {product_count} products")
                    
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
            
            # Remove duplicates
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            final_count = len(df)
            if initial_count != final_count:
                self.logger.info(f"Removed {initial_count - final_count} duplicate rows")
            
            # Reset index to ensure unique labels before any processing
            df = df.reset_index(drop=True)
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
        """Load Excel file and prepare data exactly like MAIN.py. Enhanced for cross-platform compatibility."""
        try:
            # Get platform manager for consistent configuration
            pm = get_platform()
            
            # Platform detection for consistent logging
            platform_summary = pm.get_platform_summary()
            self.logger.info(f"Platform summary: {platform_summary}")
            
            # Check if we've already loaded this exact file
            if (self._last_loaded_file == file_path and 
                self.df is not None and 
                not self.df.empty):
                self.logger.debug(f"File {file_path} already loaded, skipping reload")
                return True
            
            self.logger.debug(f"Loading file: {file_path}")
            
            # Validate file exists and is accessible
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                return False
            
            if not os.access(file_path, os.R_OK):
                self.logger.error(f"File not readable: {file_path}")
                return False
            
            # Check file size using platform-specific limits
            file_size = os.path.getsize(file_path)
            max_size = pm.get_file_size_limit()
            if file_size > max_size:
                self.logger.error(f"File too large for current platform: {file_size} bytes (max: {max_size})")
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
            # Use platform-specific settings
            dtype_dict = {
                "Product Type*": "string",
                "Lineage": "string",
                "Product Brand": "string",
                "Vendor": "string",
                "Weight Unit* (grams/gm or ounces/oz)": "string",
                "Product Name*": "string"
            }
            
            # Try different Excel engines based on platform capabilities
            excel_engines = pm.get_excel_engines()
            df = None
            chunk_threshold = 10 * 1024 * 1024  # 10MB
            for engine in excel_engines:
                try:
                    self.logger.debug(f"Attempting to read with engine: {engine}")
                    if file_size > chunk_threshold:
                        self.logger.info("Large file detected, using chunked reading")
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
            
            # Remove duplicates
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            final_count = len(df)
            if initial_count != final_count:
                self.logger.info(f"Removed {initial_count - final_count} duplicate rows")
            
            self.df = df
            # Ensure unique index to prevent "cannot reindex on an axis with duplicate labels" error
            self.df = self.df.reset_index(drop=True)
            self.logger.debug(f"Original columns: {self.df.columns.tolist()}")

            # Define product_name_col at the beginning to ensure it's available throughout the method
            product_name_col = 'Product Name*'
            if product_name_col not in self.df.columns:
                product_name_col = 'ProductName' if 'ProductName' in self.df.columns else None
            if not product_name_col:
                product_name_col = 'ProductName'  # Default fallback
            
            self.logger.info(f"Using product name column: '{product_name_col}' (available columns: {list(self.df.columns)})")

            # 2) Trim product names - ensure consistent processing across platforms
            if "Product Name*" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name*"].str.lstrip()
            elif "Product Name" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name"].str.lstrip()
            elif "ProductName" in self.df.columns:
                self.df["Product Name*"] = self.df["ProductName"].str.lstrip()
            else:
                self.logger.error("No product name column found")
                self.df["Product Name*"] = "Unknown"

            # 3) Ensure required columns exist - consistent across platforms
            for col in ["Product Type*", "Lineage", "Product Brand"]:
                if col not in self.df.columns:
                    self.df[col] = "Unknown"

            # 4) Exclude sample rows and deactivated products - consistent filtering
            initial_count = len(self.df)
            excluded_by_type = self.df[self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            self.df = self.df[~self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            self.logger.info(f"Excluded {len(excluded_by_type)} products by product type: {excluded_by_type['Product Type*'].unique().tolist()}")
            
            # Also exclude products with excluded patterns in the name
            for pattern in EXCLUDED_PRODUCT_PATTERNS:
                try:
                    # Reset index before each pattern to ensure alignment
                    self.df = self.df.reset_index(drop=True)
                    pattern_mask = self.df["Product Name*"].str.contains(pattern, case=False, na=False)
                    excluded_by_pattern = self.df[pattern_mask]
                    self.df = self.df[~pattern_mask]
                    if len(excluded_by_pattern) > 0:
                        self.logger.info(f"Excluded {len(excluded_by_pattern)} products containing pattern '{pattern}': {excluded_by_pattern['Product Name*'].tolist()}")
                except Exception as e:
                    self.logger.error(f"Error filtering pattern '{pattern}': {e}")
                    # Continue with next pattern instead of failing completely
                    continue
            
            final_count = len(self.df)
            self.logger.info(f"Product filtering complete: {initial_count} -> {final_count} products (excluded {initial_count - final_count})")
            
            # Reset index after filtering to ensure unique labels
            self.df = self.df.reset_index(drop=True)
            
            # Additional safety check: ensure no duplicate indices exist
            if self.df.index.duplicated().any():
                self.logger.warning("Duplicate indices detected after filtering, resetting index")
            self.df = self.df.reset_index(drop=True)

            # 5) Rename for convenience - consistent column mapping
            self.df.rename(columns={
                "Product Name*": "ProductName",
                "Weight Unit* (grams/gm or ounces/oz)": "Units",
                "Price* (Tier Name for Bulk)": "Price",
                "Vendor/Supplier*": "Vendor",
                "DOH Compliant (Yes/No)": "DOH",
                "Concentrate Type": "Ratio"
            }, inplace=True)
            
            # Update product_name_col to point to the renamed column
            product_name_col = 'ProductName'

            # 6) Normalize units - consistent across platforms
            if "Units" in self.df.columns:
                self.df["Units"] = self.df["Units"].str.lower().replace(
                    {"ounces": "oz", "grams": "g"}, regex=True
                )

            # 7) Standardize Lineage - ensure consistent lineage mapping
            if "Lineage" in self.df.columns:
                # Normalize lineage values consistently across platforms
                self.df["Lineage"] = (
                    self.df["Lineage"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .replace({
                            "indica_hybrid": "HYBRID/INDICA",
                            "sativa_hybrid": "HYBRID/SATIVA",
                            "sativa": "SATIVA",
                            "hybrid": "HYBRID",
                            "indica": "INDICA",
                            "cbd": "CBD",
                            "cbd_blend": "CBD",
                            "mixed": "MIXED",
                            "paraphernalia": "PARAPHERNALIA"
                        })
                        .fillna("HYBRID")
                        .str.upper()
                )
                
                # Log lineage distribution for debugging
                lineage_counts = self.df["Lineage"].value_counts()
                self.logger.info(f"Lineage distribution: {lineage_counts.to_dict()}")

            # Continue with the rest of the processing...
            # (rest of the existing load_file method remains the same)

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
                product_name_col = 'Product Name*'
                # Reset index to ensure unique labels before any operations
                self.df = self.df.reset_index(drop=True)
                
                if product_name_col not in self.df.columns:
                    product_name_col = 'ProductName' if 'ProductName' in self.df.columns else None
                
                # Ensure product_name_col is available throughout the method
                if not product_name_col:
                    product_name_col = 'ProductName'  # Default fallback
                
                if product_name_col and product_name_col in self.df.columns:
                    # BULLETPROOF FIX: Complete rewrite to handle all edge cases
                    self.logger.info("Using bulletproof method for Description column assignment")
                    
                    try:
                        # Step 1: Always reset index to ensure clean state
                        self.df = self.df.reset_index(drop=True)
                        self.logger.info(f"DataFrame shape after reset: {self.df.shape}")
                        
                        # Step 2: Get product names as a simple list
                        if product_name_col in self.df.columns:
                            product_names_list = self.df[product_name_col].astype(str).tolist()
                            self.logger.info(f"Product names list length: {len(product_names_list)}")
                            
                            # Step 3: Generate descriptions using list comprehension
                            descriptions_list = []
                            for i, name in enumerate(product_names_list):
                                try:
                                    desc = get_description(name)
                                    descriptions_list.append(desc)
                                except Exception as e:
                                    self.logger.warning(f"Error getting description for product {i}: {e}")
                                    descriptions_list.append("")
                            
                            self.logger.info(f"Descriptions list length: {len(descriptions_list)}")
                            
                            # Step 4: Verify lengths match
                            if len(descriptions_list) != len(self.df):
                                self.logger.error(f"Length mismatch: descriptions={len(descriptions_list)}, df={len(self.df)}")
                                # Pad or truncate to match
                                if len(descriptions_list) < len(self.df):
                                    descriptions_list.extend([""] * (len(self.df) - len(descriptions_list)))
                                else:
                                    descriptions_list = descriptions_list[:len(self.df)]
                            
                            # Step 5: Create new DataFrame with all existing data plus Description
                            new_df_data = {}
                            
                            # Copy all existing columns
                            for col in self.df.columns:
                                try:
                                    # Convert Series to list safely
                                    if hasattr(self.df[col], 'tolist'):
                                        new_df_data[col] = self.df[col].tolist()
                                    else:
                                        # Fallback for non-Series objects
                                        new_df_data[col] = list(self.df[col])
                                except Exception as e:
                                    self.logger.warning(f"Error converting column {col} to list: {e}")
                                    # Create empty list of correct length
                                    new_df_data[col] = [""] * len(self.df)
                            
                            # Add Description column
                            new_df_data["Description"] = descriptions_list
                            
                            # Step 6: Create completely new DataFrame
                            self.df = pd.DataFrame(new_df_data)
                        else:
                            self.logger.error(f"Product name column '{product_name_col}' not found in DataFrame")
                            # Create Description column with empty values
                            self.df["Description"] = ""
                        self.logger.info(f"New DataFrame shape: {self.df.shape}")
                        self.logger.info("Bulletproof method successful")
                        
                    except Exception as e:
                        self.logger.error(f"Bulletproof method failed: {e}")
                        
                        try:
                            # Emergency fallback: Create minimal working DataFrame
                            self.logger.info("Attempting emergency fallback")
                            
                            # Get the length of the original DataFrame
                            original_length = len(self.df)
                            
                            # Create minimal data with essential columns
                            minimal_data = {
                                "Description": [""] * original_length
                            }
                            
                            # Add any existing columns that we can safely copy
                            safe_columns = ["Product Name*", "Product Type*", "Lineage", "Product Brand"]
                            for col in safe_columns:
                                if col in self.df.columns:
                                    try:
                                        # Convert Series to list safely
                                        if hasattr(self.df[col], 'tolist'):
                                            col_data = self.df[col].tolist()
                                        else:
                                            col_data = list(self.df[col])
                                        
                                        if len(col_data) == original_length:
                                            minimal_data[col] = col_data
                                        else:
                                            minimal_data[col] = [""] * original_length
                                    except Exception as e:
                                        self.logger.warning(f"Error copying column {col}: {e}")
                                        minimal_data[col] = [""] * original_length
                            
                            # Ensure product_name_col is included in the minimal data
                            if product_name_col and product_name_col not in minimal_data:
                                if product_name_col in self.df.columns:
                                    try:
                                        if hasattr(self.df[product_name_col], 'tolist'):
                                            minimal_data[product_name_col] = self.df[product_name_col].tolist()
                                        else:
                                            minimal_data[product_name_col] = list(self.df[product_name_col])
                                    except Exception as e:
                                        self.logger.warning(f"Error copying {product_name_col}: {e}")
                                        minimal_data[product_name_col] = [""] * original_length
                                else:
                                    minimal_data[product_name_col] = [""] * original_length
                            
                            # Create new DataFrame
                            self.df = pd.DataFrame(minimal_data)
                            self.logger.info(f"Emergency fallback successful: {self.df.shape}")
                            
                        except Exception as e2:
                            self.logger.error(f"Emergency fallback failed: {e2}")
                            # Absolute last resort: empty DataFrame with essential columns
                            last_resort_data = {
                                "Description": [""],
                                "Product Type*": ["Unknown"],
                                "Lineage": ["HYBRID"],
                                "Product Brand": ["Unknown"],
                                "Product Strain": ["Mixed"]
                            }
                            if product_name_col:
                                last_resort_data[product_name_col] = [""]
                            self.df = pd.DataFrame(last_resort_data)
                            self.logger.info("Absolute last resort: empty DataFrame created")
                else:
                    # If no product name column found, create empty Description column
                    self.logger.warning(f"No product name column found, creating empty Description column")
                    self.df["Description"] = ""
                
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
                self.df.loc[mask_para, "Description"] = (
                    self.df.loc[mask_para, "Description"]
                    .str.replace(r"\s*-\s*\d+g$", "", regex=True)
                )

                # Calculate complexity for Description column
                try:
                    # Ensure we have a clean index before applying complexity
                    if self.df.index.duplicated().any():
                        self.logger.warning("Duplicate indices detected before Description_Complexity assignment, resetting index")
                        self.df = self.df.reset_index(drop=True)
                    self.df["Description_Complexity"] = self.df["Description"].apply(_complexity)
                except Exception as e:
                    self.logger.error(f"Error assigning Description_Complexity column: {e}")
                    # Fallback: create Description_Complexity column with default values
                    self.df["Description_Complexity"] = "medium"

                # Build cannabinoid content info
                self.logger.debug("Extracting cannabinoid content from Product Name")
                # Extract text following the FINAL hyphen only
                if product_name_col and product_name_col in self.df.columns:
                    # Extract ratio and handle nulls safely
                    ratio_extracted = self.df[product_name_col].str.extract(r".*-\s*(.+)")
                    # Fill nulls with empty string, but ensure it's a string type first
                    self.df["Ratio"] = ratio_extracted.astype("string").fillna("")
                else:
                    self.df["Ratio"] = ""
                self.logger.debug(f"Sample cannabinoid content values before processing: {self.df['Ratio'].head()}")
                
                self.df["Ratio"] = self.df["Ratio"].str.replace(r" / ", " ", regex=True)
                self.logger.debug(f"Sample cannabinoid content values after processing: {self.df['Ratio'].head()}")

                # Set Ratio_or_THC_CBD based on product type
                def set_ratio_or_thc_cbd(row):
                    product_type = str(row.get("Product Type*", "")).strip().lower()
                    ratio = str(row.get("Ratio", "")).strip()
                    classic_types = [
                        "flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge"
                    ]
                    BAD_VALUES = {"", "CBD", "THC", "CBD:", "THC:", "CBD:\n", "THC:\n"}
                    
                    # For pre-rolls and infused pre-rolls, always use THC: CBD: format
                    if product_type in ["pre-roll", "infused pre-roll"]:
                        return "THC:\nCBD:"
                    
                    # For solventless concentrate, check if ratio is a weight + unit format
                    if product_type == "solventless concentrate":
                        if not ratio or ratio in BAD_VALUES or not is_weight_with_unit(ratio):
                            return "1g"
                        return ratio
                    
                    if product_type in classic_types:
                        if not ratio or ratio in BAD_VALUES:
                            return "THC:\nCBD:"
                        # If ratio contains THC/CBD values, use it directly
                        if any(cannabinoid in ratio.upper() for cannabinoid in ['THC', 'CBD', 'CBC', 'CBG', 'CBN']):
                            return ratio
                        # If it's a valid ratio format, use it
                        if is_real_ratio(ratio):
                            return ratio
                        # Otherwise, use default THC:CBD format
                        return "THC:\nCBD:"
                    
                    # NEW: For Edibles, if ratio is missing, default to "THC:\nCBD:"
                    edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                    if product_type in edible_types:
                        if not ratio or ratio in BAD_VALUES:
                            return "THC:\nCBD:"
                    
                    return ratio

                # Check if DataFrame is still valid before proceeding
                if self.df is not None and len(self.df) > 0:
                    self.df["Ratio_or_THC_CBD"] = self.df.apply(set_ratio_or_thc_cbd, axis=1)
                    self.logger.debug(f"Ratio_or_THC_CBD values: {self.df['Ratio_or_THC_CBD'].head()}")
                else:
                    self.logger.error("DataFrame is None or empty, cannot set Ratio_or_THC_CBD")
                    return False

                # Ensure Product Strain exists and is categorical
                if "Product Strain" not in self.df.columns:
                    self.df["Product Strain"] = ""
                # Fill null values before converting to categorical
                self.df["Product Strain"] = self.df["Product Strain"].fillna("Mixed")
                self.df["Product Strain"] = self.df["Product Strain"].astype("category")

                # Special case: paraphernalia gets Product Strain set to "Paraphernalia"
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
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
                # Use .any() to avoid Series boolean ambiguity
                if mask_para.any():
                    self.df.loc[mask_para, "Product Strain"] = "Paraphernalia"

                # Force CBD Blend for any ratio containing CBD, CBC, CBN or CBG
                mask_cbd_ratio = self.df["Ratio"].str.contains(
                    r"\b(?:CBD|CBC|CBN|CBG)\b", case=False, na=False
                )
                # Use .any() to avoid Series boolean ambiguity
                if mask_cbd_ratio.any():
                    self.df.loc[mask_cbd_ratio, "Product Strain"] = "CBD Blend"
                
                # If Description contains ":" or "CBD", set Product Strain to 'CBD Blend'
                mask_cbd_blend = self.df["Description"].str.contains(":", na=False) | self.df["Description"].str.contains("CBD", case=False, na=False)
                # Use .any() to avoid Series boolean ambiguity
                if mask_cbd_blend.any():
                    self.df.loc[mask_cbd_blend, "Product Strain"] = "CBD Blend"

            # 9) Convert key fields to categorical
            if self.df is not None and len(self.df) > 0:
                for col in ["Product Type*", "Lineage", "Product Brand", "Vendor"]:
                    if col in self.df.columns:
                        # Always convert to string and fillna first
                        self.df[col] = self.df[col].astype("string")
                        # Fill nulls before converting to categorical
                        self.df[col] = self.df[col].fillna("Unknown")
                        # Convert to categorical
                        self.df[col] = self.df[col].astype("category")
            else:
                self.logger.error("DataFrame is None or empty, cannot convert fields to categorical")
                return False

            # 10) CBD and Mixed overrides
            if "Lineage" in self.df.columns:
                # If Product Strain is 'CBD Blend', set Lineage to 'CBD'
                if "Product Strain" in self.df.columns:
                    cbd_blend_mask = self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend"
                    # Check if Lineage is categorical before adding categories
                    if hasattr(self.df["Lineage"], 'cat') and hasattr(self.df["Lineage"].cat, 'categories'):
                        if "CBD" not in self.df["Lineage"].cat.categories:
                            self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["CBD"])
                    self.df.loc[cbd_blend_mask, "Lineage"] = "CBD"

                # If Description or Product Name* contains CBD, CBG, CBN, CBC, set Lineage to 'CBD'
                cbd_mask = (
                    self.df["Description"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) |
                    (self.df[product_name_col].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) if product_name_col and product_name_col in self.df.columns else False)
                )
                # Use .any() to avoid Series boolean ambiguity
                if cbd_mask.any():
                    self.df.loc[cbd_mask, "Lineage"] = "CBD"

                # If Lineage is missing or empty, set to 'MIXED'
                empty_lineage_mask = self.df["Lineage"].isnull() | (self.df["Lineage"].astype(str).str.strip() == "")
                # Check if Lineage is categorical before adding categories
                if hasattr(self.df["Lineage"], 'cat') and hasattr(self.df["Lineage"].cat, 'categories'):
                    if "MIXED" not in self.df["Lineage"].cat.categories:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                # Use .any() to avoid Series boolean ambiguity
                if empty_lineage_mask.any():
                    self.df.loc[empty_lineage_mask, "Lineage"] = "MIXED"

                # --- NEW: For all edibles, set Lineage to 'MIXED' unless already 'CBD' ---
                edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                if "Product Type*" in self.df.columns:
                    edible_mask = self.df["Product Type*"].str.strip().str.lower().isin([e.lower() for e in edible_types])
                    not_cbd_mask = self.df["Lineage"].astype(str).str.upper() != "CBD"
                    # Check if Lineage is categorical before adding categories
                    if hasattr(self.df["Lineage"], 'cat') and hasattr(self.df["Lineage"].cat, 'categories'):
                        if "MIXED" not in self.df["Lineage"].cat.categories:
                            self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                    # Use .any() to avoid Series boolean ambiguity
                    combined_mask = edible_mask & not_cbd_mask
                    if combined_mask.any():
                        self.df.loc[combined_mask, "Lineage"] = "MIXED"

            # 11) Normalize Weight* and CombinedWeight
            if "Weight*" in self.df.columns:
                self.df["Weight*"] = pd.to_numeric(self.df["Weight*"], errors="coerce") \
                    .apply(lambda x: str(int(x)) if pd.notnull(x) and float(x).is_integer() else str(x))
            if "Weight*" in self.df.columns and "Units" in self.df.columns:
                # Fill null values before converting to categorical - more robust approach for pandas 2.0.3
                try:
                    # Create combined weight as string first, then handle nulls
                    combined_weight = (self.df["Weight*"] + self.df["Units"]).astype("string").fillna("Unknown")
                    self.df["CombinedWeight"] = combined_weight.astype("category")
                except Exception as e:
                    self.logger.warning(f"Error converting CombinedWeight to categorical: {e}")
                    # Fallback: keep as string type
                    combined_weight = (self.df["Weight*"] + self.df["Units"]).astype("string").fillna("Unknown")
                    self.df["CombinedWeight"] = combined_weight

            # 12) Format Price
            if "Price" in self.df.columns:
                def format_p(p):
                    if pd.isna(p) or p == '':
                        return ""
                    s = str(p).strip().lstrip("$").replace("'", "").strip()
                    try:
                        v = float(s)
                        if v == 0:
                            return ""  # Guarantee blank for zero or missing
                        if v == int(v):
                            return f"${int(v)}"
                        else:
                            return f"${v:.2f}"
                    except:
                        return f"${s}"
                # Ensure we have a clean index before applying price formatting
                if self.df.index.duplicated().any():
                    self.logger.warning("Duplicate indices detected before Price assignment, resetting index")
                    self.df = self.df.reset_index(drop=True)
                self.df["Price"] = self.df["Price"].apply(format_p)
                self.df["Price"] = self.df["Price"].astype("string")

            # 13) Special pre-roll Ratio logic
            def process_ratio(row):
                # Handle None row
                if row is None:
                    return ""
                # Safely get values with defaults
                try:
                    product_type = str(row.get("Product Type*", "")).strip().lower()
                    ratio = str(row.get("Ratio", "")).strip()
                except Exception:
                    return ""
                if product_type in ["pre-roll", "infused pre-roll"]:
                    if not ratio:
                        return ""
                    parts = ratio.split(" - ")
                    if len(parts) >= 3:
                        new = " - ".join(parts[2:]).strip()
                    elif len(parts) == 2:
                        new = parts[1].strip()
                    else:
                        new = parts[0].strip()
                    return f" - {new}" if new and not new.startswith(" - ") else new
                return ratio
            
            self.logger.debug("Applying special pre-roll ratio logic")
            try:
                # Check if DataFrame is still valid before proceeding
                if self.df is not None and len(self.df) > 0:
                    # Ensure we have a clean index before applying ratio processing
                    if self.df.index.duplicated().any():
                        self.logger.warning("Duplicate indices detected before Ratio assignment, resetting index")
                        self.df = self.df.reset_index(drop=True)
                    self.df["Ratio"] = self.df.apply(process_ratio, axis=1)
                    self.logger.debug(f"Final Ratio values after pre-roll processing: {self.df['Ratio'].head()}")
                else:
                    self.logger.error("DataFrame is None or empty, cannot process ratio")
                    return False
            except Exception as e:
                self.logger.error(f"Error processing ratio: {e}")
                # Fallback: create empty Ratio column
                if self.df is not None:
                    self.df["Ratio"] = ""
                else:
                    return False

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
                cols.remove("JointRatio")
                cols.insert(ratio_col_idx + 1, "JointRatio")
                # Ensure Description_Complexity is preserved
                if "Description_Complexity" not in cols:
                    cols.append("Description_Complexity")
                self.df = self.df[cols]

            # --- Reorder columns: move Description_Complexity, Ratio_or_THC_CBD, CombinedWeight after Lineage ---
            cols = self.df.columns.tolist()
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
            
            # Cache dropdown values
            self._cache_dropdown_values()
            self.logger.debug(f"Final columns after all processing: {self.df.columns.tolist()}")
            # Debug logging with safe column access
            debug_columns = []
            for col in ['Product Name*', 'Description', 'Ratio', 'Product Strain']:
                if col in self.df.columns:
                    debug_columns.append(col)
            if debug_columns:
                self.logger.debug(f"Sample data after all processing:\n{self.df[debug_columns].head()}")
            
            # Platform-consistent data validation and normalization
            self.validate_and_normalize_data()
            
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
            
            # Cache the processed file only if it's not None
            if self.df is not None:
                self._file_cache[cache_key] = self.df.copy()
                self._last_loaded_file = file_path
                
                # Final validation check
                if self.df is None or len(self.df) == 0:
                    self.logger.error("DataFrame is None or empty after processing")
                    return False
                
                # Manage cache size
                self._manage_cache_size()
                
                # Force garbage collection to free memory
                import gc
                gc.collect()

                self.logger.info(f"File loaded successfully: {len(self.df)} rows, {len(self.df.columns)} columns")
                return True
            else:
                self.logger.error("File processing failed - DataFrame is None")
                return False

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
                # PATCH: Exclude 'MIXED' from lineage dropdown if classic types are present in the filtered data
                if filter_id == 'lineage':
                    # If any classic types are present, exclude 'MIXED' from lineage dropdown
                    classic_types_present = self.df['Product Type*'].str.strip().str.lower().isin(CLASSIC_TYPES).any()
                    if classic_types_present:
                        values = [v for v in values if v.upper() != 'MIXED']
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
        
        # Debug: Show lineage distribution
        if 'Lineage' in filtered_df.columns:
            lineage_counts = filtered_df['Lineage'].value_counts()
            logger.info(f"get_available_tags: Lineage distribution: {dict(lineage_counts)}")
        
        tags = []
        filtered_out_count = 0
        filtered_out_reasons = {}
        
        for idx, row in filtered_df.iterrows():
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
                filtered_out_count += 1
                reason = f"weight={weight}" if weight == '-1g' else f"product_type={product_type}"
                filtered_out_reasons[reason] = filtered_out_reasons.get(reason, 0) + 1
                continue  # Skip this tag
            tags.append(tag)
        
        # Log filtering statistics
        if filtered_out_count > 0:
            logger.info(f"get_available_tags: Filtered out {filtered_out_count} items: {filtered_out_reasons}")
        
        # Sort tags by weight (least to greatest)
        def parse_weight(tag):
            return ExcelProcessor.parse_weight_str(tag.get('weight', ''), tag.get('weightWithUnits', ''))
        
        sorted_tags = sorted(tags, key=parse_weight)
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
            # Use the correct column name: 'Product Name*' instead of 'ProductName'
            product_name_col = 'Product Name*'
            if product_name_col not in self.df.columns:
                # Fallback to other possible column names
                possible_cols = ['ProductName', 'Product Name', 'Description']
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
                # Log the normalized versions of selected tags for debugging
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
                        "solventless concentrate", "vape cartridge"
                    ]
                    
                    # For classic types, ensure proper ratio format
                    if product_type in classic_types:
                        # Check if we have a valid ratio, otherwise use default
                        if not ratio_text or ratio_text in ["", "CBD", "THC", "CBD:", "THC:", "CBD:\n", "THC:\n"]:
                            ratio_text = "THC:\nCBD:"
                        # If ratio contains THC/CBD values, use it directly
                        elif any(cannabinoid in ratio_text.upper() for cannabinoid in ['THC', 'CBD', 'CBC', 'CBG', 'CBN']):
                            ratio_text = ratio_text  # Keep as is
                        # If it's a valid ratio format, use it
                        elif is_real_ratio(ratio_text):
                            ratio_text = ratio_text  # Keep as is
                        # Otherwise, use default THC:CBD format
                        else:
                            ratio_text = "THC:\nCBD:"
                    
                    # Format the ratio text
                    ratio_text = format_ratio_multiline(ratio_text)
                    
                    # Ensure we have a valid ratio text
                    if not ratio_text:
                        if product_type in classic_types:
                            ratio_text = "THC:\nCBD:"
                        else:
                            ratio_text = ""
                    
                    product_name = make_nonbreaking_hyphens(product_name)
                    description = make_nonbreaking_hyphens(description)
                    
                    # Get DOH value without normalization
                    doh_value = str(record.get('DOH', '')).strip().upper()
                    logger.debug(f"Processing DOH value: {doh_value}")
                    
                    # NEW LOGIC: Handle Product Strain and Lineage based on Classic Types
                    product_brand = record.get('Product Brand', '').upper()
                    original_lineage = str(record.get('Lineage', '')).upper()
                    original_product_strain = record.get('Product Strain', '')
                    
                    if product_type in classic_types:
                        # For Classic Types: Keep Lineage as is, remove Product Strain value
                        final_lineage = original_lineage
                        final_product_strain = ""  # Remove Product Strain value
                        lineage_needs_centering = False
                    else:
                        # For non-Classic Types: Use actual Product Strain value
                        final_lineage = product_brand  # Use Product Brand as Lineage
                        final_product_strain = original_product_strain  # Use actual Product Strain value
                        lineage_needs_centering = True  # Center the Product Brand when used as Lineage
                    
                    # Debug print for verification
                    print(f"Product: {product_name}, Type: {product_type}, ProductStrain: '{final_product_strain}'")
                    
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
                        'ProductStrain': wrap_with_marker(final_product_strain, "PRODUCTSTRAIN") if not product_type in classic_types else '',
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
        weight_val = record.get('Weight*', None)
        units_val = record.get('Units', '')
        product_type = record.get('Product Type*', '').strip().lower()
        edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
        preroll_types = {"pre-roll", "infused pre-roll"}

        # For pre-rolls and infused pre-rolls, use JointRatio if available
        if product_type in preroll_types:
            joint_ratio = record.get('JointRatio', '')
            if joint_ratio:
                return str(joint_ratio)
            else:
                return "THC:\nCBD:"

        try:
            weight_val = float(weight_val) if weight_val not in (None, '', 'nan') else None
        except Exception:
            weight_val = None

        if product_type in edible_types and units_val in {"g", "grams"} and weight_val is not None:
            weight_val = weight_val * 0.03527396195
            units_val = "oz"

        if weight_val is not None and units_val:
            weight_str = f"{weight_val:.2f}".rstrip("0").rstrip(".")
            weight_units = f"-{weight_str}{units_val}"
        else:
            weight_units = ""
        return weight_units

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
            "weight": "CombinedWeight",
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
                values = temp_df[col].dropna().unique().tolist()
                values = [str(v) for v in values if str(v).strip()]
                # Exclude unwanted product types from dropdown
                if filter_key == "productType":
                    filtered_values = []
                    for v in values:
                        v_lower = v.strip().lower()
                        if ("trade sample" in v_lower or "deactivated" in v_lower):
                            continue
                        filtered_values.append(v)
                    values = filtered_values
                options[filter_key] = clean_list(values)
            else:
                options[filter_key] = []
        return options

    def resolve_lineage_discrepancies(self, similarity_threshold: float = 0.8, min_group_size: int = 2) -> Dict[str, Any]:
        """
        Resolve lineage discrepancies by analyzing similar product descriptions and standardizing lineages.
        
        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider descriptions similar
            min_group_size: Minimum number of similar products to form a group for standardization
            
        Returns:
            Dict containing statistics about the resolution process
        """
        if self.df is None or self.df.empty:
            self.logger.warning("No data loaded to resolve lineage discrepancies")
            return {"error": "No data loaded"}
        
        self.logger.info("Starting lineage discrepancy resolution...")
        
        # Import required libraries for text similarity
        try:
            from difflib import SequenceMatcher
            from collections import defaultdict, Counter
            import numpy as np
        except ImportError as e:
            self.logger.error(f"Required libraries not available: {e}")
            return {"error": f"Required libraries not available: {e}"}
        
        # Statistics tracking
        stats = {
            "total_products": len(self.df),
            "groups_analyzed": 0,
            "lineages_standardized": 0,
            "products_affected": 0,
            "changes_made": [],
            "groups_found": []
        }
        
        # Ensure required columns exist
        if "Description" not in self.df.columns:
                            self.df["Description"] = self.df["ProductName"].astype("string").fillna("")
        if "Lineage" not in self.df.columns:
            self.logger.warning("Lineage column not found")
            return {"error": "Lineage column not found"}
        
        # Clean and normalize descriptions
        self.df["Description_Clean"] = self.df["Description"].astype("string").fillna("").astype(str).str.lower()
        self.df["Description_Clean"] = self.df["Description_Clean"].str.replace(r'[^\w\s]', ' ', regex=True)
        self.df["Description_Clean"] = self.df["Description_Clean"].str.replace(r'\s+', ' ', regex=True).str.strip()
        
        # Group products by similar descriptions
        processed_indices = set()
        groups = []
        
        for idx, row in self.df.iterrows():
            if idx in processed_indices:
                continue
                
            current_desc = row["Description_Clean"]
            if not current_desc or current_desc == "nan":
                continue
            
            # Find similar descriptions
            similar_indices = [idx]
            similar_descriptions = [current_desc]
            
            for other_idx, other_row in self.df.iterrows():
                if other_idx in processed_indices or other_idx == idx:
                    continue
                    
                other_desc = other_row["Description_Clean"]
                if not other_desc or other_desc == "nan":
                    continue
                
                # Calculate similarity
                similarity = SequenceMatcher(None, current_desc, other_desc).ratio()
                
                if similarity >= similarity_threshold:
                    similar_indices.append(other_idx)
                    similar_descriptions.append(other_desc)
            
            # Only create group if we have enough similar products
            if len(similar_indices) >= min_group_size:
                group = {
                    "indices": similar_indices,
                    "descriptions": similar_descriptions,
                    "lineages": [self.df.loc[i, "Lineage"] for i in similar_indices],
                    "product_names": [self.df.loc[i, "ProductName"] for i in similar_indices]
                }
                groups.append(group)
                processed_indices.update(similar_indices)
                stats["groups_found"].append({
                    "size": len(similar_indices),
                    "representative_desc": current_desc,
                    "lineages": group["lineages"]
                })
        
        stats["groups_analyzed"] = len(groups)
        self.logger.info(f"Found {len(groups)} groups of similar products")
        
        # Analyze and standardize lineages within each group
        for group in groups:
            if len(group["indices"]) < min_group_size:
                continue
            
            # Count lineages in this group
            lineage_counts = Counter(group["lineages"])
            most_common_lineage = lineage_counts.most_common(1)[0][0]
            most_common_count = lineage_counts.most_common(1)[0][1]
            
            # Calculate percentage of most common lineage
            lineage_percentage = most_common_count / len(group["lineages"])
            
            # Only standardize if majority is clear (more than 60% have same lineage)
            if lineage_percentage > 0.6:
                # Find products that need to be changed
                products_to_change = []
                for i, (idx, lineage) in enumerate(zip(group["indices"], group["lineages"])):
                    if lineage != most_common_lineage:
                        products_to_change.append({
                            "index": idx,
                            "old_lineage": lineage,
                            "new_lineage": most_common_lineage,
                            "product_name": group["product_names"][i],
                            "description": group["descriptions"][i]
                        })
                
                # Apply changes
                for change in products_to_change:
                    self.df.loc[change["index"], "Lineage"] = change["new_lineage"]
                    stats["changes_made"].append(change)
                    stats["products_affected"] += 1
                
                stats["lineages_standardized"] += 1
                
                self.logger.info(f"Standardized group with {len(group['indices'])} products: "
                               f"{most_common_lineage} ({most_common_count}/{len(group['lineages'])} = {lineage_percentage:.1%})")
        
        # Log summary
        self.logger.info(f"Lineage resolution complete:")
        self.logger.info(f"  - Groups analyzed: {stats['groups_analyzed']}")
        self.logger.info(f"  - Lineages standardized: {stats['lineages_standardized']}")
        self.logger.info(f"  - Products affected: {stats['products_affected']}")
        
        # Clean up temporary column
        if "Description_Clean" in self.df.columns:
            self.df = self.df.drop(columns=["Description_Clean"])
        
        return stats
    
    def get_lineage_discrepancy_report(self) -> Dict[str, Any]:
        """
        Generate a report of lineage discrepancies in the current dataset.
        
        Returns:
            Dict containing discrepancy analysis
        """
        if self.df is None or self.df.empty:
            return {"error": "No data loaded"}
        
        if "Description" not in self.df.columns or "Lineage" not in self.df.columns:
            return {"error": "Required columns (Description, Lineage) not found"}
        
        # Import required libraries
        try:
            from difflib import SequenceMatcher
            from collections import defaultdict, Counter
        except ImportError as e:
            return {"error": f"Required libraries not available: {e}"}
        
        # Clean descriptions for comparison
        self.df["Description_Clean"] = self.df["Description"].astype("string").fillna("").astype(str).str.lower()
        self.df["Description_Clean"] = self.df["Description_Clean"].str.replace(r'[^\w\s]', ' ', regex=True)
        self.df["Description_Clean"] = self.df["Description_Clean"].str.replace(r'\s+', ' ', regex=True).str.strip()
        
        # Find similar descriptions with different lineages
        discrepancies = []
        processed_pairs = set()
        
        for idx1, row1 in self.df.iterrows():
            desc1 = row1["Description_Clean"]
            lineage1 = row1["Lineage"]
            
            if not desc1 or desc1 == "nan":
                continue
            
            for idx2, row2 in self.df.iterrows():
                if idx1 >= idx2:  # Avoid duplicate comparisons
                    continue
                
                desc2 = row2["Description_Clean"]
                lineage2 = row2["Lineage"]
                
                if not desc2 or desc2 == "nan":
                    continue
                
                # Calculate similarity
                similarity = SequenceMatcher(None, desc1, desc2).ratio()
                
                # If descriptions are similar but lineages differ
                if similarity >= 0.8 and lineage1 != lineage2:
                    pair_key = tuple(sorted([idx1, idx2]))
                    if pair_key not in processed_pairs:
                        discrepancies.append({
                            "product1": {
                                "index": idx1,
                                "name": row1["ProductName"],
                                "description": desc1,
                                "lineage": lineage1
                            },
                            "product2": {
                                "index": idx2,
                                "name": row2["ProductName"],
                                "description": desc2,
                                "lineage": lineage2
                            },
                            "similarity": similarity
                        })
                        processed_pairs.add(pair_key)
        
        # Group discrepancies by description similarity
        discrepancy_groups = defaultdict(list)
        for disc in discrepancies:
            # Use the first description as the group key
            key = disc["product1"]["description"]
            discrepancy_groups[key].append(disc)
        
        # Analyze each group
        group_analysis = []
        for desc, group in discrepancy_groups.items():
            lineages = []
            for disc in group:
                lineages.extend([disc["product1"]["lineage"], disc["product2"]["lineage"]])
            
            lineage_counts = Counter(lineages)
            most_common = lineage_counts.most_common(1)[0] if lineage_counts else ("Unknown", 0)
            
            group_analysis.append({
                "description": desc,
                "products_count": len(group) * 2,  # Each discrepancy involves 2 products
                "lineages_found": dict(lineage_counts),
                "recommended_lineage": most_common[0],
                "recommended_count": most_common[1],
                "discrepancies": group
            })
        
        # Clean up
        if "Description_Clean" in self.df.columns:
            self.df = self.df.drop(columns=["Description_Clean"])
        
        return {
            "total_discrepancies": len(discrepancies),
            "discrepancy_groups": len(group_analysis),
            "groups": group_analysis,
            "summary": {
                "total_products": len(self.df),
                "products_with_discrepancies": len(set([d["product1"]["index"] for d in discrepancies] + 
                                                      [d["product2"]["index"] for d in discrepancies]))
            }
        }

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

    def get_tags_grouped_by_weight(self, filters: Optional[Dict[str, str]] = None):
        """
        Return an OrderedDict where keys are unique weights (e.g., '1g', '3.5g', etc.) sorted numerically,
        and values are lists of tag dicts for that weight.
        """
        tags = self.get_available_tags(filters)
        # Group tags by their weight+unit string (e.g., '3.5g', '14g', etc.)
        weight_map = {}
        for tag in tags:
            # Prefer weightWithUnits if available, else fallback to weight
            key = tag.get('weightWithUnits', '').strip() or str(tag.get('weight', '')).strip()
            if not key:
                key = 'Unknown'
            weight_map.setdefault(key, []).append(tag)
        # Sort the keys using the same parse_weight_str logic
        sorted_keys = sorted(weight_map.keys(), key=lambda k: ExcelProcessor.parse_weight_str(k))
        # Build ordered dict
        grouped = OrderedDict()
        for k in sorted_keys:
            grouped[k] = weight_map[k]
        return grouped

    def complete_processing(self):
        """Complete the data processing that was deferred during fast loading."""
        if self.df is None or self.df.empty:
            self.logger.warning("No data to process")
            return False
            
        try:
            self.logger.info("Starting full data processing...")
            
            # Ensure unique index to prevent "cannot reindex on an axis with duplicate labels" error
            self.df = self.df.reset_index(drop=True)
            
            # Define product_name_col at the very beginning to ensure it's available throughout the method
            product_name_col = 'Product Name*'
            if product_name_col not in self.df.columns:
                product_name_col = 'ProductName' if 'ProductName' in self.df.columns else None
            if not product_name_col:
                product_name_col = 'ProductName'  # Default fallback
            
            self.logger.info(f"Using product name column: '{product_name_col}' (available columns: {list(self.df.columns)})")
            
            # Apply all the transformations from the original load_file method
            # This is the heavy processing that was deferred
            
            # 1) Trim product names
            if "Product Name*" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name*"].str.lstrip()
            elif "Product Name" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name"].str.lstrip()
            elif "ProductName" in self.df.columns:
                self.df["Product Name*"] = self.df["ProductName"].str.lstrip()
            else:
                self.logger.error("No product name column found")
                self.df["Product Name*"] = "Unknown"

            # 2) Ensure required columns exist
            for col in ["Product Type*", "Lineage", "Product Brand"]:
                if col not in self.df.columns:
                    self.df[col] = "Unknown"

            # 3) Exclude sample rows and deactivated products
            initial_count = len(self.df)
            excluded_by_type = self.df[self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            self.df = self.df[~self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            
            # Also exclude products with excluded patterns
            for pattern in EXCLUDED_PRODUCT_PATTERNS:
                pattern_mask = self.df["Product Name*"].str.contains(pattern, case=False, na=False)
                self.df = self.df[~pattern_mask]
            
            final_count = len(self.df)
            self.logger.info(f"Product filtering complete: {initial_count} -> {final_count} products")
            
            # Reset index after filtering to ensure unique labels
            self.df = self.df.reset_index(drop=True)

            # 4) Rename for convenience
            self.df.rename(columns={
                "Product Name*": "ProductName",
                "Weight Unit* (grams/gm or ounces/oz)": "Units",
                "Price* (Tier Name for Bulk)": "Price",
                "Vendor/Supplier*": "Vendor",
                "DOH Compliant (Yes/No)": "DOH",
                "Concentrate Type": "Ratio"
            }, inplace=True)

            # 5) Normalize units
            if "Units" in self.df.columns:
                self.df["Units"] = self.df["Units"].str.lower().replace(
                    {"ounces": "oz", "grams": "g"}, regex=True
                )

            # 6) Standardize Lineage
            if "Lineage" in self.df.columns:
                # Normalize lineage values to standard format
                lineage_mapping = {
                    'indica': 'INDICA',
                    'sativa': 'SATIVA', 
                    'hybrid': 'HYBRID',
                    'hybrid/indica': 'HYBRID/INDICA',
                    'hybrid/sativa': 'HYBRID/SATIVA',
                    'cbd': 'CBD',
                    'cbd_blend': 'CBD',
                    'mixed': 'MIXED',
                    'paraphernalia': 'PARAPHERNALIA'
                }
                
                # First, normalize existing lineage values
                # Check if Lineage column is categorical
                if self.df["Lineage"].dtype.name == 'category':
                    # For categorical columns, we need to add new categories before filling
                    current_categories = self.df["Lineage"].cat.categories.tolist()
                    new_categories = ['HYBRID', 'MIXED'] + list(lineage_mapping.values())
                    missing_categories = [cat for cat in new_categories if cat not in current_categories]
                    if missing_categories:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(missing_categories)
                
                self.df["Lineage"] = (
                    self.df["Lineage"]
                        .apply(lambda x: str(x).lower().strip() if x is not None else 'MIXED')
                        .map(lambda x: lineage_mapping.get(x, x.upper()) if x else 'MIXED')
                        .fillna('MIXED')
                )
                
                # Define classic types
                classic_types = CLASSIC_TYPES
                
                # For classic types, ensure they have a valid lineage or default to HYBRID
                if "Product Type*" in self.df.columns:
                    classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(classic_types)
                    empty_lineage_mask = (self.df["Lineage"] == "") | (self.df["Lineage"].isna())
                    
                    # Classic types with empty lineage should default to HYBRID
                    classic_empty_mask = classic_mask & empty_lineage_mask
                    if classic_empty_mask.any():
                        self.df.loc[classic_empty_mask, "Lineage"] = "HYBRID"
                        self.logger.info(f"Set {classic_empty_mask.sum()} classic type products with empty lineage to HYBRID")
                    
                    # Non-classic types with empty lineage should default to MIXED
                    non_classic_empty_mask = (~classic_mask) & empty_lineage_mask
                    if non_classic_empty_mask.any():
                        self.df.loc[non_classic_empty_mask, "Lineage"] = "MIXED"
                        self.logger.info(f"Set {non_classic_empty_mask.sum()} non-classic type products with empty lineage to MIXED")
                
                # Log final lineage distribution
                lineage_dist = self.df["Lineage"].value_counts()
                self.logger.info(f"Final lineage distribution: {lineage_dist.to_dict()}")

            # 7) Build Description & Ratio & Strain
            if "ProductName" in self.df.columns:
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
                    if hasattr(name, 'dtype') and hasattr(name, 'iloc'):  # It's a pandas Series
                        return ""
                    name = str(name).strip()
                    if not name:
                        return ""
                    if ' by ' in name:
                        return name.split(' by ')[0].strip()
                    if ' - ' in name:
                        return name.rsplit(' - ', 1)[0].strip()
                    return name.strip()

                # Ensure Product Name* is string type before applying
                if product_name_col:
                    # BULLETPROOF FIX: Complete rewrite for complete_processing
                    self.logger.info("Using bulletproof method for Description column assignment in complete_processing")
                    
                    try:
                        # Step 1: Always reset index to ensure clean state
                        self.df = self.df.reset_index(drop=True)
                        self.logger.info(f"DataFrame shape after reset in complete_processing: {self.df.shape}")
                        
                        # Step 2: Get product names as a simple list
                        product_names_list = self.df[product_name_col].astype(str).tolist()
                        self.logger.info(f"Product names list length in complete_processing: {len(product_names_list)}")
                        
                        # Step 3: Generate descriptions using list comprehension
                        descriptions_list = []
                        for i, name in enumerate(product_names_list):
                            try:
                                desc = get_description(name)
                                descriptions_list.append(desc)
                            except Exception as e:
                                self.logger.warning(f"Error getting description for product {i} in complete_processing: {e}")
                                descriptions_list.append("")
                        
                        self.logger.info(f"Descriptions list length in complete_processing: {len(descriptions_list)}")
                        
                        # Step 4: Verify lengths match
                        if len(descriptions_list) != len(self.df):
                            self.logger.error(f"Length mismatch in complete_processing: descriptions={len(descriptions_list)}, df={len(self.df)}")
                            # Pad or truncate to match
                            if len(descriptions_list) < len(self.df):
                                descriptions_list.extend([""] * (len(self.df) - len(descriptions_list)))
                            else:
                                descriptions_list = descriptions_list[:len(self.df)]
                        
                        # Step 5: Create new DataFrame with all existing data plus Description
                        new_df_data = {}
                        
                        # Copy all existing columns
                        for col in self.df.columns:
                            try:
                                # Convert Series to list safely
                                if hasattr(self.df[col], 'tolist'):
                                    new_df_data[col] = self.df[col].tolist()
                                else:
                                    # Fallback for non-Series objects
                                    new_df_data[col] = list(self.df[col])
                            except Exception as e:
                                self.logger.warning(f"Error converting column {col} to list in complete_processing: {e}")
                                # Create empty list of correct length
                                new_df_data[col] = [""] * len(self.df)
                        
                        # Add Description column
                        new_df_data["Description"] = descriptions_list
                        
                        # Step 6: Create completely new DataFrame
                        self.df = pd.DataFrame(new_df_data)
                        self.logger.info(f"New DataFrame shape in complete_processing: {self.df.shape}")
                        self.logger.info("Bulletproof method successful in complete_processing")
                        
                    except Exception as e:
                        self.logger.error(f"Bulletproof method failed in complete_processing: {e}")
                        
                        try:
                            # Emergency fallback: Create minimal working DataFrame
                            self.logger.info("Attempting emergency fallback in complete_processing")
                            
                            # Get the length of the original DataFrame
                            original_length = len(self.df)
                            
                            # Create minimal data with essential columns
                            minimal_data = {
                                "Description": [""] * original_length
                            }
                            
                            # Add any existing columns that we can safely copy
                            safe_columns = ["Product Name*", "Product Type*", "Lineage", "Product Brand"]
                            for col in safe_columns:
                                if col in self.df.columns:
                                    try:
                                        # Convert Series to list safely
                                        if hasattr(self.df[col], 'tolist'):
                                            col_data = self.df[col].tolist()
                                        else:
                                            col_data = list(self.df[col])
                                        
                                        if len(col_data) == original_length:
                                            minimal_data[col] = col_data
                                        else:
                                            minimal_data[col] = [""] * original_length
                                    except Exception as e:
                                        self.logger.warning(f"Error copying column {col}: {e}")
                                        minimal_data[col] = [""] * original_length
                            
                            # Create new DataFrame
                            self.df = pd.DataFrame(minimal_data)
                            self.logger.info(f"Emergency fallback successful in complete_processing: {self.df.shape}")
                            
                        except Exception as e2:
                            self.logger.error(f"Emergency fallback failed in complete_processing: {e2}")
                            # Absolute last resort: empty DataFrame with essential columns
                            last_resort_data = {
                                "Description": [""],
                                "Product Type*": ["Unknown"],
                                "Lineage": ["HYBRID"],
                                "Product Brand": ["Unknown"],
                                "Product Strain": ["Mixed"]
                            }
                            if product_name_col:
                                last_resort_data[product_name_col] = [""]
                            self.df = pd.DataFrame(last_resort_data)
                            self.logger.info("Absolute last resort in complete_processing: empty DataFrame created")
                
                
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
                self.df.loc[mask_para, "Description"] = (
                    self.df.loc[mask_para, "Description"]
                    .str.replace(r"\s*-\s*\d+g$", "", regex=True)
                )

                # Calculate complexity for Description column
                self.df["Description_Complexity"] = self.df["Description"].apply(_complexity)

                # Build cannabinoid content info
                self.logger.debug("Extracting cannabinoid content from Product Name")
                # Extract text following the FINAL hyphen only
                if product_name_col:
                    # Extract ratio and handle nulls safely
                    ratio_extracted = self.df[product_name_col].str.extract(r".*-\s*(.+)")
                    # Fill nulls with empty string, but ensure it's a string type first
                    self.df["Ratio"] = ratio_extracted.astype("string").fillna("")
                else:
                    self.df["Ratio"] = ""
                self.logger.debug(f"Sample cannabinoid content values before processing: {self.df['Ratio'].head()}")
                
                self.df["Ratio"] = self.df["Ratio"].str.replace(r" / ", " ", regex=True)
                self.logger.debug(f"Sample cannabinoid content values after processing: {self.df['Ratio'].head()}")

                # Set Ratio_or_THC_CBD based on product type
                def set_ratio_or_thc_cbd(row):
                    product_type = str(row.get("Product Type*", "")).strip().lower()
                    ratio = str(row.get("Ratio", "")).strip()
                    classic_types = [
                        "flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge"
                    ]
                    BAD_VALUES = {"", "CBD", "THC", "CBD:", "THC:", "CBD:\n", "THC:\n"}
                    
                    # For pre-rolls and infused pre-rolls, always use THC: CBD: format
                    if product_type in ["pre-roll", "infused pre-roll"]:
                        return "THC:\nCBD:"
                    
                    # For solventless concentrate, check if ratio is a weight + unit format
                    if product_type == "solventless concentrate":
                        if not ratio or ratio in BAD_VALUES or not is_weight_with_unit(ratio):
                            return "1g"
                        return ratio
                    
                    if product_type in classic_types:
                        if not ratio or ratio in BAD_VALUES:
                            return "THC:\nCBD:"
                        # If ratio contains THC/CBD values, use it directly
                        if any(cannabinoid in ratio.upper() for cannabinoid in ['THC', 'CBD', 'CBC', 'CBG', 'CBN']):
                            return ratio
                        # If it's a valid ratio format, use it
                        if is_real_ratio(ratio):
                            return ratio
                        # Otherwise, use default THC:CBD format
                        return "THC:\nCBD:"
                    
                    # NEW: For Edibles, if ratio is missing, default to "THC:\nCBD:"
                    edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                    if product_type in edible_types:
                        if not ratio or ratio in BAD_VALUES:
                            return "THC:\nCBD:"
                    
                    return ratio

                self.df["Ratio_or_THC_CBD"] = self.df.apply(set_ratio_or_thc_cbd, axis=1)
                self.logger.debug(f"Ratio_or_THC_CBD values: {self.df['Ratio_or_THC_CBD'].head()}")

                # Ensure Product Strain exists and is categorical
                if "Product Strain" not in self.df.columns:
                    self.df["Product Strain"] = ""
                # Fill null values before converting to categorical
                self.df["Product Strain"] = self.df["Product Strain"].fillna("Mixed")
                self.df["Product Strain"] = self.df["Product Strain"].astype("category")
                self.df["Product Strain"] = safe_fillna_categorical(self.df["Product Strain"], "Mixed")

                # Special case: paraphernalia gets Product Strain set to "Paraphernalia"
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
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
                # Use .any() to avoid Series boolean ambiguity
                if mask_para.any():
                    self.df.loc[mask_para, "Product Strain"] = "Paraphernalia"

                # Force CBD Blend for any ratio containing CBD, CBC, CBN or CBG
                mask_cbd_ratio = self.df["Ratio"].str.contains(
                    r"\b(?:CBD|CBC|CBN|CBG)\b", case=False, na=False
                )
                # Use .any() to avoid Series boolean ambiguity
                if mask_cbd_ratio.any():
                    self.df.loc[mask_cbd_ratio, "Product Strain"] = "CBD Blend"
                
                # If Description contains ":" or "CBD", set Product Strain to 'CBD Blend'
                mask_cbd_blend = self.df["Description"].str.contains(":", na=False) | self.df["Description"].str.contains("CBD", case=False, na=False)
                # Use .any() to avoid Series boolean ambiguity
                if mask_cbd_blend.any():
                    self.df.loc[mask_cbd_blend, "Product Strain"] = "CBD Blend"

            # 9) Convert key fields to categorical
            for col in ["Product Type*", "Lineage", "Product Brand", "Vendor"]:
                if col in self.df.columns:
                    # Fill null values before converting to categorical - more robust approach for pandas 2.0.3
                    try:
                        # First, ensure the column exists and has data
                        if self.df[col].isnull().any():
                            # For pandas 2.0.3, we need to handle categorical fillna differently
                            # Convert to string first, fill nulls, then convert to categorical
                            self.df[col] = self.df[col].astype("string").fillna("Unknown")
                        else:
                            # No nulls, just convert to string first
                            self.df[col] = self.df[col].astype("string")
                        
                        # Convert to categorical with error handling
                        self.df[col] = self.df[col].astype("category")
                    except Exception as e:
                        self.logger.warning(f"Error converting {col} to categorical: {e}")
                        # Fallback: keep as string type
                        self.df[col] = self.df[col].astype("string")

            # 10) CBD and Mixed overrides
            if "Lineage" in self.df.columns:
                # If Product Strain is 'CBD Blend', set Lineage to 'CBD'
                if "Product Strain" in self.df.columns:
                    cbd_blend_mask = self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend"
                    # Check if Lineage is categorical before adding categories
                    if hasattr(self.df["Lineage"], 'cat') and hasattr(self.df["Lineage"].cat, 'categories'):
                        if "CBD" not in self.df["Lineage"].cat.categories:
                            self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["CBD"])
                    self.df.loc[cbd_blend_mask, "Lineage"] = "CBD"

                # If Description or Product Name* contains CBD, CBG, CBN, CBC, set Lineage to 'CBD'
                cbd_mask = (
                    self.df["Description"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) |
                    (self.df[product_name_col].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) if product_name_col and product_name_col in self.df.columns else False)
                )
                # Use .any() to avoid Series boolean ambiguity
                if cbd_mask.any():
                    self.df.loc[cbd_mask, "Lineage"] = "CBD"

                # If Lineage is missing or empty, set to 'MIXED'
                empty_lineage_mask = self.df["Lineage"].isnull() | (self.df["Lineage"].astype(str).str.strip() == "")
                # Check if Lineage is categorical before adding categories
                if hasattr(self.df["Lineage"], 'cat') and hasattr(self.df["Lineage"].cat, 'categories'):
                    if "MIXED" not in self.df["Lineage"].cat.categories:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                # Use .any() to avoid Series boolean ambiguity
                if empty_lineage_mask.any():
                    self.df.loc[empty_lineage_mask, "Lineage"] = "MIXED"

                # --- NEW: For all edibles, set Lineage to 'MIXED' unless already 'CBD' ---
                edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
                if "Product Type*" in self.df.columns:
                    edible_mask = self.df["Product Type*"].str.strip().str.lower().isin([e.lower() for e in edible_types])
                    not_cbd_mask = self.df["Lineage"].astype(str).str.upper() != "CBD"
                    # Check if Lineage is categorical before adding categories
                    if hasattr(self.df["Lineage"], 'cat') and hasattr(self.df["Lineage"].cat, 'categories'):
                        if "MIXED" not in self.df["Lineage"].cat.categories:
                            self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["MIXED"])
                    # Use .any() to avoid Series boolean ambiguity
                    combined_mask = edible_mask & not_cbd_mask
                    if combined_mask.any():
                        self.df.loc[combined_mask, "Lineage"] = "MIXED"

            # 11) Normalize Weight* and CombinedWeight
            if "Weight*" in self.df.columns:
                self.df["Weight*"] = pd.to_numeric(self.df["Weight*"], errors="coerce") \
                    .apply(lambda x: str(int(x)) if pd.notnull(x) and float(x).is_integer() else str(x))
            if "Weight*" in self.df.columns and "Units" in self.df.columns:
                # Fill null values before converting to categorical - more robust approach for pandas 2.0.3
                try:
                    # Create combined weight as string first, then handle nulls
                    combined_weight = (self.df["Weight*"] + self.df["Units"]).astype("string").fillna("Unknown")
                    self.df["CombinedWeight"] = combined_weight.astype("category")
                except Exception as e:
                    self.logger.warning(f"Error converting CombinedWeight to categorical: {e}")
                    # Fallback: keep as string type
                    combined_weight = (self.df["Weight*"] + self.df["Units"]).astype("string").fillna("Unknown")
                    self.df["CombinedWeight"] = combined_weight

            # 12) Format Price
            if "Price" in self.df.columns:
                def format_p(p):
                    if pd.isna(p) or p == '':
                        return ""
                    s = str(p).strip().lstrip("$").replace("'", "").strip()
                    try:
                        v = float(s)
                        if v == 0:
                            return ""  # Guarantee blank for zero or missing
                        if v == int(v):
                            return f"${int(v)}"
                        else:
                            return f"${v:.2f}"
                    except:
                        return f"${s}"
                try:
                    # Ensure we have a clean index before applying price formatting
                    if self.df.index.duplicated().any():
                        self.logger.warning("Duplicate indices detected before Price assignment, resetting index")
                        self.df = self.df.reset_index(drop=True)
                    self.df["Price"] = self.df["Price"].apply(format_p)
                    self.df["Price"] = self.df["Price"].astype("string")
                except Exception as e:
                    self.logger.error(f"Error formatting Price column: {e}")
                    # Fallback: keep original price values
                    self.df["Price"] = self.df["Price"].astype("string")

            # 13) Special pre-roll Ratio logic
            def process_ratio(row):
                t = str(row.get("Product Type*", "")).strip().lower()
                if t in ["pre-roll", "infused pre-roll"]:
                    parts = str(row.get("Ratio", "")).split(" - ")
                    if len(parts) >= 3:
                        new = " - ".join(parts[2:]).strip()
                    elif len(parts) == 2:
                        new = parts[1].strip()
                    else:
                        new = parts[0].strip()
                    return f" - {new}" if new and not new.startswith(" - ") else new
                return row.get("Ratio", "")
            
            self.logger.debug("Applying special pre-roll ratio logic")
            try:
                # Ensure we have a clean index before applying ratio processing
                if self.df.index.duplicated().any():
                    self.logger.warning("Duplicate indices detected before Ratio assignment, resetting index")
                    self.df = self.df.reset_index(drop=True)
                self.df["Ratio"] = self.df.apply(process_ratio, axis=1)
                self.logger.debug(f"Final Ratio values after pre-roll processing: {self.df['Ratio'].head()}")
            except Exception as e:
                self.logger.error(f"Error processing Ratio column: {e}")
                # Fallback: keep original ratio values
                pass

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
                cols.remove("JointRatio")
                cols.insert(ratio_col_idx + 1, "JointRatio")
                # Ensure Description_Complexity is preserved
                if "Description_Complexity" not in cols:
                    cols.append("Description_Complexity")
                self.df = self.df[cols]

            # --- Reorder columns: move Description_Complexity, Ratio_or_THC_CBD, CombinedWeight after Lineage ---
            cols = self.df.columns.tolist()
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

            # 14) Apply mode lineage for Classic Types based on Product Strain
            self.logger.debug("Applying mode lineage for Classic Types based on Product Strain")
            
            # Filter for Classic Types only
            classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(CLASSIC_TYPES)
            classic_df = self.df[classic_mask].copy()
            
            if not classic_df.empty and "Product Strain" in classic_df.columns:
                # Get all unique strain names from Classic Types
                unique_strains = classic_df["Product Strain"].dropna().unique()
                valid_strains = [s for s in unique_strains if normalize_strain_name(s)]
                
                if valid_strains:
                    # Group similar strains together
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
                                # Find the mode (most common) lineage with new prioritization rules
                                lineage_counts = lineage_values.value_counts()
                                total_records = len(lineage_values)
                                
                                # Get the most common lineage
                                most_common_lineage = lineage_counts.index[0]
                                most_common_count = lineage_counts.iloc[0]
                                
                                # Check if Hybrid is the most common
                                if most_common_lineage == 'HYBRID':
                                    # Look for non-Hybrid alternatives
                                    non_hybrid_lineages = ['SATIVA', 'INDICA', 'CBD']
                                    non_hybrid_counts = {}
                                    
                                    for lineage in non_hybrid_lineages:
                                        if lineage in lineage_counts.index:
                                            non_hybrid_counts[lineage] = lineage_counts[lineage]
                                    
                                    # If we have non-Hybrid alternatives, prioritize them
                                    if non_hybrid_counts:
                                        # Find the most common non-Hybrid lineage
                                        best_non_hybrid = max(non_hybrid_counts.items(), key=lambda x: x[1])
                                        best_non_hybrid_lineage, best_non_hybrid_count = best_non_hybrid
                                        
                                        # Use the non-Hybrid lineage if it has a reasonable presence
                                        # (at least 25% of total records or at least 2 records)
                                        if best_non_hybrid_count >= max(2, total_records * 0.25):
                                            most_common_lineage = best_non_hybrid_lineage
                                            self.logger.debug(f"Prioritized non-Hybrid '{best_non_hybrid_lineage}' over Hybrid (count: {best_non_hybrid_count}/{total_records})")
                                        else:
                                            self.logger.debug(f"Keeping Hybrid as mode despite non-Hybrid alternatives (Hybrid: {most_common_count}, best non-Hybrid: {best_non_hybrid_count}/{total_records})")
                                    else:
                                        self.logger.debug(f"Hybrid is mode with no non-Hybrid alternatives (count: {most_common_count}/{total_records})")
                                
                                # Also check for Hybrid/Sativa and Hybrid/Indica combinations
                                elif most_common_lineage in ['HYBRID/SATIVA', 'HYBRID/INDICA']:
                                    # Look for pure alternatives (SATIVA, INDICA)
                                    pure_alternatives = {}
                                    if most_common_lineage == 'HYBRID/SATIVA':
                                        if 'SATIVA' in lineage_counts.index:
                                            pure_alternatives['SATIVA'] = lineage_counts['SATIVA']
                                    elif most_common_lineage == 'HYBRID/INDICA':
                                        if 'INDICA' in lineage_counts.index:
                                            pure_alternatives['INDICA'] = lineage_counts['INDICA']
                                    
                                    # If we have pure alternatives, prioritize them
                                    if pure_alternatives:
                                        best_pure = max(pure_alternatives.items(), key=lambda x: x[1])
                                        best_pure_lineage, best_pure_count = best_pure
                                        
                                        # Use the pure lineage if it has a reasonable presence
                                        if best_pure_count >= max(2, total_records * 0.25):
                                            most_common_lineage = best_pure_lineage
                                            self.logger.debug(f"Prioritized pure '{best_pure_lineage}' over {most_common_lineage} (count: {best_pure_count}/{total_records})")
                                        else:
                                            self.logger.debug(f"Keeping {most_common_lineage} as mode despite pure alternatives (count: {most_common_count}, best pure: {best_pure_count}/{total_records})")
                                
                                strain_lineage_map[group_key] = most_common_lineage
                                
                                # Log the grouping and mode lineage
                                strain_list = ", ".join(group_strains)
                                self.logger.debug(f"Strain Group '{group_key}' ({strain_list}) -> Mode Lineage: '{most_common_lineage}' (from {len(lineage_values)} records)")
                                self.logger.debug(f"Lineage distribution: {lineage_counts.to_dict()}")
                
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

        except Exception as e:
            self.logger.error(f"Error in mode lineage processing: {e}")

        # Convert string columns to categorical where appropriate to save memory
        categorical_columns = ['Product Type*', 'Lineage', 'Product Brand', 'Vendor', 'Product Strain']
        for col in categorical_columns:
            if col in self.df.columns:
                # Only convert if the column has reasonable number of unique values
                unique_count = self.df[col].nunique()
                if unique_count < len(self.df) * 0.5:  # Less than 50% unique values
                    self.df[col] = self.df[col].astype('category')
                    self.logger.debug(f"Converted {col} to categorical (unique values: {unique_count})")
        
        # Cache dropdown values
        self._cache_dropdown_values()
        self.logger.debug(f"Final columns after all processing: {self.df.columns.tolist()}")
        # Debug logging with safe column access
        debug_columns = []
        for col in ['Product Name*', 'Description', 'Ratio', 'Product Strain']:
            if col in self.df.columns:
                debug_columns.append(col)
        if debug_columns:
            self.logger.debug(f"Sample data after all processing:\n{self.df[debug_columns].head()}")
        
        # Platform-consistent data validation and normalization
        if self.df is not None:
            self.validate_and_normalize_data()
        
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

        self.logger.info(f"File loaded successfully: {len(self.df)} rows, {len(self.df.columns)} columns")
        return True

    def validate_and_normalize_data(self):
        """
        Validate and normalize data consistently across all platforms.
        This ensures the same processing steps are applied identically.
        """
        if self.df is None or self.df.empty:
            self.logger.warning("No data to validate and normalize")
            return False
            
        try:
            self.logger.info("Starting platform-consistent data validation and normalization...")
            
            # 1. Handle Lineage values FIRST (before general string normalization)
            if "Lineage" in self.df.columns:
                # Normalize lineage values to standard format
                lineage_mapping = {
                    'indica': 'INDICA',
                    'sativa': 'SATIVA', 
                    'hybrid': 'HYBRID',
                    'hybrid/indica': 'HYBRID/INDICA',
                    'hybrid/sativa': 'HYBRID/SATIVA',
                    'cbd': 'CBD',
                    'cbd_blend': 'CBD',
                    'mixed': 'MIXED',
                    'paraphernalia': 'PARAPHERNALIA'
                }
                
                # First, normalize existing lineage values
                # Check if Lineage column is categorical
                if self.df["Lineage"].dtype.name == 'category':
                    # For categorical columns, we need to add new categories before filling
                    current_categories = self.df["Lineage"].cat.categories.tolist()
                    new_categories = ['HYBRID', 'MIXED'] + list(lineage_mapping.values())
                    missing_categories = [cat for cat in new_categories if cat not in current_categories]
                    if missing_categories:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(missing_categories)
                
                self.df["Lineage"] = (
                    self.df["Lineage"]
                        .apply(lambda x: str(x).lower().strip() if x is not None else 'MIXED')
                        .map(lambda x: lineage_mapping.get(x, x.upper()) if x else 'MIXED')
                        .fillna('MIXED')
                )
                
                # Define classic types
                classic_types = CLASSIC_TYPES
                
                # For classic types, ensure they have a valid lineage or default to HYBRID
                if "Product Type*" in self.df.columns:
                    classic_mask = self.df["Product Type*"].str.strip().str.lower().isin(classic_types)
                    empty_lineage_mask = (self.df["Lineage"] == "") | (self.df["Lineage"].isna())
                    
                    # Classic types with empty lineage should default to HYBRID
                    classic_empty_mask = classic_mask & empty_lineage_mask
                    if classic_empty_mask.any():
                        self.df.loc[classic_empty_mask, "Lineage"] = "HYBRID"
                        self.logger.info(f"Set {classic_empty_mask.sum()} classic type products with empty lineage to HYBRID")
                    
                    # Non-classic types with empty lineage should default to MIXED
                    non_classic_empty_mask = (~classic_mask) & empty_lineage_mask
                    if non_classic_empty_mask.any():
                        self.df.loc[non_classic_empty_mask, "Lineage"] = "MIXED"
                        self.logger.info(f"Set {non_classic_empty_mask.sum()} non-classic type products with empty lineage to MIXED")
                
                # Log final lineage distribution
                lineage_dist = self.df["Lineage"].value_counts()
                self.logger.info(f"Final lineage distribution: {lineage_dist.to_dict()}")
            
            # 2. Ensure all other string columns are properly normalized
            string_columns = ["ProductName", "Description", "Product Brand", "Vendor", "Product Type*"]
            for col in string_columns:
                if col in self.df.columns:
                    # Check if column is categorical
                    if self.df[col].dtype.name == 'category':
                        # For categorical columns, add 'Unknown' and '' as needed
                        current_categories = self.df[col].cat.categories.tolist()
                        to_add = []
                        if 'Unknown' not in current_categories:
                            to_add.append('Unknown')
                        if to_add:
                            self.df[col] = self.df[col].cat.add_categories(to_add)
                        self.df[col] = self.df[col].fillna('Unknown')
                        # For categorical columns, don't replace with empty strings - use 'Unknown' instead
                        # Ensure 'Unknown' is in categories before replacing
                        if 'Unknown' not in self.df[col].cat.categories:
                            self.df[col] = self.df[col].cat.add_categories(['Unknown'])
                        self.df[col] = self.df[col].replace({None: 'Unknown', pd.NA: 'Unknown', float('nan'): 'Unknown'})
                    else:
                        self.df[col] = self.df[col].fillna('Unknown')
                        self.df[col] = self.df[col].replace({None: '', pd.NA: '', float('nan'): ''})

            # --- Lineage normalization (already handled above, but ensure fillna is safe) ---
            if "Lineage" in self.df.columns:
                if self.df["Lineage"].dtype.name == 'category':
                    current_categories = self.df["Lineage"].cat.categories.tolist()
                    to_add = []
                    if 'HYBRID' not in current_categories:
                        to_add.append('HYBRID')
                    if 'MIXED' not in current_categories:
                        to_add.append('MIXED')
                    if to_add:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(to_add)
                # Now safe to fillna - ensure we're not trying to fill with empty string
                if self.df["Lineage"].dtype.name == 'category':
                    # For categorical, ensure 'MIXED' is in categories
                    if 'MIXED' not in self.df["Lineage"].cat.categories:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(['MIXED'])
                self.df["Lineage"] = self.df["Lineage"].fillna('MIXED')

            # 3. Validate required columns exist and have data
            required_columns = ["ProductName", "Product Type*", "Lineage", "Product Brand"]
            missing_columns = []
            empty_columns = []
            
            for col in required_columns:
                if col not in self.df.columns:
                    missing_columns.append(col)
                elif self.df[col].isna().all() or (self.df[col] == '').all():
                    empty_columns.append(col)
            
            if missing_columns:
                self.logger.warning(f"Missing required columns: {missing_columns}")
                for col in missing_columns:
                    self.df[col] = "Unknown"
            
            if empty_columns:
                self.logger.warning(f"Empty required columns: {empty_columns}")
                for col in empty_columns:
                    self.df[col] = "Unknown"
            
            # 4. Ensure consistent data types
            # Convert numeric columns to appropriate types
            numeric_columns = ["Weight*"]  # Only Weight* should be forced to numeric with fillna(0)
            for col in numeric_columns:
                if col in self.df.columns:
                    # Try to convert to numeric, fill NaN with 0
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)
            # Do NOT convert Price to numeric or fill NaN with 0; leave as is for formatting
            
            # 5. Remove any completely empty rows
            initial_rows = len(self.df)
            self.df = self.df.dropna(how='all')
            final_rows = len(self.df)
            
            if initial_rows != final_rows:
                self.logger.info(f"Removed {initial_rows - final_rows} completely empty rows")
            
            # 6. Log final data summary
            self.logger.info(f"Data validation complete: {len(self.df)} rows, {len(self.df.columns)} columns")
            self.logger.info(f"Sample data after validation:\n{self.df[['ProductName', 'Product Type*', 'Lineage']].head()}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in data validation: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

def safe_fillna_categorical(series, value="Unknown"):
    if pd.api.types.is_categorical_dtype(series):
        if value not in series.cat.categories:
            series = series.cat.add_categories([value])
    return series.fillna(value)

