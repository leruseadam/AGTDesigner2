#!/usr/bin/env python3
"""
Test script to verify that JSON matching properly adheres to vendor filtering.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.data.json_matcher import JSONMatcher
from src.core.data.excel_processor import ExcelProcessor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_vendor_filtering():
    """Test that JSON matching respects vendor filtering."""
    
    print("=== TESTING VENDOR FILTERING FIX ===\n")
    
    # Initialize Excel processor
    excel_processor = ExcelProcessor()
    
    # Load test data
    test_file = "uploads/A Greener Today - Bothell_inventory_07-15-2025  7_04 PM.xlsx"
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    excel_processor.load_file(test_file)
    print(f"Loaded Excel file with {len(excel_processor.df)} records")
    
    # Initialize JSON matcher
    json_matcher = JSONMatcher(excel_processor)
    
    # Build the cache
    json_matcher._build_sheet_cache()
    print("Built sheet cache for JSON matcher")
    
    # Test cases with different vendors
    test_cases = [
        {
            "name": "Medically Compliant - Dank Czar Live Hash Rosin Reserve - GMO - 1g (Boxed 5ml)",
            "vendor": "Dank Czar",
            "expected_vendor": "DCZ Holdings Inc."
        },
        {
            "name": "Medically Compliant - Omega Distillate Cartridge - Cherry Lemonheadz - 1g",
            "vendor": "Omega",
            "expected_vendor": "Omega"
        },
        {
            "name": "Black Mamba Distillate Cartridge by Airo Pro - 1g",
            "vendor": "Airo Pro",
            "expected_vendor": "Airo Pro"
        }
    ]
    
    print("\n=== TESTING CANDIDATE SELECTION ===")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print(f"JSON Vendor: {test_case['vendor']}")
        print(f"Expected Excel Vendor: {test_case['expected_vendor']}")
        
        # Create mock JSON item
        json_item = {
            "product_name": test_case["name"],
            "vendor": test_case["vendor"]
        }
        
        # Get candidates
        candidates = json_matcher._find_candidates_optimized(json_item)
        
        print(f"Found {len(candidates)} candidates")
        
        # Check vendor consistency
        vendor_mismatches = []
        vendor_matches = []
        
        for candidate in candidates[:10]:  # Check first 10 candidates
            candidate_vendor = candidate.get("vendor", "").strip()
            if candidate_vendor:
                if candidate_vendor.lower() != test_case["expected_vendor"].lower():
                    vendor_mismatches.append(candidate["original_name"])
                else:
                    vendor_matches.append(candidate["original_name"])
        
        print(f"Vendor matches: {len(vendor_matches)}")
        print(f"Vendor mismatches: {len(vendor_mismatches)}")
        
        if vendor_mismatches:
            print("❌ VENDOR MISMATCHES FOUND:")
            for mismatch in vendor_mismatches[:3]:  # Show first 3
                print(f"  - {mismatch}")
        else:
            print("✅ All candidates have matching vendors")
        
        if vendor_matches:
            print("✅ Vendor matches found:")
            for match in vendor_matches[:3]:  # Show first 3
                print(f"  - {match}")
    
    print("\n=== TESTING SCORE CALCULATION ===")
    
    # Test scoring with vendor mismatches
    test_scoring_cases = [
        {
            "json_item": {
                "product_name": "Medically Compliant - Dank Czar Live Hash Rosin Reserve - GMO - 1g",
                "vendor": "Dank Czar"
            },
            "cache_item": {
                "original_name": "Black Mamba Distillate Cartridge by Airo Pro - 1g",
                "vendor": "Airo Pro",
                "key_terms": {"black", "mamba", "distillate", "cartridge"},
                "norm": "black mamba distillate cartridge"
            },
            "expected_score": 0.0  # Should be rejected due to vendor mismatch
        },
        {
            "json_item": {
                "product_name": "Medically Compliant - Dank Czar Live Hash Rosin Reserve - GMO - 1g",
                "vendor": "Dank Czar"
            },
            "cache_item": {
                "original_name": "Dank Czar Hash Research Dab Mat",
                "vendor": "DCZ Holdings Inc.",
                "key_terms": {"dank", "czar", "hash", "research", "dab", "mat"},
                "norm": "dank czar hash research dab mat"
            },
            "expected_score": ">0.0"  # Should be allowed due to vendor match
        }
    ]
    
    for i, test_case in enumerate(test_scoring_cases, 1):
        print(f"\nScoring Test {i}:")
        print(f"JSON: {test_case['json_item']['product_name']} (vendor: {test_case['json_item']['vendor']})")
        print(f"Cache: {test_case['cache_item']['original_name']} (vendor: {test_case['cache_item']['vendor']})")
        
        score = json_matcher._calculate_match_score(test_case['json_item'], test_case['cache_item'])
        print(f"Score: {score:.3f}")
        
        if test_case['expected_score'] == 0.0:
            if score == 0.0:
                print("✅ Correctly rejected vendor mismatch")
            else:
                print("❌ Should have rejected vendor mismatch")
        elif test_case['expected_score'] == ">0.0":
            if score > 0.0:
                print("✅ Correctly allowed vendor match")
            else:
                print("❌ Should have allowed vendor match")
    
    print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    test_vendor_filtering() 