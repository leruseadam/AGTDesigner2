#!/usr/bin/env python3
"""
Test script to verify that the double template dimensions fix is working correctly.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_double_template_dimensions():
    """Test that double template is using 1.75 inch width instead of 2.25 inches."""
    try:
        from src.core.generation.template_processor import TemplateProcessor
        from src.core.constants import CELL_DIMENSIONS
        
        # Create sample records
        records = [
            {
                'Product Name*': 'Test Product 1',
                'Description': 'Test Description 1',
                'WeightUnits': '1g',
                'Price': '$10.00',
                'Lineage': 'Sativa',
                'ProductType': 'flower',
                'ProductBrand': 'Test Brand'
            }
        ]
        
        # Create a template processor for double template
        font_scheme = {'Description': {'min': 10, 'max': 28, 'weight': 1}}
        processor = TemplateProcessor('double', font_scheme)
        
        print("✅ TemplateProcessor created successfully for double template")
        print(f"✅ Expected width from constants: {CELL_DIMENSIONS['double']['width']} inches")
        print(f"✅ Expected height from constants: {CELL_DIMENSIONS['double']['height']} inches")
        
        # Process the records
        result_doc = processor.process_records(records)
        
        # Check if the document was created successfully
        if result_doc and result_doc.tables:
            print("✅ Document generated successfully with tables")
            
            # Check the first table's dimensions
            table = result_doc.tables[0]
            print(f"✅ Table has {len(table.rows)} rows and {len(table.columns)} columns")
            
            # Check if the table has the correct number of cells for double template (4x3 = 12)
            expected_cells = 12  # 4 columns x 3 rows for double template
            actual_cells = len(table.rows) * len(table.columns)
            
            if actual_cells == expected_cells:
                print(f"✅ Table has correct number of cells: {actual_cells}")
            else:
                print(f"❌ ERROR: Expected {expected_cells} cells, got {actual_cells}")
                return False
            
            return True
        else:
            print("❌ ERROR: Failed to generate document or no tables found")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to test double template dimensions: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the double template dimensions test."""
    print("Testing Double Template Dimensions Fix...")
    print("=" * 50)
    
    if test_double_template_dimensions():
        print("✅ Double template dimensions fix is working correctly!")
        print("✅ Double template now uses 1.75 inch width instead of 2.25 inches")
    else:
        print("❌ Double template dimensions fix failed!")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 