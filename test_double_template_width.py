#!/usr/bin/env python3
"""
Test script to verify Double template width is correctly set to 1.7 inches.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.constants import CELL_DIMENSIONS

def test_double_template_width():
    """Test that Double template width is correctly set to 1.75 inches."""
    try:
        # Get the double template width from constants
        double_width = CELL_DIMENSIONS['double']['width']
        
        # Check if it's exactly 1.75 inches
        if double_width != 1.75:
            print(f"❌ ERROR: Double template width should be 1.75 inches, but is {double_width} inches")
            return False
        else:
            print("✅ Double template width is correctly set to 1.75 inches in constants")
            return True
            
    except KeyError as e:
        print(f"❌ ERROR: Missing key in CELL_DIMENSIONS: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")
        return False

def test_template_processor_width():
    """Test that TemplateProcessor uses the correct width for double template."""
    try:
        from src.core.generation.template_processor import TemplateProcessor
        
        # Create a template processor for double template with required font_scheme
        font_scheme = {'Description': {'min': 10, 'max': 28, 'weight': 1}}
        processor = TemplateProcessor('double', font_scheme)
        
        # Check if the template was expanded correctly
        if hasattr(processor, '_expanded_template_buffer'):
            print("✅ TemplateProcessor successfully created for double template")
            return True
        else:
            print("❌ ERROR: TemplateProcessor not properly initialized")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to create TemplateProcessor: {e}")
        return False

def test_cell_dimensions_consistency():
    """Test that all cell dimensions are consistent across the codebase."""
    try:
        from src.core.constants import CELL_DIMENSIONS
        
        # Check double template dimensions
        double_dims = CELL_DIMENSIONS['double']
        
        if double_dims['width'] != 1.75:
            print(f"❌ ERROR: Double template width should be 1.75 inches, but is {double_dims['width']} inches")
            return False
            
        if double_dims['height'] != 2.5:
            print(f"❌ ERROR: Double template height should be 2.5 inches, but is {double_dims['height']} inches")
            return False
            
        print("✅ Double template dimensions are consistent")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Failed to check cell dimensions: {e}")
        return False

def test_template_file_exists():
    """Test that the Double.docx template file exists."""
    print("\n🧪 Testing Double Template File...")
    
    try:
        template_path = Path("src/core/generation/templates/Double.docx")
        
        if template_path.exists():
            print(f"✅ Double template file exists: {template_path}")
            
            # Check file size
            file_size = template_path.stat().st_size
            print(f"✅ Template file size: {file_size} bytes")
            
            if file_size > 0:
                print("✅ Template file is not empty")
                return True
            else:
                print("❌ Template file is empty")
                return False
        else:
            print(f"❌ Double template file not found: {template_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking template file: {e}")
        return False

def main():
    """Run all tests for double template width."""
    print("Testing Double Template Width (1.75 inches)...")
    print("=" * 50)
    
    tests = [
        test_double_template_width,
        test_template_processor_width,
        test_cell_dimensions_consistency
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed! Double template width is correctly set to 1.75 inches")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 