#!/usr/bin/env python3
"""
Debug script to test double template font sizing specifically.
"""

from src.core.generation.template_processor import TemplateProcessor
from src.core.generation.unified_font_sizing import get_font_size, get_font_size_by_marker
from docx import Document
import io

def test_double_template_font_sizing():
    """Test double template font sizing with specific test data."""
    print("=== DOUBLE TEMPLATE FONT SIZING DEBUG ===")
    
    # Test data that should trigger different font sizes
    test_record = {
        'ProductBrand': 'Test Brand Name',
        'Price': '$25.99',
        'Lineage': 'Hybrid',
        'Ratio_or_THC_CBD': '1:1 THC:CBD',
        'Description': 'Test description text',
        'ProductStrain': 'Test Strain',
        'ProductType': 'flower'  # Classic type
    }
    
    print("Test record:", test_record)
    print()
    
    # Test individual font sizing first
    print("Individual font sizing tests:")
    print("-" * 40)
    
    # Test brand font sizing
    brand_font = get_font_size_by_marker('Test Brand Name', 'PRODUCTBRAND', 'double', 1.0, 'flower')
    print(f"Brand 'Test Brand Name' -> {brand_font.pt}pt")
    
    # Test ratio font sizing
    ratio_font = get_font_size_by_marker('1:1 THC:CBD', 'RATIO', 'double', 1.0, 'flower')
    print(f"Ratio '1:1 THC:CBD' -> {ratio_font.pt}pt")
    
    # Test THC_CBD font sizing
    thc_cbd_font = get_font_size_by_marker('1:1 THC:CBD', 'THC_CBD', 'double', 1.0, 'flower')
    print(f"THC_CBD '1:1 THC:CBD' -> {thc_cbd_font.pt}pt")
    
    print()
    
    # Test template processing
    print("Template processing test:")
    print("-" * 40)
    
    try:
        # Create template processor
        processor = TemplateProcessor('double', {}, 1.0)
        
        # Process the record
        result_doc = processor.process_records([test_record])
        
        if result_doc and result_doc.tables:
            table = result_doc.tables[0]
            print(f"Document generated successfully")
            print(f"Table dimensions: {len(table.rows)}x{len(table.columns)}")
            
            # Check font sizes in all cells
            for row_idx, row in enumerate(table.rows):
                for col_idx, cell in enumerate(row.cells):
                    print(f"\nCell ({row_idx}, {col_idx}):")
                    for para_idx, paragraph in enumerate(cell.paragraphs):
                        if paragraph.text.strip():
                            print(f"  Paragraph {para_idx}: '{paragraph.text[:50]}...'")
                            for run_idx, run in enumerate(paragraph.runs):
                                if run.text.strip():
                                    font_size = run.font.size.pt if run.font.size else "No size"
                                    print(f"    Run {run_idx}: '{run.text[:30]}...' -> {font_size}pt")
        else:
            print("Failed to generate document")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_double_template_font_sizing() 