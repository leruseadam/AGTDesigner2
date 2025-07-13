# PythonAnywhere Debug Guide

## Quick Fix Steps

If your PythonAnywhere version is failing to load items while the local version works, follow these steps:

### Step 1: Upload the Debug Script

1. Copy the `pythonanywhere_debug_script.py` file to your PythonAnywhere project
2. Upload it to your PythonAnywhere project directory

### Step 2: Run the Debug Script

In your PythonAnywhere bash console:

```bash
# Navigate to your project directory
cd ~/your-project-directory

# Run the debug script
python pythonanywhere_debug_script.py
```

### Step 3: Check the Results

The script will output detailed information about:
- Environment detection
- File system access
- Excel files availability
- Module imports
- ExcelProcessor functionality
- Memory usage
- Template files

### Step 4: Common Issues and Solutions

#### Issue 1: No Excel Files Found
**Symptoms**: "No Excel files found in uploads directory"
**Solution**: 
1. Upload an Excel file through the web interface
2. Or copy a file to the uploads directory manually

#### Issue 2: Default Inventory Missing
**Symptoms**: "Default inventory file not found"
**Solution**:
```bash
# Copy an Excel file to the data directory
cp ~/Downloads/your-file.xlsx ./data/default_inventory.xlsx
```

#### Issue 3: Import Errors
**Symptoms**: Module import failures
**Solution**:
```bash
# Activate your virtual environment
source ~/your-venv/bin/activate

# Install missing packages
pip install pandas openpyxl python-docx docxtpl
```

#### Issue 4: Permission Errors
**Symptoms**: "File not readable" or "Permission denied"
**Solution**:
```bash
# Fix permissions
chmod -R 755 .
chmod -R 644 uploads/*.xlsx
```

#### Issue 5: Memory Issues
**Symptoms**: Memory allocation failures
**Solution**:
1. Use smaller Excel files
2. Restart your PythonAnywhere web app
3. Check memory usage in the debug output

### Step 5: Share Debug Output

After running the script, share the output with me so I can help identify the specific issue.

## Manual Debugging Steps

If the script doesn't work, try these manual steps:

### 1. Check File Structure
```bash
ls -la
ls -la uploads/
ls -la data/
```

### 2. Test Python Imports
```bash
python -c "import pandas; print('pandas:', pandas.__version__)"
python -c "import openpyxl; print('openpyxl available')"
python -c "import docx; print('python-docx available')"
```

### 3. Test File Loading
```bash
python -c "
import sys
sys.path.insert(0, '.')
from src.core.data.excel_processor import get_default_upload_file
print('Default file:', get_default_upload_file())
"
```

### 4. Check Web App Configuration

In your PythonAnywhere Web tab:
- Verify source code path is correct
- Check virtual environment path
- Ensure static files mapping is set
- Check environment variables

### 5. Check Error Logs

In your PythonAnywhere Web tab:
- Click on "Error log" to see recent errors
- Look for specific error messages related to file loading

## Expected Output

A successful debug run should show:
```
✅ PythonAnywhere detected: True
✅ All directories exist and are readable
✅ Excel files found in uploads
✅ Default inventory exists
✅ All modules imported successfully
✅ ExcelProcessor initialized
✅ File loaded successfully
✅ Available tags count: [number]
```

## Next Steps

1. Run the debug script
2. Share the output with me
3. I'll provide specific fixes based on the results

The most common issues are:
- Missing Excel files
- Import/dependency problems
- Permission issues
- Memory constraints

Let me know what the debug script shows and I'll help you fix the specific issue! 