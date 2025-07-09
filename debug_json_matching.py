#!/usr/bin/env python3
"""
Debug script to test JSON matching functionality step by step
"""

import os
import sys
import pandas as pd
import logging

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.data.excel_processor import ExcelProcessor
from src.core.data.json_matcher import JSONMatcher

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_json_matching():
    """Debug the JSON matching functionality step by step"""
    try:
        # Initialize Excel processor
        excel_processor = ExcelProcessor()
        
        # Load a sample Excel file
        excel_files = [
            'uploads/A Greener Today - Bothell_inventory_07-07-2025 10_19 AM.xlsx',
            'uploads/default.xlsx',
            'uploads/sample.xlsx'
        ]
        
        excel_file = None
        for file_path in excel_files:
            if os.path.exists(file_path):
                excel_file = file_path
                break
                
        if not excel_file:
            logger.error("No Excel file found for testing")
            return False
            
        logger.info(f"Loading Excel file: {excel_file}")
        
        if not excel_processor.load_file(excel_file):
            logger.error("Failed to load Excel file")
            return False
            
        logger.info(f"Successfully loaded Excel file with {len(excel_processor.df)} records")
        
        # Show available columns
        logger.info(f"Available columns: {list(excel_processor.df.columns)}")
        
        # Initialize JSON matcher
        json_matcher = JSONMatcher(excel_processor)
        
        # Build sheet cache
        json_matcher._build_sheet_cache()
        cache_status = json_matcher.get_sheet_cache_status()
        logger.info(f"Sheet cache status: {cache_status}")
        
        # Show first few cache items
        logger.info("\n=== FIRST FEW CACHE ITEMS ===")
        for i, item in enumerate(json_matcher._sheet_cache[:5]):
            logger.info(f"Cache item {i+1}:")
            logger.info(f"  Original name: '{item['original_name']}'")
            logger.info(f"  Normalized: '{item['norm']}'")
            logger.info(f"  Key terms: {item['key_terms']}")
            logger.info(f"  Vendor: '{item['vendor']}'")
            logger.info(f"  Brand: '{item['brand']}'")
        
        # Test with sample JSON data
        logger.info("\n=== TESTING MATCHING LOGIC ===")
        
        # Create mock JSON items
        json_items = [
            {"product_name": "Medically Compliant - Dank Czar Rosin All-In-One - GMO - 1g"},
            {"product_name": "Medically Compliant - Dank Czar Rosin All-In-One - Grape Gas - 1g"},
            {"product_name": "Medically Compliant - Melt Stix - F: Elephant Garlic H: Cookies & Cream - 2pk"},
            {"product_name": "Blue Dream Flower - Premium Quality - 3.5g"},
            {"product_name": "THC Gummies - Mixed Berry - 100mg"}
        ]
        
        # Test matching each JSON item
        for i, json_item in enumerate(json_items):
            logger.info(f"\nTesting JSON item {i+1}: '{json_item['product_name']}'")
            
            # Extract key terms and vendor for this JSON item
            json_key_terms = json_matcher._extract_key_terms(json_item['product_name'])
            json_vendor = json_matcher._extract_vendor(json_item['product_name'])
            json_norm = json_matcher._normalize(json_item['product_name'])
            
            logger.info(f"  JSON key terms: {json_key_terms}")
            logger.info(f"  JSON vendor: '{json_vendor}'")
            logger.info(f"  JSON normalized: '{json_norm}'")
            
            best_score = 0.0
            best_match = None
            best_match_name = ""
            
            # Try to match against first 10 cache items for debugging
            for j, cache_item in enumerate(json_matcher._sheet_cache[:10]):
                cache_name = cache_item["original_name"]
                
                # Calculate match score
                score = json_matcher._calculate_match_score(json_item, cache_item)
                
                if score > best_score:
                    best_score = score
                    best_match = cache_item
                    best_match_name = cache_name
                
                # Show detailed scoring for first few attempts
                if j < 3:
                    logger.info(f"    vs '{cache_name}' (score: {score:.3f})")
                    logger.info(f"      Cache key terms: {cache_item['key_terms']}")
                    logger.info(f"      Cache vendor: '{cache_item['vendor']}'")
                    logger.info(f"      Cache normalized: '{cache_item['norm']}'")
                    
                    # Show overlap details
                    if json_key_terms and cache_item['key_terms']:
                        overlap = json_key_terms.intersection(cache_item['key_terms'])
                        logger.info(f"      Term overlap: {overlap}")
                        
            # Report results
            if best_score >= 0.3:
                logger.info(f"  ✓ MATCHED: '{best_match_name}' (score: {best_score:.3f})")
            else:
                logger.info(f"  ✗ NO MATCH (best score: {best_score:.3f})")
                
                # Show potential matches with lower thresholds
                logger.info(f"    Potential matches (score > 0.1):")
                for cache_item in json_matcher._sheet_cache[:20]:
                    score = json_matcher._calculate_match_score(json_item, cache_item)
                    if score > 0.1:
                        logger.info(f"      '{cache_item['original_name']}' (score: {score:.3f})")
        
        logger.info("\n=== DEBUGGING COMPLETE ===")
        return True
        
    except Exception as e:
        logger.error(f"Error in debug_json_matching: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    debug_json_matching() 