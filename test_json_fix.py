#!/usr/bin/env python3
"""
Test script to verify the JSON matcher fix
"""

import sys
import os
import requests
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_json_matcher_fix():
    """Test the JSON matcher with the problematic URL"""
    print("🧪 Testing JSON Matcher Fix")
    print("=" * 50)
    
    # Test URL that was causing issues
    url = "https://files.cultivera.com/435553542D5753313030303438/Interop/25/28/0KMK8B1FTA5RZZ67/Cultivera_ORD-153392_422044.json"
    
    try:
        # Test with Flask endpoint
        print("Testing with Flask JSON matcher...")
        data = {'url': url}
        
        response = requests.post('http://127.0.0.1:9090/api/json-match',
                               json=data,
                               headers={'Content-Type': 'application/json'},
                               timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ JSON matching completed successfully!")
            print(f"   Matched count: {result.get('matched_count', 0)}")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Cache status: {result.get('cache_status', 'Unknown')}")
            
            if result.get('matched_names'):
                print(f"   Matched products: {len(result['matched_names'])}")
                for i, name in enumerate(result['matched_names'][:5]):  # Show first 5
                    print(f"     {i+1}. {name}")
                if len(result['matched_names']) > 5:
                    print(f"     ... and {len(result['matched_names']) - 5} more")
            else:
                print("   No products matched")
                
        else:
            error_data = response.json()
            print(f"❌ JSON matching failed: {error_data.get('error', 'Unknown error')}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ Test completed successfully!")
    return True

if __name__ == "__main__":
    test_json_matcher_fix() 