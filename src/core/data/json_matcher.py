import re
import json
import urllib.request
import logging
import time
from difflib import SequenceMatcher
from typing import List, Dict, Set, Optional, Tuple
import pandas as pd
from .product_database import ProductDatabase
from collections import defaultdict

# Compile regex patterns once for performance
_DIGIT_UNIT_RE = re.compile(r"\b\d+(?:g|mg)\b")
_NON_WORD_RE = re.compile(r"[^\w\s-]")
_SPLIT_RE = re.compile(r"[-\s]+")

# Type override lookup
TYPE_OVERRIDES = {
    "all-in-one": "vape cartridge",
    "rosin": "concentrate",
    "mini buds": "flower",
    "bud": "flower",
    "pre-roll": "pre-roll",
}

# Mapping from possible JSON keys to canonical DB fields
JSON_TO_DB_FIELD_MAP = {
    # Product fields
    "product_name": "product_name",
    "Product Name*": "product_name",
    "ProductName": "product_name",
    "description": "description",
    "Description": "description",
    "vendor": "vendor",
    "Vendor": "vendor",
    "brand": "brand",
    "Product Brand": "brand",
    "price": "price",
    "Price": "price",
    "line_price": "price",
    "weight": "weight",
    "unit_weight": "weight",
    "units": "units",
    "unit_weight_uom": "units",
    "uom": "units",
    "strain_name": "strain_name",
    "Strain Name": "strain_name",
    "lineage": "lineage",
    "canonical_lineage": "canonical_lineage",
    "product_type": "product_type",
    "inventory_type": "product_type",
    "inventory_category": "product_category",
    "product_sku": "product_sku",
    "inventory_id": "inventory_id",
    "id": "id",
    # Add more as needed
}

# Helper: Extract cannabinoid values from lab_result_data
CANNABINOID_TYPES = ["thc", "thca", "cbd", "cbda", "total-cannabinoids"]

def extract_cannabinoids(lab_result_data):
    result = {}
    if not lab_result_data:
        return result
    potency = lab_result_data.get("potency", [])
    for c in potency:
        ctype = c.get("type", "").lower()
        if ctype in CANNABINOID_TYPES:
            result[ctype] = c.get("value")
    # COA link
    if "coa" in lab_result_data:
        result["coa"] = lab_result_data["coa"]
    return result

# Main function: Process manifest JSON and return list of product dicts
# Each dict contains all relevant DB fields, including cannabinoids/COA

def extract_products_from_manifest(manifest_json):
    """
    Given a manifest JSON (with inventory_transfer_items),
    return a list of dicts, each with all relevant DB fields.
    """
    items = manifest_json.get("inventory_transfer_items", [])
    products = []
    for item in items:
        product = {}
        # Map flat fields
        for k, v in item.items():
            db_field = JSON_TO_DB_FIELD_MAP.get(k, None)
            if db_field:
                product[db_field] = v
        # Nested lab_result_data
        lab_result_data = item.get("lab_result_data", {})
        cannabinoids = extract_cannabinoids(lab_result_data)
        product.update(cannabinoids)
        products.append(product)
    return product

# Example usage:
# products = extract_products_from_manifest(manifest_json)
# for p in products:
#     print(p)

def map_json_to_db_fields(json_item):
    """Map incoming JSON keys to canonical DB columns."""
    mapped = {}
    for k, v in json_item.items():
        db_key = JSON_TO_DB_FIELD_MAP.get(k, k)
        mapped[db_key] = v
    return mapped

class JSONMatcher:
    """Handles JSON URL fetching and product matching functionality."""
    
    def __init__(self, excel_processor):
        self.excel_processor = excel_processor
        self._sheet_cache = None
        self._indexed_cache = None  # New indexed cache for O(1) lookups
        self.json_matched_names = None
        self._strain_cache = None
        self._lineage_cache = None
        
    def _build_sheet_cache(self):
        """Build a cache of sheet data for fast matching."""
        logging.info("Building sheet cache...")
        if self.excel_processor is None:
            logging.warning("Cannot build sheet cache: ExcelProcessor is None")
            self._sheet_cache = []
            self._indexed_cache = {}
            return
            
        df = self.excel_processor.df
        if df is None:
            logging.warning("Cannot build sheet cache: DataFrame is None")
            self._sheet_cache = []
            self._indexed_cache = {}
            return
            
        if df.empty:
            logging.warning("Cannot build sheet cache: DataFrame is empty")
            self._sheet_cache = []
            self._indexed_cache = {}
            return
            
        logging.info(f"Building sheet cache from DataFrame with {len(df)} rows")
            
        # Determine the best description column to use
        description_col = None
        for col in ["Product Name*", "ProductName", "Description"]:
            if col in df.columns:
                description_col = col
                break
                
        if not description_col:
            logging.error("No suitable description column found")
            self._sheet_cache = []
            self._indexed_cache = {}
            return
            
        # Filter out samples and nulls
        if description_col == "Description":
            df = df[
                df[description_col].notna() &
                ~df[description_col].astype(str).str.lower().str.contains("sample", na=False)
            ]
        else:
            # For ProductName/Product Name*, just filter out nulls
            df = df[df[description_col].notna()]
        
        cache = []
        indexed_cache = {
            'exact_names': {},  # O(1) exact name lookup
            'vendor_groups': defaultdict(list),  # O(1) vendor-based grouping
            'key_terms': defaultdict(list),  # O(1) key term lookup
            'normalized_names': defaultdict(list),  # O(1) normalized name lookup
        }
        
        for idx, row in df.iterrows():
            # Ensure idx is hashable by converting to string if needed
            hashable_idx = str(idx) if not isinstance(idx, (int, str, float)) else idx
            
            # Get description with proper type checking
            desc_raw = row.get(description_col, "")
            desc = str(desc_raw) if desc_raw is not None else ""
            norm = self._normalize(desc)
            toks = set(norm.split())
            
            # Extract key terms for better matching
            key_terms = self._extract_key_terms(desc)
            
            # Get other fields with proper type checking
            brand_raw = row.get("Product Brand", "")
            brand = str(brand_raw) if brand_raw is not None else ""
            vendor_raw = row.get("Vendor", "")
            vendor = str(vendor_raw) if vendor_raw is not None else ""
            
            cache_item = {
                "idx": hashable_idx,
                "original_name": desc,
                "norm": norm,
                "tokens": toks,
                "key_terms": key_terms,
                "brand": brand,
                "vendor": vendor,
                "product_type": str(row.get("Product Type*", "")),
                "lineage": str(row.get("Lineage", "")),
                "strain": str(row.get("Product Strain", ""))
            }
            
            try:
                cache.append(cache_item)
                
                # Build indexed cache for O(1) lookups
                # 1. Exact name index
                exact_name = desc.lower().strip()
                if exact_name:
                    indexed_cache['exact_names'][exact_name] = cache_item
                
                # 2. Vendor index
                vendor_lower = vendor.lower().strip()
                if vendor_lower:
                    indexed_cache['vendor_groups'][vendor_lower].append(cache_item)
                
                # 3. Key terms index (for each key term)
                for term in key_terms:
                    indexed_cache['key_terms'][term].append(cache_item)
                
                # 4. Normalized name index
                if norm:
                    indexed_cache['normalized_names'][norm].append(cache_item)
                    
            except Exception as e:
                logging.warning(f"Error creating cache item for row {idx}: {e}")
                continue
                
        self._sheet_cache = cache
        self._indexed_cache = indexed_cache
        logging.info(f"Built sheet cache with {len(cache)} entries using column '{description_col}'")
        logging.info(f"Built indexed cache with {len(indexed_cache['exact_names'])} exact names, {len(indexed_cache['vendor_groups'])} vendors, {len(indexed_cache['key_terms'])} key terms")
        
    def _normalize(self, s: str) -> str:
        """Normalize text for matching by removing digits, units, and special characters."""
        # Ensure input is a string
        s = str(s or "")
        s = s.lower()
        s = _DIGIT_UNIT_RE.sub("", s)
        s = _NON_WORD_RE.sub(" ", s)
        return _SPLIT_RE.sub(" ", s).strip()
        
    def _extract_key_terms(self, name: str) -> Set[str]:
        """Extract meaningful product terms, excluding common prefixes/suffixes."""
        try:
            # Ensure input is a string
            name = str(name or "")
            name_lower = name.lower()
            words = set(name_lower.replace('-', ' ').replace('_', ' ').split())
            
            # Common words to exclude
            common_words = {
                'medically', 'compliant', 'all', 'in', 'one', '1g', '2g', '3.5g', '7g', '14g', '28g', 'oz', 'gram', 'grams',
                'pk', 'pack', 'packs', 'piece', 'pieces', 'roll', 'rolls', 'stix', 'stick', 'sticks', 'brand', 'vendor', 'product',
                'the', 'and', 'or', 'with', 'for', 'of', 'by', 'from', 'to', 'in', 'on', 'at', 'a', 'an', 'mg', 'thc', 'cbd'
            }
            
            # Filter out common words and short words (less than 3 characters)
            key_terms = {word for word in words if word not in common_words and len(word) >= 3}
            
            # Add product type indicators for better matching
            product_types = {
                'rosin', 'wax', 'shatter', 'live', 'resin', 'distillate', 'cartridge', 'pre-roll', 'pre-rolls',
                'blunt', 'blunts', 'edible', 'edibles', 'tincture', 'tinctures', 'topical', 'topicals',
                'concentrate', 'concentrates', 'flower', 'buds', 'infused', 'flavour', 'flavor'
            }
            
            # Add product type terms if found
            for word in words:
                if word in product_types:
                    key_terms.add(word)
            
            # Add strain names (common cannabis strain words)
            strain_indicators = {
                'gmo', 'runtz', 'cookies', 'cream', 'wedding', 'cake', 'blueberry', 'banana', 'strawberry',
                'grape', 'lemon', 'lime', 'orange', 'cherry', 'apple', 'mango', 'pineapple', 'passion',
                'dragon', 'fruit', 'guava', 'pink', 'lemonade', 'haze', 'kush', 'diesel', 'og', 'sherbet',
                'gelato', 'mintz', 'grinch', 'cosmic', 'combo', 'honey', 'bread', 'tricho', 'jordan',
                'super', 'boof', 'grandy', 'candy', 'afghani', 'hashplant', 'yoda', 'amnesia'
            }
            
            # Add strain terms if found
            for word in words:
                if word in strain_indicators:
                    key_terms.add(word)
            
            # Add multi-word terms for better matching
            name_parts = name_lower.split()
            for i in range(len(name_parts) - 1):
                bigram = f"{name_parts[i]} {name_parts[i+1]}"
                if len(bigram) >= 6:  # Only add meaningful bigrams
                    key_terms.add(bigram)
                  
            return key_terms
        except Exception as e:
            logging.warning(f"Error in _extract_key_terms: {e}")
            return set()
        
    def _extract_vendor(self, name: str) -> str:
        """Extract vendor/brand information from product name."""
        try:
            # Ensure input is a string
            name = str(name or "")
            name_lower = name.lower()
            
            # Handle "by" format (e.g., "Product Name by Vendor") - check this first
            if " by " in name_lower:
                parts = name_lower.split(" by ", 1)
                if len(parts) > 1:
                    vendor_part = parts[1].strip()
                    # Take first word of vendor
                    vendor_words = vendor_part.split()
                    return vendor_words[0].lower() if vendor_words else ""
            
            # Handle "Medically Compliant -" prefix
            if name_lower.startswith("medically compliant -"):
                after_prefix = name.split("-", 1)[1].strip()
                brand_words = after_prefix.split()
                if brand_words:
                    # Take only the first word (brand name) instead of first two
                    return brand_words[0].lower()
                return after_prefix.lower()
                
            # Handle other dash-separated formats
            parts = name.split("-", 1)
            if len(parts) > 1:
                brand_words = parts[0].strip().split()
                return brand_words[0].lower() if brand_words else ""
                
            # Handle parentheses format (e.g., "Product Name (Vendor)")
            if "(" in name_lower and ")" in name_lower:
                start = name_lower.find("(") + 1
                end = name_lower.find(")")
                if start < end:
                    vendor_part = name_lower[start:end].strip()
                    vendor_words = vendor_part.split()
                    return vendor_words[0].lower() if vendor_words else ""
                
            # Fallback: use first word
            words = name_lower.split()
            return words[0].lower() if words else ""
        except Exception as e:
            logging.warning(f"Error in _extract_vendor: {e}")
            return ""
        
    def _find_candidates_optimized(self, json_item: dict) -> List[dict]:
        """Find candidate matches using indexed lookups instead of O(n²) comparisons."""
        candidates = set()  # Use set for deduplication by index
        candidate_indices = set()  # Track indices to avoid duplicates
        json_name = str(json_item.get("product_name", "")).lower().strip()
        
        # Extract vendor from JSON item - try multiple sources
        json_vendor = None
        if json_item.get("vendor"):
            json_vendor = str(json_item.get("vendor", "")).strip().lower()
        elif json_item.get("brand"):
            json_vendor = str(json_item.get("brand", "")).strip().lower()
        else:
            # Extract vendor from product name
            json_vendor = self._extract_vendor(json_name)
        
        # Debug logging for specific items
        if "banana og" in json_name:
            logging.info(f"Finding candidates for: {json_name} (extracted vendor: {json_vendor})")
        
        if not json_name:
            return []
            
        # Strategy 1: Exact name match (O(1)) - always allow this regardless of vendor
        if json_name in self._indexed_cache['exact_names']:
            exact_match = self._indexed_cache['exact_names'][json_name]
            return [exact_match]  # Return immediately for exact match
            
        # Strategy 2: Vendor-based filtering (STRICT - only use vendor candidates if available)
        vendor_candidates = []
        if json_vendor:
            # First try exact vendor match
            if json_vendor in self._indexed_cache['vendor_groups']:
                vendor_candidates = self._indexed_cache['vendor_groups'][json_vendor]
            else:
                # Try fuzzy vendor matching for similar vendor names
                vendor_candidates = self._find_fuzzy_vendor_matches(json_vendor)
            
            # If we have vendor candidates, try to find better matches within the vendor
            if vendor_candidates:
                better_vendor_candidates = self._find_better_vendor_matches(json_item, vendor_candidates)
                if better_vendor_candidates:
                    vendor_candidates = better_vendor_candidates
                
            # Add vendor candidates to the result set
            for candidate in vendor_candidates:
                if candidate["idx"] not in candidate_indices:
                    candidates.add(candidate["idx"])
                    candidate_indices.add(candidate["idx"])
                    
            # Debug logging for specific items
            if "banana og" in json_name:
                logging.info(f"Found {len(vendor_candidates)} vendor candidates for vendor '{json_vendor}'")
                
            # If we have vendor candidates, ONLY return those - no fallback strategies
            if vendor_candidates:
                # Convert indices back to cache items
                candidate_list = []
                for idx in candidates:
                    for cache_item in self._sheet_cache:
                        if cache_item["idx"] == idx:
                            candidate_list.append(cache_item)
                            break
                return candidate_list[:50]  # Limit to top 50 candidates
        else:
            # If no vendor match found, log it but continue with other strategies
            if "banana og" in json_name:
                logging.info(f"No vendor candidates found for vendor '{json_vendor}'")
                logging.info(f"Available vendors: {list(self._indexed_cache['vendor_groups'].keys())[:10]}")
            
        # Strategy 3: Key term overlap (ONLY if no vendor candidates found)
        if not vendor_candidates:  # Only use key terms if no vendor candidates
            json_key_terms = self._extract_key_terms(json_name)
            for term in json_key_terms:
                if term in self._indexed_cache['key_terms']:
                    for candidate in self._indexed_cache['key_terms'][term]:
                        if candidate["idx"] not in candidate_indices:
                            candidates.add(candidate["idx"])
                            candidate_indices.add(candidate["idx"])
                
        # Strategy 4: Normalized name lookup (ONLY if no vendor candidates found)
        if not vendor_candidates:  # Only use normalized names if no vendor candidates
            json_norm = self._normalize(json_name)
            if json_norm in self._indexed_cache['normalized_names']:
                for candidate in self._indexed_cache['normalized_names'][json_norm]:
                    if candidate["idx"] not in candidate_indices:
                        candidates.add(candidate["idx"])
                        candidate_indices.add(candidate["idx"])
            
        # Strategy 5: Contains matching (ONLY if no vendor candidates and few other candidates)
        if not vendor_candidates and len(candidates) < 5:  # Only do expensive operations if we have few candidates
            for cache_item in self._sheet_cache:
                if cache_item["idx"] not in candidate_indices:
                    cache_name = str(cache_item["original_name"]).lower()
                    if json_name in cache_name or cache_name in json_name:
                        candidates.add(cache_item["idx"])
                        candidate_indices.add(cache_item["idx"])
                    
        # Convert indices back to cache items
        candidate_list = []
        for idx in candidates:
            for cache_item in self._sheet_cache:
                if cache_item["idx"] == idx:
                    candidate_list.append(cache_item)
                    break
                    
        # Limit candidates to prevent excessive processing
        if len(candidate_list) > 50:  # Limit to top 50 candidates
            candidate_list = candidate_list[:50]
            
        return candidate_list
        
    def _find_fuzzy_vendor_matches(self, json_vendor: str) -> List[dict]:
        """Find vendor matches using fuzzy matching for similar vendor names."""
        if not json_vendor:
            return []
            
        matches = []
        available_vendors = list(self._indexed_cache['vendor_groups'].keys())
        
        # Common vendor name variations and abbreviations
        vendor_variations = {
            'dank czar': ['dcz holdings inc', 'dcz', 'dank czar holdings'],
            'dcz holdings': ['dank czar', 'dcz', 'dcz holdings inc'],
            'dcz': ['dank czar', 'dcz holdings inc', 'dcz holdings'],
            'omega': ['jsm llc', 'omega labs', 'omega cannabis'],
            'airo pro': ['harmony farms', 'airo', 'airopro'],
            'jsm': ['omega', 'jsm llc', 'jsm labs'],
            'harmony': ['airo pro', 'harmony farms', 'harmony cannabis'],
        }
        
        # Check for known variations
        for variation_key, variations in vendor_variations.items():
            if json_vendor in variation_key or any(v in json_vendor for v in variations):
                for vendor in available_vendors:
                    if any(v in vendor for v in variations) or vendor in variations:
                        matches.extend(self._indexed_cache['vendor_groups'][vendor])
        
        # If no matches found with known variations, try partial matching
        if not matches:
            for vendor in available_vendors:
                # Check if vendor contains key words from json_vendor
                json_words = set(json_vendor.split())
                vendor_words = set(vendor.split())
                
                # Check for word overlap
                overlap = json_words.intersection(vendor_words)
                if overlap and len(overlap) >= 1:  # At least one word in common
                    matches.extend(self._indexed_cache['vendor_groups'][vendor])
        
        # If still no matches, try substring matching (more permissive)
        if not matches:
            json_vendor_lower = json_vendor.lower()
            for vendor in available_vendors:
                vendor_lower = vendor.lower()
                # Check if either vendor contains the other as a substring
                if json_vendor_lower in vendor_lower or vendor_lower in json_vendor_lower:
                    matches.extend(self._indexed_cache['vendor_groups'][vendor])
        
        return matches
        
    def _find_better_vendor_matches(self, json_item: dict, vendor_candidates: List[dict]) -> List[dict]:
        """Find better matches within the same vendor by prioritizing similar product types and strain names."""
        if not vendor_candidates:
            return []
            
        json_name = str(json_item.get("product_name", "")).lower()
        json_key_terms = self._extract_key_terms(json_name)
        
        # Score each vendor candidate
        scored_candidates = []
        for candidate in vendor_candidates:
            candidate_name = str(candidate.get("original_name", "")).lower()
            candidate_key_terms = candidate.get("key_terms", set())
            
            # Calculate similarity score
            score = 0.0
            
            # Product type similarity
            product_types = {'rosin', 'wax', 'shatter', 'live', 'resin', 'distillate', 'cartridge', 'pre-roll', 'blunt', 'edible', 'tincture', 'topical', 'concentrate', 'flower', 'infused'}
            json_product_types = json_key_terms.intersection(product_types)
            candidate_product_types = candidate_key_terms.intersection(product_types)
            
            if json_product_types and candidate_product_types:
                if json_product_types == candidate_product_types:
                    score += 0.4  # Exact product type match
                elif json_product_types.intersection(candidate_product_types):
                    score += 0.2  # Partial product type match
            
            # Strain name similarity
            strain_indicators = {'gmo', 'runtz', 'cookies', 'cream', 'wedding', 'cake', 'blueberry', 'banana', 'strawberry', 'grape', 'lemon', 'cherry', 'apple', 'mango', 'pineapple', 'passion', 'dragon', 'fruit', 'guava', 'pink', 'lemonade', 'haze', 'kush', 'diesel', 'og', 'sherbet', 'gelato', 'mintz', 'grinch', 'cosmic', 'combo', 'honey', 'bread', 'tricho', 'jordan', 'super', 'boof', 'grandy', 'candy', 'afghani', 'hashplant', 'yoda', 'amnesia'}
            json_strains = json_key_terms.intersection(strain_indicators)
            candidate_strains = candidate_key_terms.intersection(strain_indicators)
            
            if json_strains and candidate_strains:
                if json_strains == candidate_strains:
                    score += 0.5  # Exact strain match
                elif json_strains.intersection(candidate_strains):
                    score += 0.3  # Partial strain match
            
            # General term overlap
            overlap = json_key_terms.intersection(candidate_key_terms)
            if overlap:
                overlap_ratio = len(overlap) / min(len(json_key_terms), len(candidate_key_terms)) if min(len(json_key_terms), len(candidate_key_terms)) > 0 else 0
                score += overlap_ratio * 0.3
            
            # Contains matching
            if json_name in candidate_name or candidate_name in json_name:
                score += 0.2
            
            scored_candidates.append((candidate, score))
        
        # Sort by score and return top candidates
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [candidate for candidate, score in scored_candidates if score > 0.1]  # Only return candidates with meaningful scores
        
    def _calculate_match_score(self, json_item: dict, cache_item: dict) -> float:
        """Calculate a match score between JSON item and cache item."""
        try:
            # --- BEGIN: Strict cannabis type filtering ---
            # Define recognized cannabis product types (update as needed)
            CANNABIS_TYPES = [
                "concentrate", "vape cartridge", "flower", "edible", "tincture", "capsule", "topical", "pre-roll"
            ]
            def is_cannabis_type(type_str):
                if not type_str:
                    return False
                type_str = str(type_str).lower()
                return any(t in type_str for t in CANNABIS_TYPES)

            # Get product type/category from both JSON and cache item
            json_type = json_item.get("product_type") or json_item.get("inventory_type") or json_item.get("inventory_category")
            cache_type = cache_item.get("product_type") or cache_item.get("product_category")

            # If either is not a cannabis type, do not match
            if not is_cannabis_type(json_type) or not is_cannabis_type(cache_type):
                return 0.0
            # --- END: Strict cannabis type filtering ---

            # Ensure we have string values before calling .lower()
            json_name = str(json_item.get("product_name", "")).lower()
            cache_name = str(cache_item["original_name"]).lower()
            
            # Strategy 1: Exact match (highest score) - FAST PATH
            if json_name == cache_name:
                return 1.0
                
            # Strategy 2: Contains match - FAST PATH
            if json_name in cache_name or cache_name in json_name:
                return 0.9
                
            # Strategy 3: Vendor matching - STRICT - reject vendor mismatches
            # Extract vendor from JSON item - try multiple sources
            json_vendor = None
            if json_item.get("vendor"):
                json_vendor = str(json_item.get("vendor", "")).strip().lower()
            elif json_item.get("brand"):
                json_vendor = str(json_item.get("brand", "")).strip().lower()
            else:
                # Extract vendor from product name
                json_vendor = self._extract_vendor(str(json_item.get("product_name", "")))
            
            cache_vendor = str(cache_item.get("vendor", "")).strip().lower() if cache_item.get("vendor") else None
            
            # STRICT vendor matching - reject vendor mismatches
            if json_vendor and cache_vendor:
                if json_vendor != cache_vendor:
                    # Check for fuzzy vendor matching (same logic as in _find_fuzzy_vendor_matches)
                    vendor_matches = False
                    
                    # Common vendor name variations and abbreviations
                    vendor_variations = {
                        'dank czar': ['dcz holdings inc', 'dcz', 'dank czar holdings'],
                        'dcz holdings': ['dank czar', 'dcz', 'dcz holdings inc'],
                        'dcz': ['dank czar', 'dcz holdings inc', 'dcz holdings'],
                    }
                    
                    # Check for known variations
                    for variation_key, variations in vendor_variations.items():
                        if (json_vendor in variation_key or any(v in json_vendor for v in variations)) and \
                           (cache_vendor in variation_key or any(v in cache_vendor for v in variations)):
                            vendor_matches = True
                            break
                    
                    # If no known variations, check for word overlap
                    if not vendor_matches:
                        json_words = set(json_vendor.split())
                        cache_words = set(cache_vendor.split())
                        overlap = json_words.intersection(cache_words)
                        if overlap and len(overlap) >= 1:
                            vendor_matches = True
                    
                    # If vendors don't match and no fuzzy match found, reject this candidate
                    if not vendor_matches:
                        return 0.0  # Completely reject vendor mismatches
            
            # Vendor bonus for exact matches
            vendor_bonus = 0.0
            if json_vendor and cache_vendor and json_vendor == cache_vendor:
                vendor_bonus = 0.4  # 40% bonus for exact vendor match
                
            # Strategy 4: Key terms overlap - MEDIUM COST
            json_key_terms = self._extract_key_terms(str(json_item.get("product_name", "")))
            cache_key_terms = cache_item["key_terms"]
            
            if json_key_terms and cache_key_terms:
                overlap = json_key_terms.intersection(cache_key_terms)
                if overlap:
                    # Calculate Jaccard similarity
                    union = json_key_terms.union(cache_key_terms)
                    jaccard = len(overlap) / len(union) if union else 0
                    
                    # Calculate overlap ratio
                    min_terms = min(len(json_key_terms), len(cache_key_terms))
                    overlap_ratio = len(overlap) / min_terms if min_terms > 0 else 0
                    
                    # Bonus for product type matches
                    product_type_bonus = 0.0
                    product_types = {'rosin', 'wax', 'shatter', 'live', 'resin', 'distillate', 'cartridge', 'pre-roll', 'blunt', 'edible', 'tincture', 'topical', 'concentrate', 'flower', 'infused'}
                    json_product_types = json_key_terms.intersection(product_types)
                    cache_product_types = cache_key_terms.intersection(product_types)
                    if json_product_types and cache_product_types and json_product_types == cache_product_types:
                        product_type_bonus = 0.2  # 20% bonus for matching product types
                    
                    # Bonus for strain name matches
                    strain_bonus = 0.0
                    strain_indicators = {'gmo', 'runtz', 'cookies', 'cream', 'wedding', 'cake', 'blueberry', 'banana', 'strawberry', 'grape', 'lemon', 'cherry', 'apple', 'mango', 'pineapple', 'passion', 'dragon', 'fruit', 'guava', 'pink', 'lemonade', 'haze', 'kush', 'diesel', 'og', 'sherbet', 'gelato', 'mintz', 'grinch', 'cosmic', 'combo', 'honey', 'bread', 'tricho', 'jordan', 'super', 'boof', 'grandy', 'candy', 'afghani', 'hashplant', 'yoda', 'amnesia'}
                    json_strains = json_key_terms.intersection(strain_indicators)
                    cache_strains = cache_key_terms.intersection(strain_indicators)
                    if json_strains and cache_strains and json_strains == cache_strains:
                        strain_bonus = 0.3  # 30% bonus for matching strain names
                    
                    # Combine both metrics
                    term_score = (jaccard + overlap_ratio) / 2
                    if term_score >= 0.3:  # Lowered threshold for better matching
                        final_score = min(0.9, term_score) + vendor_bonus + product_type_bonus + strain_bonus
                        return max(0.1, final_score)  # Ensure minimum score of 0.1
                    
            # Strategy 5: Normalized name matching - MEDIUM COST
            json_norm = self._normalize(str(json_item.get("product_name", "")))
            cache_norm = cache_item["norm"]
            
            if json_norm and cache_norm:
                # Check for any word overlap
                json_words = set(json_norm.split())
                cache_words = set(cache_norm.split())
                word_overlap = len(json_words.intersection(cache_words))
                
                if word_overlap >= 1:
                    base_score = 0.4 + (word_overlap * 0.1)  # Base 0.4 + 0.1 per overlapping word
                    final_score = min(0.95, base_score) + vendor_bonus
                    return max(0.1, final_score)  # Ensure minimum score of 0.1
                    
            # Strategy 6: Strain-aware matching - EXPENSIVE, only if other strategies failed
            # Only do this if we have a reasonable chance of finding a match
            if len(json_name) > 10 and len(cache_name) > 10:  # Only for longer names
                try:
                    json_strains = self._find_strains_in_text(str(json_item.get("product_name", "")))
                    cache_strains = self._find_strains_in_text(str(cache_item["original_name"]))
                    
                    if json_strains and cache_strains:
                        json_lineages = {strain[1] for strain in json_strains}
                        cache_lineages = {strain[1] for strain in cache_strains}
                        lineage_overlap = json_lineages.intersection(cache_lineages)
                        if lineage_overlap:
                            # Moderate boost for lineage matches
                            final_score = 0.75 + vendor_bonus
                            return max(0.1, final_score)
                    
                except Exception as e:
                    logging.warning(f"Error in strain matching: {e}")
                    
            # Strategy 7: Fuzzy matching - EXPENSIVE, only as last resort
            # Only do fuzzy matching if names are reasonably similar in length
            if abs(len(json_name) - len(cache_name)) <= 10:  # Only if length difference is small
                try:
                    ratio = SequenceMatcher(None, json_name, cache_name).ratio()
                    if ratio >= 0.7:
                        final_score = (ratio * 0.5) + vendor_bonus  # Scale down fuzzy matches
                        return max(0.1, final_score)
                except:
                    pass
                    
            # If we get here, return a very low score but not 0
            return max(0.05, vendor_bonus)
            
        except Exception as e:
            logging.error(f"Error in _calculate_match_score: {e}")
            logging.error(f"json_item: {json_item}")
            logging.error(f"cache_item: {cache_item}")
            return 0.05  # Return very low score instead of 0
        
    def fetch_and_match(self, url: str) -> List[str]:
        """
        Fetch JSON from URL and match products against the loaded Excel data.
        
        Args:
            url: URL to fetch JSON data from
            
        Returns:
            List of matched product names
        """
        if not url.lower().startswith("http"):
            raise ValueError("Please provide a valid HTTP URL")
            
        # Build cache if needed
        if self._sheet_cache is None or self._indexed_cache is None:
            self._build_sheet_cache()
            
        if not self._sheet_cache:
            logging.warning("No sheet cache available for matching")
            return []
            
        try:
            # Use the proxy endpoint to handle authentication and CORS
            import requests
            
            # Prepare the request to our proxy endpoint
            proxy_data = {
                'url': url,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            }
            
            # Add authentication headers if they're in the URL or if we detect they're needed
            if 'api-trace.getbamboo.com' in url:
                # For Bamboo API, we might need specific headers
                # You can add specific authentication headers here if needed
                pass
            
            # Try to make the request directly first (for external URLs)
            try:
                response = requests.get(url, headers=proxy_data['headers'], timeout=30)
                response.raise_for_status()
                payload = response.json()
            except (requests.exceptions.RequestException, ValueError) as direct_error:
                logging.info(f"Direct request failed, trying proxy: {direct_error}")
                # Fallback to proxy endpoint if direct request fails
                import os
                base_url = os.environ.get('FLASK_BASE_URL', 'http://127.0.0.1:9090')
                response = requests.post(f'{base_url}/api/proxy-json', 
                                       json=proxy_data, 
                                       timeout=30)
                response.raise_for_status()
                payload = response.json()
                
            items = payload.get("inventory_transfer_items", [])
            if not items:
                logging.warning("No inventory transfer items found in JSON")
                return []
                
            logging.info(f"Processing {len(items)} JSON items for matching")
            
            matched_idxs = set()
            match_scores = {}  # Track scores for debugging
            fallback_tags = []  # Collect fallback tags for unmatched products
            product_db = ProductDatabase()
            
            # Performance monitoring
            start_time = time.time()
            max_processing_time = 300  # 5 minutes maximum
            processed_count = 0
            matched_count = 0

            # For each JSON item, find the best match using optimized candidate selection
            for i, item in enumerate(items):
                # Check timeout
                elapsed_time = time.time() - start_time
                if elapsed_time > max_processing_time:
                    logging.warning(f"JSON matching timeout after {elapsed_time:.1f}s, processed {i}/{len(items)} items")
                    break
                
                if not item.get("product_name"):
                    continue
                    
                # Debug logging for specific item
                product_name = str(item.get("product_name", ""))
                vendor = str(item.get("vendor", ""))
                if "banana og" in product_name.lower():
                    logging.info(f"Processing Banana OG item: {product_name} (vendor: {vendor})")
                    
                # Ensure product_name is a string
                product_name = str(item.get("product_name", ""))
                if not product_name.strip():
                    continue
                    
                # Log progress every 20 items (reduced from 10 for less logging overhead)
                if (i + 1) % 20 == 0:
                    logging.info(f"Processing JSON item {i + 1}/{len(items)}: '{product_name[:50]}...'")
                    
                processed_count += 1
                best_score = 0.0
                best_match_idx = None
                
                # Use optimized candidate selection instead of comparing against all items
                candidates = self._find_candidates_optimized(item)
                
                # Debug logging for specific item
                if "banana og" in product_name.lower():
                    logging.info(f"Found {len(candidates)} candidates for Banana OG item")
                    if candidates:
                        logging.info(f"Sample candidates: {[c['original_name'] for c in candidates[:3]]}")
                
                if not candidates:
                    logging.debug(f"No candidates found for '{product_name}'")
                    continue
                    
                # Try to match against filtered candidates (much smaller set)
                for cache_item in candidates:
                    score = self._calculate_match_score(item, cache_item)
                    if score > best_score:
                        best_score = score
                        best_match_idx = cache_item["idx"]
                        
                        # Early termination for very good matches
                        if best_score >= 0.9:
                            break
                        
                # Only accept matches with reasonable confidence
                if best_score >= 0.1:  # Lowered threshold for testing
                    matched_idxs.add(best_match_idx)
                    match_scores[best_match_idx] = best_score
                    matched_count += 1
                    logging.debug(f"Matched '{product_name}' to '{self._get_cache_item_name(best_match_idx)}' (score: {best_score:.2f})")
                else:
                    logging.debug(f"No match found for '{product_name}' (best score: {best_score:.2f})")
                    # --- Fallback tag creation with DB reference ---
                    pname = product_name
                    ptype_raw = item.get("product_type", "")
                    ptype = str(ptype_raw).lower() if ptype_raw else ""
                    qty = item.get("qty", 1)
                    
                    # Try to find strains in the product name for better lineage assignment
                    found_strains = self._find_strains_in_text(pname)
                    if found_strains:
                        # Use the first (most specific) strain found
                        best_strain, best_lineage = found_strains[0]
                        lineage = best_lineage
                        logging.debug(f"Found strain '{best_strain}' in '{pname}', using lineage '{lineage}'")
                    else:
                        # Fallback to database lookup
                        db_info = product_db.get_product_info(pname)
                        if db_info:
                            lineage = db_info.get("lineage") or db_info.get("canonical_lineage") or "HYBRID"
                            price = db_info.get("price") or 25
                            vendor = db_info.get("vendor")
                            brand = db_info.get("brand")
                            # Ensure all are strings for .lower()
                            if not isinstance(lineage, str):
                                lineage = str(lineage) if lineage is not None else "HYBRID"
                            if not isinstance(price, (int, float, str)):
                                price = 25
                            if not isinstance(vendor, str):
                                vendor = str(vendor) if vendor is not None else None
                            if not isinstance(brand, str):
                                brand = str(brand) if brand is not None else None
                        else:
                            # Guess price based on type
                            pname_lower = pname.lower()
                            ptype_lower = ptype.lower() if isinstance(ptype, str) else ""
                            if "pre-roll" in pname_lower or "pre-roll" in ptype_lower:
                                price = 20
                            elif "flower" in pname_lower or "flower" in ptype_lower:
                                price = 35
                            elif any(x in pname_lower for x in ["concentrate", "dab", "rosin", "wax"]):
                                price = 50
                            else:
                                price = 25
                            lineage = "HYBRID"
                            vendor_raw = item.get("vendor")
                            brand_raw = item.get("brand")
                            vendor = str(vendor_raw) if vendor_raw is not None else None
                            brand = str(brand_raw) if brand_raw is not None else None
                    mapped_json = map_json_to_db_fields(item)
                    
                    # Get formatted weight with units (similar to Excel processor)
                    weight_raw = mapped_json.get("weight", "")
                    weight_with_units = weight_raw
                    if weight_raw and mapped_json.get("units"):
                        weight_with_units = f"{weight_raw} {mapped_json.get('units')}"
                    
                    # Create fallback tag with same structure as Excel processor
                    product_name = mapped_json.get("product_name", "") or mapped_json.get("description", "") or "Unnamed Product"
                    
                    # Sanitize lineage (same as Excel processor)
                    lineage = str(mapped_json.get("lineage", "MIXED") or "").strip().upper()
                    if lineage not in ['SATIVA', 'INDICA', 'HYBRID', 'HYBRID/SATIVA', 'HYBRID/INDICA', 'CBD', 'MIXED', 'PARAPHERNALIA']:
                        lineage = "MIXED"
                    
                    fallback_tag = {
                        'Product Name*': product_name,
                        'Vendor': mapped_json.get("vendor", ""),
                        'Vendor/Supplier*': mapped_json.get("vendor", ""),
                        'Product Brand': mapped_json.get("brand", ""),
                        'ProductBrand': mapped_json.get("brand", ""),
                        'Lineage': lineage,
                        'Product Type*': mapped_json.get("product_type", ""),
                        'Product Type': mapped_json.get("product_type", ""),
                        'Weight*': weight_raw,
                        'Weight': weight_raw,
                        'WeightWithUnits': weight_with_units,
                        'WeightUnits': weight_with_units,
                        'Quantity*': mapped_json.get("quantity", ""),
                        'Quantity Received*': mapped_json.get("quantity", ""),
                        'Quantity': mapped_json.get("quantity", ""),  # Add uppercase Quantity
                        'quantity': mapped_json.get("quantity", ""),
                        # Lowercase versions for backward compatibility
                        'vendor': mapped_json.get("vendor", ""),
                        'productBrand': mapped_json.get("brand", ""),
                        'lineage': lineage,
                        'productType': mapped_json.get("product_type", ""),
                        'weight': weight_raw,
                        'weightWithUnits': weight_with_units,
                        'displayName': product_name,
                        # Additional fields for consistency with Excel processor
                        'Price': mapped_json.get("price", ""),
                        'Strain Name': mapped_json.get("strain_name", ""),
                        'Units': mapped_json.get("units", ""),
                        'Description': product_name,  # Add Description field
                        'Product Strain': mapped_json.get("strain_name", ""),  # Add Product Strain field
                        'Ratio': mapped_json.get("ratio", ""),  # Add Ratio field
                        'Ratio_or_THC_CBD': mapped_json.get("ratio", ""),  # Add Ratio_or_THC_CBD field
                        'CombinedWeight': weight_raw,  # Add CombinedWeight field
                        'Description_Complexity': "1",  # Add Description_Complexity field
                        'JointRatio': weight_with_units,  # Add JointRatio field
                        'Test result unit (% or mg)': mapped_json.get("test_unit", ""),  # Add test result unit
                        'THC test result': mapped_json.get("thc", ""),  # Add THC test result
                        'CBD test result': mapped_json.get("cbd", ""),  # Add CBD test result
                        'Source': "JSON Fallback"
                    }
                    fallback_tags.append(fallback_tag)

            # Performance summary
            total_time = time.time() - start_time
            items_per_second = processed_count / total_time if total_time > 0 else 0
            logging.info(f"JSON matching completed in {total_time:.2f}s: {matched_count}/{processed_count} items matched ({items_per_second:.1f} items/sec)")

            # Get the final matched product names
            result_tags = []
            if matched_idxs:
                df = self.excel_processor.df
                # Convert string indices back to original indices for DataFrame access
                original_indices = []
                for idx_str in matched_idxs:
                    try:
                        if isinstance(idx_str, int):
                            original_indices.append(idx_str)
                        elif isinstance(idx_str, str) and idx_str.isdigit():
                            original_indices.append(int(idx_str))
                        else:
                            # For non-numeric indices, try to find the original index
                            for i, (orig_idx, _) in enumerate(df.iterrows()):
                                if str(orig_idx) == str(idx_str):
                                    original_indices.append(orig_idx)
                                    break
                    except (ValueError, TypeError):
                        # If conversion fails, skip this index
                        continue

                # For each matched row, return all relevant DB fields with same structure as Excel processor
                result_tags = []
                for idx in original_indices:
                    row = df.loc[idx]
                    
                    # Get quantity from various possible column names (same as Excel processor)
                    quantity = row.get('Quantity*', '') or row.get('Quantity Received*', '') or row.get('Quantity', '') or row.get('qty', '') or ''
                    
                    # Get formatted weight with units (same as Excel processor)
                    weight_raw = row.get('Weight*', '')
                    weight_with_units = weight_raw
                    if weight_raw and row.get('Units'):
                        weight_with_units = f"{weight_raw} {row.get('Units')}"
                    
                    # Use the dynamically detected product name column (same as Excel processor)
                    product_name_col = 'Product Name*'
                    if product_name_col not in df.columns:
                        possible_cols = ['ProductName', 'Product Name', 'Description']
                        product_name_col = next((col for col in possible_cols if col in df.columns), None)
                        if not product_name_col:
                            product_name_col = 'Description'
                    
                    product_name = row.get(product_name_col, '') or row.get('Description', '') or 'Unnamed Product'
                    
                    # Helper function to safely get values (same as Excel processor)
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
                    
                    # Sanitize lineage (same as Excel processor)
                    lineage = str(row.get('Lineage', 'MIXED') or '').strip().upper()
                    if lineage not in ['SATIVA', 'INDICA', 'HYBRID', 'HYBRID/SATIVA', 'HYBRID/INDICA', 'CBD', 'MIXED', 'PARAPHERNALIA']:
                        lineage = "MIXED"
                    
                    tag = {
                        'Product Name*': safe_get_value(product_name),
                        'Vendor': safe_get_value(row.get('Vendor', '')),
                        'Vendor/Supplier*': safe_get_value(row.get('Vendor', '')),
                        'Product Brand': safe_get_value(row.get('Product Brand', '')),
                        'ProductBrand': safe_get_value(row.get('Product Brand', '')),
                        'Lineage': lineage,
                        'Product Type*': safe_get_value(row.get('Product Type*', '')),
                        'Product Type': safe_get_value(row.get('Product Type*', '')),
                        'Weight*': safe_get_value(weight_raw),
                        'Weight': safe_get_value(weight_raw),
                        'WeightWithUnits': safe_get_value(weight_with_units),
                        'WeightUnits': safe_get_value(weight_with_units),
                        'Quantity*': safe_get_value(quantity),
                        'Quantity Received*': safe_get_value(quantity),
                        'Quantity': safe_get_value(quantity),  # Add uppercase Quantity
                        'quantity': safe_get_value(quantity),
                        # Lowercase versions for backward compatibility
                        'vendor': safe_get_value(row.get('Vendor', '')),
                        'productBrand': safe_get_value(row.get('Product Brand', '')),
                        'lineage': lineage,
                        'productType': safe_get_value(row.get('Product Type*', '')),
                        'weight': safe_get_value(weight_raw),
                        'weightWithUnits': safe_get_value(weight_with_units),
                        'displayName': safe_get_value(product_name),
                        # Additional fields for consistency with Excel processor
                        'Price': safe_get_value(row.get('Price', '')),
                        'Strain Name': safe_get_value(row.get('Product Strain', '')),
                        'Units': safe_get_value(row.get('Units', '')),
                        'Description': safe_get_value(row.get('Description', product_name)),
                        'Product Strain': safe_get_value(row.get('Product Strain', '')),
                        'Ratio': safe_get_value(row.get('Ratio', '')),
                        'Ratio_or_THC_CBD': safe_get_value(row.get('Ratio_or_THC_CBD', '')),
                        'CombinedWeight': safe_get_value(row.get('CombinedWeight', weight_raw)),
                        'Description_Complexity': safe_get_value(row.get('Description_Complexity', '1')),
                        'JointRatio': safe_get_value(row.get('JointRatio', weight_with_units)),
                        'Test result unit (% or mg)': safe_get_value(row.get('Test result unit (% or mg)', '')),
                        'THC test result': safe_get_value(row.get('THC test result', '')),
                        'CBD test result': safe_get_value(row.get('CBD test result', '')),
                        'Source': "Excel Match"
                    }
                    result_tags.append(tag)

            # Combine matched and fallback tags
            all_tags = result_tags + fallback_tags
            # Store the full tag objects for later use
            self.json_matched_tags = all_tags
            
            # Also extract product names for backward compatibility
            self.json_matched_names = []
            for tag in all_tags:
                try:
                    product_name = tag.get("Product Name*") or tag.get("ProductName") or tag.get("product_name") or ""
                    if product_name:
                        self.json_matched_names.append(product_name)
                except Exception as e:
                    logging.warning(f"Error extracting product name from tag: {e}")
                    continue

            return all_tags

        except Exception as e:
            logging.error(f"Error in fetch_and_match: {e}")
            return []
            
    def _get_cache_item_name(self, idx_str: str) -> str:
        """Get the original name of a cache item by index."""
        for item in self._sheet_cache:
            if item["idx"] == idx_str:
                return item["original_name"]
        return "Unknown"
        
    def get_matched_names(self) -> Optional[List[str]]:
        """Get the currently matched product names from JSON."""
        return self.json_matched_names
        
    def get_matched_tags(self) -> Optional[List[Dict]]:
        """Get the currently matched full tag objects from JSON."""
        return getattr(self, 'json_matched_tags', None)
        
    def clear_matches(self):
        """Clear the current JSON matches."""
        self.json_matched_names = None
        self.json_matched_tags = None
        
    def rebuild_sheet_cache(self):
        """Force rebuild the sheet cache."""
        self._sheet_cache = None
        self._indexed_cache = None
        self._build_sheet_cache()
        
    def rebuild_strain_cache(self):
        """Force rebuild the strain cache."""
        self._strain_cache = None
        self._lineage_cache = None
        self._build_strain_cache()
        
    def rebuild_all_caches(self):
        """Force rebuild all caches."""
        self.rebuild_sheet_cache()
        self.rebuild_strain_cache()
        
    def get_sheet_cache_status(self):
        """Get the status of the sheet cache."""
        if self._sheet_cache is None:
            return "Not built"
        elif not self._sheet_cache:
            return "Empty"
        else:
            cache_info = f"Built with {len(self._sheet_cache)} entries"
            if self._indexed_cache:
                cache_info += f" (indexed: {len(self._indexed_cache['exact_names'])} exact, {len(self._indexed_cache['vendor_groups'])} vendors, {len(self._indexed_cache['key_terms'])} terms)"
            return cache_info
            
    def get_strain_cache_status(self):
        """Get the status of the strain cache."""
        if self._strain_cache is None:
            return "Not built"
        elif not self._strain_cache:
            return "Empty"
        else:
            return f"Built with {len(self._strain_cache)} strains and {len(self._lineage_cache)} lineages"
        
    def process_json_inventory(self, url: str) -> pd.DataFrame:
        """
        Process JSON inventory data and return as DataFrame for inventory slips.
        
        Args:
            url: URL to fetch JSON data from
            
        Returns:
            DataFrame with processed inventory data
        """
        try:
            # Use the proxy endpoint to handle authentication and CORS
            import requests
            
            # Prepare the request to our proxy endpoint
            proxy_data = {
                'url': url,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            }
            
            # Try to make the request directly first (for external URLs)
            try:
                response = requests.get(url, headers=proxy_data['headers'], timeout=30)
                response.raise_for_status()
                payload = response.json()
            except (requests.exceptions.RequestException, ValueError) as direct_error:
                logging.info(f"Direct request failed, trying proxy: {direct_error}")
                # Fallback to proxy endpoint if direct request fails
                import os
                base_url = os.environ.get('FLASK_BASE_URL', 'http://127.0.0.1:9090')
                response = requests.post(f'{base_url}/api/proxy-json', 
                                       json=proxy_data, 
                                       timeout=30)
                response.raise_for_status()
                payload = response.json()
                
            items = payload.get("inventory_transfer_items", [])
            vendor_meta = f"{payload.get('from_license_number', '')} – {payload.get('from_license_name', '')}"
            raw_date = payload.get("est_arrival_at", "").split("T")[0]
            
            records = []
            for itm in items:
                # Ensure all values are strings to prevent type issues
                product_name = str(itm.get("product_name", "")) if itm.get("product_name") is not None else ""
                inventory_id = str(itm.get("inventory_id", "")) if itm.get("inventory_id") is not None else ""
                qty = str(itm.get("qty", "")) if itm.get("qty") is not None else ""
                
                records.append({
                    "Product Name*": product_name,
                    "Barcode*": inventory_id,
                    "Quantity Received*": qty,
                    "Accepted Date": raw_date,
                    "Vendor": vendor_meta,
                })
                
            df = pd.DataFrame(records)
            logging.info(f"Processed {len(records)} inventory items from JSON")
            return df
            
        except Exception as e:
            logging.error(f"Error processing JSON inventory: {str(e)}")
            raise 

    def _build_strain_cache(self):
        """Build a cache of strain data from the product database for fast matching."""
        try:
            product_db = ProductDatabase()
            self._strain_cache = product_db.get_all_strains()
            self._lineage_cache = product_db.get_strain_lineage_map()
            
            # Debug: Check what's in the strain cache
            if self._strain_cache:
                sample_strains = list(self._strain_cache)[:5]
                logging.info(f"Sample strains in cache: {sample_strains}")
                for strain in sample_strains:
                    if not isinstance(strain, str):
                        logging.warning(f"Non-string strain found: {type(strain)} - {strain}")
            
            logging.info(f"Built strain cache with {len(self._strain_cache)} strains and {len(self._lineage_cache)} lineages")
        except Exception as e:
            logging.warning(f"Could not build strain cache: {e}")
            self._strain_cache = set()
            self._lineage_cache = {}
        
    def _find_strains_in_text(self, text: str) -> List[Tuple[str, str]]:
        """Find known strains in text and return (strain_name, lineage) pairs."""
        if not self._strain_cache:
            self._build_strain_cache()
            
        # Ensure input is a string
        text = str(text or "")
        if not text:
            return []
            
        text_lower = text.lower()
        found_strains = []
        
        # Check for exact strain matches
        for strain in self._strain_cache:
            # Ensure strain is a string before calling .lower()
            if isinstance(strain, str):
                if strain.lower() in text_lower:
                    lineage = self._lineage_cache.get(strain, "HYBRID")
                    found_strains.append((strain, lineage))
            else:
                # Skip non-string strains and log for debugging
                logging.warning(f"Skipping non-string strain in cache: {type(strain)} - {strain}")
                
        # Sort by length (longer strains first) to prioritize more specific matches
        found_strains.sort(key=lambda x: len(x[0]), reverse=True)
        
        return found_strains 