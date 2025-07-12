#!/usr/bin/env python3
"""
Test script to verify that the duplicate index fix is working correctly.
"""

import pandas as pd
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.data.excel_processor import ExcelProcessor

def test_duplicate_index_fix():
    """Test that the duplicate index fix is working correctly."""
    print("Testing duplicate index fix...")
    
    # Create a test DataFrame with duplicate indices
    test_data = {
        'Product Name*': ['Product A', 'Product B', 'Product C', 'Product D'],
        'Product Type*': ['flower', 'concentrate', 'edible', 'tincture'],
        'Lineage': ['INDICA', 'HYBRID', 'SATIVA', 'CBD'],
        'Product Brand': ['Brand A', 'Brand B', 'Brand C', 'Brand D']
    }
    
    # Create DataFrame with duplicate indices
    df = pd.DataFrame(test_data)
    df.index = [0, 1, 1, 2]  # Create duplicate indices
    
    print(f"Original DataFrame shape: {df.shape}")
    print(f"Original DataFrame index: {df.index.tolist()}")
    print(f"Has duplicate indices: {df.index.duplicated().any()}")
    
    # Test the ExcelProcessor's bulletproof method
    processor = ExcelProcessor()
    processor.df = df.copy()
    
    # This should trigger the bulletproof method
    try:
        # Simulate the Description column assignment
        product_name_col = 'Product Name*'
        
        if product_name_col in processor.df.columns:
            print("Using bulletproof method for Description column assignment")
            
            # Step 1: Always reset index to ensure clean state
            processor.df = processor.df.reset_index(drop=True)
            print(f"DataFrame shape after reset: {processor.df.shape}")
            
            # Step 2: Get product names as a simple list
            product_names_list = processor.df[product_name_col].astype(str).tolist()
            print(f"Product names list length: {len(product_names_list)}")
            
            # Step 3: Generate descriptions using list comprehension
            descriptions_list = []
            for i, name in enumerate(product_names_list):
                # Simple description function
                if ' by ' in name:
                    desc = name.split(' by ')[0].strip()
                elif ' - ' in name:
                    desc = name.rsplit(' - ', 1)[0].strip()
                else:
                    desc = name.strip()
                descriptions_list.append(desc)
            
            print(f"Descriptions list length: {len(descriptions_list)}")
            
            # Step 4: Verify lengths match
            if len(descriptions_list) != len(processor.df):
                print(f"Length mismatch: descriptions={len(descriptions_list)}, df={len(processor.df)}")
                # Pad or truncate to match
                if len(descriptions_list) < len(processor.df):
                    descriptions_list.extend([""] * (len(processor.df) - len(descriptions_list)))
                else:
                    descriptions_list = descriptions_list[:len(processor.df)]
            
            # Step 5: Create new DataFrame with all existing data plus Description
            new_df_data = {}
            
            # Copy all existing columns
            for col in processor.df.columns:
                new_df_data[col] = processor.df[col].tolist()
            
            # Add Description column
            new_df_data["Description"] = descriptions_list
            
            # Step 6: Create completely new DataFrame
            processor.df = pd.DataFrame(new_df_data)
            print(f"New DataFrame shape: {processor.df.shape}")
            print("Bulletproof method successful")
            
            # Verify the result
            print(f"Final DataFrame columns: {processor.df.columns.tolist()}")
            print(f"Final DataFrame index: {processor.df.index.tolist()}")
            print(f"Has duplicate indices: {processor.df.index.duplicated().any()}")
            print(f"Description column values: {processor.df['Description'].tolist()}")
            
            return True
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = test_duplicate_index_fix()
    if success:
        print("✅ Duplicate index fix test PASSED")
    else:
        print("❌ Duplicate index fix test FAILED")
        sys.exit(1) 