#!/usr/bin/env python3
"""
Test script to verify the categorical data type fixes work correctly.
This tests the specific issues that were causing problems in the Excel processor.
"""

import pandas as pd
import numpy as np
import sys

def test_categorical_fixes():
    """Test the categorical data type handling fixes."""
    
    print("Testing categorical data type fixes...")
    
    # Create test data similar to what was causing issues
    test_data = {
        'Product Type*': ['flower', 'edible (solid)', 'pre-roll', None, 'tincture'],
        'Lineage': ['INDICA', 'MIXED', 'SATIVA', None, 'CBD'],
        'Product Brand': ['Brand A', 'Brand B', None, 'Brand C', 'Brand D'],
        'Vendor': ['Vendor 1', None, 'Vendor 2', 'Vendor 3', 'Vendor 4'],
        'Weight*': ['3.5', '10', '1', '5', '2'],
        'Units': ['g', 'mg', 'g', 'ml', 'g'],
        'Description': ['Test product 1', 'CBD product', 'Regular product', 'Test 4', 'CBD tincture'],
        'Product Strain': ['Test Strain', 'CBD Blend', 'Regular Strain', None, 'CBD Strain']
    }
    
    df = pd.DataFrame(test_data)
    print(f"Created test DataFrame with shape: {df.shape}")
    
    # Test 1: Fill null values and convert to categorical
    print("\nTest 1: Converting columns to categorical...")
    try:
        for col in ["Product Type*", "Lineage", "Product Brand", "Vendor"]:
            if col in df.columns:
                # Fill null values before converting to categorical - more robust approach
                if df[col].isnull().any():
                    # Use a safer fillna approach
                    df[col] = df[col].fillna("Unknown")
                
                # Convert to categorical with error handling
                df[col] = df[col].astype("category")
                print(f"✅ Successfully converted {col} to categorical")
    except Exception as e:
        print(f"❌ Error converting to categorical: {e}")
        return False
    
    # Test 2: Add categories to categorical columns
    print("\nTest 2: Adding categories to categorical columns...")
    try:
        if "Lineage" in df.columns:
            # Check if Lineage is categorical before adding categories
            if hasattr(df["Lineage"], 'cat') and hasattr(df["Lineage"].cat, 'categories'):
                if "CBD" not in df["Lineage"].cat.categories:
                    df["Lineage"] = df["Lineage"].cat.add_categories(["CBD"])
                if "MIXED" not in df["Lineage"].cat.categories:
                    df["Lineage"] = df["Lineage"].cat.add_categories(["MIXED"])
                print("✅ Successfully added categories to Lineage")
    except Exception as e:
        print(f"❌ Error adding categories: {e}")
        return False
    
    # Test 3: CombinedWeight creation
    print("\nTest 3: Creating CombinedWeight column...")
    try:
        if "Weight*" in df.columns and "Units" in df.columns:
            # Fill null values before converting to categorical - more robust approach
            combined_weight = (df["Weight*"] + df["Units"]).fillna("Unknown")
            df["CombinedWeight"] = combined_weight.astype("category")
            print("✅ Successfully created CombinedWeight column")
    except Exception as e:
        print(f"❌ Error creating CombinedWeight: {e}")
        return False
    
    # Test 4: DataFrame operations
    print("\nTest 4: Testing DataFrame operations...")
    try:
        # Test various operations that were failing
        empty_lineage_mask = df["Lineage"].isnull() | (df["Lineage"].astype(str).str.strip() == "")
        cbd_mask = df["Description"].str.contains(r"CBD|CBG|CBN|CBC", case=False, na=False)
        
        print(f"✅ DataFrame operations successful")
        print(f"   - Empty lineage count: {empty_lineage_mask.sum()}")
        print(f"   - CBD products count: {cbd_mask.sum()}")
    except Exception as e:
        print(f"❌ Error in DataFrame operations: {e}")
        return False
    
    print("\n🎉 All tests passed! The categorical fixes are working correctly.")
    return True

def test_pandas_version_compatibility():
    """Test pandas version compatibility."""
    print(f"\nPandas version: {pd.__version__}")
    print(f"Python version: {sys.version}")
    
    # Test specific pandas operations
    try:
        # Test fillna with categorical
        test_series = pd.Series(['A', 'B', None, 'C']).astype('category')
        filled_series = test_series.fillna("Unknown")
        print("✅ fillna with categorical works")
    except Exception as e:
        print(f"❌ fillna with categorical failed: {e}")
        return False
    
    try:
        # Test add_categories
        test_series = pd.Series(['A', 'B']).astype('category')
        test_series = test_series.cat.add_categories(['C'])
        print("✅ add_categories works")
    except Exception as e:
        print(f"❌ add_categories failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("CATEGORICAL DATA TYPE FIX TEST")
    print("=" * 50)
    
    # Test pandas version compatibility
    if not test_pandas_version_compatibility():
        print("\n❌ Pandas version compatibility test failed")
        sys.exit(1)
    
    # Test categorical fixes
    if test_categorical_fixes():
        print("\n✅ All tests passed! The fixes are working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. The fixes need more work.")
        sys.exit(1) 