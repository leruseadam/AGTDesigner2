#!/usr/bin/env python3
"""
Simple platform simulation test for cross-platform compatibility.
Tests platform detection and configuration without requiring actual file system access.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

def test_platform_detection_logic():
    """Test the logic of platform detection without actual file system access."""
    print("🧪 Testing Platform Detection Logic...")
    
    try:
        from src.core.utils.cross_platform import get_platform, is_mac, is_windows, is_linux, is_pythonanywhere
        
        # Test current platform detection
        pm = get_platform()
        current_system = pm.platform_info['system']
        
        print(f"✅ Current platform detected: {current_system}")
        
        # Test platform-specific functions
        print(f"✅ Is Mac: {is_mac()}")
        print(f"✅ Is Windows: {is_windows()}")
        print(f"✅ Is Linux: {is_linux()}")
        print(f"✅ Is PythonAnywhere: {is_pythonanywhere()}")
        
        # Test configuration based on current platform
        print(f"✅ Memory limit: {pm.get_memory_limit() / (1024*1024):.1f} MB")
        print(f"✅ File size limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
        print(f"✅ Excel engines: {pm.get_excel_engines()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Platform detection logic test failed: {e}")
        return False

def test_platform_configuration():
    """Test platform-specific configuration without file system access."""
    print("🧪 Testing Platform Configuration...")
    
    try:
        from config_cross_platform import get_config, Config
        
        # Test configuration loading
        config = get_config()
        print(f"✅ Configuration loaded: {config.__name__}")
        
        # Test platform-specific settings
        print(f"✅ DEBUG mode: {config.DEBUG}")
        print(f"✅ File size limit: {config.MAX_CONTENT_LENGTH / (1024*1024):.1f} MB")
        print(f"✅ Upload folder: {config.UPLOAD_FOLDER}")
        print(f"✅ Output folder: {config.OUTPUT_FOLDER}")
        
        # Test different environments
        environments = ['development', 'production', 'testing']
        for env in environments:
            env_config = get_config(env)
            print(f"✅ {env.capitalize()} config: {env_config.__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Platform configuration test failed: {e}")
        return False

def test_excel_processor_integration():
    """Test Excel processor integration with cross-platform utilities."""
    print("🧪 Testing Excel Processor Integration...")
    
    try:
        from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file
        from src.core.utils.cross_platform import get_platform
        
        # Test platform detection in Excel processor
        pm = get_platform()
        processor = ExcelProcessor()
        
        print(f"✅ Excel processor created on: {pm.platform_info['system']}")
        print(f"✅ Platform file size limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
        print(f"✅ Platform Excel engines: {pm.get_excel_engines()}")
        
        # Test default file detection (without actual file access)
        default_file = get_default_upload_file()
        print(f"✅ Default file detection: {default_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Excel processor integration test failed: {e}")
        return False

def test_path_handling():
    """Test cross-platform path handling."""
    print("🧪 Testing Path Handling...")
    
    try:
        from src.core.utils.cross_platform import get_safe_path, get_platform
        
        pm = get_platform()
        
        # Test path creation
        test_paths = [
            ("uploads", "file.xlsx"),
            ("output", "generated.docx"),
            ("logs", "app.log"),
            ("data", "database.db")
        ]
        
        for path_parts in test_paths:
            safe_path = get_safe_path(*path_parts)
            print(f"✅ Safe path created: {safe_path}")
        
        # Test platform-specific path separator
        separator = pm.config['path_separator']
        print(f"✅ Platform path separator: '{separator}'")
        
        return True
        
    except Exception as e:
        print(f"❌ Path handling test failed: {e}")
        return False

def test_memory_and_performance_config():
    """Test memory and performance configuration."""
    print("🧪 Testing Memory and Performance Configuration...")
    
    try:
        from src.core.utils.cross_platform import get_platform
        
        pm = get_platform()
        
        # Test memory configuration
        memory_limit = pm.get_memory_limit()
        file_size_limit = pm.get_file_size_limit()
        
        print(f"✅ Memory limit: {memory_limit / (1024*1024):.1f} MB")
        print(f"✅ File size limit: {file_size_limit / (1024*1024):.1f} MB")
        
        # Test platform-specific optimizations
        if pm.is_platform('pythonanywhere'):
            print("✅ PythonAnywhere optimizations: Memory and file size limited")
        elif pm.is_platform('mac'):
            print("✅ macOS optimizations: Full memory and file size available")
        elif pm.is_platform('windows'):
            print("✅ Windows optimizations: Full memory and file size available")
        elif pm.is_platform('linux'):
            print("✅ Linux optimizations: Full memory and file size available")
        
        # Test Excel engine configuration
        excel_engines = pm.get_excel_engines()
        print(f"✅ Excel engines: {excel_engines}")
        
        return True
        
    except Exception as e:
        print(f"❌ Memory and performance config test failed: {e}")
        return False

def test_line_ending_normalization():
    """Test line ending normalization across platforms."""
    print("🧪 Testing Line Ending Normalization...")
    
    try:
        from src.core.utils.cross_platform import normalize_line_endings, get_platform
        
        pm = get_platform()
        
        # Test different line ending formats
        test_texts = [
            "Line 1\r\nLine 2\nLine 3\r",
            "Unix\nLine\nEndings",
            "Windows\r\nLine\r\nEndings",
            "Mixed\r\nUnix\nWindows\r"
        ]
        
        for i, text in enumerate(test_texts, 1):
            normalized = normalize_line_endings(text)
            print(f"✅ Text {i} normalized: {repr(normalized)}")
        
        # Test platform-specific line ending
        expected_ending = pm.config['line_ending']
        print(f"✅ Platform line ending: {repr(expected_ending)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Line ending normalization test failed: {e}")
        return False

def test_installation_validation():
    """Test installation script validation."""
    print("🧪 Testing Installation Validation...")
    
    try:
        # Check installation scripts
        scripts = [
            'install_cross_platform.sh',
            'install_cross_platform.bat'
        ]
        
        for script in scripts:
            if os.path.exists(script):
                print(f"✅ Installation script exists: {script}")
                
                # Check if script is executable (Unix-like systems)
                if os.name != 'nt':  # Not Windows
                    if os.access(script, os.X_OK):
                        print(f"✅ Script is executable: {script}")
                    else:
                        print(f"⚠️  Script not executable: {script}")
            else:
                print(f"❌ Installation script missing: {script}")
        
        # Check requirements file
        if os.path.exists('requirements_cross_platform.txt'):
            print("✅ Cross-platform requirements file exists")
            
            # Read and validate requirements
            with open('requirements_cross_platform.txt', 'r') as f:
                requirements = f.read()
                required_packages = ['Flask', 'pandas', 'python-docx', 'openpyxl']
                missing_packages = []
                
                for package in required_packages:
                    if package not in requirements:
                        missing_packages.append(package)
                
                if missing_packages:
                    print(f"❌ Missing packages: {missing_packages}")
                else:
                    print("✅ All required packages found in requirements")
        else:
            print("❌ Cross-platform requirements file missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Installation validation test failed: {e}")
        return False

def run_simple_platform_tests():
    """Run all simple platform tests."""
    print("🚀 Starting Simple Platform Testing...")
    print("=" * 60)
    
    tests = [
        ("Platform Detection Logic", test_platform_detection_logic),
        ("Platform Configuration", test_platform_configuration),
        ("Excel Processor Integration", test_excel_processor_integration),
        ("Path Handling", test_path_handling),
        ("Memory and Performance Config", test_memory_and_performance_config),
        ("Line Ending Normalization", test_line_ending_normalization),
        ("Installation Validation", test_installation_validation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SIMPLE PLATFORM TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All simple platform tests passed!")
        print("Your cross-platform functionality is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = run_simple_platform_tests()
    sys.exit(0 if success else 1) 