# PythonAnywhere Deployment Guide

## Quick Deployment Steps

### Step 1: Access PythonAnywhere Console
1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Log in to your account
3. Click on the **Consoles** tab
4. Start a new **Bash console**

### Step 2: Navigate to Your Project
```bash
cd /home/adamcordova/AGTDesigner
```

### Step 3: Pull Latest Changes
```bash
git pull origin main
```

### Step 4: Update Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Initialize Database
```bash
python -c "from src.core.data.product_database import ProductDatabase; db = ProductDatabase(); db.init_database(); print('Database initialized')"
```

### Step 6: Reload Web App
1. Go to the **Web** tab
2. Find your web app
3. Click **Reload**

## Automated Deployment

### Option 1: Use the Deployment Script
1. Upload `deploy_to_pythonanywhere.sh` to your PythonAnywhere account
2. Make it executable: `chmod +x deploy_to_pythonanywhere.sh`
3. Run it: `./deploy_to_pythonanywhere.sh`

### Option 2: Manual Commands
Run these commands in sequence:

```bash
# Navigate to project
cd /home/adamcordova/AGTDesigner

# Backup current state
cp -r . ../AGTDesigner_backup_$(date +%Y%m%d_%H%M%S)

# Stash any local changes
git stash

# Pull latest changes
git fetch origin
git reset --hard origin/main

# Update dependencies
pip install -r requirements.txt

# Initialize database
python -c "from src.core.data.product_database import ProductDatabase; db = ProductDatabase(); db.init_database()"

# Test application
python -c "from app import create_app; app = create_app(); print('App loaded successfully')"
```

## Verification Steps

### 1. Check Application Status
Visit: `https://adamcordova.pythonanywhere.com/api/status`

### 2. Test Product Database Features
- **Database Stats**: `https://adamcordova.pythonanywhere.com/api/database-stats`
- **Vendor Stats**: `https://adamcordova.pythonanywhere.com/api/database-vendor-stats`
- **Database Export**: `https://adamcordova.pythonanywhere.com/api/database-export`

### 3. Check Logs
In PythonAnywhere console:
```bash
tail -f /var/log/adamcordova.pythonanywhere.com.error.log
```

## Troubleshooting

### Common Issues

#### 1. Git Pull Fails
```bash
# Check git status
git status

# Reset to clean state
git reset --hard HEAD
git clean -fd

# Try pull again
git pull origin main
```

#### 2. Dependencies Fail to Install
```bash
# Upgrade pip
pip install --upgrade pip

# Install with verbose output
pip install -r requirements.txt -v
```

#### 3. Database Issues
```bash
# Remove old database
rm -f product_database.db*

# Reinitialize
python -c "from src.core.data.product_database import ProductDatabase; db = ProductDatabase(); db.init_database()"
```

#### 4. Web App Won't Reload
1. Check error logs in the **Web** tab
2. Verify WSGI file points to correct app
3. Check Python version compatibility

### WSGI Configuration
Make sure your WSGI file (`/var/www/adamcordova_pythonanywhere_com_wsgi.py`) contains:

```python
import sys
path = '/home/adamcordova/AGTDesigner'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

## New Features to Test

After deployment, test these new features:

### 1. Product Database Statistics
- Visit `/api/database-stats` to see comprehensive database statistics
- Check vendor, brand, and product type counts

### 2. Vendor Analytics
- Visit `/api/database-vendor-stats` for detailed vendor/brand analysis
- View vendor-brand combinations and product distributions

### 3. Database Export
- Visit `/api/database-export` to download database as Excel file

### 4. Performance Monitoring
- Visit `/api/performance` to check database performance metrics

## Rollback Plan

If something goes wrong:

```bash
# Restore from backup
cd /home/adamcordova
rm -rf AGTDesigner
cp -r AGTDesigner_backup_YYYYMMDD_HHMMSS AGTDesigner

# Reinstall dependencies
cd AGTDesigner
pip install -r requirements.txt

# Reload web app
# (Go to Web tab and click Reload)
```

## Support

If you encounter issues:
1. Check the error logs in PythonAnywhere
2. Verify all dependencies are installed
3. Ensure database is properly initialized
4. Test the application locally first 