#!/usr/bin/env python3
"""
Test script to verify JSON matching with real Cultivera data
"""

import json
import requests
import sys
from urllib.parse import urlparse

# The real Cultivera JSON URL
CULTIVERA_JSON_URL = "https://files.cultivera.com/435553542D57533130383235/Interop/25/16/3EGQ3216P7YSVJCF/Cultivera_ORD-5430_422044.json"

def fetch_cultivera_data():
    """Fetch the Cultivera JSON data"""
    print("🌐 Fetching Cultivera JSON data...")
    try:
        response = requests.get(CULTIVERA_JSON_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Extract product names from inventory_transfer_items
        product_names = []
        if 'inventory_transfer_items' in data:
            for item in data['inventory_transfer_items']:
                if 'product_name' in item:
                    product_names.append(item['product_name'])
        
        print(f"✅ Retrieved {len(product_names)} products from Cultivera JSON")
        print(f"📋 Sample products:")
        for i, name in enumerate(product_names[:5]):
            print(f"   {i+1}. {name}")
        
        return product_names
        
    except Exception as e:
        print(f"❌ Error fetching Cultivera data: {e}")
        return []

def test_json_matching_with_cultivera():
    """Test JSON matching with Cultivera data"""
    
    print("🧪 Testing JSON Matching with Cultivera Data")
    print("=" * 60)
    
    # Test 1: Check if server is running
    try:
        response = requests.get("http://127.0.0.1:9090/api/status", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print("❌ Server responded with error:", response.status_code)
            return False
    except requests.exceptions.RequestException as e:
        print("❌ Server is not running:", e)
        return False
    
    # Test 2: Fetch Cultivera data
    cultivera_products = fetch_cultivera_data()
    if not cultivera_products:
        print("❌ Failed to fetch Cultivera data")
        return False
    
    # Test 3: Get available tags from current Excel file
    try:
        response = requests.get("http://127.0.0.1:9090/api/available-tags", timeout=10)
        if response.status_code == 200:
            available_tags_data = response.json()
            available_tags = [tag.get('Product Name*', '') for tag in available_tags_data if isinstance(tag, dict)]
            print(f"✅ Retrieved {len(available_tags)} available tags from Excel file")
            
            # Show sample of available tags to see the case
            sample_tags = available_tags[:3]
            print(f"📋 Sample Excel tags: {sample_tags}")
            
        else:
            print("❌ Failed to get available tags:", response.status_code)
            return False
    except Exception as e:
        print("❌ Error getting available tags:", e)
        return False
    
    # Test 4: Test case-insensitive matching with Cultivera products
    print(f"\n🔍 Testing Case-Insensitive Matching with {len(cultivera_products)} Cultivera products...")
    
    # Create case-insensitive lookup map
    available_tags_lower = {tag.lower(): tag for tag in available_tags if tag}
    
    matched_count = 0
    unmatched_products = []
    matched_products = []
    
    for cultivera_product in cultivera_products:
        cultivera_product_lower = cultivera_product.lower()
        if cultivera_product_lower in available_tags_lower:
            matched_count += 1
            original_case = available_tags_lower[cultivera_product_lower]
            matched_products.append(original_case)
            print(f"✅ MATCHED: '{cultivera_product}' -> '{original_case}'")
        else:
            unmatched_products.append(cultivera_product)
            print(f"❌ NO MATCH: '{cultivera_product}'")
    
    print(f"\n📊 Matching Results:")
    print(f"   Total Cultivera products: {len(cultivera_products)}")
    print(f"   Matched products: {matched_count}")
    print(f"   Unmatched products: {len(unmatched_products)}")
    print(f"   Success rate: {(matched_count/len(cultivera_products)*100):.1f}%")
    
    if matched_products:
        print(f"\n✅ Matched products ({len(matched_products)}):")
        for i, product in enumerate(matched_products[:10]):
            print(f"   {i+1}. {product}")
        if len(matched_products) > 10:
            print(f"   ... and {len(matched_products) - 10} more")
    
    if unmatched_products:
        print(f"\n❌ Unmatched products ({len(unmatched_products)}):")
        for i, product in enumerate(unmatched_products[:10]):
            print(f"   {i+1}. {product}")
        if len(unmatched_products) > 10:
            print(f"   ... and {len(unmatched_products) - 10} more")
    
    # Test 5: Test the JSON matching endpoint with Cultivera URL
    print(f"\n🚀 Testing JSON Matching Endpoint with Cultivera URL...")
    
    try:
        response = requests.post(
            "http://127.0.0.1:9090/api/json-match",
            json={
                "url": CULTIVERA_JSON_URL
            },
            timeout=60
        )
        
        if response.status_code == 200:
            match_result = response.json()
            print(f"✅ JSON matching successful!")
            print(f"   Matched products: {match_result.get('matched_count', 0)}")
            print(f"   Total products in JSON: {match_result.get('total_products', 0)}")
            print(f"   Success rate: {match_result.get('success_rate', 0):.1f}%")
            
            # Show some matched products
            matched_names = match_result.get('matched_names', [])
            if matched_names:
                print(f"   Sample matched products:")
                for i, name in enumerate(matched_names[:5]):
                    print(f"     {i+1}. {name}")
            
            return True
        else:
            error_data = response.json()
            print(f"❌ JSON matching failed: {response.status_code} - {error_data.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing JSON matching: {e}")
        return False
    
    return matched_count > 0

def test_label_generation_with_matched_products():
    """Test label generation with matched products"""
    print(f"\n🎯 Testing Label Generation with Matched Products...")
    
    # First, perform JSON matching
    try:
        response = requests.post(
            "http://127.0.0.1:9090/api/json-match",
            json={
                "url": CULTIVERA_JSON_URL
            },
            timeout=60
        )
        
        if response.status_code == 200:
            match_result = response.json()
            matched_names = match_result.get('matched_names', [])
            
            if matched_names:
                # Test with first few matched products
                test_tags = matched_names[:3]  # Test with first 3 matched tags
                
                print(f"   Testing with {len(test_tags)} matched products:")
                for i, tag in enumerate(test_tags):
                    print(f"     {i+1}. {tag}")
                
                # Test label generation
                response = requests.post(
                    "http://127.0.0.1:9090/api/generate",
                    json={
                        "selected_tags": test_tags,
                        "template_type": "mini",
                        "scale_factor": 1.0
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    print(f"✅ SUCCESS: Generated labels for {len(test_tags)} matched products!")
                    print(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                    print(f"   Content-Length: {len(response.content)} bytes")
                    return True
                else:
                    error_data = response.json()
                    print(f"❌ Label generation failed: {response.status_code} - {error_data.get('error', 'Unknown error')}")
                    return False
            else:
                print("❌ No matched products to test with")
                return False
                
        else:
            print("❌ JSON matching failed, cannot test label generation")
            return False
            
    except Exception as e:
        print(f"❌ Error testing label generation: {e}")
        return False

def main():
    """Main test function"""
    print("Cultivera JSON Matching Test")
    print("=" * 60)
    
    # Test 1: Basic JSON matching
    success1 = test_json_matching_with_cultivera()
    
    # Test 2: Label generation with matched products
    success2 = test_label_generation_with_matched_products()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Case-insensitive matching is working with real Cultivera data")
        print("✅ JSON matching endpoint is working correctly")
        print("✅ Label generation works with matched products")
    elif success1:
        print("🎉 PARTIAL SUCCESS!")
        print("✅ Case-insensitive matching is working with real Cultivera data")
        print("✅ JSON matching endpoint is working correctly")
        print("⚠️  Label generation needs investigation")
    else:
        print("❌ TESTS FAILED")
        print("🔧 Check the server logs for more details")
    
    return 0 if (success1 and success2) else 1

if __name__ == "__main__":
    sys.exit(main()) 