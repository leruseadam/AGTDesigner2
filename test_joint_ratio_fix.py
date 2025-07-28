#!/usr/bin/env python3
"""
Test script to verify JointRatio creation and fix the NaN issue.
"""

import pandas as pd
import tempfile
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.data.excel_processor import ExcelProcessor

def create_test_excel_with_joint_ratio():
    """Create a test Excel file with Joint Ratio data."""
    print("Creating test Excel file with Joint Ratio data...")
    
    # Sample data with Joint Ratio column
    data = {
        'Product Name*': [
            'Test Pre-Roll 1',
            'Test Pre-Roll 2', 
            'Test Flower 1',
            'Test Concentrate 1'
        ],
        'Product Type*': [
            'pre-roll',
            'infused pre-roll',
            'flower',
            'concentrate'
        ],
        'Description': [
            'Test Pre-Roll Description 1',
            'Test Pre-Roll Description 2',
            'Test Flower Description',
            'Test Concentrate Description'
        ],
        'Joint Ratio': [
            '1g x 2 Pack',
            '0.5g x 3 Pack',
            '',  # Empty for non-pre-roll
            ''   # Empty for non-pre-roll
        ],
        'Ratio': [
            '1g x 2 Pack',
            '0.5g x 3 Pack',
            'THC: 25% CBD: 2%',
            'THC: 80%'
        ],
        'Lineage': ['HYBRID', 'SATIVA', 'INDICA', 'HYBRID'],
        'Product Brand': ['Brand A', 'Brand B', 'Brand C', 'Brand D'],
        'Vendor/Supplier*': ['Vendor 1', 'Vendor 2', 'Vendor 3', 'Vendor 4'],
        'Weight*': ['2', '1.5', '3.5', '1'],
        'Weight Unit* (grams/gm or ounces/oz)': ['g', 'g', 'g', 'g'],
        'Price* (Tier Name for Bulk)': ['$15', '$12', '$45', '$60'],
        'DOH Compliant (Yes/No)': ['Yes', 'Yes', 'Yes', 'Yes'],
        'Product Strain': ['Strain A', 'Strain B', 'Strain C', 'Strain D']
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        return tmp.name

def create_test_excel_without_joint_ratio():
    """Create a test Excel file without Joint Ratio column."""
    print("Creating test Excel file without Joint Ratio column...")
    
    # Sample data without Joint Ratio column
    data = {
        'Product Name*': [
            'Test Pre-Roll 1',
            'Test Pre-Roll 2', 
            'Test Flower 1',
            'Test Concentrate 1'
        ],
        'Product Type*': [
            'pre-roll',
            'infused pre-roll',
            'flower',
            'concentrate'
        ],
        'Description': [
            'Test Pre-Roll Description 1',
            'Test Pre-Roll Description 2',
            'Test Flower Description',
            'Test Concentrate Description'
        ],
        'Ratio': [
            '1g x 2 Pack',
            '0.5g x 3 Pack',
            'THC: 25% CBD: 2%',
            'THC: 80%'
        ],
        'Lineage': ['HYBRID', 'SATIVA', 'INDICA', 'HYBRID'],
        'Product Brand': ['Brand A', 'Brand B', 'Brand C', 'Brand D'],
        'Vendor/Supplier*': ['Vendor 1', 'Vendor 2', 'Vendor 3', 'Vendor 4'],
        'Weight*': ['2', '1.5', '3.5', '1'],
        'Weight Unit* (grams/gm or ounces/oz)': ['g', 'g', 'g', 'g'],
        'Price* (Tier Name for Bulk)': ['$15', '$12', '$45', '$60'],
        'DOH Compliant (Yes/No)': ['Yes', 'Yes', 'Yes', 'Yes'],
        'Product Strain': ['Strain A', 'Strain B', 'Strain C', 'Strain D']
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        return tmp.name

def test_joint_ratio_creation():
    """Test JointRatio creation with different scenarios."""
    print("\n=== Testing JointRatio Creation ===")
    
    # Test 1: With Joint Ratio column
    print("\n1. Testing with Joint Ratio column...")
    file_with_joint_ratio = create_test_excel_with_joint_ratio()
    
    processor = ExcelProcessor()
    success = processor.load_file(file_with_joint_ratio)
    
    if success:
        print("✓ File loaded successfully")
        print(f"Columns: {processor.df.columns.tolist()}")
        
        # Check JointRatio column
        if 'JointRatio' in processor.df.columns:
            print("✓ JointRatio column exists")
            joint_ratio_values = processor.df['JointRatio'].tolist()
            print(f"JointRatio values: {joint_ratio_values}")
            
            # Check for NaN values
            nan_count = processor.df['JointRatio'].isna().sum()
            print(f"NaN values in JointRatio: {nan_count}")
            
            if nan_count == 0:
                print("✓ No NaN values in JointRatio")
            else:
                print("✗ Found NaN values in JointRatio")
        else:
            print("✗ JointRatio column missing")
    else:
        print("✗ Failed to load file")
    
    # Clean up
    os.unlink(file_with_joint_ratio)
    
    # Test 2: Without Joint Ratio column
    print("\n2. Testing without Joint Ratio column...")
    file_without_joint_ratio = create_test_excel_without_joint_ratio()
    
    processor2 = ExcelProcessor()
    success2 = processor2.load_file(file_without_joint_ratio)
    
    if success2:
        print("✓ File loaded successfully")
        print(f"Columns: {processor2.df.columns.tolist()}")
        
        # Check JointRatio column
        if 'JointRatio' in processor2.df.columns:
            print("✓ JointRatio column exists")
            joint_ratio_values = processor2.df['JointRatio'].tolist()
            print(f"JointRatio values: {joint_ratio_values}")
            
            # Check for NaN values
            nan_count = processor2.df['JointRatio'].isna().sum()
            print(f"NaN values in JointRatio: {nan_count}")
            
            if nan_count == 0:
                print("✓ No NaN values in JointRatio")
            else:
                print("✗ Found NaN values in JointRatio")
        else:
            print("✗ JointRatio column missing")
    else:
        print("✗ Failed to load file")
    
    # Clean up
    os.unlink(file_without_joint_ratio)

if __name__ == "__main__":
    test_joint_ratio_creation() 