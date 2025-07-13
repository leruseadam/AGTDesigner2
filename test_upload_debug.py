#!/usr/bin/env python3
"""
Test script to verify upload functionality
"""
import requests
import os
import sys

def test_upload_endpoint():
    """Test the upload endpoint with a simple Excel file"""
    
    # Test URLs
    local_url = "http://localhost:9090"
    remote_url = "https://www.agtpricetags.com"
    
    # Test both local and remote
    for base_url in [local_url, remote_url]:
        print(f"\n=== Testing {base_url} ===")
        
        try:
            # Test 1: Check if server is running
            print("1. Testing server status...")
            response = requests.get(f"{base_url}/api/status", timeout=10)
            if response.status_code == 200:
                print("   ✅ Server is running")
                status_data = response.json()
                print(f"   Data loaded: {status_data.get('data_loaded', 'Unknown')}")
                print(f"   Data shape: {status_data.get('data_shape', 'Unknown')}")
            else:
                print(f"   ❌ Server returned status {response.status_code}")
                continue
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Cannot connect to {base_url}: {e}")
            continue
            
        # Test 2: Check available tags endpoint
        try:
            print("2. Testing available tags endpoint...")
            response = requests.get(f"{base_url}/api/available-tags", timeout=10)
            if response.status_code == 200:
                tags = response.json()
                print(f"   ✅ Available tags endpoint working")
                print(f"   Tags count: {len(tags) if isinstance(tags, list) else 'Not a list'}")
            else:
                print(f"   ❌ Available tags endpoint returned {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error testing available tags: {e}")
            
        # Test 3: Check selected tags endpoint
        try:
            print("3. Testing selected tags endpoint...")
            response = requests.get(f"{base_url}/api/selected-tags", timeout=10)
            if response.status_code == 200:
                tags = response.json()
                print(f"   ✅ Selected tags endpoint working")
                print(f"   Tags count: {len(tags) if isinstance(tags, list) else 'Not a list'}")
            else:
                print(f"   ❌ Selected tags endpoint returned {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error testing selected tags: {e}")

if __name__ == "__main__":
    test_upload_endpoint() 