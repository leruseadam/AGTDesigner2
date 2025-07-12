# AGT Designer Cross-Platform Guide

## Overview

AGT Designer is now fully cross-platform compatible, providing consistent behavior and performance across:
- **macOS** (10.14+)
- **Windows** (10/11)
- **Linux** (Ubuntu 18.04+, CentOS 7+)
- **PythonAnywhere** (cloud hosting)

## Key Cross-Platform Features

### 1. Automatic Platform Detection
The application automatically detects your platform and optimizes settings accordingly:

```python
from src.core.utils.cross_platform import get_platform

pm = get_platform()
print(f"Platform: {pm.platform_info['system']}")
print(f"Is PythonAnywhere: {pm.is_platform('pythonanywhere')}")
```

### 2. Consistent File Handling
All file paths are normalized for your platform:
- **Windows**: Uses backslashes (`\`)
- **Mac/Linux**: Uses forward slashes (`/`)
- **PythonAnywhere**: Uses platform-agnostic paths

### 3. Platform-Specific Optimizations
- **Memory limits**: Automatically adjusted based on platform capabilities
- **File size limits**: Optimized for each platform's constraints
- **Excel engines**: Platform-specific engine selection
- **Caching**: Platform-appropriate caching strategies

## Installation

### Quick Installation

#### macOS/Linux
```bash
# Make script executable
chmod +x install_cross_platform.sh

# Run installation
./install_cross_platform.sh
```

#### Windows
```batch
# Run installation
install_cross_platform.bat
```

#### Manual Installation
```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements_cross_platform.txt

# 4. Create directories
mkdir -p uploads output logs cache data
```

## Platform-Specific Configuration

### macOS
- **Memory Limit**: 1GB
- **File Size Limit**: 100MB
- **Excel Engines**: openpyxl, xlrd
- **Performance**: Native optimization

### Windows
- **Memory Limit**: 1GB
- **File Size Limit**: 100MB
- **Excel Engines**: openpyxl, xlrd
- **Performance**: Windows-optimized

### Linux
- **Memory Limit**: 1GB
- **File Size Limit**: 100MB
- **Excel Engines**: openpyxl, xlrd
- **Performance**: Linux-optimized

### PythonAnywhere
- **Memory Limit**: 512MB
- **File Size Limit**: 50MB
- **Excel Engines**: openpyxl only
- **Performance**: Cloud-optimized with chunking

## File Path Handling

### Cross-Platform Path Creation
```python
from src.core.utils.cross_platform import get_safe_path

# Creates platform-appropriate paths
file_path = get_safe_path("uploads", "data", "file.xlsx")
```

### Directory Management
```python
from src.core.utils.cross_platform import ensure_directory

# Creates directories with proper permissions
ensure_directory("uploads")
```

## Platform Detection

### Check Current Platform
```python
from src.core.utils.cross_platform import is_mac, is_windows, is_linux, is_pythonanywhere

if is_mac():
    print("Running on macOS")
elif is_windows():
    print("Running on Windows")
elif is_linux():
    print("Running on Linux")
elif is_pythonanywhere():
    print("Running on PythonAnywhere")
```

### Platform Information
```python
from src.core.utils.cross_platform import get_platform

pm = get_platform()
print(f"System: {pm.platform_info['system']}")
print(f"Python Version: {pm.platform_info['python_version']}")
print(f"Is Development: {pm.platform_info['is_development']}")
```

## Configuration

### Cross-Platform Configuration
The application uses `config_cross_platform.py` for platform-specific settings:

```python
from config_cross_platform import get_config

config = get_config()  # Automatically detects environment
app.config.from_object(config)
```

### Environment Variables
Set these environment variables for custom configuration:

```bash
# Development mode
export FLASK_ENV=development

# Production mode
export FLASK_ENV=production

# Custom secret key
export SECRET_KEY=your-secret-key
```

## Performance Optimization

### Memory Management
- **Automatic garbage collection** on memory-intensive operations
- **Chunked file processing** for large files
- **Platform-specific memory limits**

### Caching
- **File caching** for repeated operations
- **Template caching** for faster generation
- **Database caching** for improved performance

### File Processing
- **Streaming uploads** for large files
- **Background processing** for non-blocking operations
- **Progress tracking** for long-running tasks

## Troubleshooting

### Common Issues

#### File Permission Errors
```bash
# macOS/Linux: Fix permissions
chmod -R 755 uploads output logs cache data

# Windows: Run as administrator or check folder permissions
```

#### Memory Issues
```python
# Check memory usage
from src.core.utils.cross_platform import get_platform
pm = get_platform()
print(f"Memory limit: {pm.get_memory_limit() / (1024*1024):.1f} MB")
```

#### Excel Engine Issues
```python
# Check available engines
from src.core.utils.cross_platform import get_platform
pm = get_platform()
print(f"Available Excel engines: {pm.get_excel_engines()}")
```

### Platform-Specific Issues

#### macOS
- **Gatekeeper**: Allow applications from identified developers
- **Python path**: Ensure Python is in PATH
- **Permissions**: Grant necessary permissions to terminal

#### Windows
- **Antivirus**: Add application to antivirus exclusions
- **Python installation**: Use official Python installer
- **Path length**: Use shorter paths if possible

#### Linux
- **Dependencies**: Install system-level dependencies
- **Permissions**: Use appropriate user permissions
- **Python version**: Use Python 3.8+

#### PythonAnywhere
- **File size**: Keep files under 50MB
- **Memory**: Monitor memory usage
- **Packages**: Use whitelisted packages only

## Development

### Cross-Platform Development
```python
# Use cross-platform utilities in your code
from src.core.utils.cross_platform import (
    get_platform, get_safe_path, ensure_directory,
    normalize_line_endings, get_temp_file
)

# Platform-agnostic file operations
pm = get_platform()
file_path = get_safe_path(pm.get_path('uploads_dir'), 'file.xlsx')
```

### Testing Across Platforms
```bash
# Test on different platforms
# macOS
./run_tests.sh

# Windows
run_tests.bat

# Linux
./run_tests.sh

# PythonAnywhere
python -m pytest tests/
```

## Deployment

### Local Deployment
```bash
# Start application
python app.py

# Or use platform-specific scripts
./run_app.sh      # macOS/Linux
run_app.bat       # Windows
```

### Cloud Deployment (PythonAnywhere)
```bash
# Upload files
# Configure WSGI file
# Set environment variables
# Start application
```

## Best Practices

### 1. Use Cross-Platform Utilities
Always use the provided cross-platform utilities instead of platform-specific code.

### 2. Test on Multiple Platforms
Test your changes on at least two different platforms before deployment.

### 3. Handle Platform Differences
Use platform detection to handle platform-specific requirements gracefully.

### 4. Monitor Performance
Use platform-specific performance monitoring tools.

### 5. Document Platform-Specific Behavior
Document any platform-specific behavior or limitations.

## Support

### Getting Help
- **Documentation**: Check this guide and other docs
- **Logs**: Check platform-specific log files
- **Community**: Use GitHub issues for bug reports

### Platform-Specific Support
- **macOS**: Check Console.app for system logs
- **Windows**: Check Event Viewer for system logs
- **Linux**: Check system logs in /var/log
- **PythonAnywhere**: Check error logs in web app

## Conclusion

AGT Designer's cross-platform compatibility ensures consistent behavior and performance across all supported platforms. The automatic platform detection and optimization features make it easy to deploy and use on any platform without manual configuration.

For more information, see the individual platform-specific documentation files in the `docs/` directory. 