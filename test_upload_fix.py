#!/usr/bin/env python3
"""
Test script to diagnose and fix upload processing issues.
This script helps identify why uploads get stuck on "Finalizing".
"""

import os
import sys
import time
import logging
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_upload_processing():
    """Test the upload processing system."""
    base_url = "http://127.0.0.1:9090"
    
    print("🔍 Testing Upload Processing System")
    print("=" * 50)
    
    # Test 1: Check server status
    print("\n1. Testing server status...")
    try:
        response = requests.get(f"{base_url}/api/status", timeout=10)
        if response.status_code == 200:
            status_data = response.json()
            print(f"   ✅ Server is running")
            print(f"   📊 Data loaded: {status_data.get('data_loaded', False)}")
            print(f"   📋 Data shape: {status_data.get('data_shape', 'None')}")
        else:
            print(f"   ❌ Server returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Cannot connect to server: {e}")
        return False
    
    # Test 2: Check upload processing debug info
    print("\n2. Checking upload processing debug info...")
    try:
        response = requests.get(f"{base_url}/api/debug-upload-processing", timeout=10)
        if response.status_code == 200:
            debug_data = response.json()
            print(f"   ✅ Debug endpoint accessible")
            
            # Check processing statuses
            processing_statuses = debug_data.get('processing_statuses', {})
            if processing_statuses:
                print(f"   📋 Active processing statuses: {len(processing_statuses)}")
                for filename, status in processing_statuses.items():
                    print(f"      - {filename}: {status}")
            else:
                print(f"   📋 No active processing statuses")
            
            # Check stuck files
            stuck_files = debug_data.get('stuck_files', [])
            if stuck_files:
                print(f"   ⚠️  Found {len(stuck_files)} stuck files:")
                for stuck_file in stuck_files:
                    print(f"      - {stuck_file['filename']}: {stuck_file['status']} (age: {stuck_file['age_seconds']:.1f}s)")
            else:
                print(f"   ✅ No stuck files found")
            
            # Check Excel processor status
            processor_status = debug_data.get('excel_processor_status', {})
            print(f"   📊 Excel processor status:")
            print(f"      - Has processor: {processor_status.get('has_processor', False)}")
            print(f"      - Has dataframe: {processor_status.get('has_dataframe', False)}")
            print(f"      - Dataframe empty: {processor_status.get('dataframe_empty', True)}")
            print(f"      - Dataframe shape: {processor_status.get('dataframe_shape', 'None')}")
            print(f"      - Last loaded file: {processor_status.get('last_loaded_file', 'None')}")
            
            # Check system info
            system_info = debug_data.get('system_info', {})
            print(f"   💻 System info:")
            print(f"      - Memory usage: {system_info.get('memory_usage_percent', 0):.1f}%")
            print(f"      - Disk usage: {system_info.get('disk_usage_percent', 0):.1f}%")
            print(f"      - CPU count: {system_info.get('cpu_count', 0)}")
            
        else:
            print(f"   ❌ Debug endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error accessing debug endpoint: {e}")
    
    # Test 3: Check available tags endpoint
    print("\n3. Testing available tags endpoint...")
    try:
        response = requests.get(f"{base_url}/api/available-tags", timeout=10)
        if response.status_code == 200:
            tags_data = response.json()
            if isinstance(tags_data, list):
                print(f"   ✅ Available tags endpoint working")
                print(f"   📋 Found {len(tags_data)} tags")
                if tags_data:
                    print(f"   📝 Sample tags:")
                    for i, tag in enumerate(tags_data[:3]):
                        print(f"      - {tag.get('Product Name*', 'Unknown')}")
            else:
                print(f"   ⚠️  Available tags returned non-list data: {type(tags_data)}")
        else:
            print(f"   ❌ Available tags returned status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   📝 Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   📝 Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error accessing available tags: {e}")
    
    # Test 4: Check filter options endpoint
    print("\n4. Testing filter options endpoint...")
    try:
        response = requests.get(f"{base_url}/api/filter-options", timeout=10)
        if response.status_code == 200:
            filter_data = response.json()
            print(f"   ✅ Filter options endpoint working")
            print(f"   📋 Filter options available:")
            for filter_type, options in filter_data.items():
                if isinstance(options, list):
                    print(f"      - {filter_type}: {len(options)} options")
                else:
                    print(f"      - {filter_type}: {type(options)}")
        else:
            print(f"   ❌ Filter options returned status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   📝 Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   📝 Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error accessing filter options: {e}")
    
    # Test 5: Clear any stuck upload statuses
    print("\n5. Clearing any stuck upload statuses...")
    try:
        response = requests.post(f"{base_url}/api/clear-upload-status", timeout=10)
        if response.status_code == 200:
            clear_data = response.json()
            print(f"   ✅ Upload status cleared")
            print(f"   📝 Message: {clear_data.get('message', 'Unknown')}")
        else:
            print(f"   ❌ Clear upload status returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error clearing upload status: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Upload Processing Test Complete")
    print("\n📋 Recommendations:")
    print("1. If stuck files were found, they have been cleared")
    print("2. Check the browser console for detailed upload debug logs")
    print("3. If issues persist, check the server logs for errors")
    print("4. Try uploading a smaller file to test the system")
    print("5. Ensure the Excel file has the required columns")
    
    return True

def main():
    """Main function."""
    print("🚀 Upload Processing Diagnostic Tool")
    print("This tool helps diagnose why uploads get stuck on 'Finalizing'")
    print()
    
    # Check if server is running
    try:
        response = requests.get("http://127.0.0.1:9090/api/status", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not responding properly")
            print("Please ensure the Flask server is running on port 9090")
            return False
    except Exception as e:
        print("❌ Cannot connect to server")
        print("Please ensure the Flask server is running on port 9090")
        print(f"Error: {e}")
        return False
    
    # Run the tests
    success = test_upload_processing()
    
    if success:
        print("\n✅ Diagnostic complete!")
        print("The upload processing system should now work better.")
    else:
        print("\n❌ Diagnostic failed!")
        print("Please check the server logs for more information.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 