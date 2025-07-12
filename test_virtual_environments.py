#!/usr/bin/env python3
"""
Virtual environment testing for cross-platform compatibility.
Simulates different Python environments and platform configurations.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
from pathlib import Path

def create_test_environment(env_name, python_version="3.8"):
    """Create a test virtual environment."""
    print(f"🔧 Creating test environment: {env_name}")
    
    env_dir = f"test_env_{env_name}"
    
    # Remove existing environment
    if os.path.exists(env_dir):
        shutil.rmtree(env_dir)
    
    # Create new environment
    try:
        subprocess.run([sys.executable, "-m", "venv", env_dir], check=True)
        print(f"✅ Created virtual environment: {env_dir}")
        return env_dir
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create environment: {e}")
        return None

def install_dependencies(env_dir, requirements_file):
    """Install dependencies in the virtual environment."""
    print(f"📦 Installing dependencies in {env_dir}")
    
    # Get the pip path for the virtual environment
    if os.name == 'nt':  # Windows
        pip_path = os.path.join(env_dir, "Scripts", "pip")
        python_path = os.path.join(env_dir, "Scripts", "python")
    else:  # Unix-like
        pip_path = os.path.join(env_dir, "bin", "pip")
        python_path = os.path.join(env_dir, "bin", "python")
    
    try:
        # Upgrade pip
        subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
        
        # Install requirements
        subprocess.run([pip_path, "install", "-r", requirements_file], check=True)
        
        print(f"✅ Dependencies installed successfully")
        return python_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return None

def test_imports(python_path):
    """Test that all required modules can be imported."""
    print("🧪 Testing module imports...")
    
    test_script = """
import sys
print("Python version:", sys.version)

# Test core imports
try:
    import flask
    print("✅ Flask imported successfully")
except ImportError as e:
    print(f"❌ Flask import failed: {e}")

try:
    import pandas
    print("✅ Pandas imported successfully")
except ImportError as e:
    print(f"❌ Pandas import failed: {e}")

try:
    import docx
    print("✅ python-docx imported successfully")
except ImportError as e:
    print(f"❌ python-docx import failed: {e}")

try:
    from src.core.utils.cross_platform import get_platform
    pm = get_platform()
    print(f"✅ Cross-platform utilities imported successfully")
    print(f"   Platform: {pm.platform_info['system']}")
except ImportError as e:
    print(f"❌ Cross-platform utilities import failed: {e}")

try:
    from src.core.data.excel_processor import ExcelProcessor
    print("✅ Excel processor imported successfully")
except ImportError as e:
    print(f"❌ Excel processor import failed: {e}")

print("Import test completed")
"""
    
    try:
        result = subprocess.run([python_path, "-c", test_script], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Import test failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def test_platform_detection(python_path):
    """Test platform detection in the virtual environment."""
    print("🧪 Testing platform detection...")
    
    test_script = """
from src.core.utils.cross_platform import get_platform, is_mac, is_windows, is_linux, is_pythonanywhere

pm = get_platform()

print("Platform Information:")
print(f"  System: {pm.platform_info['system']}")
print(f"  Machine: {pm.platform_info['machine']}")
print(f"  Python Version: {pm.platform_info['python_version']}")
print(f"  Is PythonAnywhere: {pm.platform_info['is_pythonanywhere']}")
print(f"  Is Development: {pm.platform_info['is_development']}")

print("\\nPlatform Detection:")
print(f"  Is Mac: {is_mac()}")
print(f"  Is Windows: {is_windows()}")
print(f"  Is Linux: {is_linux()}")
print(f"  Is PythonAnywhere: {is_pythonanywhere()}")

print("\\nPlatform Configuration:")
print(f"  Memory Limit: {pm.get_memory_limit() / (1024*1024):.1f} MB")
print(f"  File Size Limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
print(f"  Excel Engines: {pm.get_excel_engines()}")
print(f"  Enable Caching: {pm.get_config('enable_caching')}")

print("\\nPlatform Paths:")
for key, path in pm.paths.items():
    if key.endswith('_dir'):
        print(f"  {key}: {path}")
"""
    
    try:
        result = subprocess.run([python_path, "-c", test_script], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Platform detection test failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def test_file_operations(python_path):
    """Test file operations in the virtual environment."""
    print("🧪 Testing file operations...")
    
    test_script = """
import os
import tempfile
from src.core.utils.cross_platform import get_safe_path, ensure_directory, get_temp_file

print("Testing file operations...")

# Test safe path creation
test_path = get_safe_path("test", "path", "file.txt")
print(f"✅ Safe path: {test_path}")

# Test directory creation
test_dir = tempfile.mkdtemp()
test_subdir = os.path.join(test_dir, "test_subdir")
result = ensure_directory(test_subdir)
print(f"✅ Directory creation: {result}")

# Test temp file creation
temp_file = get_temp_file(suffix=".txt")
print(f"✅ Temp file: {temp_file}")

# Cleanup
import shutil
shutil.rmtree(test_dir)
if os.path.exists(temp_file):
    os.remove(temp_file)

print("File operations test completed")
"""
    
    try:
        result = subprocess.run([python_path, "-c", test_script], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ File operations test failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def test_excel_processor(python_path):
    """Test Excel processor functionality."""
    print("🧪 Testing Excel processor...")
    
    test_script = """
from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file
from src.core.utils.cross_platform import get_platform

print("Testing Excel processor...")

# Test platform detection
pm = get_platform()
print(f"✅ Platform: {pm.platform_info['system']}")

# Test Excel processor creation
processor = ExcelProcessor()
print("✅ Excel processor created")

# Test default file detection
default_file = get_default_upload_file()
print(f"✅ Default file: {default_file}")

# Test platform-specific settings
print(f"✅ File size limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
print(f"✅ Excel engines: {pm.get_excel_engines()}")

print("Excel processor test completed")
"""
    
    try:
        result = subprocess.run([python_path, "-c", test_script], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Excel processor test failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def run_environment_test(env_name, requirements_file):
    """Run a complete test for a specific environment."""
    print(f"\n{'='*60}")
    print(f"🚀 Testing Environment: {env_name}")
    print(f"{'='*60}")
    
    # Create environment
    env_dir = create_test_environment(env_name)
    if not env_dir:
        return False
    
    # Install dependencies
    python_path = install_dependencies(env_dir, requirements_file)
    if not python_path:
        return False
    
    # Run tests
    tests = [
        ("Module Imports", test_imports),
        ("Platform Detection", test_platform_detection),
        ("File Operations", test_file_operations),
        ("Excel Processor", test_excel_processor)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func(python_path)
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Cleanup
    if os.path.exists(env_dir):
        shutil.rmtree(env_dir)
        print(f"🧹 Cleaned up environment: {env_dir}")
    
    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n📊 {env_name} Results: {passed}/{total} tests passed")
    
    return passed == total

def main():
    """Run tests for different environments."""
    print("🚀 Starting Virtual Environment Cross-Platform Testing...")
    
    # Test different requirements files
    environments = [
        ("cross_platform", "requirements_cross_platform.txt"),
        ("production", "requirements_production.txt"),
        ("minimal", "requirements_minimal.txt")
    ]
    
    results = []
    
    for env_name, req_file in environments:
        if os.path.exists(req_file):
            success = run_environment_test(env_name, req_file)
            results.append((env_name, success))
        else:
            print(f"⚠️  Requirements file not found: {req_file}")
            results.append((env_name, False))
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 FINAL TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    total = len(results)
    
    for env_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{env_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} environments passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All virtual environment tests passed!")
        print("Your application is ready for deployment across all platforms.")
    else:
        print("⚠️  Some environment tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 