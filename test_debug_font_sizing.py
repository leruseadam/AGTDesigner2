#!/usr/bin/env python3
"""
Debug test to understand font sizing logic.
"""

import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.core.generation.unified_font_sizing import get_font_size, calculate_text_complexity
from docx.shared import Pt

def debug_font_sizing():
    """Debug font sizing logic step by step."""
    
    print("Debugging font sizing logic...")
    print("=" * 50)
    
    test_cases = [
        'CONSTELLATION',
        'CONSTELLATION CANNABIS', 
        'CONSTELLATION ABC',
        'ABC DEF GHI'
    ]
    
    for text in test_cases:
        print(f"\nTesting: '{text}'")
        print("-" * 30)
        
        # Check complexity
        complexity = calculate_text_complexity(text, 'standard')
        print(f"Complexity: {complexity}")
        
        # Check word lengths
        words = text.split()
        word_lengths = [len(word) for word in words]
        print(f"Words: {words}")
        print(f"Word lengths: {word_lengths}")
        
        # Check for long words (10+ chars)
        long_words = [word for word in words if len(word) >= 10]
        print(f"Long words (10+ chars): {long_words}")
        print(f"Number of long words: {len(long_words)}")
        
        # Test brand font sizing for double template
        font_size = get_font_size(text, 'brand', 'double', 1.0)
        print(f"Brand font size (double): {font_size.pt}pt")
        
        # Test description font sizing for double template
        desc_font_size = get_font_size(text, 'description', 'double', 1.0)
        print(f"Description font size (double): {desc_font_size.pt}pt")
        
        # Check if our logic should trigger
        should_trigger_brand = len(long_words) >= 2
        should_trigger_desc = len([w for w in words if len(w) >= 9]) >= 2
        
        print(f"Should trigger brand rule (8pt): {should_trigger_brand}")
        print(f"Should trigger desc rule (18pt): {should_trigger_desc}")

if __name__ == "__main__":
    debug_font_sizing() 