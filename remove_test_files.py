#!/usr/bin/env python3
"""
Script to remove all test inventory files from the uploads directory.
Run this on your PythonAnywhere server to clean up test files.
"""

import os
import glob
import shutil

def remove_test_files():
    """Remove all test inventory files from uploads directory."""
    
    # Get the uploads directory path
    uploads_dir = os.path.expanduser("~/uploads")
    
    print(f"Looking for test files in: {uploads_dir}")
    
    if not os.path.exists(uploads_dir):
        print(f"Uploads directory does not exist: {uploads_dir}")
        return
    
    # List all files in uploads directory
    all_files = os.listdir(uploads_dir)
    print(f"Found {len(all_files)} files in uploads directory:")
    
    for filename in all_files:
        print(f"  - {filename}")
    
    # Files to remove (test files)
    test_patterns = [
        "*Test Inventory*",
        "*test inventory*", 
        "*default_inventory*",
        "*test*inventory*",
        "*sample*inventory*"
    ]
    
    removed_files = []
    
    for pattern in test_patterns:
        matches = glob.glob(os.path.join(uploads_dir, pattern))
        for file_path in matches:
            try:
                os.remove(file_path)
                removed_files.append(os.path.basename(file_path))
                print(f"✅ Removed: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"❌ Failed to remove {file_path}: {e}")
    
    # Also check for specific known test files
    specific_test_files = [
        "A Greener Today - Test Inventory.xlsx",
        "default_inventory.xlsx",
        "test_inventory.xlsx",
        "sample_inventory.xlsx"
    ]
    
    for filename in specific_test_files:
        file_path = os.path.join(uploads_dir, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                removed_files.append(filename)
                print(f"✅ Removed: {filename}")
            except Exception as e:
                print(f"❌ Failed to remove {filename}: {e}")
    
    if removed_files:
        print(f"\n🎉 Successfully removed {len(removed_files)} test files:")
        for filename in removed_files:
            print(f"  - {filename}")
    else:
        print("\n✅ No test files found to remove")
    
    # Show remaining files
    remaining_files = os.listdir(uploads_dir)
    print(f"\n📁 Remaining files in uploads directory ({len(remaining_files)}):")
    for filename in remaining_files:
        print(f"  - {filename}")

if __name__ == "__main__":
    print("🧹 Test File Cleanup Script")
    print("=" * 40)
    remove_test_files()
    print("\n✨ Cleanup complete!") 