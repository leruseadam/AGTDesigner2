#!/usr/bin/env python3
"""
Test script to verify improved JSON matching functionality
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

def test_improved_json_matching():
    """Test the improved JSON matching functionality"""
    try:
        # Initialize Excel processor
        excel_processor = ExcelProcessor()
        
        # Load a sample Excel file (you may need to adjust the path)
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
        
        # Initialize JSON matcher
        json_matcher = JSONMatcher(excel_processor)
        
        # Build sheet cache
        json_matcher._build_sheet_cache()
        cache_status = json_matcher.get_sheet_cache_status()
        logger.info(f"Sheet cache status: {cache_status}")
        
        # Test key term extraction
        logger.info("\n=== TESTING KEY TERM EXTRACTION ===")
        test_names = [
            "Medically Compliant - Dank Czar Rosin All-In-One - GMO - 1g",
            "Medically Compliant - Dank Czar Rosin All-In-One - Grape Gas - 1g",
            "Medically Compliant - Melt Stix - F: Elephant Garlic H: Cookies & Cream - 2pk",
            "Blue Dream Flower - Premium Quality - 3.5g",
            "THC Gummies - Mixed Berry - 100mg"
        ]
        
        for name in test_names:
            key_terms = json_matcher._extract_key_terms(name)
            vendor = json_matcher._extract_vendor(name)
            logger.info(f"'{name}'")
            logger.info(f"  Vendor: '{vendor}'")
            logger.info(f"  Key terms: {key_terms}")
            
        # Test matching with sample JSON data
        logger.info("\n=== TESTING MATCHING LOGIC ===")
        
        # Create mock JSON items
        json_items = [
            {"product_name": "Medically Compliant - Dank Czar Rosin All-In-One - GMO - 1g"},
            {"product_name": "Medically Compliant - Dank Czar Rosin All-In-One - Grape Gas - 1g"},
            {"product_name": "Medically Compliant - Melt Stix - F: Elephant Garlic H: Cookies & Cream - 2pk"},
            {"product_name": "Blue Dream Flower - Premium Quality - 3.5g"},
            {"product_name": "THC Gummies - Mixed Berry - 100mg"}
        ]
        
        # Get available tags for comparison
        available_tags = excel_processor.get_available_tags()
        logger.info(f"Available tags count: {len(available_tags)}")
        
        # Test matching each JSON item
        for i, json_item in enumerate(json_items):
            logger.info(f"\nTesting JSON item {i+1}: '{json_item['product_name']}'")
            
            best_score = 0.0
            best_match = None
            best_match_name = ""
            
            # Try to match against all available tags
            for tag in available_tags[:20]:  # Test against first 20 tags for performance
                tag_name = tag.get('Product Name*', '')
                if not tag_name:
                    continue
                    
                # Create a mock cache item for scoring
                cache_item = {
                    "original_name": tag_name,
                    "key_terms": json_matcher._extract_key_terms(tag_name),
                    "norm": json_matcher._normalize(tag_name)
                }
                
                # Calculate match score
                score = json_matcher._calculate_match_score(json_item, cache_item)
                
                if score > best_score:
                    best_score = score
                    best_match = tag
                    best_match_name = tag_name
                    
            # Report results
            if best_score >= 0.3:
                logger.info(f"  ✓ MATCHED: '{best_match_name}' (score: {best_score:.2f})")
            else:
                logger.info(f"  ✗ NO MATCH (best score: {best_score:.2f})")
                
                # Show potential matches with lower thresholds
                logger.info(f"    Potential matches:")
                for tag in available_tags[:10]:
                    tag_name = tag.get('Product Name*', '')
                    if not tag_name:
                        continue
                        
                    cache_item = {
                        "original_name": tag_name,
                        "key_terms": json_matcher._extract_key_terms(tag_name),
                        "norm": json_matcher._normalize(tag_name)
                    }
                    
                    score = json_matcher._calculate_match_score(json_item, cache_item)
                    if score > 0.1:  # Show any score > 0.1
                        logger.info(f"      '{tag_name}' (score: {score:.2f})")
        
        logger.info("\n=== TESTING COMPLETE ===")
        return True
        
    except Exception as e:
        logger.error(f"Error in test_improved_json_matching: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    test_improved_json_matching() 