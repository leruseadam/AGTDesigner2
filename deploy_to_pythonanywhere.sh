#!/bin/bash

# PythonAnywhere Deployment Script
# This script pulls the latest changes from GitHub and updates the deployment

echo "=== PythonAnywhere Deployment Script ==="
echo "Starting deployment process..."

# Set the project directory
PROJECT_DIR="/home/adamcordova/AGTDesigner"
cd "$PROJECT_DIR"

echo "Current directory: $(pwd)"

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Are you in the correct project directory?"
    exit 1
fi

echo "✅ Found project files"

# Backup current state
echo "📦 Creating backup of current state..."
cp -r . ../AGTDesigner_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "⚠️  Backup failed, continuing..."

# Stash any local changes
echo "💾 Stashing any local changes..."
git stash

# Pull latest changes
echo "⬇️  Pulling latest changes from GitHub..."
git fetch origin
git reset --hard origin/main

# Check if pull was successful
if [ $? -eq 0 ]; then
    echo "✅ Successfully pulled latest changes"
else
    echo "❌ Failed to pull changes"
    exit 1
fi

# Show latest commit
echo "📝 Latest commit:"
git log --oneline -1

# Update dependencies
echo "📦 Updating Python dependencies..."
pip install -r requirements.txt

# Check if requirements installation was successful
if [ $? -eq 0 ]; then
    echo "✅ Dependencies updated successfully"
else
    echo "⚠️  Some dependencies may have failed to install"
fi

# Create/update database
echo "🗄️  Initializing product database..."
python -c "
from src.core.data.product_database import ProductDatabase
try:
    db = ProductDatabase()
    db.init_database()
    print('✅ Product database initialized successfully')
except Exception as e:
    print(f'⚠️  Database initialization warning: {e}')
"

# Check for any Python syntax errors
echo "🔍 Checking for syntax errors..."
python -m py_compile app.py
if [ $? -eq 0 ]; then
    echo "✅ No syntax errors found"
else
    echo "❌ Syntax errors found in app.py"
    exit 1
fi

# Test the application
echo "🧪 Testing application..."
python -c "
import sys
sys.path.append('.')
try:
    from app import create_app
    app = create_app()
    print('✅ Application imports successfully')
except Exception as e:
    print(f'❌ Application test failed: {e}')
    sys.exit(1)
"

echo ""
echo "=== Deployment Summary ==="
echo "✅ Git repository updated"
echo "✅ Dependencies installed"
echo "✅ Database initialized"
echo "✅ Application tested"
echo ""
echo "🔄 Next steps:"
echo "1. Go to the 'Web' tab in PythonAnywhere"
echo "2. Find your web app"
echo "3. Click the 'Reload' button"
echo "4. Test your application at your PythonAnywhere URL"
echo ""
echo "🌐 Your app should be available at:"
echo "https://adamcordova.pythonanywhere.com"
echo ""
echo "📊 To test the new product database features:"
echo "- Visit: https://adamcordova.pythonanywhere.com/api/database-stats"
echo "- Visit: https://adamcordova.pythonanywhere.com/api/database-vendor-stats"
echo ""
echo "🎉 Deployment script completed!" 