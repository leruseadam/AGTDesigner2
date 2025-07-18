#!/usr/bin/env python3
"""
Debug script to help troubleshoot upload issues.
This script can be used to test upload functionality and check processing status.
"""

import requests
import time
import json
import os
import sys

def test_upload_status():
    """Test the upload status endpoint."""
    print("🔍 Testing upload status endpoint...")
    
    try:
        response = requests.get('http://127.0.0.1:9090/api/debug-upload-status')
        if response.ok:
            data = response.json()
            print(f"✅ Upload status endpoint working")
            print(f"📊 Total files in processing: {data['total_files']}")
            
            if data['statuses']:
                print("\n📋 Current processing statuses:")
                for status in data['statuses']:
                    print(f"  - {status['filename']}: {status['status']} (age: {status['age_seconds']}s)")
            else:
                print("  No files currently processing")
            
            if data['excel_processor']:
                print(f"\n💾 Excel Processor Status:")
                print(f"  - Has processor: {data['excel_processor']['has_processor']}")
                print(f"  - Has dataframe: {data['excel_processor']['has_dataframe']}")
                if data['excel_processor']['dataframe_shape']:
                    print(f"  - DataFrame shape: {data['excel_processor']['dataframe_shape']}")
                print(f"  - Last loaded file: {data['excel_processor']['last_loaded_file']}")
            
            return data
        else:
            print(f"❌ Upload status endpoint failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error testing upload status: {e}")
        return None

def test_available_tags():
    """Test the available tags endpoint."""
    print("\n🔍 Testing available tags endpoint...")
    
    try:
        response = requests.get('http://127.0.0.1:9090/api/available-tags')
        if response.ok:
            data = response.json()
            print(f"✅ Available tags endpoint working")
            print(f"📊 Tags available: {len(data.get('tags', []))}")
            return data
        else:
            print(f"❌ Available tags endpoint failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error testing available tags: {e}")
        return None

def test_upload_file(file_path):
    """Test uploading a file."""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    print(f"\n📤 Testing file upload: {file_path}")
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post('http://127.0.0.1:9090/upload', files=files)
        
        if response.ok:
            data = response.json()
            print(f"✅ Upload successful: {data.get('filename', 'Unknown')}")
            return data.get('filename')
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error uploading file: {e}")
        return None

def monitor_upload_status(filename, max_attempts=30):
    """Monitor upload status for a specific file."""
    print(f"\n👀 Monitoring upload status for: {filename}")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(f'http://127.0.0.1:9090/api/upload-status?filename={filename}')
            if response.ok:
                data = response.json()
                status = data['status']
                age = data.get('age_seconds', 0)
                
                print(f"  Attempt {attempt + 1}: {status} (age: {age}s)")
                
                if status == 'ready':
                    print("✅ File processing completed!")
                    return True
                elif status == 'processing':
                    print("⏳ Still processing...")
                elif status == 'not_found':
                    print("⚠️  File not found in processing status")
                elif status.startswith('error'):
                    print(f"❌ Processing error: {status}")
                    return False
                
            else:
                print(f"❌ Status check failed: {response.status_code}")
            
            time.sleep(3)  # Wait 3 seconds between checks
            
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            time.sleep(3)
    
    print("⏰ Monitoring timed out")
    return False

def main():
    """Main function to run debug tests."""
    print("🚀 Label Maker Upload Debug Tool")
    print("=" * 50)
    
    # Test current status
    status_data = test_upload_status()
    
    # Test available tags
    tags_data = test_available_tags()
    
    # If a file path is provided as argument, test upload
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        filename = test_upload_file(file_path)
        
        if filename:
            # Monitor the upload
            success = monitor_upload_status(filename)
            
            if success:
                print("\n🎉 Upload and processing completed successfully!")
                
                # Test available tags again
                print("\n🔍 Testing available tags after upload...")
                new_tags_data = test_available_tags()
                
                if new_tags_data and tags_data:
                    old_count = len(tags_data.get('tags', []))
                    new_count = len(new_tags_data.get('tags', []))
                    print(f"📊 Tags before upload: {old_count}")
                    print(f"📊 Tags after upload: {new_count}")
                    print(f"📈 Change: {new_count - old_count}")
            else:
                print("\n❌ Upload processing failed or timed out")
    
    print("\n🔍 Final status check:")
    test_upload_status()

if __name__ == "__main__":
    main() 