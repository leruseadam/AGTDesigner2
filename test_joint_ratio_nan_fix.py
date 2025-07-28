#!/usr/bin/env python3
"""
Comprehensive test to check for NaN values in JointRatio and fix the issue.
"""

import pandas as pd
import tempfile
import os
import sys
import numpy as np

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.data.excel_processor import ExcelProcessor

def create_test_excel_with_nan_joint_ratio():
    """Create a test Excel file with potential NaN JointRatio values."""
    print("Creating test Excel file with potential NaN JointRatio values...")
    
    # Sample data with various JointRatio scenarios
    data = {
        'Product Name*': [
            'Test Pre-Roll 1',
            'Test Pre-Roll 2', 
            'Test Pre-Roll 3',
            'Test Pre-Roll 4',
            'Test Flower 1',
            'Test Concentrate 1'
        ],
        'Product Type*': [
            'pre-roll',
            'infused pre-roll',
            'pre-roll',
            'infused pre-roll',
            'flower',
            'concentrate'
        ],
        'Description': [
            'Test Pre-Roll Description 1',
            'Test Pre-Roll Description 2',
            'Test Pre-Roll Description 3',
            'Test Pre-Roll Description 4',
            'Test Flower Description',
            'Test Concentrate Description'
        ],
        'Joint Ratio': [
            '1g x 2 Pack',
            '0.5g x 3 Pack',
            np.nan,  # Explicit NaN
            '',      # Empty string
            '',      # Empty for non-pre-roll
            ''       # Empty for non-pre-roll
        ],
        'Ratio': [
            '1g x 2 Pack',
            '0.5g x 3 Pack',
            '1g x 1 Pack',
            '0.5g x 2 Pack',
            'THC: 25% CBD: 2%',
            'THC: 80%'
        ],
        'Lineage': ['HYBRID', 'SATIVA', 'INDICA', 'HYBRID', 'INDICA', 'HYBRID'],
        'Product Brand': ['Brand A', 'Brand B', 'Brand C', 'Brand D', 'Brand E', 'Brand F'],
        'Vendor/Supplier*': ['Vendor 1', 'Vendor 2', 'Vendor 3', 'Vendor 4', 'Vendor 5', 'Vendor 6'],
        'Weight*': ['2', '1.5', '1', '1', '3.5', '1'],
        'Weight Unit* (grams/gm or ounces/oz)': ['g', 'g', 'g', 'g', 'g', 'g'],
        'Price* (Tier Name for Bulk)': ['$15', '$12', '$10', '$8', '$45', '$60'],
        'DOH Compliant (Yes/No)': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes'],
        'Product Strain': ['Strain A', 'Strain B', 'Strain C', 'Strain D', 'Strain E', 'Strain F']
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        return tmp.name

def test_joint_ratio_nan_handling():
    """Test JointRatio NaN handling comprehensively."""
    print("\n=== Testing JointRatio NaN Handling ===")
    
    # Create test file
    test_file = create_test_excel_with_nan_joint_ratio()
    
    processor = ExcelProcessor()
    success = processor.load_file(test_file)
    
    if success:
        print("✓ File loaded successfully")
        print(f"Columns: {processor.df.columns.tolist()}")
        
        # Check JointRatio column
        if 'JointRatio' in processor.df.columns:
            print("✓ JointRatio column exists")
            
            # Get all JointRatio values
            joint_ratio_values = processor.df['JointRatio'].tolist()
            print(f"JointRatio values: {joint_ratio_values}")
            
            # Check for NaN values
            nan_count = processor.df['JointRatio'].isna().sum()
            print(f"NaN values in JointRatio: {nan_count}")
            
            # Check for empty strings
            empty_count = (processor.df['JointRatio'] == '').sum()
            print(f"Empty strings in JointRatio: {empty_count}")
            
            # Check for None values
            none_count = (processor.df['JointRatio'].isnull()).sum()
            print(f"None/null values in JointRatio: {none_count}")
            
            # Detailed analysis of each value
            print("\nDetailed JointRatio analysis:")
            for i, value in enumerate(joint_ratio_values):
                print(f"  Row {i}: '{value}' (type: {type(value)}, isna: {pd.isna(value)}, isempty: {value == ''})")
            
            # Test get_selected_records to see if NaN persists
            print("\nTesting get_selected_records...")
            try:
                # Get all records
                all_records = processor.get_selected_records()
                print(f"✓ get_selected_records returned {len(all_records)} records")
                
                # Check JointRatio in processed records
                for i, record in enumerate(all_records):
                    joint_ratio = record.get('JointRatio', '')
                    print(f"  Processed record {i}: JointRatio = '{joint_ratio}' (type: {type(joint_ratio)})")
                    
                    # Check if it's NaN or problematic
                    if pd.isna(joint_ratio) or joint_ratio == 'nan' or joint_ratio == 'NaN':
                        print(f"    ✗ PROBLEM: JointRatio is NaN or 'nan' in processed record {i}")
                    else:
                        print(f"    ✓ JointRatio is valid in processed record {i}")
                        
            except Exception as e:
                print(f"✗ Error in get_selected_records: {e}")
                
        else:
            print("✗ JointRatio column missing")
    else:
        print("✗ Failed to load file")
    
    # Clean up
    os.unlink(test_file)

def test_joint_ratio_fix():
    """Test the fix for JointRatio NaN values."""
    print("\n=== Testing JointRatio Fix ===")
    
    # Create test file
    test_file = create_test_excel_with_nan_joint_ratio()
    
    processor = ExcelProcessor()
    success = processor.load_file(test_file)
    
    if success:
        print("✓ File loaded successfully")
        
        # Apply the fix: ensure JointRatio is never NaN
        if 'JointRatio' in processor.df.columns:
            # Replace NaN values with empty string
            processor.df['JointRatio'] = processor.df['JointRatio'].fillna('')
            
            # Check if fix worked
            nan_count = processor.df['JointRatio'].isna().sum()
            print(f"NaN values after fix: {nan_count}")
            
            if nan_count == 0:
                print("✓ Fix successful: No NaN values in JointRatio")
            else:
                print("✗ Fix failed: Still have NaN values")
                
            # Test get_selected_records again
            try:
                all_records = processor.get_selected_records()
                print(f"✓ get_selected_records returned {len(all_records)} records after fix")
                
                # Check JointRatio in processed records
                for i, record in enumerate(all_records):
                    joint_ratio = record.get('JointRatio', '')
                    if pd.isna(joint_ratio) or joint_ratio == 'nan' or joint_ratio == 'NaN':
                        print(f"    ✗ PROBLEM: JointRatio still NaN in processed record {i}")
                    else:
                        print(f"    ✓ JointRatio is valid in processed record {i}")
                        
            except Exception as e:
                print(f"✗ Error in get_selected_records after fix: {e}")
    
    # Clean up
    os.unlink(test_file)

if __name__ == "__main__":
    test_joint_ratio_nan_handling()
    test_joint_ratio_fix() 