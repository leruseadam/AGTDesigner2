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
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Error testing server: {e}")
        return False

def test_upload_endpoint(base_url="http://localhost:5000"):
    """Test the upload endpoint with a simple request."""
    
    # Test file path - create a simple test file if it doesn't exist
    test_file = "test_upload.xlsx"
    
    if not os.path.exists(test_file):
        print(f"Creating test file: {test_file}")
        # Create a simple Excel file for testing
        try:
            import pandas as pd
            df = pd.DataFrame({
                'Product Name*': ['Test Product 1', 'Test Product 2'],
                'Vendor': ['Test Vendor', 'Test Vendor'],
                'THC %': ['10.5', '15.2'],
                'CBD %': ['0.5', '1.2']
            })
            df.to_excel(test_file, index=False)
            print(f"Test file created: {test_file}")
        except ImportError:
            print("❌ pandas not available, creating minimal test file...")
            # Create a minimal Excel file without pandas
            import zipfile
            import xml.etree.ElementTree as ET
            
            # Create a minimal Excel file structure
            with zipfile.ZipFile(test_file, 'w') as zf:
                # Add minimal required files
                zf.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
                
                zf.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheets>
<sheet name="Sheet1" sheetId="1" r:id="rId1"/>
</sheets>
</workbook>''')
                
                zf.writestr('xl/worksheets/sheet1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
<row r="1">
<c r="A1" t="s"><v>Product Name*</v></c>
<c r="B1" t="s"><v>Vendor</v></c>
</row>
<row r="2">
<c r="A2" t="s"><v>Test Product</v></c>
<c r="B2" t="s"><v>Test Vendor</v></c>
</row>
</sheetData>
</worksheet>''')
    
    try:
        # Test the upload endpoint
        url = f"{base_url}/upload"
        
        with open(test_file, 'rb') as f:
            files = {'file': (test_file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            
            print(f"Sending POST request to {url}...")
            response = requests.post(url, files=files, timeout=30)
            
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

def test_available_tags(base_url="http://localhost:5000"):
    """Test if available tags endpoint is working."""
    try:
        url = f"{base_url}/api/available-tags"
        print(f"Testing available tags at {url}...")
        
        response = requests.get(url, timeout=10)
        print(f"Available tags status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Available tags: {len(data) if isinstance(data, list) else 'Not a list'}")
            return True
        else:
            print(f"❌ Available tags failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing available tags: {e}")
        return False

def main():
    print("=== Upload Debug Test ===")
    
    # Test different server URLs
    servers = [
        "http://localhost:5000",
        "https://www.agtpricetags.com",
        "http://www.agtpricetags.com"
    ]
    
    working_server = None
    
    for server in servers:
        print(f"\n--- Testing {server} ---")
        if test_server_status(server):
            working_server = server
            break
    
    if not working_server:
        print("\n❌ No servers are accessible.")
        print("Please check:")
        print("1. If running locally: python app.py")
        print("2. If testing remote: Check your internet connection")
        sys.exit(1)
    
    print(f"\n✅ Found working server: {working_server}")
    
    # Test upload
    print(f"\n--- Testing upload on {working_server} ---")
    if test_upload_endpoint(working_server):
        print("\n✅ Upload functionality is working!")
    else:
        print("\n❌ Upload functionality has issues.")
        print("Check the server logs for more details.")
    
    # Test available tags
    print(f"\n--- Testing available tags on {working_server} ---")
    test_available_tags(working_server)

if __name__ == "__main__":
    main() 