#!/usr/bin/env python3
"""
Test script to reproduce the double template width issue.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_double_template_generation():
    """Test double template generation to see the width issue."""
    try:
        from src.core.generation.template_processor import TemplateProcessor
        
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
            },
            {
                'Product Name*': 'Test Product 2',
                'Description': 'Test Description 2',
                'WeightUnits': '2g',
                'Price': '$20.00',
                'Lineage': 'Indica',
                'ProductType': 'flower',
                'ProductBrand': 'Test Brand'
            }
        ]
        
        # Create a template processor for double template
        font_scheme = {'Description': {'min': 10, 'max': 28, 'weight': 1}}
        processor = TemplateProcessor('double', font_scheme)
        
        print("Processing records with double template...")
        result_doc = processor.process_records(records)
        
        if result_doc and result_doc.tables:
            table = result_doc.tables[0]
            print(f"Table has {len(table.columns)} columns")
            
            # Check the actual column widths
            for i, column in enumerate(table.columns):
                width = column.width
                if hasattr(width, 'inches'):
                    print(f"Column {i+1} width: {width.inches} inches")
                else:
                    print(f"Column {i+1} width: {width}")
            
            # Check cell widths
            for i, row in enumerate(table.rows):
                for j, cell in enumerate(row.cells):
                    width = cell.width
                    if hasattr(width, 'inches'):
                        print(f"Cell ({i+1},{j+1}) width: {width.inches} inches")
                    else:
                        print(f"Cell ({i+1},{j+1}) width: {width}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to test double template generation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    print("Testing Double Template Width Issue...")
    print("=" * 50)
    
    test_double_template_generation()
    
    print("=" * 50)
    print("Test completed.")

if __name__ == "__main__":
    main() 