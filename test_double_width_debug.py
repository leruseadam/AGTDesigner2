#!/usr/bin/env python3
"""
Test script to debug the double template width issue.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_double_template_processor():
    """Test that TemplateProcessor correctly handles double template type."""
    try:
        from src.core.generation.template_processor import TemplateProcessor
        
        # Create a template processor for double template with required font_scheme
        font_scheme = {'Description': {'min': 10, 'max': 28, 'weight': 1}}
        
        print("Testing TemplateProcessor with template_type='double'...")
        processor = TemplateProcessor('double', font_scheme)
        
        print(f"TemplateProcessor created successfully")
        print(f"Template type: {processor.template_type}")
        print(f"Template type type: {type(processor.template_type)}")
        print(f"Template type == 'double': {processor.template_type == 'double'}")
        print(f"Template type == 'vertical': {processor.template_type == 'vertical'}")
        
        # Test the width calculation logic
        if processor.template_type == 'double':
            total_table_width = 6.8
            col_width = 1.75
            print(f"Double template - total_table_width: {total_table_width}, col_width: {col_width}")
        elif processor.template_type == 'vertical':
            total_table_width = 6.75
            col_width = total_table_width / 3
            print(f"Vertical template - total_table_width: {total_table_width}, col_width: {col_width}")
        else:
            print(f"Unexpected template type: '{processor.template_type}'")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to test TemplateProcessor: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_template_type_comparison():
    """Test string comparison with template types."""
    print("\nTesting string comparisons...")
    
    test_cases = [
        ('double', 'double'),
        ('double', 'vertical'),
        ('vertical', 'double'),
        ('DOUBLE', 'double'),
        ('Double', 'double'),
        (' double ', 'double'),
    ]
    
    for case1, case2 in test_cases:
        result = case1 == case2
        print(f"'{case1}' == '{case2}': {result}")

def main():
    """Run the debug tests."""
    print("Debugging Double Template Width Issue...")
    print("=" * 50)
    
    test_template_type_comparison()
    test_double_template_processor()
    
    print("=" * 50)
    print("Debug tests completed.")

if __name__ == "__main__":
    main() 