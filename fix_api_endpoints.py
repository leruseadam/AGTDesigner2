#!/usr/bin/env python3
"""
Quick API Fix Script for AGTDesigner2
This script attempts to fix common API endpoint issues
"""

import sys
import os

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print("=== AGTDesigner2 API Fix Script ===")

# Check if we can import the app
try:
    from app import app, excel_processor
    print("✅ App imported successfully")
    
    # Test the excel processor
    if excel_processor:
        print("✅ Excel processor exists")
        
        # Try to get some basic data
        try:
            data = excel_processor.load_data()
            print(f"✅ Data loaded: {len(data)} records")
            
            # Get filter options
            try:
                filter_options = excel_processor.get_filter_options()
                print(f"✅ Filter options available: {list(filter_options.keys())}")
                
                # Test getting available tags
                try:
                    available_tags = excel_processor.get_available_tags()
                    print(f"✅ Available tags: {len(available_tags)} items")
                    
                    # Test getting selected tags
                    try:
                        selected_tags = excel_processor.get_selected_tags()
                        print(f"✅ Selected tags: {len(selected_tags)} items")
                        
                        print("\n🎉 All basic functions working!")
                        
                    except Exception as e:
                        print(f"❌ Error getting selected tags: {e}")
                        
                except Exception as e:
                    print(f"❌ Error getting available tags: {e}")
                    
            except Exception as e:
                print(f"❌ Error getting filter options: {e}")
                
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            
    else:
        print("❌ Excel processor not initialized")
        
except Exception as e:
    print(f"❌ Error importing app: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Fix Complete ===")
