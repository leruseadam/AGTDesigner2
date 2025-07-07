#!/usr/bin/env python3
"""
Fix for API endpoints - Load default data on startup
"""

import sys
import os

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print("=== Fixing API Endpoints ===")

try:
    # Import and get the excel processor
    from app import get_excel_processor
    from src.core.data.excel_processor import get_default_upload_file
    
    print("Loading default data...")
    
    # Get the excel processor
    excel_processor = get_excel_processor()
    
    # Try to get default file
    default_file = get_default_upload_file()
    print(f"Default file: {default_file}")
    
    if default_file and os.path.exists(default_file):
        print(f"Loading default file: {default_file}")
        excel_processor.load_file(default_file)
        
        if excel_processor.df is not None:
            print(f"✅ Data loaded successfully: {len(excel_processor.df)} records")
            
            # Test the API endpoints
            print("\nTesting API endpoints...")
            
            try:
                available_tags = excel_processor.get_available_tags()
                print(f"✅ Available tags: {len(available_tags)} items")
            except Exception as e:
                print(f"❌ Error getting available tags: {e}")
                
            try:
                selected_tags = excel_processor.get_selected_tags()
                print(f"✅ Selected tags: {len(selected_tags)} items")
            except Exception as e:
                print(f"❌ Error getting selected tags: {e}")
                
        else:
            print("❌ Failed to load data from default file")
    else:
        print("❌ No default file found or file doesn't exist")
        
        # Try to find any Excel files
        print("\nLooking for Excel files...")
        excel_files = []
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith(('.xlsx', '.xls', '.csv')):
                    excel_files.append(os.path.join(root, file))
                    
        if excel_files:
            print(f"Found Excel files: {excel_files}")
            try:
                excel_processor.load_file(excel_files[0])
                if excel_processor.df is not None:
                    print(f"✅ Loaded {excel_files[0]}: {len(excel_processor.df)} records")
                else:
                    print(f"❌ Failed to load {excel_files[0]}")
            except Exception as e:
                print(f"❌ Error loading {excel_files[0]}: {e}")
        else:
            print("❌ No Excel files found in project")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Fix Complete ===")
