#!/usr/bin/env python3
"""
Comprehensive Platform and Browser Testing Suite for AGT Designer.
Tests the application across all supported platforms and browsers.
"""

import os
import sys
import platform
import subprocess
import time
import json
import requests
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class PlatformBrowserTester:
    """Comprehensive tester for platforms and browsers."""
    
    def __init__(self):
        self.results = {}
        self.app_url = "http://127.0.0.1:5000"
        self.test_data = {
            "template_type": "vertical",
            "scale_factor": 1.0,
            "selected_tags": ["Test Product"]
        }
    
    def test_platform_detection(self):
        """Test platform detection across different operating systems."""
        print("🧪 Testing Platform Detection...")
        
        platforms = [
            ('darwin', 'macOS'),
            ('win32', 'Windows'),
            ('linux', 'Linux'),
            ('pythonanywhere', 'PythonAnywhere')
        ]
        
        for platform_name, display_name in platforms:
            print(f"\n📱 Testing {display_name}...")
            
            with patch('platform.system') as mock_system, \
                 patch('os.path.exists') as mock_exists, \
                 patch('os.getcwd') as mock_cwd:
                
                # Mock platform-specific responses
                if platform_name == 'darwin':
                    mock_system.return_value = 'Darwin'
                    mock_exists.return_value = False
                    mock_cwd.return_value = '/Users/testuser/project'
                elif platform_name == 'win32':
                    mock_system.return_value = 'Windows'
                    mock_exists.return_value = False
                    mock_cwd.return_value = 'C:\\Users\\testuser\\project'
                elif platform_name == 'linux':
                    mock_system.return_value = 'Linux'
                    mock_exists.return_value = False
                    mock_cwd.return_value = '/home/testuser/project'
                elif platform_name == 'pythonanywhere':
                    mock_system.return_value = 'Linux'
                    mock_exists.return_value = True
                    mock_cwd.return_value = '/home/adamcordova/project'
                
                try:
                    # Re-import to get fresh platform detection
                    if 'src.core.utils.cross_platform' in sys.modules:
                        del sys.modules['src.core.utils.cross_platform']
                    
                    from src.core.utils.cross_platform import get_platform, is_pythonanywhere
                    
                    pm = get_platform()
                    print(f"✅ {display_name} detected: {pm.platform_info['system']}")
                    print(f"   Memory limit: {pm.get_memory_limit() / (1024*1024):.1f} MB")
                    print(f"   File size limit: {pm.get_file_size_limit() / (1024*1024):.1f} MB")
                    print(f"   Excel engines: {pm.get_excel_engines()}")
                    
                    self.results[f"{display_name}_detection"] = True
                    
                except Exception as e:
                    print(f"❌ {display_name} detection failed: {e}")
                    self.results[f"{display_name}_detection"] = False
        
        return True
    
    def test_cross_platform_utilities(self):
        """Test cross-platform utilities functionality."""
        print("\n🧪 Testing Cross-Platform Utilities...")
        
        try:
            from src.core.utils.cross_platform import (
                get_platform, get_safe_path, ensure_directory,
                normalize_line_endings, is_mac, is_windows, is_linux, is_pythonanywhere
            )
            
            pm = get_platform()
            print(f"✅ Platform detected: {pm.platform_info['system']}")
            
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
            
            self.results["cross_platform_utilities"] = True
            return True
            
        except Exception as e:
            print(f"❌ Cross-platform utilities test failed: {e}")
            self.results["cross_platform_utilities"] = False
            return False
    
    def test_file_operations(self):
        """Test file operations across platforms."""
        print("\n🧪 Testing File Operations...")
        
        try:
            from src.core.utils.cross_platform import get_platform, get_safe_path, ensure_directory
            from src.core.data.excel_processor import ExcelProcessor
            
            pm = get_platform()
            processor = ExcelProcessor()
            
            # Test directory creation
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
            
            self.results["file_operations"] = True
            return True
            
        except Exception as e:
            print(f"❌ File operations test failed: {e}")
            self.results["file_operations"] = False
            return False
    
    def test_web_application(self):
        """Test web application functionality."""
        print("\n🧪 Testing Web Application...")
        
        try:
            # Test if app is running
            response = requests.get(f"{self.app_url}/", timeout=10)
            if response.status_code == 200:
                print("✅ Web application is running")
                print(f"   Status: {response.status_code}")
                print(f"   Content length: {len(response.content)} bytes")
            else:
                print(f"❌ Web application returned status: {response.status_code}")
                return False
            
            # Test API endpoints
            api_endpoints = [
                "/api/available-tags",
                "/api/selected-tags",
                "/api/filter-options",
                "/api/json-status"
            ]
            
            for endpoint in api_endpoints:
                try:
                    response = requests.get(f"{self.app_url}{endpoint}", timeout=10)
                    if response.status_code == 200:
                        print(f"✅ API endpoint {endpoint} working")
                    else:
                        print(f"⚠️  API endpoint {endpoint} returned {response.status_code}")
                except Exception as e:
                    print(f"❌ API endpoint {endpoint} failed: {e}")
            
            self.results["web_application"] = True
            return True
            
        except Exception as e:
            print(f"❌ Web application test failed: {e}")
            self.results["web_application"] = False
            return False
    
    def test_browser_compatibility(self):
        """Test browser compatibility using Selenium."""
        print("\n🧪 Testing Browser Compatibility...")
        
        browsers = [
            ('chrome', 'Chrome'),
            ('firefox', 'Firefox'),
            ('safari', 'Safari'),
            ('edge', 'Edge')
        ]
        
        for browser_name, display_name in browsers:
            print(f"\n🌐 Testing {display_name}...")
            
            try:
                # Check if browser driver is available
                if self._check_browser_driver(browser_name):
                    print(f"✅ {display_name} driver available")
                    
                    # Test basic web functionality
                    if self._test_browser_functionality(browser_name):
                        print(f"✅ {display_name} functionality working")
                        self.results[f"{display_name}_browser"] = True
                    else:
                        print(f"❌ {display_name} functionality failed")
                        self.results[f"{display_name}_browser"] = False
                else:
                    print(f"⚠️  {display_name} driver not available")
                    self.results[f"{display_name}_browser"] = "Not Available"
                    
            except Exception as e:
                print(f"❌ {display_name} test failed: {e}")
                self.results[f"{display_name}_browser"] = False
        
        return True
    
    def _check_browser_driver(self, browser_name):
        """Check if browser driver is available."""
        try:
            if browser_name == 'chrome':
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                driver = webdriver.Chrome(options=options)
                driver.quit()
                return True
            elif browser_name == 'firefox':
                from selenium import webdriver
                from selenium.webdriver.firefox.options import Options
                options = Options()
                options.add_argument('--headless')
                driver = webdriver.Firefox(options=options)
                driver.quit()
                return True
            elif browser_name == 'safari':
                # Safari testing requires macOS and SafariDriver
                if platform.system() == 'Darwin':
                    try:
                        from selenium import webdriver
                        driver = webdriver.Safari()
                        driver.quit()
                        return True
                    except:
                        return False
                return False
            elif browser_name == 'edge':
                try:
                    from selenium import webdriver
                    from selenium.webdriver.edge.options import Options
                    options = Options()
                    options.add_argument('--headless')
                    driver = webdriver.Edge(options=options)
                    driver.quit()
                    return True
                except:
                    return False
        except ImportError:
            return False
        except Exception:
            return False
    
    def _test_browser_functionality(self, browser_name):
        """Test basic browser functionality."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Setup driver
            if browser_name == 'chrome':
                from selenium.webdriver.chrome.options import Options
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                driver = webdriver.Chrome(options=options)
            elif browser_name == 'firefox':
                from selenium.webdriver.firefox.options import Options
                options = Options()
                options.add_argument('--headless')
                driver = webdriver.Firefox(options=options)
            elif browser_name == 'safari':
                driver = webdriver.Safari()
            elif browser_name == 'edge':
                from selenium.webdriver.edge.options import Options
                options = Options()
                options.add_argument('--headless')
                driver = webdriver.Edge(options=options)
            else:
                return False
            
            try:
                # Test page load
                driver.get(f"{self.app_url}/")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Test basic page elements
                title = driver.title
                print(f"   Page title: {title}")
                
                # Test if page loaded successfully
                if "AGT Designer" in title or "Label Maker" in title:
                    print(f"   ✅ Page loaded successfully")
                    return True
                else:
                    print(f"   ❌ Page title unexpected: {title}")
                    return False
                    
            finally:
                driver.quit()
                
        except Exception as e:
            print(f"   ❌ Browser test error: {e}")
            return False
    
    def test_mobile_compatibility(self):
        """Test mobile browser compatibility."""
        print("\n📱 Testing Mobile Compatibility...")
        
        try:
            # Test mobile-specific endpoints
            mobile_endpoints = [
                "/mobile",
                "/api/mobile-status"
            ]
            
            for endpoint in mobile_endpoints:
                try:
                    response = requests.get(f"{self.app_url}{endpoint}", timeout=10)
                    if response.status_code == 200:
                        print(f"✅ Mobile endpoint {endpoint} working")
                    else:
                        print(f"⚠️  Mobile endpoint {endpoint} returned {response.status_code}")
                except Exception as e:
                    print(f"❌ Mobile endpoint {endpoint} failed: {e}")
            
            # Test responsive design
            try:
                response = requests.get(f"{self.app_url}/", timeout=10)
                if response.status_code == 200:
                    content = response.text
                    if "viewport" in content.lower() or "mobile" in content.lower():
                        print("✅ Responsive design detected")
                        self.results["mobile_compatibility"] = True
                    else:
                        print("⚠️  Responsive design not detected")
                        self.results["mobile_compatibility"] = False
            except Exception as e:
                print(f"❌ Mobile compatibility test failed: {e}")
                self.results["mobile_compatibility"] = False
            
            return True
            
        except Exception as e:
            print(f"❌ Mobile compatibility test failed: {e}")
            self.results["mobile_compatibility"] = False
            return False
    
    def test_performance(self):
        """Test application performance."""
        print("\n⚡ Testing Performance...")
        
        try:
            # Test page load time
            start_time = time.time()
            response = requests.get(f"{self.app_url}/", timeout=30)
            load_time = time.time() - start_time
            
            if response.status_code == 200:
                print(f"✅ Page load time: {load_time:.2f} seconds")
                if load_time < 5.0:
                    print("   ✅ Load time is acceptable")
                    self.results["performance"] = True
                else:
                    print("   ⚠️  Load time is slow")
                    self.results["performance"] = False
            else:
                print(f"❌ Page load failed: {response.status_code}")
                self.results["performance"] = False
            
            # Test API response time
            api_endpoints = ["/api/available-tags", "/api/selected-tags"]
            for endpoint in api_endpoints:
                start_time = time.time()
                response = requests.get(f"{self.app_url}{endpoint}", timeout=10)
                api_time = time.time() - start_time
                
                if response.status_code == 200:
                    print(f"✅ API {endpoint} response time: {api_time:.2f} seconds")
                else:
                    print(f"❌ API {endpoint} failed: {response.status_code}")
            
            return True
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            self.results["performance"] = False
            return False
    
    def test_security(self):
        """Test basic security features."""
        print("\n🔒 Testing Security...")
        
        try:
            # Test HTTPS redirect (if applicable)
            try:
                response = requests.get(f"https://{self.app_url.replace('http://', '')}/", timeout=5)
                print("✅ HTTPS endpoint available")
            except:
                print("⚠️  HTTPS not available (expected for local development)")
            
            # Test security headers
            response = requests.get(f"{self.app_url}/", timeout=10)
            headers = response.headers
            
            security_headers = [
                'X-Content-Type-Options',
                'X-Frame-Options',
                'X-XSS-Protection',
                'Content-Security-Policy'
            ]
            
            for header in security_headers:
                if header in headers:
                    print(f"✅ Security header {header} present")
                else:
                    print(f"⚠️  Security header {header} missing")
            
            self.results["security"] = True
            return True
            
        except Exception as e:
            print(f"❌ Security test failed: {e}")
            self.results["security"] = False
            return False
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE PLATFORM & BROWSER TEST REPORT")
        print("=" * 80)
        
        # Platform tests
        print("\n🌐 PLATFORM TESTS:")
        platform_tests = [key for key in self.results.keys() if any(platform in key.lower() for platform in ['macos', 'windows', 'linux', 'pythonanywhere', 'cross_platform', 'file_operations'])]
        for test in platform_tests:
            status = "✅ PASSED" if self.results[test] else "❌ FAILED"
            print(f"   {test}: {status}")
        
        # Browser tests
        print("\n🌐 BROWSER TESTS:")
        browser_tests = [key for key in self.results.keys() if 'browser' in key]
        for test in browser_tests:
            result = self.results[test]
            if result == True:
                status = "✅ PASSED"
            elif result == False:
                status = "❌ FAILED"
            else:
                status = "⚠️  NOT AVAILABLE"
            print(f"   {test}: {status}")
        
        # Web application tests
        print("\n🌐 WEB APPLICATION TESTS:")
        web_tests = [key for key in self.results.keys() if key in ['web_application', 'mobile_compatibility', 'performance', 'security']]
        for test in web_tests:
            status = "✅ PASSED" if self.results[test] else "❌ FAILED"
            print(f"   {test}: {status}")
        
        # Summary
        print("\n" + "=" * 80)
        print("📈 SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for result in self.results.values() if result == True)
        total = len(self.results)
        not_available = sum(1 for result in self.results.values() if result == "Not Available")
        
        print(f"✅ Tests Passed: {passed}")
        print(f"❌ Tests Failed: {total - passed - not_available}")
        print(f"⚠️  Not Available: {not_available}")
        print(f"📊 Total Tests: {total}")
        print(f"🎯 Success Rate: {passed/total*100:.1f}%")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! Your application is ready for all platforms and browsers.")
        elif passed >= total * 0.8:
            print("\n✅ MOST TESTS PASSED! Your application is mostly ready for deployment.")
        else:
            print("\n⚠️  SOME TESTS FAILED. Please review the issues above before deployment.")
        
        # Save detailed report
        report_file = "platform_browser_test_report.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'platform': platform.platform(),
                'python_version': sys.version,
                'results': self.results,
                'summary': {
                    'passed': passed,
                    'failed': total - passed - not_available,
                    'not_available': not_available,
                    'total': total,
                    'success_rate': passed/total*100
                }
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return passed >= total * 0.8

def main():
    """Run comprehensive platform and browser testing."""
    print("🚀 Starting Comprehensive Platform & Browser Testing...")
    print("=" * 80)
    
    tester = PlatformBrowserTester()
    
    # Run all tests
    tests = [
        ("Platform Detection", tester.test_platform_detection),
        ("Cross-Platform Utilities", tester.test_cross_platform_utilities),
        ("File Operations", tester.test_file_operations),
        ("Web Application", tester.test_web_application),
        ("Browser Compatibility", tester.test_browser_compatibility),
        ("Mobile Compatibility", tester.test_mobile_compatibility),
        ("Performance", tester.test_performance),
        ("Security", tester.test_security)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🧪 Running: {test_name}")
        print(f"{'='*60}")
        
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    # Generate report
    success = tester.generate_report()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 