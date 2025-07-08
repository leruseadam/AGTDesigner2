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
    """Calculate similarity between two strain names."""
    if not strain1 or not strain2:
        return 0.0
    
    norm1 = normalize_strain_name(strain1)
    norm2 = normalize_strain_name(strain2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Exact match
    if norm1 == norm2:
        return 1.0
    
    # Check if one is contained in the other (e.g., "OG Kush" vs "OG")
    if norm1 in norm2 or norm2 in norm1:
        return 0.9
    
    # Check for common variations
    variations = {
        'og kush': ['og', 'og kush', 'original gangster kush'],
        'blue dream': ['blue dream', 'blue dream haze'],
        'white widow': ['white widow', 'white widow x'],
        'purple haze': ['purple haze', 'purple haze x'],
        'jack herer': ['jack herer', 'jack'],
        'northern lights': ['northern lights', 'nl'],
        'sour diesel': ['sour diesel', 'sour d', 'sour deez'],
        'afghan kush': ['afghan kush', 'afghan'],
        'uk cheese': ['uk cheese', 'cheese', 'exodus cheese'],
        'amnesia haze': ['amnesia haze', 'amnesia']
    }
    
    for canonical, variants in variations.items():
        if norm1 in variants and norm2 in variants:
            return 0.95
    
    # Calculate basic string similarity
    from difflib import SequenceMatcher
    return SequenceMatcher(None, norm1, norm2).ratio()


def group_similar_strains(strains, similarity_threshold=0.8):
    """Group similar strain names together."""
    if not strains:
        return {}
    
    # Normalize all strains
    normalized_strains = {}
    for strain in strains:
        norm = normalize_strain_name(strain)
        if norm:
            normalized_strains[strain] = norm
    
    # Group similar strains
    groups = {}
    processed = set()
    
    for strain1, norm1 in normalized_strains.items():
        if strain1 in processed:
            continue
            
        # Start a new group
        group_key = strain1
        groups[group_key] = [strain1]
        processed.add(strain1)
        
        # Find similar strains
        for strain2, norm2 in normalized_strains.items():
            if strain2 in processed:
                continue
                
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
        """Fast file loading with essential processing for uploads."""
        try:
            self.logger.debug(f"Fast loading file: {file_path}")
            
            # Validate file exists
            import os
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                return False
            
            # Clear previous data
            if hasattr(self, 'df') and self.df is not None:
                del self.df
                import gc
                gc.collect()
            
            # Read with minimal processing
            try:
                self.df = pd.read_excel(file_path, engine='openpyxl')
                self.logger.info(f"Fast loaded: {len(self.df)} rows, {len(self.df.columns)} columns")
                
                # Basic cleanup only
                if self.df.empty:
                    self.logger.error("No data found in Excel file")
                    return False
                
                # Remove duplicates
                initial_count = len(self.df)
                self.df.drop_duplicates(inplace=True)
                if len(self.df) != initial_count:
                    self.logger.info(f"Removed {initial_count - len(self.df)} duplicate rows")
                
                # ESSENTIAL: Ensure required columns exist for frontend compatibility
                if "Product Name*" in self.df.columns:
                    self.df["Product Name*"] = self.df["Product Name*"].str.lstrip()
                elif "Product Name" in self.df.columns:
                    self.df["Product Name*"] = self.df["Product Name"].str.lstrip()
                elif "ProductName" in self.df.columns:
                    self.df["Product Name*"] = self.df["ProductName"].str.lstrip()
                else:
                    self.logger.error("No product name column found")
                    return False

                # Ensure required columns exist
                for col in ["Product Type*", "Lineage", "Product Brand"]:
                    if col not in self.df.columns:
                        self.df[col] = "Unknown"
                
                # ESSENTIAL: Rename columns for frontend compatibility
                self.df.rename(columns={
                    "Product Name*": "ProductName",
                    "Weight Unit* (grams/gm or ounces/oz)": "Units",
                    "Price* (Tier Name for Bulk)": "Price",
                    "Vendor/Supplier*": "Vendor",
                    "DOH Compliant (Yes/No)": "DOH",
                    "Concentrate Type": "Ratio"
                }, inplace=True)
                
                # Ensure ProductName column exists after rename
                if "ProductName" not in self.df.columns:
                    self.logger.error("ProductName column not found after rename")
                    return False
                
                self._last_loaded_file = file_path
                self.logger.info(f"Fast load completed successfully with {len(self.df)} rows")
                return True
                
            except Exception as e:
                self.logger.error(f"Fast load failed: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in fast_load_file: {e}")
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
            
            # Remove duplicates
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            final_count = len(df)
            if initial_count != final_count:
                self.logger.info(f"Removed {initial_count - final_count} duplicate rows")
            
            self.df = df
            self.logger.debug(f"Original columns: {self.df.columns.tolist()}")

            # 2) Trim product names
            # Fallback logic for Product Name*
            if "Product Name*" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name*"].str.lstrip()
            elif "Product Name" in self.df.columns:
                self.df["Product Name*"] = self.df["Product Name"].str.lstrip()
            elif "ProductName" in self.df.columns:
                self.df["Product Name*"] = self.df["ProductName"].str.lstrip()
            else:
                self.logger.error("No product name column found. Expected 'Product Name*', 'Product Name', or 'ProductName'.")
                self.df["Product Name*"] = "Unknown"

            # 3) Ensure required columns exist
            for col in ["Product Type*", "Lineage", "Product Brand"]:
                if col not in self.df.columns:
                    self.df[col] = "Unknown"

            # 4) Exclude sample rows and deactivated products
            initial_count = len(self.df)
            excluded_by_type = self.df[self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            self.df = self.df[~self.df["Product Type*"].isin(EXCLUDED_PRODUCT_TYPES)]
            self.logger.info(f"Excluded {len(excluded_by_type)} products by product type: {excluded_by_type['Product Type*'].unique().tolist()}")
            
            # Also exclude products with excluded patterns in the name
            for pattern in EXCLUDED_PRODUCT_PATTERNS:
                pattern_mask = self.df["Product Name*"].str.contains(pattern, case=False, na=False)
                excluded_by_pattern = self.df[pattern_mask]
                self.df = self.df[~pattern_mask]
                if len(excluded_by_pattern) > 0:
                    self.logger.info(f"Excluded {len(excluded_by_pattern)} products containing pattern '{pattern}': {excluded_by_pattern['Product Name*'].tolist()}")
            
            final_count = len(self.df)
            self.logger.info(f"Product filtering complete: {initial_count} -> {final_count} products (excluded {initial_count - final_count})")

            # 5) Rename for convenience
            self.df.rename(columns={
                "Product Name*": "ProductName",
                "Weight Unit* (grams/gm or ounces/oz)": "Units",
                "Price* (Tier Name for Bulk)": "Price",
                "Vendor/Supplier*": "Vendor",
                "DOH Compliant (Yes/No)": "DOH",
                "Concentrate Type": "Ratio"
            }, inplace=True)

            # 6) Normalize units
            if "Units" in self.df.columns:
                self.df["Units"] = self.df["Units"].str.lower().replace(
                    {"ounces": "oz", "grams": "g"}, regex=True
                )

            # 7) Standardize Lineage
            if "Lineage" in self.df.columns:
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
                    .fillna("HYBRID")
                    .str.upper()
                )

            # 8) Build Description & Ratio & Strain
            if "ProductName" in self.df.columns:
                self.logger.debug("Building Description and Ratio columns")

                def get_description(name):
                    if pd.isna(name):
                        return ""
                    return str(name).strip()

                self.df["Description"] = self.df["ProductName"].apply(get_description)
                
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
                self.df["Ratio"] = self.df["ProductName"].str.extract(r".*-\s*(.+)").fillna("")
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
                    # Fill null values before converting to categorical
                    self.df[col] = self.df[col].fillna("Unknown")
                    self.df[col] = self.df[col].astype("category")

            # 10) CBD and Mixed overrides
            if "Lineage" in self.df.columns:
                # If Product Strain is 'CBD Blend', set Lineage to 'CBD'
                if "Product Strain" in self.df.columns:
                    cbd_blend_mask = self.df["Product Strain"].astype(str).str.lower().str.strip() == "cbd blend"
                    if "CBD" not in self.df["Lineage"].cat.categories:
                        self.df["Lineage"] = self.df["Lineage"].cat.add_categories(["CBD"])
                    self.df.loc[cbd_blend_mask, "Lineage"] = "CBD"

                # If Description or Product Name* contains CBD, CBG, CBN, CBC, set Lineage to 'CBD'
                cbd_mask = (
                    self.df["Description"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False) |
                    self.df["ProductName"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False)
                )
                # Use .any() to avoid Series boolean ambiguity
                if cbd_mask.any():
                    self.df.loc[cbd_mask, "Lineage"] = "CBD"

                # If Lineage is missing or empty, set to 'MIXED'
                empty_lineage_mask = self.df["Lineage"].isnull() | (self.df["Lineage"].astype(str).str.strip() == "")
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
            return []
        
        filtered_df = self.apply_filters(filters) if filters else self.df
        
        tags = []
        for _, row in filtered_df.iterrows():
            # Get quantity from various possible column names
            quantity = row.get('Quantity*', '') or row.get('Quantity Received*', '') or row.get('Quantity', '') or row.get('qty', '') or ''
            
            # Get formatted weight with units
            weight_with_units = self._format_weight_units(row)
            raw_weight = row.get('Weight*', '')
            
            # Use the renamed "ProductName" but provide it under the key the UI expects.
            tag = {
                'Product Name*': row.get('ProductName', ''),
                'vendor': row.get('Vendor', ''),
                'productBrand': row.get('Product Brand', ''),
                'lineage': row.get('Lineage', 'MIXED'),
                'productType': row.get('Product Type*', ''),
                'weight': raw_weight,
                'weightWithUnits': weight_with_units,
                'Quantity*': str(quantity) if quantity else '',
                'Quantity Received*': str(quantity) if quantity else '',
                'quantity': str(quantity) if quantity else ''
            }
            # --- Filtering logic ---
            product_brand = str(tag['productBrand']).strip().lower()
            product_type = str(tag['productType']).strip().lower().replace('  ', ' ')
            weight = str(tag['weight']).strip().lower()
            if (
                product_brand == 'unknown' or
                ('trade sample' in product_type and 'not for sale' in product_type) or
                weight == '-1g'
            ):
                continue  # Skip this tag
            tags.append(tag)
        
        # Sort tags by weight (least to greatest)
        def parse_weight(tag):
            return ExcelProcessor.parse_weight_str(tag.get('weight', ''), tag.get('weightWithUnits', ''))
        return sorted(tags, key=parse_weight)

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
            canonical_map = {normalize_name(name): name for name in self.df['ProductName']}
            logger.debug(f"Canonical map sample: {dict(list(canonical_map.items())[:5])}")
            
            # Map incoming selected tags to canonical names
            canonical_selected = [canonical_map.get(normalize_name(tag)) for tag in selected_tags if canonical_map.get(normalize_name(tag))]
            logger.debug(f"Selected tags: {selected_tags}")
            logger.debug(f"Canonical selected tags: {canonical_selected}")
            
            if not canonical_selected:
                logger.warning("No canonical matches for selected tags")
                logger.warning(f"Available canonical keys (sample): {list(canonical_map.keys())[:10]}")
                # Log the normalized versions of selected tags for debugging
                normalized_selected = [normalize_name(tag) for tag in selected_tags]
                logger.warning(f"Normalized selected tags: {normalized_selected}")
                return []
            
            logger.debug(f"Canonical selected tags: {canonical_selected}")
            
            # Filter DataFrame to only include selected records by canonical ProductName
            filtered_df = self.df[self.df['ProductName'].isin(canonical_selected)]
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
                product_name = rec.get('ProductName', '').strip().lower()
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
                    # Normalize Product Name* to ProductName
                    product_name = record.get('ProductName', '').strip()
                    # Ensure Description is always set
                    description = record.get('Description', '')
                    if not description:
                        description = product_name or record.get('ProductName', '')
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
                        'ProductName': product_name,
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
                options[filter_key] = sorted(values)
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
            self.df["Description"] = self.df["ProductName"].fillna("")
        if "Lineage" not in self.df.columns:
            self.logger.warning("Lineage column not found")
            return {"error": "Lineage column not found"}
        
        # Clean and normalize descriptions
        self.df["Description_Clean"] = self.df["Description"].fillna("").astype(str).str.lower()
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
        self.df["Description_Clean"] = self.df["Description"].fillna("").astype(str).str.lower()
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
        """Complete full processing of the loaded data when needed."""
        if self.df is None or self.df.empty:
            self.logger.warning("No data to process")
            return False
            
        try:
            self.logger.info("Starting full data processing...")
            
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
                    .fillna("HYBRID")
                    .str.upper()
                )

            # 7) Build Description & Ratio & Strain
            if "ProductName" in self.df.columns:
                def get_description(name):
                    if pd.isna(name):
                        return ""
                    return str(name).strip()

                self.df["Description"] = self.df["ProductName"].apply(get_description)
                
                mask_para = self.df["Product Type*"].str.strip().str.lower() == "paraphernalia"
                self.df.loc[mask_para, "Description"] = (
                    self.df.loc[mask_para, "Description"]
                    .str.replace(r"\s*-\s*\d+g$", "", regex=True)
                )

            self.logger.info("Full data processing completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in complete_processing: {e}")
            return False


def get_default_upload_file() -> Optional[str]:
        """
        Returns the path to the default Excel file.
        First looks in uploads directory, then in Downloads.
        Returns the most recent "A Greener Today" file found.
        Updated for PythonAnywhere compatibility.
        """
        import os
        from pathlib import Path
        
        # Get the current working directory (should be the project root)
        current_dir = os.getcwd()
        print(f"Current working directory: {current_dir}")
        
        # First, look in the uploads directory relative to current directory
        uploads_dir = os.path.join(current_dir, "uploads")