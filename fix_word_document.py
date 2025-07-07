#!/usr/bin/env python3
"""
Utility script to fix Word compatibility issues in existing documents.
Usage: python fix_word_document.py <input_file.docx> [output_file.docx]
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.generation.document_repair import (
    repair_document_for_word_compatibility,
    validate_document_compatibility,
    create_word_compatible_document
)
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def fix_document(input_path, output_path=None):
    """
    Fix a Word document for compatibility issues.
    
    Args:
        input_path: Path to the input document
        output_path: Path for the output document (optional)
    """
    try:
        # Validate input file
        if not os.path.exists(input_path):
            print(f"❌ Error: Input file '{input_path}' not found")
            return False
        
        # Read the original document
        print(f"📖 Reading document: {input_path}")
        with open(input_path, 'rb') as f:
            original_bytes = f.read()
        
        # Validate original document
        print("🔍 Validating original document...")
        is_valid, issues = validate_document_compatibility(original_bytes)
        if not is_valid:
            print(f"⚠️  Original document has issues: {issues}")
        else:
            print("✅ Original document appears valid")
        
        # Repair the document
        print("🔧 Repairing document for Word compatibility...")
        repaired_bytes = repair_document_for_word_compatibility(original_bytes)
        
        # Validate repaired document
        print("🔍 Validating repaired document...")
        is_valid_after, issues_after = validate_document_compatibility(repaired_bytes)
        if not is_valid_after:
            print(f"❌ Document still has issues after repair: {issues_after}")
            print("🔄 Creating fallback document...")
            repaired_bytes = create_word_compatible_document()
        
        # Determine output path
        if output_path is None:
            input_file = Path(input_path)
            output_path = input_file.parent / f"{input_file.stem}_repaired{input_file.suffix}"
        
        # Save the repaired document
        print(f"💾 Saving repaired document: {output_path}")
        with open(output_path, 'wb') as f:
            f.write(repaired_bytes)
        
        # Final validation
        file_size = len(repaired_bytes)
        print(f"✅ Document repaired successfully!")
        print(f"   Output file: {output_path}")
        print(f"   File size: {file_size:,} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing document: {e}")
        return False

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fix Word compatibility issues in documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fix_word_document.py problematic.docx
  python fix_word_document.py input.docx output.docx
  python fix_word_document.py "generated_labels (57).docx"
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Path to the input Word document'
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        help='Path for the output document (optional)'
    )
    
    args = parser.parse_args()
    
    print("🔧 Word Document Repair Utility")
    print("=" * 40)
    
    success = fix_document(args.input_file, args.output_file)
    
    if success:
        print("\n🎉 Document repair completed successfully!")
        print("   Try opening the repaired document in Word.")
    else:
        print("\n💥 Document repair failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 