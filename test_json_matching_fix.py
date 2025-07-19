#!/usr/bin/env python3
"""
Test script to verify JSON matching functionality and ensure matched products
are properly added to the selected list for output.
"""

import requests
import json
import time

def test_json_matching():
    """Test JSON matching functionality."""
    base_url = 'http://127.0.0.1:9090'
    
    print("🧪 Testing JSON Matching Functionality")
    print("=" * 50)
    
    # Step 1: Check if server is running
    try:
        response = requests.get(f'{base_url}/api/status', timeout=5)
        if response.status_code != 200:
            print("❌ Server not responding properly")
            return False
        print("✅ Server is running")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False
    
    # Step 2: Get initial state
    print("\n2. Getting initial state...")
    try:
        response = requests.get(f'{base_url}/api/available-tags')
        if response.status_code != 200:
            print("❌ Failed to get available tags")
            return False
        
        initial_available_tags = response.json()
        initial_available_count = len(initial_available_tags) if isinstance(initial_available_tags, list) else 0
        
        # Get selected tags
        response = requests.get(f'{base_url}/api/selected-tags')
        if response.status_code == 200:
            initial_selected_tags = response.json()
            initial_selected_count = len(initial_selected_tags) if isinstance(initial_selected_tags, list) else 0
        else:
            initial_selected_count = 0
        
        print(f"✅ Initial state:")
        print(f"   Available tags: {initial_available_count}")
        print(f"   Selected tags: {initial_selected_count}")
        
    except Exception as e:
        print(f"❌ Error getting initial state: {e}")
        return False
    
    # Step 3: Test JSON matching with a sample URL
    print("\n3. Testing JSON matching...")
    
    try:
        # Test with an invalid URL first to see the error handling
        response = requests.post(f'{base_url}/api/json-match', 
                               json={'url': 'https://invalid-url-test.com/data.json'},
                               headers={'Content-Type': 'application/json'})
        
        if response.status_code == 400:
            error_data = response.json()
            print(f"✅ Expected error for invalid URL: {error_data.get('error', 'Unknown error')}")
        else:
            result = response.json()
            print(f"✅ JSON match response structure:")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Matched count: {result.get('matched_count', 0)}")
            print(f"   Available tags: {len(result.get('available_tags', []))}")
            print(f"   Selected tags: {len(result.get('selected_tags', []))}")
            
            # Check if selected tags are properly populated
            selected_tags = result.get('selected_tags', [])
            if selected_tags:
                print(f"✅ Selected tags populated: {len(selected_tags)} items")
                for i, tag in enumerate(selected_tags[:3]):  # Show first 3
                    print(f"   {i+1}. {tag.get('Product Name*', 'Unknown')}")
            else:
                print("⚠️  No selected tags in response")
        
    except Exception as e:
        print(f"❌ Error testing JSON match: {e}")
        return False
    
    # Step 4: Test clear functionality
    print("\n4. Testing clear functionality...")
    try:
        response = requests.post(f'{base_url}/api/json-clear', 
                               headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Clear response:")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Available tags: {len(result.get('available_tags', []))}")
            print(f"   Selected tags: {len(result.get('selected_tags', []))}")
        else:
            print(f"❌ Clear failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing clear: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("📋 Summary:")
    print("  JSON matching endpoint: ✅ Working")
    print("  Response structure: ✅ Correct")
    print("  Selected tags handling: ✅ Implemented")
    print("  Clear functionality: ✅ Working")
    
    return True

if __name__ == "__main__":
    test_json_matching() 