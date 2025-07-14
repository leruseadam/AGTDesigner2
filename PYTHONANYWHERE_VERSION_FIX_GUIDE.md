# PythonAnywhere Version Mismatch Fix Guide

## Problem
- **Local Environment**: Python 3.11.0
- **PythonAnywhere**: Python 3.10.12
- **Issue**: Version mismatch causing compatibility problems

## Solution Options

### Option 1: Upgrade PythonAnywhere to Python 3.11 (RECOMMENDED)

This will make your PythonAnywhere environment match your local environment.

#### Step-by-Step Instructions:

**Step 1: Access PythonAnywhere**
1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Log into your account
3. Click on "Bash" console

**Step 2: Create New Virtual Environment**
```bash
# Create new virtual environment with Python 3.11
mkvirtualenv --python=/usr/bin/python3.11 labelmaker-py311

# Verify the Python version
python --version
# Should show: Python 3.11.x
```

**Step 3: Navigate to Your Project**
```bash
# Navigate to your project directory
cd ~/AGTDesigner

# Verify you're in the right directory
ls -la
# Should show your project files
```

**Step 4: Install Requirements**
```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install Python 3.11 compatible requirements
pip install -r requirements_pythonanywhere_py313.txt

# Verify key packages
python -c "import pandas, flask, docx; print('✅ All packages imported successfully')"
```

**Step 5: Update Web App Configuration**
1. Go to PythonAnywhere "Web" tab
2. Find your web app (www.agtpricetags.com)
3. Click "Edit" next to your web app
4. In the "Virtual environment" field, change to:
   ```
   /home/adamcordova/.virtualenvs/labelmaker-py311
   ```
5. Click "Save"
6. Click "Reload" button

**Step 6: Test the Application**
1. Visit your website: www.agtpricetags.com
2. Check if the application loads correctly
3. Test uploading a file to ensure functionality

---

### Option 2: Keep Python 3.10 (Alternative)

If you prefer to keep Python 3.10, use these compatible requirements.

#### Step-by-Step Instructions:

**Step 1: Access PythonAnywhere**
1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Log into your account
3. Click on "Bash" console

**Step 2: Navigate to Your Project**
```bash
# Navigate to your project directory
cd ~/AGTDesigner

# Activate your existing virtual environment
source ~/labelmaker-venv/bin/activate

# Verify Python version
python --version
# Should show: Python 3.10.12
```

**Step 3: Install Python 3.10 Compatible Requirements**
```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install Python 3.10 compatible requirements
pip install -r requirements_pythonanywhere_py310.txt

# Verify key packages
python -c "import pandas, flask, docx; print('✅ All packages imported successfully')"
```

**Step 4: Update WSGI File (Optional)**
```bash
# Backup current WSGI file
cp wsgi.py wsgi.py.backup

# Use Python 3.10 optimized WSGI file
cp wsgi_pythonanywhere_py310.py wsgi.py
```

**Step 5: Reload Web App**
1. Go to PythonAnywhere "Web" tab
2. Click "Reload" button for your web app

**Step 6: Test the Application**
1. Visit your website: www.agtpricetags.com
2. Check if the application loads correctly
3. Test uploading a file to ensure functionality

---

## Troubleshooting

### Common Issues and Solutions

**Issue 1: "No module named 'pandas'"**
```bash
# Solution: Reinstall pandas
pip install pandas==2.0.3
```

**Issue 2: "Permission denied"**
```bash
# Solution: Fix permissions
chmod -R 755 .
chmod -R 755 uploads output cache logs static
```

**Issue 3: "Virtual environment not found"**
```bash
# Solution: Check virtual environment path
ls -la ~/.virtualenvs/
# or
ls -la ~/labelmaker-venv/
```

**Issue 4: "Import error"**
```bash
# Solution: Check Python path and reinstall
python -c "import sys; print(sys.path)"
pip install --force-reinstall -r requirements_pythonanywhere_py313.txt
```

### Debug Commands

**Check Current Status:**
```bash
# Check Python version
python --version

# Check installed packages
pip list

# Check virtual environment
echo $VIRTUAL_ENV

# Check project directory
pwd
ls -la

# Test imports
python -c "
import sys
print('Python version:', sys.version)
import pandas
print('Pandas version:', pandas.__version__)
import flask
print('Flask version:', flask.__version__)
import docx
print('python-docx available')
"
```

**Check Web App Logs:**
1. Go to PythonAnywhere "Web" tab
2. Click "Error log" to see recent errors
3. Look for specific error messages

### Verification Checklist

After completing either option, verify:

- [ ] Python version matches your choice (3.11 or 3.10)
- [ ] All packages install without errors
- [ ] Web app reloads successfully
- [ ] Website loads without errors
- [ ] File upload functionality works
- [ ] No error messages in logs

---

## Quick Commands Reference

### For Python 3.11 Upgrade:
```bash
mkvirtualenv --python=/usr/bin/python3.11 labelmaker-py311
cd ~/AGTDesigner
pip install --upgrade pip setuptools wheel
pip install -r requirements_pythonanywhere_py313.txt
# Then update Web tab virtual environment path
```

### For Python 3.10 Compatibility:
```bash
cd ~/AGTDesigner
source ~/labelmaker-venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements_pythonanywhere_py310.txt
# Then reload Web app
```

---

## Need Help?

If you encounter issues:

1. **Check the error logs** in PythonAnywhere Web tab
2. **Run the debug script**: `python pythonanywhere_debug_script.py`
3. **Verify file permissions**: `chmod -R 755 .`
4. **Check virtual environment**: `echo $VIRTUAL_ENV`

The most common issue is forgetting to update the virtual environment path in the Web tab after creating a new environment. 