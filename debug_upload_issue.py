#!/usr/bin/env python3
"""
Debug script to diagnose upload issues on PythonAnywhere
Run this on PythonAnywhere to check what's happening with file uploads
"""

import os
import sys
import time
import logging
from pathlib import Path

def check_upload_status():
    """Check the current upload processing status"""
    print("=== UPLOAD STATUS CHECK ===")
    
    # Check if we can import the processing status
    try:
        # Try to import the processing status from app
        sys.path.append('/home/adamcordova/AGTDesigner')
        from app import processing_status, processing_timestamps, processing_lock
        
        with processing_lock:
            print(f"Current processing statuses: {dict(processing_status)}")
            print(f"Processing timestamps: {dict(processing_timestamps)}")
            
        return True
    except Exception as e:
        print(f"Error accessing processing status: {e}")
        return False

def check_excel_processor():
    """Check the current Excel processor state"""
    print("\n=== EXCEL PROCESSOR CHECK ===")
    
    try:
        from app import get_excel_processor
        
        processor = get_excel_processor()
        if processor is None:
            print("❌ Excel processor is None")
            return False
            
        print(f"✅ Excel processor exists: {type(processor)}")
        
        if hasattr(processor, 'df'):
            if processor.df is None:
                print("❌ DataFrame is None")
            elif processor.df.empty:
                print("❌ DataFrame is empty")
            else:
                print(f"✅ DataFrame has {len(processor.df)} rows, {len(processor.df.columns)} columns")
                print(f"   Sample data:")
                print(processor.df.head(3))
        else:
            print("❌ No DataFrame attribute found")
            
        if hasattr(processor, '_last_loaded_file'):
            print(f"📁 Last loaded file: {processor._last_loaded_file}")
            if processor._last_loaded_file and os.path.exists(processor._last_loaded_file):
                print(f"✅ File exists on disk")
                file_size = os.path.getsize(processor._last_loaded_file)
                print(f"   File size: {file_size} bytes")
            else:
                print(f"❌ File does not exist on disk")
        else:
            print("❌ No _last_loaded_file attribute")
            
        return True
        
    except Exception as e:
        print(f"❌ Error checking Excel processor: {e}")
        return False

def check_upload_folder():
    """Check the upload folder contents"""
    print("\n=== UPLOAD FOLDER CHECK ===")
    
    upload_folder = '/home/adamcordova/AGTDesigner/uploads'
    
    if not os.path.exists(upload_folder):
        print(f"❌ Upload folder does not exist: {upload_folder}")
        return False
        
    print(f"✅ Upload folder exists: {upload_folder}")
    
    files = os.listdir(upload_folder)
    print(f"📁 Files in upload folder ({len(files)}):")
    
    for file in sorted(files):
        file_path = os.path.join(upload_folder, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            print(f"   {file} ({size} bytes, modified: {mtime_str})")
        else:
            print(f"   {file} (directory)")
            
    return True

def check_cache_status():
    """Check cache status"""
    print("\n=== CACHE STATUS CHECK ===")
    
    try:
        from app import cache
        
        # Try to get cache info
        cache_info = {}
        for key in ['available_tags', 'selected_tags', 'filter_options']:
            try:
                value = cache.get(key)
                if value is not None:
                    cache_info[key] = f"exists ({type(value)})"
                else:
                    cache_info[key] = "not found"
            except:
                cache_info[key] = "error accessing"
                
        print("Cache status:")
        for key, status in cache_info.items():
            print(f"   {key}: {status}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error checking cache: {e}")
        return False

def check_session_data():
    """Check session data"""
    print("\n=== SESSION DATA CHECK ===")
    
    try:
        from flask import session
        
        session_keys = ['selected_tags', 'file_path', 'current_filter_mode']
        session_info = {}
        
        for key in session_keys:
            if key in session:
                value = session[key]
                if isinstance(value, list):
                    session_info[key] = f"list with {len(value)} items"
                elif isinstance(value, str):
                    session_info[key] = f"string: {value[:50]}..."
                else:
                    session_info[key] = f"{type(value)}: {str(value)[:50]}..."
            else:
                session_info[key] = "not found"
                
        print("Session data:")
        for key, status in session_info.items():
            print(f"   {key}: {status}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error checking session: {e}")
        return False

def main():
    """Run all diagnostic checks"""
    print("🔍 PythonAnywhere Upload Issue Diagnostic")
    print("=" * 50)
    
    # Change to the project directory
    os.chdir('/home/adamcordova/AGTDesigner')
    print(f"Working directory: {os.getcwd()}")
    
    # Run all checks
    checks = [
        check_upload_folder,
        check_upload_status,
        check_excel_processor,
        check_cache_status,
        check_session_data
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 All checks passed! The upload system appears to be working correctly.")
    else:
        print("⚠️  Some checks failed. This may indicate the source of the upload issue.")
        
    print("\n💡 Next steps:")
    print("1. If uploads are still not working, check the PythonAnywhere error logs")
    print("2. Try uploading a new file and check if the status changes")
    print("3. Check if the web app needs to be reloaded")

if __name__ == "__main__":
    main() 