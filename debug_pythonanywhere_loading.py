#!/usr/bin/env python3
"""
PythonAnywhere Loading Diagnostic Script
This script helps identify why the PythonAnywhere version is failing to load items
while the local version works correctly.
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pythonanywhere_debug.log')
    ]
)
logger = logging.getLogger(__name__)

def test_environment():
    """Test the current environment and detect PythonAnywhere."""
    logger.info("=== Environment Detection ===")
    
    # Check if we're on PythonAnywhere
    pythonanywhere_indicators = [
        'PYTHONANYWHERE_SITE' in os.environ,
        'PYTHONANYWHERE_DOMAIN' in os.environ,
        os.path.exists('/var/log/pythonanywhere'),
        'pythonanywhere.com' in os.environ.get('HTTP_HOST', ''),
        os.path.exists('/home/adamcordova'),
        'pythonanywhere' in os.getcwd().lower()
    ]
    
    is_pythonanywhere = any(pythonanywhere_indicators)
    logger.info(f"PythonAnywhere detected: {is_pythonanywhere}")
    
    # Check Python version
    logger.info(f"Python version: {sys.version}")
    
    # Check current working directory
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # Check environment variables
    logger.info(f"FLASK_ENV: {os.environ.get('FLASK_ENV', 'Not set')}")
    logger.info(f"DEVELOPMENT_MODE: {os.environ.get('DEVELOPMENT_MODE', 'Not set')}")
    
    return is_pythonanywhere

def test_imports():
    """Test if all required modules can be imported."""
    logger.info("=== Import Testing ===")
    
    required_modules = [
        'flask',
        'pandas',
        'numpy',
        'docx',
        'docxtpl',
        'openpyxl',
        'PIL',
        'watchdog'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✅ {module} imported successfully")
        except ImportError as e:
            logger.error(f"❌ {module} import failed: {e}")

def test_file_paths():
    """Test file paths and permissions."""
    logger.info("=== File Path Testing ===")
    
    # Test common paths
    test_paths = [
        ".",
        "./uploads",
        "./data",
        "./static",
        "./templates",
        "./src",
        "./src/core",
        "./src/core/data",
        "./src/core/generation",
        "./src/core/generation/templates"
    ]
    
    for path in test_paths:
        if os.path.exists(path):
            logger.info(f"✅ Path exists: {path}")
            if os.access(path, os.R_OK):
                logger.info(f"✅ Path readable: {path}")
            else:
                logger.error(f"❌ Path not readable: {path}")
        else:
            logger.error(f"❌ Path does not exist: {path}")

def test_excel_processor():
    """Test the ExcelProcessor class."""
    logger.info("=== ExcelProcessor Testing ===")
    
    try:
        from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file
        
        # Test ExcelProcessor initialization
        logger.info("Testing ExcelProcessor initialization...")
        processor = ExcelProcessor()
        logger.info("✅ ExcelProcessor initialized successfully")
        
        # Test get_default_upload_file
        logger.info("Testing get_default_upload_file...")
        default_file = get_default_upload_file()
        if default_file:
            logger.info(f"✅ Default file found: {default_file}")
            
            # Test if file exists and is readable
            if os.path.exists(default_file):
                logger.info(f"✅ Default file exists: {default_file}")
                if os.access(default_file, os.R_OK):
                    logger.info(f"✅ Default file readable: {default_file}")
                    
                    # Test file size
                    file_size = os.path.getsize(default_file)
                    logger.info(f"✅ Default file size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
                else:
                    logger.error(f"❌ Default file not readable: {default_file}")
            else:
                logger.error(f"❌ Default file does not exist: {default_file}")
        else:
            logger.warning("⚠️ No default file found")
        
        return processor
        
    except Exception as e:
        logger.error(f"❌ ExcelProcessor test failed: {e}")
        logger.error(traceback.format_exc())
        return None

def test_file_loading(processor):
    """Test file loading functionality."""
    logger.info("=== File Loading Testing ===")
    
    if not processor:
        logger.error("❌ Cannot test file loading - processor not available")
        return False
    
    # Test get_default_upload_file again
    from src.core.data.excel_processor import get_default_upload_file
    default_file = get_default_upload_file()
    
    if not default_file:
        logger.error("❌ No default file available for testing")
        return False
    
    # Test fast_load_file
    logger.info(f"Testing fast_load_file with: {default_file}")
    try:
        success = processor.fast_load_file(default_file)
        if success:
            logger.info("✅ fast_load_file successful")
            logger.info(f"✅ DataFrame shape: {processor.df.shape if processor.df is not None else 'None'}")
            logger.info(f"✅ DataFrame columns: {list(processor.df.columns) if processor.df is not None else 'None'}")
            return True
        else:
            logger.error("❌ fast_load_file failed")
            return False
    except Exception as e:
        logger.error(f"❌ fast_load_file exception: {e}")
        logger.error(traceback.format_exc())
        return False

def test_available_tags(processor):
    """Test getting available tags."""
    logger.info("=== Available Tags Testing ===")
    
    if not processor or processor.df is None:
        logger.error("❌ Cannot test available tags - no data loaded")
        return False
    
    try:
        tags = processor.get_available_tags()
        logger.info(f"✅ Available tags count: {len(tags)}")
        
        if tags:
            logger.info(f"✅ First few tags: {tags[:3]}")
        else:
            logger.warning("⚠️ No available tags found")
        
        return True
    except Exception as e:
        logger.error(f"❌ Available tags test failed: {e}")
        logger.error(traceback.format_exc())
        return False

def test_cross_platform():
    """Test cross-platform utilities."""
    logger.info("=== Cross-Platform Testing ===")
    
    try:
        from src.core.utils.cross_platform import get_platform, platform_manager
        
        # Test platform detection
        pm = get_platform()
        logger.info(f"✅ Platform manager created")
        logger.info(f"✅ Platform info: {pm.platform_info}")
        
        # Test path detection
        uploads_dir = pm.get_path('uploads_dir')
        logger.info(f"✅ Uploads directory: {uploads_dir}")
        
        # Test if uploads directory exists
        if os.path.exists(uploads_dir):
            logger.info(f"✅ Uploads directory exists: {uploads_dir}")
            files = os.listdir(uploads_dir)
            logger.info(f"✅ Files in uploads: {files}")
        else:
            logger.error(f"❌ Uploads directory does not exist: {uploads_dir}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Cross-platform test failed: {e}")
        logger.error(traceback.format_exc())
        return False

def test_template_files():
    """Test template file accessibility."""
    logger.info("=== Template Files Testing ===")
    
    template_files = [
        "src/core/generation/templates/horizontal.docx",
        "src/core/generation/templates/vertical.docx",
        "src/core/generation/templates/mini.docx",
        "src/core/generation/templates/Double.docx",
        "src/core/generation/templates/inventory.docx"
    ]
    
    for template_file in template_files:
        if os.path.exists(template_file):
            logger.info(f"✅ Template exists: {template_file}")
            if os.access(template_file, os.R_OK):
                logger.info(f"✅ Template readable: {template_file}")
                file_size = os.path.getsize(template_file)
                logger.info(f"✅ Template size: {file_size} bytes")
            else:
                logger.error(f"❌ Template not readable: {template_file}")
        else:
            logger.error(f"❌ Template does not exist: {template_file}")

def test_memory_usage():
    """Test memory usage and limits."""
    logger.info("=== Memory Usage Testing ===")
    
    try:
        import psutil
        memory = psutil.virtual_memory()
        logger.info(f"✅ Total memory: {memory.total / (1024**3):.2f} GB")
        logger.info(f"✅ Available memory: {memory.available / (1024**3):.2f} GB")
        logger.info(f"✅ Memory usage: {memory.percent:.1f}%")
        
        # Test if we can allocate a reasonable amount of memory
        try:
            import numpy as np
            test_array = np.zeros((1000, 1000), dtype=np.float64)
            logger.info("✅ Memory allocation test successful")
            del test_array
        except Exception as e:
            logger.error(f"❌ Memory allocation test failed: {e}")
            
    except ImportError:
        logger.warning("⚠️ psutil not available for memory monitoring")

def main():
    """Run all diagnostic tests."""
    logger.info("🚀 Starting PythonAnywhere Loading Diagnostics")
    logger.info("=" * 60)
    
    # Run all tests
    tests = [
        ("Environment", test_environment),
        ("Imports", test_imports),
        ("File Paths", test_file_paths),
        ("Cross-Platform", test_cross_platform),
        ("Template Files", test_template_files),
        ("Memory Usage", test_memory_usage),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} Test ---")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Test ExcelProcessor and file loading
    logger.info(f"\n--- ExcelProcessor Test ---")
    processor = test_excel_processor()
    if processor:
        results["ExcelProcessor"] = True
        results["File Loading"] = test_file_loading(processor)
        results["Available Tags"] = test_available_tags(processor)
    else:
        results["ExcelProcessor"] = False
        results["File Loading"] = False
        results["Available Tags"] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("\n🎉 All tests passed! The issue might be elsewhere.")
    else:
        logger.info("\n⚠️ Some tests failed. Check the logs above for details.")
    
    # Recommendations
    logger.info("\n" + "=" * 60)
    logger.info("💡 RECOMMENDATIONS")
    logger.info("=" * 60)
    
    if not results.get("Environment", False):
        logger.info("• Check if you're running on PythonAnywhere")
        logger.info("• Verify environment variables are set correctly")
    
    if not results.get("Imports", False):
        logger.info("• Install missing dependencies")
        logger.info("• Check virtual environment activation")
    
    if not results.get("File Paths", False):
        logger.info("• Check file permissions")
        logger.info("• Ensure all required directories exist")
    
    if not results.get("ExcelProcessor", False):
        logger.info("• Check ExcelProcessor initialization")
        logger.info("• Verify all required modules are available")
    
    if not results.get("File Loading", False):
        logger.info("• Check if default file exists and is accessible")
        logger.info("• Verify file format is supported")
        logger.info("• Check memory constraints")
    
    if not results.get("Available Tags", False):
        logger.info("• Check if data was loaded correctly")
        logger.info("• Verify DataFrame structure")
    
    logger.info("\n🔍 For more detailed debugging:")
    logger.info("• Check the pythonanywhere_debug.log file")
    logger.info("• Review PythonAnywhere error logs")
    logger.info("• Test with a smaller file first")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 