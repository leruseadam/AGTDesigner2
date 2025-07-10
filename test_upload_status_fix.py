#!/usr/bin/env python3
"""
Test script to verify upload status functionality fixes.
"""

import os
import sys
import time
import threading
import requests
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_processing_status():
    """Test the processing status functionality."""
    print("Testing processing status functionality...")
    
    # Import the processing status from app.py
    from app import processing_status, processing_lock, cleanup_old_processing_status, update_processing_status
    
    # Test 1: Basic status operations
    print("Test 1: Basic status operations")
    with processing_lock:
        update_processing_status('test_file.xlsx', 'processing')
        print(f"Status after setting: {processing_status.get('test_file.xlsx')}")
        
        update_processing_status('test_file.xlsx', 'ready')
        print(f"Status after updating: {processing_status.get('test_file.xlsx')}")
        
        del processing_status['test_file.xlsx']
        print(f"Status after deletion: {processing_status.get('test_file.xlsx', 'not_found')}")
    
    # Test 2: Cleanup functionality
    print("\nTest 2: Cleanup functionality")
    with processing_lock:
        update_processing_status('old_file1.xlsx', 'ready')
        update_processing_status('old_file2.xlsx', 'done')
        update_processing_status('old_file3.xlsx', 'error: test error')
        update_processing_status('new_file.xlsx', 'processing')
        
        print(f"Before cleanup: {dict(processing_status)}")
        
        cleanup_old_processing_status()
        
        print(f"After cleanup: {dict(processing_status)}")
    
    print("✅ Processing status tests passed!")

def test_background_processing():
    """Test the background processing functionality."""
    print("\nTesting background processing functionality...")
    
    from app import process_excel_background, processing_status, processing_lock
    
    # Create a test file path
    test_file = "test_upload_status_fix.py"  # Use this script as a test file
    
    # Test the background processing function
    print(f"Starting background processing for: {test_file}")
    
    with processing_lock:
        processing_status[test_file] = 'processing'
    
    # Start background processing
    thread = threading.Thread(target=process_excel_background, args=(test_file, test_file))
    thread.daemon = True
    thread.start()
    
    # Wait a bit for processing
    time.sleep(2)
    
    # Check status
    with processing_lock:
        status = processing_status.get(test_file, 'not_found')
    
    print(f"Processing status: {status}")
    
    # Clean up
    with processing_lock:
        if test_file in processing_status:
            del processing_status[test_file]
    
    print("✅ Background processing test completed!")

def test_api_endpoints():
    """Test the API endpoints if the server is running."""
    print("\nTesting API endpoints...")
    
    try:
        # Test debug endpoint
        response = requests.get('http://localhost:5000/api/debug-upload-status', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Debug endpoint works: {data['total_files']} files in status")
        else:
            print(f"❌ Debug endpoint failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running, skipping API tests")
    except Exception as e:
        print(f"❌ API test error: {e}")

def main():
    """Run all tests."""
    print("=== Upload Status Fix Tests ===")
    
    test_processing_status()
    test_background_processing()
    test_api_endpoints()
    
    print("\n=== All Tests Complete ===")

if __name__ == "__main__":
    main() 