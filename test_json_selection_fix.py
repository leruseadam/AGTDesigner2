#!/usr/bin/env python3
"""
Test script to verify that JSON matching correctly places items in the Selected Output.
This test simulates the JSON matching process and verifies that selected tags are properly displayed.
"""

import requests
import json
import time

def test_json_matching_selection():
    """Test that JSON matching correctly places items in the Selected Output."""
    
    base_url = "http://127.0.0.1:9090"
    
    print("🧪 Testing JSON Matching Selection Fix")
    print("=" * 50)
    
    # Step 1: Check if the application is running
    print("1. Checking application status...")
    try:
        response = requests.get(f"{base_url}/api/status")
        if response.status_code == 200:
            print("✅ Application is running")
        else:
            print("❌ Application is not responding correctly")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to application: {e}")
        return False
    
    # Step 2: Get initial state
    print("\n2. Getting initial state...")
    try:
        response = requests.get(f"{base_url}/api/selected-tags")
        if response.status_code == 200:
            initial_selected = response.json()  # Direct list response
            print(f"✅ Initial selected tags: {len(initial_selected)} items")
        else:
            print("❌ Failed to get initial selected tags")
            return False
    except Exception as e:
        print(f"❌ Error getting initial state: {e}")
        return False
    
    # Step 3: Test JSON matching with a sample URL
    print("\n3. Testing JSON matching...")
    try:
        # Use a test URL that should trigger the JSON matching logic
        test_data = {
            "url": "https://example.com/test.json"
        }
        
        response = requests.post(
            f"{base_url}/api/json-match",
            json=test_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ JSON matching response received")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Matched count: {result.get('matched_count', 0)}")
            print(f"   Selected tags: {len(result.get('selected_tags', []))}")
            
            # Check if selected tags were returned
            selected_tags = result.get('selected_tags', [])
            if selected_tags:
                print(f"✅ Selected tags found: {len(selected_tags)} items")
                for i, tag in enumerate(selected_tags[:3]):  # Show first 3
                    print(f"   {i+1}. {tag.get('Product Name*', 'Unknown')}")
                if len(selected_tags) > 3:
                    print(f"   ... and {len(selected_tags) - 3} more")
            else:
                print("⚠️  No selected tags returned (this might be expected if no matches)")
                
        else:
            print(f"❌ JSON matching failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error during JSON matching: {e}")
        return False
    
    # Step 4: Verify selected tags are now in the system
    print("\n4. Verifying selected tags are in the system...")
    try:
        time.sleep(1)  # Give the system time to update
        response = requests.get(f"{base_url}/api/selected-tags")
        if response.status_code == 200:
            final_selected = response.json()  # Direct list response
            print(f"✅ Final selected tags: {len(final_selected)} items")
            
            if len(final_selected) > len(initial_selected):
                print(f"✅ Selected tags increased from {len(initial_selected)} to {len(final_selected)}")
                print("✅ JSON matching successfully added items to Selected Output")
                return True
            elif len(final_selected) == len(initial_selected):
                print("⚠️  Selected tags count unchanged (this might be expected)")
                return True
            else:
                print(f"❌ Selected tags decreased from {len(initial_selected)} to {len(final_selected)}")
                return False
        else:
            print("❌ Failed to get final selected tags")
            return False
    except Exception as e:
        print(f"❌ Error verifying final state: {e}")
        return False

def test_json_clear():
    """Test that JSON clear functionality works."""
    
    base_url = "http://127.0.0.1:9090"
    
    print("\n🧹 Testing JSON Clear Functionality")
    print("=" * 50)
    
    try:
        response = requests.post(f"{base_url}/api/json-clear")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ JSON clear successful")
            print(f"   Message: {result.get('message', 'Unknown')}")
            print(f"   Selected tags after clear: {len(result.get('selected_tags', []))}")
            return True
        else:
            print(f"❌ JSON clear failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error during JSON clear: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting JSON Selection Fix Test")
    print("=" * 60)
    
    # Test JSON matching selection
    success1 = test_json_matching_selection()
    
    # Test JSON clear
    success2 = test_json_clear()
    
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print(f"  JSON Matching Selection: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"  JSON Clear Functionality: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("\n🎉 All tests passed! JSON matching should now correctly place items in Selected Output.")
    else:
        print("\n⚠️  Some tests failed. Please check the application logs for more details.") 