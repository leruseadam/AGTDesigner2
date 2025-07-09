#!/usr/bin/env python3
"""
Test script to fix mini template processing issue.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.generation.template_processor import TemplateProcessor
from docx import Document

def test_mini_template_fix():
    """Test and fix the mini template processing issue."""
    
    print("Testing Mini Template Fix")
    print("=" * 50)
    
    # Test data
    test_record = {
        'ProductBrand': 'Test Brand',
        'Price': '$25.99',
        'Lineage': 'MIXED',
        'Ratio_or_THC_CBD': 'THC: 25% CBD: 2%',
        'Description': 'Test description text',
        'ProductStrain': 'Mixed',
        'ProductType': 'tincture'
    }
    
    try:
        # Create processor
        processor = TemplateProcessor('mini', {}, 1.0)
        
        # Process the record
        result_doc = processor.process_records([test_record])
        
        if result_doc and result_doc.tables:
            table = result_doc.tables[0]
            print(f"Table dimensions: {len(table.rows)}x{len(table.columns)}")
            
            # Check the first cell
            cell = table.cell(0, 0)
            print(f"First cell text: '{cell.text}'")
            
            # Check if markers are still present
            if 'LINEAGE_START' in cell.text or 'PRODUCTBRAND_CENTER_START' in cell.text:
                print("❌ Markers are still present - processing failed")
                return False
            else:
                print("✅ Markers processed successfully")
                return True
        else:
            print("❌ No result document or tables")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mini_template_fix()
    if success:
        print("\n✅ Mini template processing is working correctly!")
    else:
        print("\n❌ Mini template processing needs fixing!") 