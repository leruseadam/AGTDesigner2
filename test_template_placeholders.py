#!/usr/bin/env python3
"""
Test script to examine what placeholders are in the mini template.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from src.core.generation.template_processor import get_font_scheme, TemplateProcessor

def examine_mini_template():
    """Examine the mini template to see what placeholders it contains."""
    
    print("Examining Mini Template Placeholders")
    print("=" * 50)
    
    # Get the template path
    processor = TemplateProcessor('mini', get_font_scheme('mini'), 1.0)
    template_path = processor._get_template_path()
    
    print(f"Template path: {template_path}")
    
    try:
        # Load the template
        doc = Document(template_path)
        
        print(f"\nTemplate has {len(doc.tables)} tables")
        
        if doc.tables:
            table = doc.tables[0]
            print(f"First table: {len(table.rows)} rows x {len(table.columns)} columns")
            
            # Check the first cell for placeholders
            if table.rows and table.rows[0].cells:
                first_cell = table.rows[0].cells[0]
                cell_text = first_cell.text
                print(f"\nFirst cell text: {repr(cell_text)}")
                
                # Look for common placeholders
                placeholders = [
                    'RATIO_START', 'RATIO_END',
                    'WEIGHTUNITS_START', 'WEIGHTUNITS_END',
                    'DESC_START', 'DESC_END',
                    'PRICE_START', 'PRICE_END',
                    'LINEAGE_START', 'LINEAGE_END',
                    'PRODUCTBRAND_CENTER_START', 'PRODUCTBRAND_CENTER_END',
                    'Label1.', 'Label2.', 'Label3.'
                ]
                
                print(f"\nPlaceholders found:")
                for placeholder in placeholders:
                    if placeholder in cell_text:
                        print(f"  ✓ {placeholder}")
                    else:
                        print(f"  ✗ {placeholder}")
        
        # Check all paragraphs for placeholders
        print(f"\nAll paragraphs ({len(doc.paragraphs)}):")
        for i, para in enumerate(doc.paragraphs):
            if para.text.strip():
                print(f"  Paragraph {i}: {repr(para.text)}")
                
    except Exception as e:
        print(f"Error examining template: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    examine_mini_template() 