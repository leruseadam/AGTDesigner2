#!/usr/bin/env python3
"""
Test script to verify that long brand names get forced to 14pt font in horizontal templates.
"""

from src.core.generation.unified_font_sizing import get_font_size

def test_brand_font_size_horizontal():
    """Test that long brand names get forced to 14pt font in horizontal templates."""
    
    print("=== Brand Font Size Horizontal Test ===\n")
    
    # Test cases for horizontal template
    test_cases = [
        {
            'name': 'Fairwinds Manufacturing',
            'expected_size': 14,
            'reason': '22 characters > 20, should force 14pt'
        },
        {
            'name': 'Short Brand',
            'expected_size': 14,
            'reason': '11 characters, 2 words > 9 chars, should force 14pt'
        },
        {
            'name': 'Very Long Brand Name That Exceeds Limits',
            'expected_size': 14,
            'reason': '35 characters > 20, should force 14pt'
        },
        {
            'name': 'Short',
            'expected_size': 16,
            'reason': '5 characters < 15 complexity, should get 16pt'
        },
        {
            'name': 'Medium Brand Name',
            'expected_size': 14,
            'reason': '15 characters, complexity < 25, should get 14pt'
        }
    ]
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        brand_name = test_case['name']
        expected_size = test_case['expected_size']
        reason = test_case['reason']
        
        # Get font size using unified font sizing system
        font_size = get_font_size(brand_name, 'brand', 'horizontal', 1.0)
        actual_size = font_size.pt
        
        # Check if the result matches expected
        passed = abs(actual_size - expected_size) < 0.1  # Allow small floating point differences
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Brand: '{brand_name}'")
        print(f"  Expected: {expected_size}pt")
        print(f"  Actual: {actual_size}pt")
        print(f"  Reason: {reason}")
        print()
        
        if not passed:
            all_passed = False
    
    if all_passed:
        print("🎉 ALL TESTS PASSED! Long brand names are correctly forced to 14pt font in horizontal templates.")
    else:
        print("❌ SOME TESTS FAILED! The brand font size fix is not working correctly.")
    
    return all_passed

if __name__ == "__main__":
    test_brand_font_size_horizontal() 