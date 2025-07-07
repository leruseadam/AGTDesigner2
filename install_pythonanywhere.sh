#!/bin/bash

# PythonAnywhere Installation Script
# Run this in your PythonAnywhere bash console

echo "=== PythonAnywhere Package Installation Script ==="
echo "Make sure you're in your virtual environment first!"
echo ""

# Check if in virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "WARNING: You don't seem to be in a virtual environment!"
    echo "Please run: source ~/.virtualenvs/myflaskapp-env/bin/activate"
    echo "Then run this script again."
    exit 1
fi

echo "Virtual environment detected: $VIRTUAL_ENV"
echo ""

# Upgrade pip and setuptools
echo "Upgrading pip and setuptools..."
pip install --upgrade pip setuptools wheel
if [ $? -ne 0 ]; then
    echo "Failed to upgrade pip/setuptools"
    exit 1
fi

echo ""
echo "Installing packages..."

# Core Flask dependencies
packages=(
    "Flask==3.0.2"
    "Werkzeug==3.0.1"
    "Jinja2==3.1.3"
    "itsdangerous==2.1.2"
    "click==8.1.7"
    "MarkupSafe==2.1.5"
    "numpy==1.26.4"
    "pandas==2.2.1"
    "python-dateutil==2.8.2"
    "python-docx==1.1.0"
    "docxtpl==0.16.7"
    "docxcompose==1.4.0"
    "openpyxl==3.1.2"
    "Pillow==10.2.0"
    "watchdog>=2.1.6"
)

failed_packages=()

for package in "${packages[@]}"; do
    echo "Installing $package..."
    pip install "$package"
    if [ $? -ne 0 ]; then
        echo "Failed to install $package normally, trying with --no-build-isolation..."
        pip install --no-build-isolation --no-cache-dir "$package"
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to install $package"
            failed_packages+=("$package")
        else
            echo "Successfully installed $package with --no-build-isolation"
        fi
    else
        echo "Successfully installed $package"
    fi
    echo "---"
done

echo ""
echo "=== Installation Summary ==="
if [ ${#failed_packages[@]} -eq 0 ]; then
    echo "✅ All packages installed successfully!"
else
    echo "❌ The following packages failed to install:"
    for package in "${failed_packages[@]}"; do
        echo "  - $package"
    done
fi

echo ""
echo "Verifying key imports..."
python -c "import pandas; print('✅ pandas:', pandas.__version__)" 2>/dev/null || echo "❌ pandas not available"
python -c "import flask; print('✅ Flask:', flask.__version__)" 2>/dev/null || echo "❌ Flask not available"
python -c "import docx; print('✅ python-docx available')" 2>/dev/null || echo "❌ python-docx not available"
python -c "import numpy; print('✅ numpy:', numpy.__version__)" 2>/dev/null || echo "❌ numpy not available"

echo ""
echo "=== Next Steps ==="
echo "1. If all packages installed successfully, restart your web app on PythonAnywhere"
echo "2. If some packages failed, try installing them individually with different flags"
echo "3. Check your WSGI configuration to ensure it's using the correct virtual environment"
