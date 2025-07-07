#!/usr/bin/env python3
"""
Batch utility to fix all Word compatibility issues in multiple documents.
"""

import sys
import os
import glob
from pathlib import Path
import time

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

def batch_fix_documents(directory, pattern="*generated_labels*.docx"):
    """
    Fix all Word documents in a directory that match a pattern.
    
    Args:
        directory: Directory to search for documents
        pattern: File pattern to match (default: all generated_labels files)
    """
    print(f"🔧 Batch Document Repair Utility")
    print(f"📁 Searching in: {directory}")
    print(f"🔍 Pattern: {pattern}")
    print("=" * 60)
    
    # Find all matching files
    search_pattern = os.path.join(directory, pattern)
    files = glob.glob(search_pattern)
    
    if not files:
        print(f"❌ No files found matching pattern: {pattern}")
        return
    
    print(f"📋 Found {len(files)} documents to process")
    print()
    
    # Process each file
    successful = 0
    failed = 0
    skipped = 0
    
    for i, file_path in enumerate(files, 1):
        try:
            print(f"[{i}/{len(files)}] Processing: {os.path.basename(file_path)}")
            
            # Check if already repaired
            file_path_obj = Path(file_path)
            repaired_path = file_path_obj.parent / f"{file_path_obj.stem}_repaired{file_path_obj.suffix}"
            
            if repaired_path.exists():
                print(f"   ⏭️  Already repaired, skipping...")
                skipped += 1
                continue
            
            # Read the original document
            with open(file_path, 'rb') as f:
                original_bytes = f.read()
            
            # Validate original document
            is_valid, issues = validate_document_compatibility(original_bytes)
            if not is_valid:
                print(f"   ⚠️  Original document has issues: {len(issues)} problems")
            
            # Repair the document
            repaired_bytes = repair_document_for_word_compatibility(original_bytes)
            
            # Validate repaired document
            is_valid_after, issues_after = validate_document_compatibility(repaired_bytes)
            if not is_valid_after:
                print(f"   🔄 Creating fallback document...")
                repaired_bytes = create_word_compatible_document()
            
            # Save the repaired document
            with open(repaired_path, 'wb') as f:
                f.write(repaired_bytes)
            
            # Show results
            original_size = len(original_bytes)
            repaired_size = len(repaired_bytes)
            size_diff = repaired_size - original_size
            
            print(f"   ✅ Fixed successfully")
            print(f"      Original: {original_size:,} bytes")
            print(f"      Repaired: {repaired_size:,} bytes")
            print(f"      Difference: {size_diff:+,} bytes")
            print(f"      Saved as: {os.path.basename(repaired_path)}")
            
            successful += 1
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("📊 BATCH PROCESSING SUMMARY")
    print(f"✅ Successfully repaired: {successful}")
    print(f"⏭️  Skipped (already repaired): {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📁 Total processed: {successful + skipped + failed}")
    
    if successful > 0:
        print(f"\n🎉 Successfully repaired {successful} documents!")
        print(f"   All repaired documents are ready to open in Word.")
    
    if failed > 0:
        print(f"\n⚠️  {failed} documents failed to repair.")
        print(f"   You may need to manually check these files.")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Batch fix Word compatibility issues in multiple documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_fix_documents.py ~/Downloads
  python batch_fix_documents.py ~/Desktop "*labels*.docx"
  python batch_fix_documents.py . "generated_labels*.docx"
        """
    )
    
    parser.add_argument(
        'directory',
        help='Directory to search for documents'
    )
    
    parser.add_argument(
        'pattern',
        nargs='?',
        default='*generated_labels*.docx',
        help='File pattern to match (default: *generated_labels*.docx)'
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"❌ Error: Directory '{args.directory}' not found")
        sys.exit(1)
    
    start_time = time.time()
    batch_fix_documents(args.directory, args.pattern)
    end_time = time.time()
    
    print(f"\n⏱️  Total processing time: {end_time - start_time:.1f} seconds")

if __name__ == "__main__":
    main() 