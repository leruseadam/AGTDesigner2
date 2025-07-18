import re
import json
import urllib.request
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Set, Optional, Tuple
import pandas as pd
from .product_database import ProductDatabase

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
    return products

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
        self.json_matched_names = None
        self._strain_cache = None
        self._lineage_cache = None
        
    def _build_sheet_cache(self):
        """Build a cache of sheet data for fast matching."""
        df = self.excel_processor.df
        if df is None or df.empty:
            self._sheet_cache = []
            return
            
        # Determine the best description column to use
        description_col = None
        for col in ["Product Name*", "ProductName", "Description"]:
            if col in df.columns:
                description_col = col
                break
                
        if not description_col:
            logging.error("No suitable description column found")
            self._sheet_cache = []
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
            vendor_raw = row.get("Vendor", "")
            ptype_raw = row.get("Product Type*", "")
            
            try:
                brand = str(brand_raw).lower() if brand_raw is not None else ""
                vendor = str(vendor_raw).lower() if vendor_raw is not None else ""
                ptype = str(ptype_raw).lower() if ptype_raw is not None else ""
            except Exception as e:
                logging.warning(f"Error processing row {idx}: {e}")
                brand = ""
                vendor = ""
                ptype = ""
            
            try:
                cache.append({
                    "idx": hashable_idx,
                    "brand": brand,
                    "vendor": vendor,
                    "ptype": ptype,
                    "norm": norm,
                    "toks": toks,
                    "key_terms": key_terms,
                    "original_name": desc,
                })
            except Exception as e:
                logging.warning(f"Error creating cache item for row {idx}: {e}")
                continue
        self._sheet_cache = cache
        logging.info(f"Built sheet cache with {len(cache)} entries using column '{description_col}'")
        
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
                'the', 'and', 'or', 'with', 'for', 'of', 'by', 'from', 'to', 'in', 'on', 'at', 'a', 'an'
            }
            
            # Filter out common words and short words (less than 3 characters)
            key_terms = {word for word in words if word not in common_words and len(word) >= 3}
            
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
            
            # Handle "Medically Compliant -" prefix
            if name_lower.startswith("medically compliant -"):
                after_prefix = name.split("-", 1)[1].strip()
                brand_words = after_prefix.split()
                if brand_words:
                    return " ".join(brand_words[:2]).lower()
                return after_prefix.lower()
                
            # Handle other dash-separated formats
            parts = name.split("-", 1)
            if len(parts) > 1:
                brand_words = parts[0].strip().split()
                return " ".join(brand_words[:2]).lower() if brand_words else ""
                
            # Fallback: use first two words
            words = name_lower.split()
            return " ".join(words[:2]) if words else ""
        except Exception as e:
            logging.warning(f"Error in _extract_vendor: {e}")
            return ""
        
    def _calculate_match_score(self, json_item: dict, cache_item: dict) -> float:
        """Calculate a match score between JSON item and cache item."""
        try:
            # Ensure we have string values before calling .lower()
            json_name = str(json_item.get("product_name", "")).lower()
            cache_name = str(cache_item["original_name"]).lower()
            
            # Strategy 1: Exact match (highest score)
            if json_name == cache_name:
                return 1.0
                
            # Strategy 2: Contains match
            if json_name in cache_name or cache_name in json_name:
                return 0.9
                
            # Strategy 3: Strain-aware matching (NEW)
            try:
                json_strains = self._find_strains_in_text(str(json_item.get("product_name", "")))
                cache_strains = self._find_strains_in_text(str(cache_item["original_name"]))
            except Exception as e:
                logging.warning(f"Error in strain matching: {e}")
                json_strains = []
                cache_strains = []
            
            if json_strains and cache_strains:
                # Check for strain overlap
                json_strain_names = {strain[0].lower() for strain in json_strains if isinstance(strain[0], str)}
                cache_strain_names = {strain[0].lower() for strain in cache_strains if isinstance(strain[0], str)}
                
                strain_overlap = json_strain_names.intersection(cache_strain_names)
                if strain_overlap:
                    # Strong boost for strain matches
                    strain_score = 0.85 + (len(strain_overlap) * 0.05)  # Base 0.85 + 0.05 per matching strain
                    return min(0.95, strain_score)  # Cap at 0.95
                    
                # Check for lineage compatibility
                json_lineages = {strain[1] for strain in json_strains}
                cache_lineages = {strain[1] for strain in cache_strains}
                
                lineage_overlap = json_lineages.intersection(cache_lineages)
                if lineage_overlap:
                    # Moderate boost for lineage matches
                    return 0.75
                
            # Strategy 4: Key terms overlap
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
                    
                    # Combine both metrics
                    term_score = (jaccard + overlap_ratio) / 2
                    return min(0.8, term_score)
                    
            # Strategy 5: Vendor/brand matching
            json_vendor = self._extract_vendor(str(json_item.get("product_name", "")))
            cache_vendor = self._extract_vendor(str(cache_item["original_name"]))
            
            if json_vendor and cache_vendor and json_vendor == cache_vendor:
                # Vendor match gives a base score, but we need some term overlap too
                json_norm = self._normalize(str(json_item.get("product_name", "")))
                cache_norm = cache_item["norm"]
                
                if json_norm and cache_norm:
                    # Check for any word overlap
                    json_words = set(json_norm.split())
                    cache_words = set(cache_norm.split())
                    word_overlap = len(json_words.intersection(cache_words))
                    
                    if word_overlap >= 1:
                        return 0.6 + (word_overlap * 0.1)  # Base 0.6 + 0.1 per overlapping word
                        
            # Strategy 6: Fuzzy matching
            try:
                ratio = SequenceMatcher(None, json_name, cache_name).ratio()
                if ratio >= 0.7:
                    return ratio * 0.5  # Scale down fuzzy matches
            except:
                pass
                
            return 0.0
        except Exception as e:
            logging.error(f"Error in _calculate_match_score: {e}")
            logging.error(f"json_item: {json_item}")
            logging.error(f"cache_item: {cache_item}")
            return 0.0
        
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
        if self._sheet_cache is None:
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
            
            # Make the request to our proxy endpoint
            response = requests.post('http://127.0.0.1:9090/api/proxy-json', 
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

            # For each JSON item, find the best match
            for item in items:
                if not item.get("product_name"):
                    continue
                    
                # Ensure product_name is a string
                product_name = str(item.get("product_name", ""))
                if not product_name.strip():
                    continue
                    
                best_score = 0.0
                best_match_idx = None
                json_vendor = str(item.get("vendor", "")).strip().lower() if item.get("vendor") else None
                
                # Try to match against all cache items
                for cache_item in self._sheet_cache:
                    cache_vendor = str(cache_item.get("vendor", "")).strip().lower() if cache_item.get("vendor") else None
                    # Only match if vendors are the same (or if no vendor info in JSON)
                    if json_vendor and cache_vendor and json_vendor != cache_vendor:
                        continue
                    score = self._calculate_match_score(item, cache_item)
                    if score > best_score:
                        best_score = score
                        best_match_idx = cache_item["idx"]
                        
                # Only accept matches with reasonable confidence
                if best_score >= 0.3:
                    matched_idxs.add(best_match_idx)
                    match_scores[best_match_idx] = best_score
                    logging.info(f"Matched '{product_name}' to '{self._get_cache_item_name(best_match_idx)}' (score: {best_score:.2f})")
                else:
                    logging.info(f"No match found for '{product_name}' (best score: {best_score:.2f})")
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
                        logging.info(f"Found strain '{best_strain}' in '{pname}', using lineage '{lineage}'")
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
                    fallback_tag = {k: mapped_json.get(k, None) for k in [
                        "product_name", "description", "vendor", "brand", "price", "lineage", "strain_name", "product_type", "units", "weight", "quantity"
                    ]}
                    # Add Source for traceability
                    fallback_tag["Source"] = "JSON Fallback"
                    fallback_tags.append(fallback_tag)

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

                # For each matched row, return all relevant DB fields
                result_tags = []
                for idx in original_indices:
                    row = df.loc[idx]
                    tag = {k: row.get(k, None) for k in [
                        "Product Name*", "ProductName", "Description", "Vendor", "Product Brand", "Price", "Lineage", "Strain Name", "Product Type*", "Units", "Weight*", "Quantity*"
                    ]}
                    tag["Source"] = "Excel Match"
                    result_tags.append(tag)

            # Combine matched and fallback tags
            all_tags = result_tags + fallback_tags
            self.json_matched_names = [tag["Product Name*"] for tag in all_tags]
            logging.info(f"JSON matching found {len(result_tags)} matched and {len(fallback_tags)} fallback products")

            # --- NEW: Add matched names to ExcelProcessor's selected_tags ---
            if hasattr(self, 'excel_processor') and self.excel_processor is not None:
                # Only add matched names (not fallback tags) to selected_tags
                matched_names = [tag["Product Name*"] for tag in result_tags]
                if matched_names:
                    self.excel_processor.select_tags(matched_names)

            return all_tags
                
        except Exception as e:
            logging.error(f"Error in fetch_and_match: {str(e)}")
            raise
            
    def _get_cache_item_name(self, idx_str: str) -> str:
        """Get the original name of a cache item by index."""
        for item in self._sheet_cache:
            if item["idx"] == idx_str:
                return item["original_name"]
        return "Unknown"
        
    def get_matched_names(self) -> Optional[List[str]]:
        """Get the currently matched product names from JSON."""
        return self.json_matched_names
        
    def clear_matches(self):
        """Clear the current JSON matches."""
        self.json_matched_names = None
        
    def rebuild_sheet_cache(self):
        """Force rebuild the sheet cache."""
        self._sheet_cache = None
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
            return f"Built with {len(self._sheet_cache)} entries"
            
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
            
            # Make the request to our proxy endpoint
            response = requests.post('http://127.0.0.1:9090/api/proxy-json', 
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