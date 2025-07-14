#!/usr/bin/env python3
"""
Test script to verify lineage coloring for Mixed and CBD Blend products.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.generation.docx_formatting import apply_lineage_colors, COLORS
from src.core.generation.template_processor import TemplateProcessor
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

def test_lineage_coloring_extraction():
    """Test that lineage values are correctly extracted from embedded product type information."""
    
    print("Testing Lineage Color Extraction")
    print("=" * 50)
    
    # Test cases with embedded product type information
    test_cases = [
        {
            'name': 'Mixed Tincture',
            'text': 'MIXED_PRODUCT_TYPE_tincture_IS_CLASSIC_false',
            'expected_lineage': 'MIXED',
            'expected_color': COLORS['MIXED']
        },
        {
            'name': 'CBD Blend Tincture',
            'text': 'CBD_PRODUCT_TYPE_tincture_IS_CLASSIC_false',
            'expected_lineage': 'CBD',
            'expected_color': COLORS['CBD']
        },
        {
            'name': 'CBD_BLEND Tincture',
            'text': 'CBD_BLEND_PRODUCT_TYPE_tincture_IS_CLASSIC_false',
            'expected_lineage': 'CBD_BLEND',
            'expected_color': COLORS['CBD']
        },
        {
            'name': 'Simple Mixed',
            'text': 'MIXED',
            'expected_lineage': 'MIXED',
            'expected_color': COLORS['MIXED']
        },
        {
            'name': 'Simple CBD',
            'text': 'CBD',
            'expected_lineage': 'CBD',
            'expected_color': COLORS['CBD']
        },
        {
            'name': 'Simple CBD_BLEND',
            'text': 'CBD_BLEND',
            'expected_lineage': 'CBD_BLEND',
            'expected_color': COLORS['CBD']
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Input text: '{test_case['text']}'")
        
        # Simulate the extraction logic from apply_lineage_colors
        text = test_case['text'].upper()
        
        # Extract the actual lineage value from embedded product type information
        if "_PRODUCT_TYPE_" in text:
            # Extract the lineage part before "_PRODUCT_TYPE_"
            lineage_part = text.split("_PRODUCT_TYPE_")[0]
            text = lineage_part
        
        print(f"Extracted lineage: '{text}'")
        print(f"Expected lineage: '{test_case['expected_lineage']}'")
        
        # Test color assignment
        color_hex = None
        if "PARAPHERNALIA" in text:
            color_hex = COLORS['PARA']
        elif "HYBRID/INDICA" in text or "HYBRID INDICA" in text:
            color_hex = COLORS['HYBRID_INDICA']
        elif "HYBRID/SATIVA" in text or "HYBRID SATIVA" in text:
            color_hex = COLORS['HYBRID_SATIVA']
        elif "SATIVA" in text:
            color_hex = COLORS['SATIVA']
        elif "INDICA" in text:
            color_hex = COLORS['INDICA']
        elif "HYBRID" in text:
            color_hex = COLORS['HYBRID']
        elif "CBD" in text or "CBD_BLEND" in text:
            color_hex = COLORS['CBD']
        elif "MIXED" in text:
            color_hex = COLORS['MIXED']
        
        print(f"Assigned color: {color_hex}")
        print(f"Expected color: {test_case['expected_color']}")
        
        if text == test_case['expected_lineage'] and color_hex == test_case['expected_color']:
            print("✅ PASS")
        else:
            print("❌ FAIL")

def test_template_processor_lineage_coloring():
    """Test that the template processor correctly applies lineage coloring."""
    
    print("\n\nTesting Template Processor Lineage Coloring")
    print("=" * 50)
    
    # Test data for Mixed and CBD Blend products
    test_records = [
        {
            'ProductBrand': 'Test Brand',
            'Price': '$25.99',
            'Lineage': 'MIXED',  # This should get colored blue
            'Ratio_or_THC_CBD': 'THC: 25% CBD: 2%',
            'Description': 'Test description text',
            'ProductStrain': 'Mixed',
            'ProductType': 'tincture'
        },
        {
            'ProductBrand': 'Test Brand',
            'Price': '$25.99',
            'Lineage': 'CBD',  # This should get colored yellow
            'Ratio_or_THC_CBD': 'THC: 25% CBD: 2%',
            'Description': 'Test description text',
            'ProductStrain': 'CBD Blend',
            'ProductType': 'tincture'
        }
    ]
    
    template_types = ['vertical', 'horizontal', 'mini']
    
    for template_type in template_types:
        print(f"\n{template_type.upper()} TEMPLATE:")
        print("-" * 20)
        
        for i, record in enumerate(test_records):
            print(f"\n  Record {i+1}: {record['Lineage']} lineage")
            
            try:
                # Create template processor
                processor = TemplateProcessor(template_type, {}, 1.0)
                
                # Process a single record
                result_doc = processor.process_records([record])
                
                if result_doc and result_doc.tables:
                    table = result_doc.tables[0]
                    cell = table.cell(0, 0)
                    
                    # Check if the cell has background color
                    tc = cell._tc
                    tcPr = tc.get_or_add_tcPr()
                    shading = tcPr.find(qn('w:shd'))
                    
                    if shading is not None:
                        fill_color = shading.get(qn('w:fill'))
                        print(f"    Cell background color: {fill_color}")
                        
                        # Check if the color matches expected lineage color
                        expected_color = None
                        if record['Lineage'] == 'MIXED':
                            expected_color = COLORS['MIXED']
                        elif record['Lineage'] == 'CBD':
                            expected_color = COLORS['CBD']
                        
                        if fill_color == expected_color:
                            print(f"    ✅ Color matches expected: {expected_color}")
                        else:
                            print(f"    ❌ Color mismatch. Expected: {expected_color}, Got: {fill_color}")
                    else:
                        print(f"    ❌ No background color found")
                        
                else:
                    print(f"    ❌ Failed to generate document")
                    
            except Exception as e:
                print(f"    ❌ ERROR: {e}")

def test_lineage_color_constants():
    """Test that the lineage color constants are properly defined."""
    
    print("\n\nTesting Lineage Color Constants")
    print("=" * 50)
    
    expected_colors = {
        'SATIVA': 'ED4123',
        'INDICA': '9900FF', 
        'HYBRID': '009900',
        'HYBRID_INDICA': '9900FF',
        'HYBRID_SATIVA': 'ED4123',
        'CBD': 'F1C232',
        'MIXED': '0021F5',
        'PARA': 'FFC0CB'
    }
    
    for lineage, expected_color in expected_colors.items():
        if lineage in COLORS:
            actual_color = COLORS[lineage]
            if actual_color == expected_color:
                print(f"✅ {lineage}: {actual_color}")
            else:
                print(f"❌ {lineage}: Expected {expected_color}, Got {actual_color}")
        else:
            print(f"❌ {lineage}: Missing from COLORS")

if __name__ == "__main__":
    test_lineage_coloring_extraction()
    test_template_processor_lineage_coloring()
    test_lineage_color_constants() 