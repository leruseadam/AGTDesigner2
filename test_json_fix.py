#!/usr/bin/env python3
"""
Test script to verify that the JSON matching error has been fixed.
"""

import requests
import json
import time

def test_json_matching():
    """Test the JSON matching functionality to ensure the 'Product Name*' error is fixed."""
    
    # Test data - simulate a JSON response with inventory items
    test_json_data = {
        "inventory_transfer_items": [
            {
                "product_name": "Test Product 1",
                "vendor": "Test Vendor",
                "brand": "Test Brand",
                "product_type": "Flower",
                "qty": 1
            },
            {
                "product_name": "Test Product 2", 
                "vendor": "Test Vendor",
                "brand": "Test Brand",
                "product_type": "Concentrate",
                "qty": 2
            }
        ]
    }
    
    try:
        # Test the match-json-tags endpoint which is more appropriate for testing
        print("Testing JSON tag matching endpoint...")
        response = requests.post(
            "http://127.0.0.1:9090/api/match-json-tags",
            json=test_json_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ JSON tag matching successful!")
            print(f"Matched products: {len(result.get('matched', []))}")
            print(f"Unmatched products: {len(result.get('unmatched', []))}")
            return True
        else:
            print(f"❌ JSON tag matching failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_api_status():
    """Test that the API is responding correctly."""
    try:
        response = requests.get("http://127.0.0.1:9090/api/status", timeout=10)
        if response.status_code == 200:
            print("✅ API status endpoint working")
            return True
        else:
            print(f"❌ API status failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API status test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing JSON matching fix...")
    print("=" * 50)
    
    # First test API status
    if not test_api_status():
        print("Application not running or not responding")
        exit(1)
    
    # Test JSON matching
    success = test_json_matching()
    
    if success:
        print("\n🎉 All tests passed! The JSON matching error has been fixed.")
    else:
        print("\n❌ Tests failed. The JSON matching error may still exist.")
    
    print("=" * 50) 