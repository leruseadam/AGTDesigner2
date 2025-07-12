#!/bin/bash

# PythonAnywhere Quick Update Script
# Run this in your PythonAnywhere bash console

echo "=== Quick PythonAnywhere Update ==="

# Step 1: Navigate to your project directory
cd ~/AGTDesigner

# Step 2: Pull latest changes
echo "Pulling latest changes from GitHub..."
git pull origin main

# Step 3: Clear any cached files (quick)
echo "Clearing cache..."
rm -rf __pycache__ 2>/dev/null || true
rm -rf src/__pycache__ 2>/dev/null || true

# Step 4: Check if virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  WARNING: Not in virtual environment!"
    echo "Please activate your virtual environment:"
    echo "source ~/.virtualenvs/myflaskapp-env/bin/activate"
    echo "Then run this script again."
    exit 1
fi

# Step 5: Install any new dependencies
echo "Checking for new dependencies..."
pip install -r requirements_pythonanywhere.txt

echo ""
echo "=== Quick Update Complete ==="
echo "Next steps:"
echo "1. Go to PythonAnywhere Web tab"
echo "2. Click 'Reload' for your web app"
echo "3. Test the application at https://www.agtpricetags.com"
echo ""
echo "Note: Permissions step was skipped to avoid hanging."
echo "If you have permission issues, run the full update script." 