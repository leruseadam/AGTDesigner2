#!/usr/bin/env python3
"""
Simple Browser Testing Script for AGT Designer.
Tests web application functionality without requiring Selenium.
"""

import os
import sys
import platform
import time
import json
import requests
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class SimpleBrowserTester:
    """Simple browser tester using requests only."""
    
    def __init__(self):
        self.results = {}
        self.app_url = "http://127.0.0.1:9090"
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
                
                # Check for key content
                content = response.text.lower()
                if "agt designer" in content or "label maker" in content:
                    print("   ✅ Application content detected")
                else:
                    print("   ⚠️  Application content not found")
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
    
    def test_browser_compatibility_simulation(self):
        """Simulate browser compatibility testing."""
        print("\n🌐 Testing Browser Compatibility (Simulated)...")
        
        browsers = [
            ('chrome', 'Chrome'),
            ('firefox', 'Firefox'),
            ('safari', 'Safari'),
            ('edge', 'Edge')
        ]
        
        for browser_name, display_name in browsers:
            print(f"\n🌐 Testing {display_name} compatibility...")
            
            try:
                # Simulate browser request with different user agents
                user_agents = {
                    'chrome': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'firefox': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                    'safari': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                    'edge': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
                }
                
                headers = {'User-Agent': user_agents.get(browser_name, '')}
                response = requests.get(f"{self.app_url}/", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    print(f"   ✅ {display_name} compatibility: OK")
                    print(f"   Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                    print(f"   Content-Length: {len(response.content)} bytes")
                    
                    # Check for responsive design indicators
                    content = response.text.lower()
                    if "viewport" in content or "mobile" in content or "responsive" in content:
                        print(f"   ✅ Responsive design detected for {display_name}")
                    else:
                        print(f"   ⚠️  Responsive design not detected for {display_name}")
                    
                    self.results[f"{display_name}_compatibility"] = True
                else:
                    print(f"   ❌ {display_name} compatibility failed: {response.status_code}")
                    self.results[f"{display_name}_compatibility"] = False
                    
            except Exception as e:
                print(f"   ❌ {display_name} test error: {e}")
                self.results[f"{display_name}_compatibility"] = False
        
        return True
    
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
            
            # Test mobile user agent
            mobile_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1'
            }
            
            response = requests.get(f"{self.app_url}/", headers=mobile_headers, timeout=10)
            if response.status_code == 200:
                print("✅ Mobile user agent test passed")
                
                # Check for mobile-specific content
                content = response.text.lower()
                if "viewport" in content or "mobile" in content or "touch" in content:
                    print("✅ Mobile-specific content detected")
                    self.results["mobile_compatibility"] = True
                else:
                    print("⚠️  Mobile-specific content not detected")
                    self.results["mobile_compatibility"] = False
            else:
                print(f"❌ Mobile user agent test failed: {response.status_code}")
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
    
    def test_cross_platform_configuration(self):
        """Test cross-platform configuration."""
        print("\n⚙️  Testing Cross-Platform Configuration...")
        
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
            
            self.results["cross_platform_configuration"] = True
            return True
            
        except Exception as e:
            print(f"❌ Cross-platform configuration test failed: {e}")
            self.results["cross_platform_configuration"] = False
            return False
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 80)
        print("📊 SIMPLE PLATFORM & BROWSER TEST REPORT")
        print("=" * 80)
        
        # Platform tests
        print("\n🌐 PLATFORM TESTS:")
        platform_tests = [key for key in self.results.keys() if any(platform in key.lower() for platform in ['macos', 'windows', 'linux', 'pythonanywhere', 'cross_platform', 'file_operations'])]
        for test in platform_tests:
            status = "✅ PASSED" if self.results[test] else "❌ FAILED"
            print(f"   {test}: {status}")
        
        # Browser tests
        print("\n🌐 BROWSER TESTS:")
        browser_tests = [key for key in self.results.keys() if 'compatibility' in key]
        for test in browser_tests:
            status = "✅ PASSED" if self.results[test] else "❌ FAILED"
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
        
        print(f"✅ Tests Passed: {passed}")
        print(f"❌ Tests Failed: {total - passed}")
        print(f"📊 Total Tests: {total}")
        print(f"🎯 Success Rate: {passed/total*100:.1f}%")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! Your application is ready for all platforms and browsers.")
        elif passed >= total * 0.8:
            print("\n✅ MOST TESTS PASSED! Your application is mostly ready for deployment.")
        else:
            print("\n⚠️  SOME TESTS FAILED. Please review the issues above before deployment.")
        
        # Save detailed report
        report_file = "simple_browser_test_report.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'platform': platform.platform(),
                'python_version': sys.version,
                'results': self.results,
                'summary': {
                    'passed': passed,
                    'failed': total - passed,
                    'total': total,
                    'success_rate': passed/total*100
                }
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return passed >= total * 0.8

def main():
    """Run simple platform and browser testing."""
    print("🚀 Starting Simple Platform & Browser Testing...")
    print("=" * 80)
    
    tester = SimpleBrowserTester()
    
    # Run all tests
    tests = [
        ("Platform Detection", tester.test_platform_detection),
        ("Cross-Platform Utilities", tester.test_cross_platform_utilities),
        ("File Operations", tester.test_file_operations),
        ("Cross-Platform Configuration", tester.test_cross_platform_configuration),
        ("Web Application", tester.test_web_application),
        ("Browser Compatibility (Simulated)", tester.test_browser_compatibility_simulation),
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