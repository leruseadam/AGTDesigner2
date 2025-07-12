#!/bin/bash

# PythonAnywhere Python 3.13 Fixed Installation Script
# Handles compatibility issues with Python 3.13 on PythonAnywhere

echo "=== PythonAnywhere Python 3.13 Installation Script ==="
echo "This script handles Python 3.13 compatibility issues on PythonAnywhere"

# Step 1: Clear pip cache
echo "Clearing pip cache..."
pip cache purge

# Step 2: Upgrade pip to latest version
echo "Upgrading pip..."
pip install --upgrade pip

# Step 3: Install setuptools and wheel first
echo "Installing build tools..."
pip install --upgrade setuptools wheel

# Step 4: Try minimal requirements first
echo "Attempting to install minimal requirements..."
if pip install -r requirements_pythonanywhere_py313_minimal.txt; then
    echo "✅ Minimal requirements installed successfully!"
else
    echo "❌ Minimal requirements failed, trying alternative approach..."
    
    # Step 5: Try installing packages one by one with specific versions
    echo "Installing packages individually..."
    
    # Core Flask packages
    pip install Flask==2.3.3 Flask-CORS==4.0.0 Werkzeug==2.3.7 Jinja2==3.1.2 itsdangerous==2.1.2 click==8.1.7 MarkupSafe==2.1.3
    
    # Try numpy with specific version that has wheels
    pip install numpy==1.26.4
    
    # Try pandas with specific version
    pip install pandas==2.1.4
    
    # Other packages
    pip install python-dateutil==2.8.2 python-docx==0.8.11 docxtpl==0.16.7 docxcompose==1.4.0 openpyxl==3.1.2 Pillow==10.1.0 watchdog==3.0.0 psutil==5.9.6
fi

# Step 6: Verify installation
echo "Verifying installation..."
python -c "import flask, numpy, pandas; print('✅ Core packages imported successfully')"

echo "=== Installation complete ==="
