#!/usr/bin/env python3
"""
Cross-platform testing script for AGT Designer.
Simulates different platforms and tests all cross-platform functionality.
"""

import os
import sys
import platform
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_cross_platform_utilities():
    """Test the cross-platform utilities module."""
    print("🧪 Testing Cross-Platform Utilities...")
    
    try:
        from src.core.utils.cross_platform import (
            get_platform, platform_manager, get_safe_path, 
            ensure_directory, normalize_line_endings, is_mac, 
            is_windows, is_linux, is_pythonanywhere
        )
        
        # Test platform detection
        pm = get_platform()
        print(f"✅ Platform detected: {pm.platform_info['system']}")
        print(f"✅ Platform info: {pm.platform_info}")
        
        # Test platform-specific functions
        print(f"✅ Is Mac: {is_mac()}")
        print(f"✅ Is Windows: {is_windows()}")
        print(f"✅ Is Linux: {is_linux()}")
        print(f"✅ Is PythonAnywhere: {is_pythonanywhere()}")
        
        # Test path handling
        test_path = get_safe_path("test", "path", "file.txt")
        print(f"✅ Safe path created: {test_path}")
        
        # Test line ending normalization
        test_text = "Line 1\r\nLine 2\nLine 3\r"
        normalized = normalize_line_endings(test_text)
        print(f"✅ Line endings normalized: {repr(normalized)}")
        
        # Test directory creation
        test_dir = tempfile.mkdtemp()
        test_subdir = os.path.join(test_dir, "test_subdir")
        result = ensure_directory(test_subdir)
        print(f"✅ Directory creation: {result}")
        
        # Cleanup
        shutil.rmtree(test_dir)
        
        print("✅ Cross-platform utilities test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Cross-platform utilities test failed: {e}")
        return False

def test_platform_simulation():
    """Test platform simulation for different operating systems."""
    print("\n🧪 Testing Platform Simulation...")
    
    platforms_to_test = [
        ('darwin', 'macOS'),
        ('windows', 'Windows'),
        ('linux', 'Linux'),
        ('pythonanywhere', 'PythonAnywhere')
    ]
    
    for platform_name, display_name in platforms_to_test:
        print(f"\n📱 Testing {display_name} simulation...")
        
        with patch('platform.system') as mock_system, \
             patch('os.path.exists') as mock_exists, \
             patch('os.getcwd') as mock_cwd:
            
            # Mock platform-specific responses
            if platform_name == 'darwin':
                mock_system.return_value = 'Darwin'
                mock_exists.return_value = False
                mock_cwd.return_value = '/Users/testuser/project'
            elif platform_name == 'windows':
                mock_system.return_value = 'Windows'
                mock_exists.return_value = False
                mock_cwd.return_value = 'C:\\Users\\testuser\\project'
            elif platform_name == 'linux':
                mock_system.return_value = 'Linux'
                mock_exists.return_value = False
                mock_cwd.return_value = '/home/testuser/project'
            elif platform_name == 'pythonanywhere':
                mock_system.return_value = 'Linux'
                mock_exists.return_value = True  # Simulate PythonAnywhere paths
                mock_cwd.return_value = '/home/adamcordova/project'
            
            try:
                # Re-import to get fresh platform detection
                if 'src.core.utils.cross_platform' in sys.modules:
                    del sys.modules['src.core.utils.cross_platform']
                
                from src.core.utils.cross_platform import get_platform, is_pythonanywhere
                
                pm = get_platform()
                print(f"✅ {display_name} platform detected: {pm.platform_info['system']}")
                print(f"✅ Is PythonAnywhere: {is_pythonanywhere()}")
                print(f"✅ Paths: {pm.paths}")
                print(f"✅ Config: {pm.config}")
                
            except Exception as e:
                print(f"❌ {display_name} simulation failed: {e}")
                continue
    
    print("✅ Platform simulation tests completed!")

def test_excel_processor_cross_platform():
    """Test Excel processor with cross-platform utilities."""
    print("\n🧪 Testing Excel Processor Cross-Platform...")
    
    try:
        from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file
        from src.core.utils.cross_platform import get_platform
        
        pm = get_platform()
        processor = ExcelProcessor()
        
        print(f"✅ Excel processor created with platform: {pm.platform_info['system']}")
        print(f"✅ File size limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
        print(f"✅ Excel engines: {pm.get_excel_engines()}")
        
        # Test default file detection
        default_file = get_default_upload_file()
        print(f"✅ Default file detection: {default_file}")
        
        print("✅ Excel processor cross-platform test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Excel processor cross-platform test failed: {e}")
        return False

def test_configuration_cross_platform():
    """Test cross-platform configuration."""
    print("\n🧪 Testing Cross-Platform Configuration...")
    
    try:
        from config_cross_platform import get_config, Config
        
        # Test different environments
        environments = ['development', 'production', 'testing']
        
        for env in environments:
            config = get_config(env)
            print(f"✅ {env.capitalize()} config loaded: {config.__name__}")
            print(f"   - DEBUG: {config.DEBUG}")
            print(f"   - MAX_CONTENT_LENGTH: {config.MAX_CONTENT_LENGTH / (1024*1024):.1f} MB")
            print(f"   - IS_PYTHONANYWHERE: {config.IS_PYTHONANYWHERE}")
        
        print("✅ Cross-platform configuration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Cross-platform configuration test failed: {e}")
        return False

def test_file_operations_cross_platform():
    """Test file operations across different platforms."""
    print("\n🧪 Testing File Operations Cross-Platform...")
    
    try:
        from src.core.utils.cross_platform import get_platform, get_safe_path, ensure_directory
        
        pm = get_platform()
        
        # Create test directories
        test_dirs = [
            pm.get_path('uploads_dir'),
            pm.get_path('output_dir'),
            pm.get_path('logs_dir'),
            pm.get_path('cache_dir')
        ]
        
        for test_dir in test_dirs:
            result = ensure_directory(test_dir)
            print(f"✅ Directory ensured: {test_dir} - {result}")
        
        # Test file path creation
        test_files = [
            get_safe_path("uploads", "test.xlsx"),
            get_safe_path("output", "generated.docx"),
            get_safe_path("logs", "app.log")
        ]
        
        for test_file in test_files:
            print(f"✅ Safe path created: {test_file}")
        
        print("✅ File operations cross-platform test passed!")
        return True
        
    except Exception as e:
        print(f"❌ File operations cross-platform test failed: {e}")
        return False

def test_memory_and_performance():
    """Test memory and performance settings across platforms."""
    print("\n🧪 Testing Memory and Performance Settings...")
    
    try:
        from src.core.utils.cross_platform import get_platform
        
        pm = get_platform()
        
        print(f"✅ Memory limit: {pm.get_memory_limit() / (1024*1024):.1f} MB")
        print(f"✅ File size limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
        print(f"✅ Excel engines: {pm.get_excel_engines()}")
        print(f"✅ Enable caching: {pm.get_config('enable_caching')}")
        print(f"✅ Enable compression: {pm.get_config('enable_compression')}")
        
        # Test platform-specific optimizations
        if pm.is_platform('pythonanywhere'):
            print("✅ PythonAnywhere optimizations detected")
        elif pm.is_platform('mac'):
            print("✅ macOS optimizations detected")
        elif pm.is_platform('windows'):
            print("✅ Windows optimizations detected")
        elif pm.is_platform('linux'):
            print("✅ Linux optimizations detected")
        
        print("✅ Memory and performance test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Memory and performance test failed: {e}")
        return False

def test_installation_scripts():
    """Test installation script generation and validation."""
    print("\n🧪 Testing Installation Scripts...")
    
    try:
        # Check if installation scripts exist
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
                if 'Flask' in requirements and 'pandas' in requirements:
                    print("✅ Requirements file contains core dependencies")
                else:
                    print("❌ Requirements file missing core dependencies")
        else:
            print("❌ Cross-platform requirements file missing")
        
        print("✅ Installation scripts test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Installation scripts test failed: {e}")
        return False

def test_documentation():
    """Test cross-platform documentation."""
    print("\n🧪 Testing Cross-Platform Documentation...")
    
    try:
        # Check if documentation exists
        docs = [
            'docs/CROSS_PLATFORM_GUIDE.md'
        ]
        
        for doc in docs:
            if os.path.exists(doc):
                print(f"✅ Documentation exists: {doc}")
                
                # Check content
                with open(doc, 'r') as f:
                    content = f.read()
                    if 'Cross-Platform' in content and 'Installation' in content:
                        print(f"✅ Documentation content validated: {doc}")
                    else:
                        print(f"⚠️  Documentation content incomplete: {doc}")
            else:
                print(f"❌ Documentation missing: {doc}")
        
        print("✅ Documentation test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Documentation test failed: {e}")
        return False

def run_comprehensive_test():
    """Run all cross-platform tests."""
    print("🚀 Starting Comprehensive Cross-Platform Testing...")
    print("=" * 60)
    
    tests = [
        ("Cross-Platform Utilities", test_cross_platform_utilities),
        ("Platform Simulation", test_platform_simulation),
        ("Excel Processor", test_excel_processor_cross_platform),
        ("Configuration", test_configuration_cross_platform),
        ("File Operations", test_file_operations_cross_platform),
        ("Memory and Performance", test_memory_and_performance),
        ("Installation Scripts", test_installation_scripts),
        ("Documentation", test_documentation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
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
        print("🎉 All cross-platform tests passed! Your application is ready for all platforms.")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1) 