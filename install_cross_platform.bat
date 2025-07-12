@echo off
REM Cross-platform installation script for AGT Designer (Windows)
REM Works on Windows 10/11 with Python 3.8+

setlocal enabledelayedexpansion

REM Colors for output (Windows 10+)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

echo %BLUE%=== AGT Designer Cross-Platform Installation (Windows) ===%NC%
echo.

REM Check Python installation
echo %GREEN%[INFO]%NC% Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Python not found. Please install Python 3.8 or higher.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo %GREEN%[INFO]%NC% Python %PYTHON_VERSION% found

REM Check Python version
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if %PYTHON_MAJOR% LSS 3 (
    echo %RED%[ERROR]%NC% Python 3.8 or higher is required. Found: %PYTHON_VERSION%
    pause
    exit /b 1
)

if %PYTHON_MAJOR% EQU 3 (
    if %PYTHON_MINOR% LSS 8 (
        echo %RED%[ERROR]%NC% Python 3.8 or higher is required. Found: %PYTHON_VERSION%
        pause
        exit /b 1
    )
)

REM Check pip
echo %GREEN%[INFO]%NC% Checking pip installation...
pip --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% pip not found. Please install pip.
    pause
    exit /b 1
)
echo %GREEN%[INFO]%NC% pip found

REM Create virtual environment
echo %GREEN%[INFO]%NC% Creating virtual environment...
if exist venv (
    echo %YELLOW%[WARNING]%NC% Virtual environment already exists. Removing...
    rmdir /s /q venv
)

python -m venv venv
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Failed to activate virtual environment.
    pause
    exit /b 1
)
echo %GREEN%[INFO]%NC% Virtual environment created and activated

REM Upgrade pip
echo %GREEN%[INFO]%NC% Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo %YELLOW%[WARNING]%NC% Failed to upgrade pip. Continuing...
)

REM Install Python dependencies
echo %GREEN%[INFO]%NC% Installing Python dependencies...
pip install -r requirements_cross_platform.txt
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Failed to install Python dependencies.
    pause
    exit /b 1
)

REM Install Windows-specific packages
echo %GREEN%[INFO]%NC% Installing Windows-specific packages...
pip install psutil
echo %GREEN%[INFO]%NC% Python dependencies installed

REM Create necessary directories
echo %GREEN%[INFO]%NC% Creating necessary directories...
if not exist uploads mkdir uploads
if not exist output mkdir output
if not exist logs mkdir logs
if not exist cache mkdir cache
if not exist data mkdir data
echo %GREEN%[INFO]%NC% Directories created

REM Set up configuration
echo %GREEN%[INFO]%NC% Setting up configuration...
if not exist config.py (
    (
        echo # AGT Designer Configuration
        echo import os
        echo.
        echo class Config:
        echo     SECRET_KEY = os.environ.get^('SECRET_KEY'^) or 'agt-designer-secret-key-2024'
        echo     DEBUG = True
        echo     UPLOAD_FOLDER = 'uploads'
        echo     OUTPUT_FOLDER = 'output'
        echo     MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ) > config.py
    echo %GREEN%[INFO]%NC% Default configuration created
)

REM Test installation
echo %GREEN%[INFO]%NC% Testing installation...
python -c "import sys; print('Python version:', sys.version); import flask; print('Flask version:', flask.__version__); import pandas; print('Pandas version:', pandas.__version__); import docx; print('python-docx version:', docx.__version__); print('All core dependencies imported successfully!')"
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Installation test failed.
    pause
    exit /b 1
)
echo %GREEN%[INFO]%NC% Installation test completed

REM Create activation script
echo %GREEN%[INFO]%NC% Creating activation script...
(
    echo @echo off
    echo REM AGT Designer activation script ^(Windows^)
    echo.
    echo if exist venv ^(
    echo     call venv\Scripts\activate.bat
    echo     echo Virtual environment activated
    echo     echo Run 'python app.py' to start the application
    echo ^) else ^(
    echo     echo Virtual environment not found. Run install_cross_platform.bat first.
    echo ^)
    echo pause
) > activate.bat
echo %GREEN%[INFO]%NC% Activation script created: activate.bat

echo.
echo %GREEN%=== Installation Complete! ===%NC%
echo.
echo %BLUE%Next steps:%NC%
echo 1. Activate the virtual environment:
echo    activate.bat
echo    OR
echo    venv\Scripts\activate.bat
echo.
echo 2. Start the application:
echo    python app.py
echo.
echo 3. Open your browser to: http://localhost:5000
echo.
echo %YELLOW%Note:%NC% The application will automatically detect your platform
echo and optimize settings for best performance.
echo.
pause 