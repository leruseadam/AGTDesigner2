# Fix for Python 3.11 _posixsubprocess Issue

## Problem
Python 3.11 on PythonAnywhere has a broken `_posixsubprocess` module, causing pip to fail.

## Solution: Use Python 3.10 with Optimized Requirements

### Step 1: Remove the Broken Environment
```bash
# Deactivate current environment
deactivate

# Remove the broken environment
rmvirtualenv labelmaker-py311
```

### Step 2: Use Your Existing Python 3.10 Environment
```bash
# Navigate to your project
cd ~/AGTDesigner

# Activate your existing virtual environment
source ~/labelmaker-venv/bin/activate

# Verify Python version
python --version
# Should show: Python 3.10.12
```

### Step 3: Install Python 3.10 Compatible Requirements
```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install Python 3.10 compatible requirements
pip install -r requirements_pythonanywhere_py310.txt

# Verify installation
python -c "import pandas, flask, docx; print('✅ All packages imported successfully')"
```

### Step 4: Update WSGI Configuration (Optional)
```bash
# Backup current WSGI file
cp wsgi.py wsgi.py.backup

# Use Python 3.10 optimized WSGI file
cp wsgi_pythonanywhere_py310.py wsgi.py
```

### Step 5: Reload Web App
1. Go to PythonAnywhere **Web** tab
2. Click **Reload** button for your web app

### Step 6: Test
1. Visit www.agtpricetags.com
2. Verify the application loads correctly

## Alternative: Try Python 3.9

If you still want a newer Python version, try Python 3.9:

```bash
# Create Python 3.9 environment
mkvirtualenv --python=/usr/bin/python3.9 labelmaker-py39

# Navigate to project
cd ~/AGTDesigner

# Install requirements
pip install --upgrade pip setuptools wheel
pip install -r requirements_pythonanywhere.txt

# Update Web tab virtual environment to:
# /home/adamcordova/.virtualenvs/labelmaker-py39
```

## Why This Happens

PythonAnywhere's Python 3.11 installation sometimes has missing compiled modules like `_posixsubprocess`. This is a platform-specific issue that doesn't affect all PythonAnywhere accounts.

## Verification Commands

```bash
# Check Python version
python --version

# Test key imports
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

# Check virtual environment
echo $VIRTUAL_ENV
```

## Expected Result

After following these steps, you should have:
- Python 3.10.12 working correctly
- All packages installed without errors
- Web app running successfully
- No version compatibility issues with your local development 