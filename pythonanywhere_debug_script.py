#!/usr/bin/env python3
"""
PythonAnywhere Debug Script
Run this script on PythonAnywhere to diagnose loading issues.
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/pythonanywhere_debug.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Run PythonAnywhere diagnostics."""
    logger.info("🚀 PythonAnywhere Debug Script")
    logger.info("=" * 50)
    
    # 1. Environment Check
    logger.info("1. Environment Check:")
    logger.info(f"   Python version: {sys.version}")
    logger.info(f"   Current directory: {os.getcwd()}")
    logger.info(f"   Home directory: {os.path.expanduser('~')}")
    
    # Check PythonAnywhere indicators
    pythonanywhere_indicators = [
        'PYTHONANYWHERE_SITE' in os.environ,
        'PYTHONANYWHERE_DOMAIN' in os.environ,
        os.path.exists('/var/log/pythonanywhere'),
        'pythonanywhere.com' in os.environ.get('HTTP_HOST', ''),
        os.path.exists('/home/adamcordova'),
        'pythonanywhere' in os.getcwd().lower()
    ]
    
    is_pythonanywhere = any(pythonanywhere_indicators)
    logger.info(f"   PythonAnywhere detected: {is_pythonanywhere}")
    
    # 2. File System Check
    logger.info("\n2. File System Check:")
    
    # Check common directories
    directories = [
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
    
    for directory in directories:
        if os.path.exists(directory):
            logger.info(f"   ✅ {directory} exists")
            if os.access(directory, os.R_OK):
                logger.info(f"   ✅ {directory} readable")
            else:
                logger.error(f"   ❌ {directory} not readable")
        else:
            logger.error(f"   ❌ {directory} does not exist")
    
    # 3. File Check
    logger.info("\n3. File Check:")
    
    # Check for Excel files
    uploads_dir = "./uploads"
    if os.path.exists(uploads_dir):
        try:
            files = os.listdir(uploads_dir)
            excel_files = [f for f in files if f.lower().endswith('.xlsx')]
            logger.info(f"   Excel files in uploads: {excel_files}")
            
            for excel_file in excel_files:
                file_path = os.path.join(uploads_dir, excel_file)
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    logger.info(f"   ✅ {excel_file}: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
                    if os.access(file_path, os.R_OK):
                        logger.info(f"   ✅ {excel_file} readable")
                    else:
                        logger.error(f"   ❌ {excel_file} not readable")
                else:
                    logger.error(f"   ❌ {excel_file} does not exist")
        except Exception as e:
            logger.error(f"   ❌ Error listing uploads directory: {e}")
    else:
        logger.error(f"   ❌ Uploads directory does not exist: {uploads_dir}")
    
    # Check default inventory file
    default_inventory = "./data/default_inventory.xlsx"
    if os.path.exists(default_inventory):
        file_size = os.path.getsize(default_inventory)
        logger.info(f"   ✅ Default inventory exists: {file_size} bytes ({file_size / (1024*1024):.2f} MB)")
        if os.access(default_inventory, os.R_OK):
            logger.info(f"   ✅ Default inventory readable")
        else:
            logger.error(f"   ❌ Default inventory not readable")
    else:
        logger.error(f"   ❌ Default inventory does not exist")
    
    # 4. Import Check
    logger.info("\n4. Import Check:")
    
    required_modules = [
        'flask',
        'pandas', 
        'numpy',
        'docx',
        'docxtpl',
        'openpyxl',
        'PIL'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"   ✅ {module} imported successfully")
        except ImportError as e:
            logger.error(f"   ❌ {module} import failed: {e}")
    
    # 5. ExcelProcessor Test
    logger.info("\n5. ExcelProcessor Test:")
    
    try:
        # Add current directory to path
        sys.path.insert(0, os.getcwd())
        
        from src.core.data.excel_processor import ExcelProcessor, get_default_upload_file
        
        # Test initialization
        logger.info("   Testing ExcelProcessor initialization...")
        processor = ExcelProcessor()
        logger.info("   ✅ ExcelProcessor initialized")
        
        # Test get_default_upload_file
        logger.info("   Testing get_default_upload_file...")
        default_file = get_default_upload_file()
        if default_file:
            logger.info(f"   ✅ Default file found: {default_file}")
            
            if os.path.exists(default_file):
                logger.info(f"   ✅ Default file exists")
                if os.access(default_file, os.R_OK):
                    logger.info(f"   ✅ Default file readable")
                    
                    # Test fast_load_file
                    logger.info("   Testing fast_load_file...")
                    success = processor.fast_load_file(default_file)
                    if success:
                        logger.info(f"   ✅ File loaded successfully")
                        logger.info(f"   ✅ DataFrame shape: {processor.df.shape if processor.df is not None else 'None'}")
                        
                        # Test get_available_tags
                        logger.info("   Testing get_available_tags...")
                        tags = processor.get_available_tags()
                        logger.info(f"   ✅ Available tags count: {len(tags)}")
                        
                        if tags:
                            logger.info(f"   ✅ First tag: {tags[0].get('Product Name*', 'N/A')}")
                        else:
                            logger.warning("   ⚠️ No tags found")
                    else:
                        logger.error("   ❌ File loading failed")
                else:
                    logger.error("   ❌ Default file not readable")
            else:
                logger.error("   ❌ Default file does not exist")
        else:
            logger.warning("   ⚠️ No default file found")
            
    except Exception as e:
        logger.error(f"   ❌ ExcelProcessor test failed: {e}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
    
    # 6. Memory Check
    logger.info("\n6. Memory Check:")
    
    try:
        import psutil
        memory = psutil.virtual_memory()
        logger.info(f"   Total memory: {memory.total / (1024**3):.2f} GB")
        logger.info(f"   Available memory: {memory.available / (1024**3):.2f} GB")
        logger.info(f"   Memory usage: {memory.percent:.1f}%")
        
        # Test memory allocation
        try:
            import numpy as np
            test_array = np.zeros((100, 100), dtype=np.float64)
            logger.info("   ✅ Memory allocation test successful")
            del test_array
        except Exception as e:
            logger.error(f"   ❌ Memory allocation test failed: {e}")
            
    except ImportError:
        logger.warning("   ⚠️ psutil not available for memory monitoring")
    
    # 7. Template Files Check
    logger.info("\n7. Template Files Check:")
    
    template_files = [
        "src/core/generation/templates/horizontal.docx",
        "src/core/generation/templates/vertical.docx", 
        "src/core/generation/templates/mini.docx",
        "src/core/generation/templates/Double.docx"
    ]
    
    for template_file in template_files:
        if os.path.exists(template_file):
            file_size = os.path.getsize(template_file)
            logger.info(f"   ✅ {template_file}: {file_size} bytes")
        else:
            logger.error(f"   ❌ {template_file} does not exist")
    
    # 8. Cross-Platform Test
    logger.info("\n8. Cross-Platform Test:")
    
    try:
        from src.core.utils.cross_platform import get_platform
        
        pm = get_platform()
        logger.info(f"   ✅ Platform manager created")
        logger.info(f"   ✅ Platform: {pm.platform_info.get('system', 'Unknown')}")
        logger.info(f"   ✅ Is PythonAnywhere: {pm.platform_info.get('is_pythonanywhere', False)}")
        
        uploads_dir = pm.get_path('uploads_dir')
        logger.info(f"   ✅ Uploads directory: {uploads_dir}")
        
    except Exception as e:
        logger.error(f"   ❌ Cross-platform test failed: {e}")
    
    # 9. Recommendations
    logger.info("\n9. Recommendations:")
    
    if not is_pythonanywhere:
        logger.info("   ⚠️ Not detected as PythonAnywhere - check environment")
    
    # Check if we have any Excel files
    if os.path.exists("./uploads"):
        files = os.listdir("./uploads")
        excel_files = [f for f in files if f.lower().endswith('.xlsx')]
        if not excel_files:
            logger.info("   ⚠️ No Excel files found in uploads directory")
            logger.info("   💡 Upload an Excel file through the web interface")
    
    # Check if default inventory exists
    if not os.path.exists("./data/default_inventory.xlsx"):
        logger.info("   ⚠️ Default inventory file not found")
        logger.info("   💡 Copy an Excel file to ./data/default_inventory.xlsx")
    
    logger.info("\n" + "=" * 50)
    logger.info("🔍 Debug complete! Check /tmp/pythonanywhere_debug.log for details")
    logger.info("📧 Share the log file content for further assistance")

if __name__ == "__main__":
    main() 