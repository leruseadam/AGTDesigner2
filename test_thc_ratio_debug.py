#!/usr/bin/env python3
"""
Debug script to test THC_CBD and RATIO marker processing.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.generation.font_sizing import get_thresholded_font_size_ratio
from src.core.generation.template_processor import TemplateProcessor
from src.core.formatting.markers import wrap_with_marker, unwrap_marker
from docx import Document
from docx.shared import Pt

def test_thc_cbd_processing():
    """Test THC_CBD marker processing step by step."""
    
    print("Testing THC_CBD and RATIO marker processing")
    print("=" * 50)
    
    # Test data
    test_cases = [
        {
            'name': 'THC/CBD Standard',
            'content': 'THC:\nCBD:',
            'marker': 'THC_CBD'
        },
        {
            'name': 'THC/CBD with values',
            'content': 'THC: 25%\nCBD: 2%',
            'marker': 'THC_CBD'
        },
        {
            'name': 'Ratio format',
            'content': '1:1:1',
            'marker': 'RATIO'
        },
        {
            'name': 'mg values',
            'content': '100mg THC',
            'marker': 'RATIO'
        }
    ]
    
    # Test original font sizer for different template types
    print("\n1. Testing Original Font Sizer:")
    
    template_types = ['vertical', 'horizontal', 'mini']
    for template_type in template_types:
        print(f"\n  {template_type.upper()} template:")
        for case in test_cases:
            font_size = get_thresholded_font_size_ratio(case['content'], template_type, 1.0)
            print(f"    {case['name']}: {font_size.pt}pt")
    
    # Test marker wrapping/unwrapping
    print("\n2. Testing Marker Wrapping/Unwrapping:")
    for case in test_cases:
        wrapped = wrap_with_marker(case['content'], case['marker'])
        unwrapped = unwrap_marker(wrapped, case['marker'])
        print(f"  {case['name']}:")
        print(f"    Original: '{case['content']}'")
        print(f"    Wrapped: '{wrapped}'")
        print(f"    Unwrapped: '{unwrapped}'")
    
    # Test template processor
    print("\n3. Testing Template Processor:")
    processor = TemplateProcessor('vertical', {}, 1.0)
    
    # Create a test document
    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    
    for case in test_cases:
        print(f"\n  Testing {case['name']}:")
        
        # Add wrapped content to paragraph
        wrapped_content = wrap_with_marker(case['content'], case['marker'])
        paragraph = cell.paragraphs[0]
        paragraph.clear()
        paragraph.add_run(wrapped_content)
        
        print(f"    Before processing: '{paragraph.text}'")
        
        # Process the marker using the new template-specific method
        processor._process_paragraph_for_marker_template_specific(paragraph, case['marker'])
        
        print(f"    After processing: '{paragraph.text}'")
        
        # Check font size
        if paragraph.runs:
            font_size = paragraph.runs[0].font.size
            print(f"    Font size: {font_size.pt if font_size else 'None'}pt")
        else:
            print(f"    No runs found")

def test_marker_extraction():
    """Test marker extraction logic."""
    
    print("\n4. Testing Marker Extraction Logic:")
    
    test_texts = [
        "THC_CBD_STARTTHC:\nCBD:THC_CBD_END",
        "RATIO_START1:1:1RATIO_END",
        "THC_CBD_START100mg THCTHC_CBD_END",
        "THC_CBD_STARTTHC: 25%\nCBD: 2%THC_CBD_END"
    ]
    
    for text in test_texts:
        print(f"\n  Testing text: '{text}'")
        
        # Test THC_CBD extraction
        if 'THC_CBD_START' in text and 'THC_CBD_END' in text:
            start_idx = text.find('THC_CBD_START') + len('THC_CBD_START')
            end_idx = text.find('THC_CBD_END')
            content = text[start_idx:end_idx].strip()
            print(f"    THC_CBD content: '{content}'")
        
        # Test RATIO extraction
        if 'RATIO_START' in text and 'RATIO_END' in text:
            start_idx = text.find('RATIO_START') + len('RATIO_START')
            end_idx = text.find('RATIO_END')
            content = text[start_idx:end_idx].strip()
            print(f"    RATIO content: '{content}'")

if __name__ == "__main__":
    test_thc_cbd_processing()
    test_marker_extraction() 