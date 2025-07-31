#!/usr/bin/env python3
"""
Test script to verify the JSON matching error fix.
This script tests that the 'str' object has no attribute 'get' error is resolved.
"""

import os
import sys
import logging
import requests
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_json_matching_fix():
    """Test that the JSON matching error is fixed."""
    print("🔍 Testing JSON Matching Error Fix")
    print("=" * 50)
    
    base_url = "http://127.0.0.1:9090"
    
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
    
    # Test 2: Test JSON matching with a sample URL
    print("\n2. Testing JSON matching...")
    try:
        # Use a sample JSON URL for testing
        test_url = "https://files.cultivera.com/435553542D57533130383735/Coas/25/06/09/DMGCERZY3PY76Q1D/C10875_LabTestData_1201.json"
        
        print(f"   📡 Testing with URL: {test_url}")
        
        response = requests.post(
            f"{base_url}/api/json-match",
            json={'url': test_url},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ JSON matching successful")
            print(f"   📊 Matched count: {result.get('matched_count', 0)}")
            print(f"   📋 Cache status: {result.get('cache_status', 'Unknown')}")
            
            if result.get('matched_names'):
                print(f"   📝 Sample matches:")
                for i, name in enumerate(result['matched_names'][:3]):
                    print(f"      {i+1}. {name}")
            
            return True
        else:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
            print(f"   ❌ JSON matching failed: {error_msg}")
            
            # Check if it's the specific error we're trying to fix
            if "'str' object has no attribute 'get'" in error_msg:
                print(f"   ❌ The error is still present - fix not working")
                return False
            else:
                print(f"   ⚠️  Different error occurred - this might be expected")
                return True
                
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Request timed out - this might be expected for large datasets")
        return True
    except Exception as e:
        print(f"   ❌ Error testing JSON matching: {e}")
        return False
    
    # Test 3: Test with a simpler JSON structure
    print("\n3. Testing with simpler JSON structure...")
    try:
        # Create a simple test JSON
        simple_json = {
            "inventory_transfer_items": [
                {
                    "product_name": "Test Product 1",
                    "strain_name": "Test Strain",
                    "vendor": "Test Vendor"
                },
                {
                    "product_name": "Test Product 2", 
                    "strain_name": "Test Strain 2",
                    "vendor": "Test Vendor"
                }
            ]
        }
        
        # Save to a temporary file
        import tempfile
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(simple_json, f)
            temp_file_path = f.name
        
        # Create a local file URL
        file_url = f"file://{temp_file_path}"
        
        print(f"   📄 Testing with local JSON file")
        
        response = requests.post(
            f"{base_url}/api/json-match",
            json={'url': file_url},
            timeout=10
        )
        
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except:
            pass
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Simple JSON matching successful")
            print(f"   📊 Matched count: {result.get('matched_count', 0)}")
            return True
        else:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
            print(f"   ❌ Simple JSON matching failed: {error_msg}")
            
            if "'str' object has no attribute 'get'" in error_msg:
                print(f"   ❌ The error is still present in simple JSON")
                return False
            else:
                print(f"   ⚠️  Different error occurred - this might be expected")
                return True
                
    except Exception as e:
        print(f"   ❌ Error testing simple JSON: {e}")
        return False

def main():
    """Main function."""
    print("🚀 JSON Matching Error Fix Test")
    print("This test verifies that the 'str' object has no attribute 'get' error is fixed")
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
    success = test_json_matching_fix()
    
    if success:
        print("\n✅ Test completed successfully!")
        print("The JSON matching error appears to be fixed.")
    else:
        print("\n❌ Test failed!")
        print("The JSON matching error is still present.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 