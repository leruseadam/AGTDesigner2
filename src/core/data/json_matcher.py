import re
import json
import urllib.request
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Set, Optional
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
        """Build a cache of normalized product data for matching."""
        if self.excel_processor.df is None:
            logging.warning("No DataFrame available for building sheet cache")
            return
            
        df = self.excel_processor.df
        
        # Check if Description column exists, if not use ProductName or Product Name*
        description_col = None
        if "Description" in df.columns:
            description_col = "Description"
        elif "ProductName" in df.columns:
            description_col = "ProductName"
        elif "Product Name*" in df.columns:
            description_col = "Product Name*"
        else:
            logging.error("No suitable description column found in DataFrame")
            return
            
        # Filter out sample rows if Description column exists and has content
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
            desc = row.get(description_col, "")
            norm = _SPLIT_RE.sub(" ",
                   _NON_WORD_RE.sub(" ",
                   _DIGIT_UNIT_RE.sub("", desc.lower())
            )).strip()
            toks = set(norm.split())
            cache.append({
                "idx": idx,
                "brand": row.get("Product Brand", "").lower(),
                "vendor": row.get("Vendor", "").lower(),
                "ptype": row.get("Product Type*", "").lower(),
                "norm": norm,
                "toks": toks,
            })
        self._sheet_cache = cache
        logging.info(f"Built sheet cache with {len(cache)} entries using column '{description_col}'")
        
    def _normalize(self, s: str) -> str:
        """Normalize text for matching by removing digits, units, and special characters."""
        s = (s or "").lower()
        s = _DIGIT_UNIT_RE.sub("", s)
        s = _NON_WORD_RE.sub(" ", s)
        return _SPLIT_RE.sub(" ", s).strip()
        
    def fetch_and_match(self, url: str) -> tuple[List[str], List[dict]]:
        """
        Fetch JSON from URL and match products against the loaded Excel data.
        
        Args:
            url: URL to fetch JSON data from
            
        Returns:
            Tuple of (matched product names, unmatched JSON items)
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
                
            # Gather JSON brands/vendor
            json_brands = {itm.get("product_brand", "").lower() for itm in items if itm.get("product_brand")}
            json_vendor = payload.get("from_license_name", "").lower()
            
            # Prefilter cache by brand/vendor
            pre = [
                r for r in self._sheet_cache
                if (r["brand"] in json_brands) or (r["vendor"] == json_vendor)
            ]
            
            matched_idxs = set()
            
            # For each JSON item, try to match against the prefiltered cache
            for itm in items:
                raw = itm.get("product_name") or ""
                name_norm = self._normalize(raw)
                if not name_norm:
                    continue
                name_toks = set(name_norm.split())
                
                # Type override
                override = next(
                    (ptype for kw, ptype in TYPE_OVERRIDES.items() if kw in name_norm),
                    None
                )
                
                # Work on a slice of prefiltered items
                bucket = [r for r in pre if (override is None or r["ptype"] == override)]
                
                # 1) Substring matching
                for r in bucket:
                    if r["norm"] in name_norm or name_norm in r["norm"]:
                        matched_idxs.add(r["idx"])
                
                # 2) Token overlap >= 2
                for r in bucket:
                    if len(name_toks & r["toks"]) >= 2:
                        matched_idxs.add(r["idx"])
                
                # 3) Jaccard similarity >= 0.3
                for r in bucket:
                    u = name_toks | r["toks"]
                    if u and len(name_toks & r["toks"]) / len(u) >= 0.3:
                        matched_idxs.add(r["idx"])
                
                # 4) SequenceMatcher fallback on normalized text
                for r in bucket:
                    short, long = (name_norm, r["norm"]) if len(name_norm) < len(r["norm"]) else (r["norm"], name_norm)
                    win = len(short)
                    for i in range(len(long) - win + 1):
                        if SequenceMatcher(None, long[i:i+win], short).ratio() >= 0.6:
                            matched_idxs.add(r["idx"])
                            break
            
            # Always include all prefiltered rows
            matched_idxs.update(r["idx"] for r in pre)
            
            # Get the final matched product names
            if matched_idxs:
                df = self.excel_processor.df
                # Try both possible column names
                if 'Product Name*' in df.columns:
                    final = sorted(df.loc[list(matched_idxs), 'Product Name*'].tolist())
                elif 'ProductName' in df.columns:
                    final = sorted(df.loc[list(matched_idxs), 'ProductName'].tolist())
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