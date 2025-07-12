#!/usr/bin/env python3
"""
Comprehensive performance test script for the Label Maker application.
Tests all major components without requiring the web server.
"""

import time
import sys
import os
import psutil
import gc
from functools import wraps

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def timing_decorator(func_name=None):
    """Decorator to time function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                memory_used = end_memory - start_memory
                name = func_name or func.__name__
                if elapsed > 0.1:  # Log slow operations
                    print(f"⏱️  {name}: {elapsed:.3f}s (Memory: {memory_used:+.1f}MB)")
                else:
                    print(f"✅ {name}: {elapsed:.3f}s (Memory: {memory_used:+.1f}MB)")
        return wrapper
    return decorator

@timing_decorator("Import all core modules")
def import_all_modules():
    """Import all core modules and measure performance."""
    modules = [
        "src.core.data.excel_processor",
        "src.core.data.product_database", 
        "src.core.generation.template_processor",
        "src.core.generation.docx_formatting",
        "src.core.generation.font_sizing",
        "src.core.generation.mini_font_sizing",
        "src.core.generation.text_processing",
        "src.core.formatting.markers",
        "src.core.utils.common",
        "src.core.utils.cross_platform"
    ]
    
    imported_modules = {}
    for module in modules:
        try:
            imported_modules[module] = __import__(module)
        except Exception as e:
            print(f"❌ Failed to import {module}: {e}")
    
    return imported_modules

@timing_decorator("Create ExcelProcessor")
def create_excel_processor():
    """Create ExcelProcessor instance."""
    from src.core.data.excel_processor import ExcelProcessor
    return ExcelProcessor()

@timing_decorator("Load default file")
def load_default_file():
    """Load the default Excel file."""
    from src.core.data.excel_processor import get_default_upload_file, ExcelProcessor
    
    excel_processor = ExcelProcessor()
    default_file = get_default_upload_file()
    if default_file:
        success = excel_processor.load_file(default_file)
        if success:
            print(f"   📊 Loaded {len(excel_processor.df)} rows, {len(excel_processor.df.columns)} columns")
            print(f"   💾 Memory usage: {psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB")
        return success
    return False

@timing_decorator("Create ProductDatabase")
def create_product_database():
    """Create ProductDatabase instance."""
    from src.core.data.product_database import ProductDatabase
    return ProductDatabase()

@timing_decorator("Create TemplateProcessor")
def create_template_processor():
    """Create TemplateProcessor instance."""
    from src.core.generation.template_processor import TemplateProcessor
    return TemplateProcessor("mini", {})  # Use default template type and font scheme

@timing_decorator("Test font sizing")
def test_font_sizing():
    """Test font sizing functionality."""
    from src.core.generation.font_sizing import get_thresholded_font_size
    
    test_cases = [
        ("Short Text", "A"),
        ("Medium Text", "This is a medium length text"),
        ("Long Text", "This is a very long text that should test the font sizing algorithm"),
        ("Very Long Text", "This is an extremely long text that should definitely test the font sizing algorithm with multiple words and characters")
    ]
    
    results = []
    for name, text in test_cases:
        size = get_thresholded_font_size(text, orientation='vertical', scale_factor=1.0, field_type='default')
        results.append((name, size))
    
    return results

@timing_decorator("Test text processing")
def test_text_processing():
    """Test text processing functionality."""
    from src.core.generation.text_processing import clean_text, extract_cannabinoid_content
    
    test_texts = [
        "Test Product 25% THC",
        "CBD Product 500mg",
        "Hybrid Strain - 20% THC, 2% CBD",
        "Simple Product Name"
    ]
    
    results = []
    for text in test_texts:
        cleaned = clean_text(text)
        cannabinoid = extract_cannabinoid_content(text)
        results.append((text, cleaned, cannabinoid))
    
    return results

@timing_decorator("Test template processing")
def test_template_processing():
    """Test template processing functionality."""
    from src.core.generation.template_processor import TemplateProcessor
    
    processor = TemplateProcessor()
    
    # Test template loading
    templates = processor.get_available_templates()
    
    # Test marker extraction
    if templates:
        first_template = list(templates.keys())[0]
        markers = processor.extract_markers(first_template)
        return {
            'templates_found': len(templates),
            'first_template': first_template,
            'markers_found': len(markers) if markers else 0
        }
    
    return {'templates_found': 0}

@timing_decorator("Test cross-platform utilities")
def test_cross_platform():
    """Test cross-platform utilities."""
    from src.core.utils.cross_platform import get_platform_info, ensure_directory
    
    # Test platform detection
    platform_info = get_platform_info()
    
    # Test directory creation
    test_dir = "test_performance_dir"
    ensure_directory(test_dir)
    created = os.path.exists(test_dir)
    
    # Cleanup
    if created:
        os.rmdir(test_dir)
    
    return {
        'platform': platform_info['platform']['system'],
        'directory_creation': created
    }

@timing_decorator("Memory cleanup")
def cleanup_memory():
    """Force garbage collection and measure memory."""
    initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
    gc.collect()
    final_memory = psutil.Process().memory_info().rss / 1024 / 1024
    return initial_memory - final_memory

def main():
    """Main comprehensive performance test function."""
    print("🚀 Starting Comprehensive Performance Test...")
    print("=" * 60)
    
    # Get initial system info
    print(f"\n💻 System Information:")
    print(f"   Platform: {sys.platform}")
    print(f"   Python: {sys.version}")
    print(f"   CPU Cores: {psutil.cpu_count()}")
    print(f"   Memory: {psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB")
    print(f"   Initial Memory Usage: {psutil.Process().memory_info().rss / 1024 / 1024:.1f} MB")
    
    # Test 1: Module imports
    print(f"\n📦 Testing Module Imports:")
    imported_modules = import_all_modules()
    
    # Test 2: Instance creation
    print(f"\n🔧 Testing Instance Creation:")
    excel_processor = create_excel_processor()
    product_db = create_product_database()
    template_processor = create_template_processor()
    
    # Test 3: File loading
    print(f"\n📁 Testing File Loading:")
    load_success = load_default_file()
    
    # Test 4: Core functionality
    print(f"\n⚙️  Testing Core Functionality:")
    font_results = test_font_sizing()
    text_results = test_text_processing()
    template_results = test_template_processing()
    
    # Test 5: Cross-platform utilities
    print(f"\n🌐 Testing Cross-Platform Utilities:")
    cross_platform_results = test_cross_platform()
    
    # Test 6: Memory cleanup
    print(f"\n🧹 Testing Memory Cleanup:")
    memory_freed = cleanup_memory()
    
    # Final memory usage
    final_memory = psutil.Process().memory_info().rss / 1024 / 1024
    
    # Results summary
    print(f"\n" + "=" * 60)
    print(f"📊 PERFORMANCE TEST RESULTS")
    print(f"=" * 60)
    
    print(f"\n✅ Successfully imported {len(imported_modules)} modules")
    print(f"✅ File loading: {'Success' if load_success else 'Failed'}")
    print(f"✅ Font sizing tested: {len(font_results)} cases")
    print(f"✅ Text processing tested: {len(text_results)} cases")
    print(f"✅ Templates found: {template_results.get('templates_found', 0)}")
    print(f"✅ Cross-platform: {cross_platform_results['platform']}")
    
    print(f"\n💾 Memory Usage:")
    print(f"   Final memory usage: {final_memory:.1f} MB")
    print(f"   Memory freed during cleanup: {memory_freed:.1f} MB")
    
    print(f"\n🎯 Performance Recommendations:")
    if final_memory > 200:
        print(f"   ⚠️  High memory usage detected ({final_memory:.1f} MB)")
        print(f"   💡 Consider implementing memory optimization")
    
    if load_success:
        print(f"   ✅ File loading performance is acceptable")
    else:
        print(f"   ❌ File loading failed - check data file")
    
    print(f"\n" + "=" * 60)
    print(f"✅ Comprehensive performance test complete!")

if __name__ == "__main__":
    main() 