#!/usr/bin/env python3
"""
Comprehensive upload test script to debug upload issues.
Works with both local and remote servers.
"""

import requests
import os
import sys
import time

def test_server_status(base_url="http://localhost:5000"):
    """Test if the server is running and responding."""
    try:
        url = f"{base_url}/api/status"
        print(f"Testing server status at {url}...")
        
        response = requests.get(url, timeout=10)
        print(f"Server status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Server response: {data}")
            return True
        else:
            print(f"❌ Server not responding properly: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server connection failed: {e}")
        return False

def test_upload_endpoint(base_url="http://localhost:5000"):
    """Test the upload endpoint with a simple request."""
    
    # Test file path - create a simple test file if it doesn't exist
    test_file = "test_upload.xlsx"
    
    if not os.path.exists(test_file):
        print(f"Creating test file: {test_file}")
        # Create a simple Excel file for testing
        import pandas as pd
        df = pd.DataFrame({
            'Product Name*': ['Test Product 1', 'Test Product 2'],
            'Vendor': ['Test Vendor', 'Test Vendor'],
            'THC %': ['10.5', '15.2'],
            'CBD %': ['0.5', '1.2']
        })
        df.to_excel(test_file, index=False)
        print(f"Test file created: {test_file}")
    
    try:
        print(f"\n=== Testing Upload Endpoint ===")
        print(f"Uploading {test_file} to {base_url}/upload")
        
        with open(test_file, 'rb') as f:
            files = {'file': (test_file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            response = requests.post(f"{base_url}/upload", files=files, timeout=30)
        
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response headers: {dict(response.headers)}")
        
        try:
            data = response.json()
            print(f"Upload response data: {data}")
            
            if response.status_code == 200:
                print("✅ Upload successful!")
                return True
            else:
                print(f"❌ Upload failed: {data.get('error', 'Unknown error')}")
                return False
        except Exception as json_error:
            print(f"❌ Error parsing JSON response: {json_error}")
            print(f"Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return False

def test_available_tags(base_url="http://localhost:5000"):
    """Test the available tags endpoint."""
    try:
        print(f"\n=== Testing Available Tags Endpoint ===")
        url = f"{base_url}/api/available-tags"
        print(f"Testing {url}")
        
        response = requests.get(url, timeout=10)
        print(f"Available tags response status: {response.status_code}")
        
        try:
            data = response.json()
            if response.status_code == 200:
                if isinstance(data, list):
                    print(f"✅ Available tags endpoint working: {len(data)} tags")
                    return True
                else:
                    print(f"❌ Unexpected response format: {type(data)}")
                    return False
            elif response.status_code == 404:
                print(f"ℹ️ No data loaded (expected): {data.get('error', 'No error message')}")
                return True
            else:
                print(f"❌ Available tags failed: {data.get('error', 'Unknown error')}")
                return False
        except Exception as json_error:
            print(f"❌ Error parsing JSON response: {json_error}")
            print(f"Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Available tags test failed: {e}")
        return False

def main():
    """Main test function."""
    print("=== Upload Debug Test ===")
    
    # Test both local and remote servers
    servers = [
        ("Local Server", "http://localhost:5000"),
        ("PythonAnywhere", "https://www.agtpricetags.com")
    ]
    
    for server_name, base_url in servers:
        print(f"\n{'='*50}")
        print(f"Testing {server_name}: {base_url}")
        print(f"{'='*50}")
        
        # Test server status
        if test_server_status(base_url):
            # Test available tags (should work even without upload)
            test_available_tags(base_url)
            
            # Test upload endpoint
            test_upload_endpoint(base_url)
            
            # Test available tags again after upload
            time.sleep(2)  # Wait a bit for processing
            test_available_tags(base_url)
        else:
            print(f"❌ {server_name} is not responding, skipping tests")

if __name__ == "__main__":
    main() 