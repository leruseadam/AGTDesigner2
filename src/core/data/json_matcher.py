import re
import json
import urllib.request
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Set, Optional, Tuple
import pandas as pd

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

class JSONMatcher:
    """Handles JSON URL fetching and product matching functionality."""
    
    def __init__(self, excel_processor):
        self.excel_processor = excel_processor
        self._sheet_cache = None
        self.json_matched_names = None
        
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
                ~df[description_col].str.lower().str.contains("sample", na=False)
            ]
        else:
            # For ProductName/Product Name*, just filter out nulls
            df = df[df[description_col].notna()]
        
        cache = []
        for idx, row in df.iterrows():
            # Ensure idx is hashable by converting to string if needed
            hashable_idx = str(idx) if not isinstance(idx, (int, str, float)) else idx
            
            desc = row.get(description_col, "")
            norm = self._normalize(desc)
            toks = set(norm.split())
            
            # Extract key terms for better matching
            key_terms = self._extract_key_terms(desc)
            
            cache.append({
                "idx": hashable_idx,
                "brand": row.get("Product Brand", "").lower(),
                "vendor": row.get("Vendor", "").lower(),
                "ptype": row.get("Product Type*", "").lower(),
                "norm": norm,
                "toks": toks,
                "key_terms": key_terms,
                "original_name": desc,
            })
        self._sheet_cache = cache
        logging.info(f"Built sheet cache with {len(cache)} entries using column '{description_col}'")
        
    def _normalize(self, s: str) -> str:
        """Normalize text for matching by removing digits, units, and special characters."""
        s = (s or "").lower()
        s = _DIGIT_UNIT_RE.sub("", s)
        s = _NON_WORD_RE.sub(" ", s)
        return _SPLIT_RE.sub(" ", s).strip()
        
    def _extract_key_terms(self, name: str) -> Set[str]:
        """Extract meaningful product terms, excluding common prefixes/suffixes."""
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
        
    def _extract_vendor(self, name: str) -> str:
        """Extract vendor/brand information from product name."""
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
        
    def _calculate_match_score(self, json_item: dict, cache_item: dict) -> float:
        """Calculate a match score between JSON item and cache item."""
        json_name = json_item.get("product_name", "").lower()
        cache_name = cache_item["original_name"].lower()
        
        # Strategy 1: Exact match (highest score)
        if json_name == cache_name:
            return 1.0
            
        # Strategy 2: Contains match
        if json_name in cache_name or cache_name in json_name:
            return 0.9
            
        # Strategy 3: Key terms overlap
        json_key_terms = self._extract_key_terms(json_item.get("product_name", ""))
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
                
        # Strategy 4: Vendor/brand matching
        json_vendor = self._extract_vendor(json_item.get("product_name", ""))
        cache_vendor = self._extract_vendor(cache_item["original_name"])
        
        if json_vendor and cache_vendor and json_vendor == cache_vendor:
            # Vendor match gives a base score, but we need some term overlap too
            json_norm = self._normalize(json_item.get("product_name", ""))
            cache_norm = cache_item["norm"]
            
            if json_norm and cache_norm:
                # Check for any word overlap
                json_words = set(json_norm.split())
                cache_words = set(cache_norm.split())
                word_overlap = len(json_words.intersection(cache_words))
                
                if word_overlap >= 1:
                    return 0.6 + (word_overlap * 0.1)  # Base 0.6 + 0.1 per overlapping word
                    
        # Strategy 5: Fuzzy matching
        try:
            ratio = SequenceMatcher(None, json_name, cache_name).ratio()
            if ratio >= 0.7:
                return ratio * 0.5  # Scale down fuzzy matches
        except:
            pass
            
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
            # Fetch JSON
            with urllib.request.urlopen(url) as resp:
                payload = json.loads(resp.read().decode())
                
            items = payload.get("inventory_transfer_items", [])
            if not items:
                logging.warning("No inventory transfer items found in JSON")
                return []
                
            logging.info(f"Processing {len(items)} JSON items for matching")
            
            matched_idxs = set()
            match_scores = {}  # Track scores for debugging
            
            # For each JSON item, find the best match
            for item in items:
                if not item.get("product_name"):
                    continue
                    
                best_score = 0.0
                best_match_idx = None
                
                # Try to match against all cache items
                for cache_item in self._sheet_cache:
                    score = self._calculate_match_score(item, cache_item)
                    
                    if score > best_score:
                        best_score = score
                        best_match_idx = cache_item["idx"]
                        
                # Only accept matches with reasonable confidence
                if best_score >= 0.3:  # Lowered threshold for better matching
                    matched_idxs.add(best_match_idx)
                    match_scores[best_match_idx] = best_score
                    logging.info(f"Matched '{item.get('product_name')}' to '{self._get_cache_item_name(best_match_idx)}' (score: {best_score:.2f})")
                else:
                    logging.info(f"No match found for '{item.get('product_name')}' (best score: {best_score:.2f})")
            
            # Get the final matched product names
            if matched_idxs:
                df = self.excel_processor.df
                # Convert string indices back to original indices for DataFrame access
                original_indices = []
                for idx_str in matched_idxs:
                    try:
                        # Try to convert back to original index type
                        if idx_str.isdigit():
                            original_indices.append(int(idx_str))
                        else:
                            # For non-numeric indices, try to find the original index
                            for i, (orig_idx, _) in enumerate(df.iterrows()):
                                if str(orig_idx) == idx_str:
                                    original_indices.append(orig_idx)
                                    break
                    except (ValueError, TypeError):
                        # If conversion fails, skip this index
                        continue
                
                # Try both possible column names
                if 'Product Name*' in df.columns:
                    final = sorted(df.loc[original_indices, 'Product Name*'].tolist())
                elif 'ProductName' in df.columns:
                    final = sorted(df.loc[original_indices, 'ProductName'].tolist())
                else:
                    logging.error("Neither 'Product Name*' nor 'ProductName' column found in DataFrame.")
                    final = []
                    
                self.json_matched_names = final
                logging.info(f"JSON matching found {len(final)} products")
                return final
            else:
                logging.warning("No products matched from JSON")
                return []
                
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
        
    def get_sheet_cache_status(self):
        """Get the status of the sheet cache."""
        if self._sheet_cache is None:
            return "Not built"
        elif not self._sheet_cache:
            return "Empty"
        else:
            return f"Built with {len(self._sheet_cache)} entries"
        
    def process_json_inventory(self, url: str) -> pd.DataFrame:
        """
        Process JSON inventory data and return as DataFrame for inventory slips.
        
        Args:
            url: URL to fetch JSON data from
            
        Returns:
            DataFrame with processed inventory data
        """
        try:
            with urllib.request.urlopen(url) as resp:
                payload = json.loads(resp.read().decode())
                
            items = payload.get("inventory_transfer_items", [])
            vendor_meta = f"{payload.get('from_license_number', '')} – {payload.get('from_license_name', '')}"
            raw_date = payload.get("est_arrival_at", "").split("T")[0]
            
            records = []
            for itm in items:
                records.append({
                    "Product Name*": itm.get("product_name", ""),
                    "Barcode*": itm.get("inventory_id", ""),
                    "Quantity Received*": itm.get("qty", ""),
                    "Accepted Date": raw_date,
                    "Vendor": vendor_meta,
                })
                
            df = pd.DataFrame(records)
            logging.info(f"Processed {len(records)} inventory items from JSON")
            return df
            
        except Exception as e:
            logging.error(f"Error processing JSON inventory: {str(e)}")
            raise 