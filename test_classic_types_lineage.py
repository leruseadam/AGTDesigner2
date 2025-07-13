#!/usr/bin/env python3
"""
Test script to verify that classic types without lineage values default to HYBRID.
"""

import pandas as pd
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.data.excel_processor import ExcelProcessor
from src.core.constants import CLASSIC_TYPES

def test_classic_types_lineage_default():
    """Test that classic types without lineage values default to HYBRID."""
    
    print("Testing classic types lineage default behavior...")
    print(f"Classic types defined: {CLASSIC_TYPES}")
    print()
    
    # Create test data with classic types that have empty lineage values
    test_data = {
        'Product Name*': [
            'Test Flower 1',
            'Test Pre-roll 1', 
            'Test Concentrate 1',
            'Test Edible 1',
            'Test Tincture 1'
        ],
        'Product Type*': [
            'flower',  # Classic type
            'pre-roll',  # Classic type
            'concentrate',  # Classic type
            'edible (solid)',  # Non-classic type
            'tincture'  # Non-classic type
        ],
        'Lineage': [
            '',  # Empty lineage for classic type
            None,  # None lineage for classic type
            '   ',  # Whitespace lineage for classic type
            '',  # Empty lineage for non-classic type
            None  # None lineage for non-classic type
        ],
        'Product Brand': ['Test Brand'] * 5,
        'Vendor': ['Test Vendor'] * 5,
        'Weight*': ['1g'] * 5,
        'Units': ['g'] * 5,
        'Price': ['10.00'] * 5
    }
    
    # Create DataFrame
    df = pd.DataFrame(test_data)
    
    # Create ExcelProcessor instance
    processor = ExcelProcessor()
    processor.df = df.copy()
    
    print("Initial data:")
    print(df[['Product Name*', 'Product Type*', 'Lineage']].to_string())
    print()
    
    # Run the lineage normalization logic
    try:
        processor.validate_and_normalize_data()
        
        print("After lineage normalization:")
        result_df = processor.df[['Product Name*', 'Product Type*', 'Lineage']]
        print(result_df.to_string())
        print()
        
        # Check results
        classic_results = result_df[result_df['Product Type*'].str.lower().isin(CLASSIC_TYPES)]
        non_classic_results = result_df[~result_df['Product Type*'].str.lower().isin(CLASSIC_TYPES)]
        
        print("Classic types lineage results:")
        for _, row in classic_results.iterrows():
            expected = "HYBRID"
            actual = row['Lineage']
            status = "✅ PASS" if actual == expected else "❌ FAIL"
            print(f"  {row['Product Name*']} ({row['Product Type*']}): {actual} - {status}")
        
        print()
        print("Non-classic types lineage results:")
        for _, row in non_classic_results.iterrows():
            expected = "MIXED"
            actual = row['Lineage']
            status = "✅ PASS" if actual == expected else "❌ FAIL"
            print(f"  {row['Product Name*']} ({row['Product Type*']}): {actual} - {status}")
        
        print()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_classic_types_lineage_default() 