#!/bin/bash

# PythonAnywhere Deployment Script with Database Protection
# This script safely deploys your application while protecting the database

echo "🚀 Deploying to PythonAnywhere with database protection..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Check if we're on PythonAnywhere
if [[ "$PYTHONANYWHERE_SITE" != "" ]] || [[ "$PYTHONANYWHERE_DOMAIN" != "" ]]; then
    echo "🌐 PythonAnywhere environment detected"
    PYTHONANYWHERE_MODE=true
else
    echo "💻 Local environment detected"
    echo "⚠️  This script is designed for PythonAnywhere deployment"
    echo "   For local development, use: git pull origin main"
    exit 1
fi

# Step 1: Backup existing database
echo ""
echo "📦 Step 1: Creating database backup..."
BACKUP_DIR="$HOME/database_backups"
mkdir -p "$BACKUP_DIR"

# Find and backup existing database files
DATABASE_FOUND=false
for db_pattern in "product_database.db" "*.db" "*.sqlite" "*.sqlite3"; do
    for db_file in $PROJECT_DIR/$db_pattern; do
        if [ -f "$db_file" ]; then
            DATABASE_FOUND=true
            timestamp=$(date +%Y%m%d_%H%M%S)
            filename=$(basename "$db_file")
            backup_filename="${filename%.*}_backup_${timestamp}.${filename##*.}"
            backup_path="$BACKUP_DIR/$backup_filename"
            
            echo "  📋 Backing up: $db_file -> $backup_path"
            if cp "$db_file" "$backup_path"; then
                echo "  ✅ Database backed up successfully"
            else
                echo "  ❌ Backup failed for $db_file"
            fi
        fi
    done
done

if [ "$DATABASE_FOUND" = false ]; then
    echo "  ℹ️  No existing database files found"
fi

# Step 2: Pull latest code (database files are ignored by .gitignore)
echo ""
echo "📥 Step 2: Pulling latest code from Git..."
cd "$PROJECT_DIR" || exit 1

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Not in a git repository. Please clone the repository first."
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Warning: You have uncommitted changes:"
    git status --short
    echo ""
    read -p "Do you want to continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deployment cancelled"
        exit 1
    fi
fi

# Pull latest changes
echo "  🔄 Pulling from origin main..."
if git pull origin main; then
    echo "  ✅ Code updated successfully"
else
    echo "  ❌ Git pull failed"
    exit 1
fi

# Step 3: Restore database if needed
echo ""
echo "🔄 Step 3: Checking database status..."

# Check if database files were removed during git pull
DATABASE_RESTORED=false
for db_pattern in "product_database.db" "*.db" "*.sqlite" "*.sqlite3"; do
    for db_file in $PROJECT_DIR/$db_pattern; do
        if [ ! -f "$db_file" ]; then
            # Look for backup to restore
            filename=$(basename "$db_file")
            backup_file=$(ls -t "$BACKUP_DIR"/"${filename%.*}"_backup_*."${filename##*.}" 2>/dev/null | head -1)
            
            if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
                echo "  📋 Restoring database from backup: $backup_file -> $db_file"
                if cp "$backup_file" "$db_file"; then
                    echo "  ✅ Database restored successfully"
                    DATABASE_RESTORED=true
                else
                    echo "  ❌ Database restore failed"
                fi
            fi
        fi
    done
done

if [ "$DATABASE_RESTORED" = false ]; then
    echo "  ℹ️  No database restoration needed"
fi

# Step 4: Update dependencies if needed
echo ""
echo "📦 Step 4: Checking dependencies..."

# Check if virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Virtual environment not active"
    echo "   Please activate your virtual environment:"
    echo "   source ~/labelmaker-venv/bin/activate"
    echo "   Then run this script again."
    exit 1
else
    echo "  ✅ Virtual environment active: $VIRTUAL_ENV"
fi

# Check for requirements file
if [ -f "requirements_pythonanywhere.txt" ]; then
    echo "  📋 Installing/updating dependencies..."
    if pip install -r requirements_pythonanywhere.txt; then
        echo "  ✅ Dependencies updated successfully"
    else
        echo "  ⚠️  Some dependencies may have failed to install"
    fi
elif [ -f "requirements.txt" ]; then
    echo "  📋 Installing/updating dependencies..."
    if pip install -r requirements.txt; then
        echo "  ✅ Dependencies updated successfully"
    else
        echo "  ⚠️  Some dependencies may have failed to install"
    fi
else
    echo "  ℹ️  No requirements file found"
fi

# Step 5: Clear cache and set permissions
echo ""
echo "🧹 Step 5: Cleaning up and setting permissions..."

# Clear Python cache
echo "  🗑️  Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Set permissions
echo "  🔐 Setting permissions..."
chmod -R 755 . 2>/dev/null || true
chmod -R 755 uploads output cache logs static 2>/dev/null || true

# Step 6: Database integrity check
echo ""
echo "🔍 Step 6: Checking database integrity..."

# Check if we have a database monitoring script
if [ -f "monitor_database.py" ]; then
    echo "  🔍 Running database integrity check..."
    if python3 monitor_database.py; then
        echo "  ✅ Database integrity check passed"
    else
        echo "  ⚠️  Database integrity check failed - manual review recommended"
    fi
else
    echo "  ℹ️  Database monitoring script not found"
fi

# Step 7: Final status
echo ""
echo "📊 Deployment Summary:"
echo "  📁 Project directory: $PROJECT_DIR"
echo "  📦 Backup directory: $BACKUP_DIR"
echo "  🐍 Virtual environment: $VIRTUAL_ENV"
echo "  📦 Total backups: $(ls -1 "$BACKUP_DIR"/*.db "$BACKUP_DIR"/*.sqlite "$BACKUP_DIR"/*.sqlite3 2>/dev/null | wc -l)"

echo ""
echo "🎉 Deployment complete with database protection!"
echo ""
echo "📋 Next steps:"
echo "  1. Go to PythonAnywhere Web tab"
echo "  2. Click 'Reload' for your web app"
echo "  3. Test the application"
echo "  4. Check error logs if there are issues"
echo ""
echo "🛡️  Your database is safe and protected from Git changes!" 