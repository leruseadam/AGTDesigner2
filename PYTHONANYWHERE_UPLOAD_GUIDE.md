# PythonAnywhere Upload Guide for Label Maker

## Prerequisites

1. **PythonAnywhere Account**: You need a PythonAnywhere account (free or paid)
2. **Git Repository**: Your code should be in a Git repository (GitHub, GitLab, etc.)
3. **PythonAnywhere Username**: Note your PythonAnywhere username (e.g., `adamcordova`)

## Step 1: Prepare Your Local Project

### 1.1 Create a Git Repository (if not already done)
```bash
# In your project directory
git init
git add .
git commit -m "Initial commit for PythonAnywhere deployment"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 1.2 Create a Clean Requirements File
The project already has `requirements_pythonanywhere.txt` which is optimized for PythonAnywhere.

## Step 2: Set Up PythonAnywhere

### 2.1 Access PythonAnywhere Console
1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Log in to your account
3. Click on the **Consoles** tab
4. Start a new **Bash console**

### 2.2 Clone Your Repository
```bash
# Navigate to your home directory
cd /home/yourusername

# Clone your repository
git clone <your-github-repo-url> AGTDesigner

# Navigate to the project
cd AGTDesigner
```

### 2.3 Install Dependencies
```bash
# Install PythonAnywhere-specific requirements
pip install -r requirements_pythonanywhere.txt

# If that fails, try the main requirements
pip install -r requirements.txt
```

## Step 3: Configure the Web App

### 3.1 Create a New Web App
1. Go to the **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Choose **Manual configuration**
4. Select **Python 3.9** (or the version you're using)
5. Set the path to: `/home/yourusername/AGTDesigner`

### 3.2 Configure WSGI File
1. In the **Web** tab, click on the WSGI configuration file link
2. Replace the content with:

```python
import sys
import os

# Add your project directory to the Python path
path = '/home/yourusername/AGTDesigner'
if path not in sys.path:
    sys.path.append(path)

# Set environment variables
os.environ['FLASK_ENV'] = 'production'
os.environ['PYTHONPATH'] = path

# Import your Flask app
from app import create_app
application = create_app()

# For debugging
if __name__ == "__main__":
    application.run()
```

### 3.3 Configure Virtual Environment
1. In the **Web** tab, find the **Virtual environment** section
2. Set it to: `/home/yourusername/.virtualenvs/AGTDesigner`

## Step 4: Set Up Virtual Environment

### 4.1 Create Virtual Environment
```bash
# In the PythonAnywhere console
mkvirtualenv --python=/usr/bin/python3.9 AGTDesigner

# Activate the virtual environment
workon AGTDesigner

# Install dependencies in the virtual environment
pip install -r requirements_pythonanywhere.txt
```

### 4.2 Install Additional Dependencies
```bash
# Install any missing packages
pip install Flask==2.3.3
pip install Flask-CORS==4.0.0
pip install pandas==2.0.3
pip install python-docx==0.8.11
pip install docxtpl==0.16.7
pip install openpyxl==3.1.2
pip install Pillow==9.5.0
```

## Step 5: Initialize the Application

### 5.1 Test the Application
```bash
# In the PythonAnywhere console
cd /home/yourusername/AGTDesigner
python -c "from app import create_app; app = create_app(); print('App loaded successfully')"
```

### 5.2 Initialize Database (if needed)
```bash
python -c "from src.core.data.product_database import ProductDatabase; db = ProductDatabase(); db.init_database(); print('Database initialized')"
```

## Step 6: Configure Static Files

### 6.1 Set Up Static Files Directory
1. In the **Web** tab, find the **Static files** section
2. Add these mappings:
   - URL: `/static/` → Directory: `/home/yourusername/AGTDesigner/static/`
   - URL: `/uploads/` → Directory: `/home/yourusername/AGTDesigner/uploads/`
   - URL: `/output/` → Directory: `/home/yourusername/AGTDesigner/output/`

### 6.2 Create Required Directories
```bash
# In the PythonAnywhere console
mkdir -p /home/yourusername/AGTDesigner/uploads
mkdir -p /home/yourusername/AGTDesigner/output
mkdir -p /home/yourusername/AGTDesigner/cache
mkdir -p /home/yourusername/AGTDesigner/logs
```

## Step 7: Reload and Test

### 7.1 Reload the Web App
1. Go to the **Web** tab
2. Click the **Reload** button for your web app

### 7.2 Test the Application
Visit your PythonAnywhere URL:
- Main app: `https://yourusername.pythonanywhere.com`
- Status check: `https://yourusername.pythonanywhere.com/api/status`
- Health check: `https://yourusername.pythonanywhere.com/api/health`

## Step 8: Automated Deployment (Optional)

### 8.1 Upload Deployment Script
Upload the `deploy_to_pythonanywhere.sh` script to your PythonAnywhere account:

```bash
# In the PythonAnywhere console
cd /home/yourusername/AGTDesigner
chmod +x deploy_to_pythonanywhere.sh
```

### 8.2 Run Deployment Script
```bash
./deploy_to_pythonanywhere.sh
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Import Errors
```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Add project to path
export PYTHONPATH="/home/yourusername/AGTDesigner:$PYTHONPATH"
```

#### 2. Permission Errors
```bash
# Fix permissions
chmod -R 755 /home/yourusername/AGTDesigner
chmod -R 777 /home/yourusername/AGTDesigner/uploads
chmod -R 777 /home/yourusername/AGTDesigner/output
```

#### 3. Memory Issues
```bash
# Check memory usage
free -h

# Optimize by reducing pandas memory usage
# The app already has memory optimization features
```

#### 4. File Upload Issues
```bash
# Check upload directory permissions
ls -la /home/yourusername/AGTDesigner/uploads

# Create if missing
mkdir -p /home/yourusername/AGTDesigner/uploads
chmod 777 /home/yourusername/AGTDesigner/uploads
```

#### 5. Template Issues
```bash
# Check template files exist
ls -la /home/yourusername/AGTDesigner/src/core/generation/templates/

# Ensure all template files are present
```

### Debugging Commands

#### Check Application Logs
```bash
# View error logs
tail -f /var/log/yourusername.pythonanywhere.com.error.log

# View access logs
tail -f /var/log/yourusername.pythonanywhere.com.access.log
```

#### Test Individual Components
```bash
# Test Excel processor
python -c "from src.core.data.excel_processor import ExcelProcessor; print('Excel processor OK')"

# Test template processor
python -c "from src.core.generation.template_processor import TemplateProcessor; print('Template processor OK')"

# Test JSON matcher
python -c "from src.core.data.json_matcher import JSONMatcher; print('JSON matcher OK')"
```

## Performance Optimization

### 1. Enable Caching
The application already includes Flask-Caching. Make sure it's configured properly.

### 2. Optimize File Processing
- Use the existing memory optimization features
- Enable fast loading mode for large files

### 3. Monitor Resource Usage
```bash
# Check disk space
df -h

# Check memory usage
free -h

# Monitor CPU usage
top
```

## Security Considerations

### 1. File Upload Security
- The application includes file type validation
- Upload directories are properly configured

### 2. Rate Limiting
- The application includes rate limiting for API endpoints
- Configure appropriate limits for your use case

### 3. Environment Variables
- Set `FLASK_ENV=production` in production
- Use secure session keys

## Maintenance

### Regular Updates
```bash
# Pull latest changes
cd /home/yourusername/AGTDesigner
git pull origin main

# Update dependencies
pip install -r requirements_pythonanywhere.txt

# Reload web app
# (Go to Web tab and click Reload)
```

### Backup Strategy
```bash
# Create regular backups
cp -r /home/yourusername/AGTDesigner /home/yourusername/AGTDesigner_backup_$(date +%Y%m%d)
```

## Support

If you encounter issues:
1. Check the PythonAnywhere error logs
2. Verify all dependencies are installed correctly
3. Test the application locally first
4. Check the application's built-in debugging endpoints

## Quick Reference

### Important URLs
- Main app: `https://yourusername.pythonanywhere.com`
- Status: `https://yourusername.pythonanywhere.com/api/status`
- Health: `https://yourusername.pythonanywhere.com/api/health`
- Database stats: `https://yourusername.pythonanywhere.com/api/database-stats`

### Key Directories
- Project: `/home/yourusername/AGTDesigner`
- Uploads: `/home/yourusername/AGTDesigner/uploads`
- Output: `/home/yourusername/AGTDesigner/output`
- Templates: `/home/yourusername/AGTDesigner/src/core/generation/templates`

### Common Commands
```bash
# Reload web app
# (Use PythonAnywhere Web tab)

# Check logs
tail -f /var/log/yourusername.pythonanywhere.com.error.log

# Update code
cd /home/yourusername/AGTDesigner && git pull origin main

# Test app
python -c "from app import create_app; app = create_app(); print('OK')"
``` 