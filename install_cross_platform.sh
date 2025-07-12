#!/bin/bash

# Cross-platform installation script for AGT Designer
# Works on Mac, Linux, and Windows (via WSL or Git Bash)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Platform detection
PLATFORM=$(uname -s)
MACHINE=$(uname -m)

echo -e "${BLUE}=== AGT Designer Cross-Platform Installation ===${NC}"
echo -e "${BLUE}Platform: $PLATFORM${NC}"
echo -e "${BLUE}Architecture: $MACHINE${NC}"
echo ""

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
check_python() {
    print_status "Checking Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
        PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
    else
        print_error "Python not found. Please install Python 3.8 or higher."
        exit 1
    fi
    
    # Check Python version
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_status "Python $PYTHON_VERSION found"
}

# Check pip
check_pip() {
    print_status "Checking pip installation..."
    
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        print_error "pip not found. Please install pip."
        exit 1
    fi
    
    print_status "pip found"
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing..."
        rm -rf venv
    fi
    
    $PYTHON_CMD -m venv venv
    
    if [ "$PLATFORM" = "MINGW64_NT" ] || [ "$PLATFORM" = "MSYS_NT" ]; then
        # Windows Git Bash
        source venv/Scripts/activate
    else
        # Mac/Linux
        source venv/bin/activate
    fi
    
    print_status "Virtual environment created and activated"
}

# Upgrade pip
upgrade_pip() {
    print_status "Upgrading pip..."
    pip install --upgrade pip
}

# Install platform-specific dependencies
install_platform_deps() {
    print_status "Installing platform-specific dependencies..."
    
    case $PLATFORM in
        "Darwin")  # macOS
            print_status "Installing macOS dependencies..."
            if command -v brew &> /dev/null; then
                brew install libxml2 libxslt
            else
                print_warning "Homebrew not found. Some dependencies may need manual installation."
            fi
            ;;
        "Linux")
            print_status "Installing Linux dependencies..."
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y python3-dev libxml2-dev libxslt1-dev
            elif command -v yum &> /dev/null; then
                sudo yum install -y python3-devel libxml2-devel libxslt-devel
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y python3-devel libxml2-devel libxslt-devel
            else
                print_warning "Package manager not found. Some dependencies may need manual installation."
            fi
            ;;
        "MINGW64_NT"|"MSYS_NT")  # Windows
            print_status "Windows detected. Using Windows-compatible packages..."
            # Windows-specific handling is done in requirements
            ;;
        *)
            print_warning "Unknown platform: $PLATFORM"
            ;;
    esac
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Install core requirements
    pip install -r requirements_cross_platform.txt
    
    # Install additional platform-specific packages if needed
    case $PLATFORM in
        "Darwin")  # macOS
            pip install psutil  # Memory monitoring on Mac
            ;;
        "Linux")
            pip install psutil  # Memory monitoring on Linux
            ;;
        "MINGW64_NT"|"MSYS_NT")  # Windows
            # Windows-specific packages if needed
            ;;
    esac
    
    print_status "Python dependencies installed"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p uploads
    mkdir -p output
    mkdir -p logs
    mkdir -p cache
    mkdir -p data
    
    print_status "Directories created"
}

# Set up configuration
setup_config() {
    print_status "Setting up configuration..."
    
    # Create default configuration if it doesn't exist
    if [ ! -f "config.py" ]; then
        cat > config.py << EOF
# AGT Designer Configuration
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'agt-designer-secret-key-2024'
    DEBUG = True
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'output'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
EOF
        print_status "Default configuration created"
    fi
}

# Test installation
test_installation() {
    print_status "Testing installation..."
    
    # Test Python imports
    python -c "
import sys
print('Python version:', sys.version)
import flask
print('Flask version:', flask.__version__)
import pandas
print('Pandas version:', pandas.__version__)
import docx
print('python-docx version:', docx.__version__)
print('All core dependencies imported successfully!')
"
    
    print_status "Installation test completed"
}

# Create activation script
create_activation_script() {
    print_status "Creating activation script..."
    
    cat > activate.sh << 'EOF'
#!/bin/bash
# AGT Designer activation script

if [ -d "venv" ]; then
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Windows Git Bash
        source venv/Scripts/activate
    else
        # Mac/Linux
        source venv/bin/activate
    fi
    echo "Virtual environment activated"
    echo "Run 'python app.py' to start the application"
else
    echo "Virtual environment not found. Run install_cross_platform.sh first."
fi
EOF
    
    chmod +x activate.sh
    print_status "Activation script created: ./activate.sh"
}

# Main installation process
main() {
    echo -e "${BLUE}Starting AGT Designer installation...${NC}"
    echo ""
    
    check_python
    check_pip
    create_venv
    upgrade_pip
    install_platform_deps
    install_python_deps
    create_directories
    setup_config
    test_installation
    create_activation_script
    
    echo ""
    echo -e "${GREEN}=== Installation Complete! ===${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Activate the virtual environment:"
    echo "   - Mac/Linux: source venv/bin/activate"
    echo "   - Windows: venv\\Scripts\\activate"
    echo "   - Or use: ./activate.sh"
    echo ""
    echo "2. Start the application:"
    echo "   python app.py"
    echo ""
    echo "3. Open your browser to: http://localhost:5000"
    echo ""
    echo -e "${YELLOW}Note:${NC} The application will automatically detect your platform"
    echo "and optimize settings for best performance."
}

# Run main function
main "$@" 