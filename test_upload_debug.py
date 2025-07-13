#!/usr/bin/env python3
"""
Simple upload test script to debug upload issues.
"""

import requests
import os
import sys

def test_upload_endpoint():
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
        # Test the upload endpoint
        url = "http://localhost:5000/upload"
        
        with open(test_file, 'rb') as f:
            files = {'file': (test_file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            print(f"Sending POST request to {url}...")
            response = requests.post(url, files=files)
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            try:
                data = response.json()
                print(f"Response data: {data}")
                
                if response.status_code == 200:
                    print("✅ Upload test successful!")
                    return True
                else:
                    print(f"❌ Upload test failed: {data.get('error', 'Unknown error')}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error parsing response: {e}")
                print(f"Response text: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error during upload test: {e}")
        return False

def test_server_status():
    """Test if the server is running and responding."""
    try:
        url = "http://localhost:5000/api/status"
        print(f"Testing server status at {url}...")
        
        response = requests.get(url, timeout=5)
        print(f"Server status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Server response: {data}")
            return True
        else:
            print(f"❌ Server not responding properly: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Error testing server: {e}")
        return False

if __name__ == "__main__":
    print("=== Upload Debug Test ===")
    
    # First test if server is running
    if not test_server_status():
        print("\n❌ Server is not running or not accessible.")
        print("Please start your Flask app first:")
        print("  python app.py")
        sys.exit(1)
    
    print("\n✅ Server is running. Testing upload...")
    
    # Test upload
    if test_upload_endpoint():
        print("\n✅ Upload functionality is working!")
    else:
        print("\n❌ Upload functionality has issues.")
        print("Check the server logs for more details.") 