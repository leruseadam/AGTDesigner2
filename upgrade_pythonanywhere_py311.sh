#!/bin/bash

# PythonAnywhere Python 3.11 Upgrade Script
# This script will help you upgrade your PythonAnywhere environment to Python 3.11

echo "=== PythonAnywhere Python 3.11 Upgrade Script ==="
echo "This will upgrade your environment to match your local Python 3.11.0"
echo ""

# Check current Python version
echo "Current Python version:"
python --version
echo ""

# Step 1: Create new virtual environment with Python 3.11
echo "Step 1: Creating new virtual environment with Python 3.11..."
echo "Please run the following command in your PythonAnywhere bash console:"
echo ""
echo "mkvirtualenv --python=/usr/bin/python3.11 labelmaker-py311"
echo ""
echo "This will create a new virtual environment using Python 3.11"
echo ""

# Step 2: Install requirements for Python 3.11
echo "Step 2: After creating the virtual environment, install requirements..."
echo "Run these commands:"
echo ""
echo "pip install --upgrade pip setuptools wheel"
echo "pip install -r requirements_pythonanywhere_py313.txt"
echo ""

# Step 3: Update WSGI configuration
echo "Step 3: Update your WSGI configuration..."
echo "In your PythonAnywhere Web tab, update the virtual environment path to:"
echo "/home/adamcordova/.virtualenvs/labelmaker-py311"
echo ""

# Step 4: Test the new environment
echo "Step 4: Test the new environment..."
echo "Run this command to verify:"
echo "python -c \"import sys; print('Python version:', sys.version)\""
echo ""

echo "=== Manual Steps Required ==="
echo "1. Go to PythonAnywhere bash console"
echo "2. Run: mkvirtualenv --python=/usr/bin/python3.11 labelmaker-py311"
echo "3. Navigate to your project: cd ~/AGTDesigner"
echo "4. Install requirements: pip install -r requirements_pythonanywhere_py313.txt"
echo "5. Go to Web tab and update virtual environment path"
echo "6. Click 'Reload' on your web app"
echo ""

echo "=== Alternative: Use Python 3.10 Compatible Requirements ==="
echo "If you prefer to keep Python 3.10, use the existing requirements:"
echo "pip install -r requirements_pythonanywhere.txt"
echo ""

echo "=== Verification ==="
echo "After upgrading, verify with:"
echo "python --version"
echo "python -c \"import pandas, flask, docx; print('All imports successful')\"" 