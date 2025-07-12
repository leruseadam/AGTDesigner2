"""
Cross-platform compatibility utilities for AGT Designer.
Ensures consistent behavior across Mac, Windows, Linux, and PythonAnywhere.
"""

import os
import sys
import platform
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import tempfile
import shutil

logger = logging.getLogger(__name__)

class PlatformManager:
    """Manages cross-platform compatibility and platform-specific configurations."""
    
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.paths = self._setup_paths()
        self.config = self._get_platform_config()
        logger.info(f"Platform detected: {self.platform_info}")
        
    def _detect_platform(self) -> Dict[str, Any]:
        """Detect current platform and environment."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Detect PythonAnywhere
        is_pythonanywhere = (
            os.path.exists("/home/adamcordova") or 
            "pythonanywhere" in os.getcwd().lower() or
            os.path.exists("/var/www") or
            "pythonanywhere.com" in os.environ.get("HOSTNAME", "")
        )
        
        # Detect virtual environment
        is_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        
        # Detect development vs production
        is_development = (
            "development" in os.environ.get("FLASK_ENV", "").lower() or
            "dev" in os.environ.get("ENVIRONMENT", "").lower() or
            os.path.exists(".env") or
            os.path.exists("requirements.txt")
        )
        
        return {
            'system': system,
            'machine': machine,
            'python_version': sys.version,
            'python_executable': sys.executable,
            'is_pythonanywhere': is_pythonanywhere,
            'is_venv': is_venv,
            'is_development': is_development,
            'cwd': os.getcwd(),
            'home_dir': str(Path.home()),
            'temp_dir': tempfile.gettempdir(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'processor': platform.processor()
        }
    
    def _setup_paths(self) -> Dict[str, str]:
        """Setup platform-specific paths."""
        home = Path.home()
        cwd = Path.cwd()
        
        # Base paths that work across platforms
        base_paths = {
            'project_root': str(cwd),
            'home_dir': str(home),
            'temp_dir': tempfile.gettempdir(),
            'uploads_dir': str(cwd / "uploads"),
            'data_dir': str(cwd / "data"),
            'output_dir': str(cwd / "output"),
            'logs_dir': str(cwd / "logs"),
            'cache_dir': str(cwd / "cache"),
        }
        
        # Platform-specific paths
        if self.platform_info['system'] == 'darwin':  # macOS
            platform_paths = {
                'downloads_dir': str(home / "Downloads"),
                'desktop_dir': str(home / "Desktop"),
                'documents_dir': str(home / "Documents"),
                'app_support': str(home / "Library" / "Application Support"),
            }
        elif self.platform_info['system'] == 'windows':
            platform_paths = {
                'downloads_dir': str(home / "Downloads"),
                'desktop_dir': str(home / "Desktop"),
                'documents_dir': str(home / "Documents"),
                'app_data': str(home / "AppData" / "Local"),
            }
        elif self.platform_info['system'] == 'linux':
            platform_paths = {
                'downloads_dir': str(home / "Downloads"),
                'desktop_dir': str(home / "Desktop"),
                'documents_dir': str(home / "Documents"),
                'config_dir': str(home / ".config"),
            }
        else:
            platform_paths = {}
        
        # PythonAnywhere specific paths
        if self.platform_info['is_pythonanywhere']:
            pythonanywhere_paths = {
                'pythonanywhere_home': "/home/adamcordova",
                'pythonanywhere_uploads': "/home/adamcordova/uploads",
                'pythonanywhere_web': "/var/www",
                'pythonanywhere_static': "/home/adamcordova/static",
            }
            platform_paths.update(pythonanywhere_paths)
        
        # Ensure directories exist
        all_paths = {**base_paths, **platform_paths}
        for path_name, path_str in all_paths.items():
            if path_name.endswith('_dir'):
                Path(path_str).mkdir(parents=True, exist_ok=True)
        
        return all_paths
    
    def _get_platform_config(self) -> Dict[str, Any]:
        """Get platform-specific configuration."""
        config = {
            'file_encoding': 'utf-8',
            'line_ending': '\n',
            'path_separator': os.path.sep,
            'max_file_size': 50 * 1024 * 1024,  # 50MB default
            'memory_limit': 512 * 1024 * 1024,  # 512MB default
            'temp_file_prefix': 'agt_',
            'excel_engines': ['openpyxl'],
            'enable_caching': True,
            'enable_compression': True,
        }
        
        # Platform-specific configurations
        if self.platform_info['system'] == 'darwin':  # macOS
            config.update({
                'file_encoding': 'utf-8',
                'line_ending': '\n',
                'max_file_size': 100 * 1024 * 1024,  # 100MB on Mac
                'memory_limit': 1024 * 1024 * 1024,  # 1GB on Mac
                'excel_engines': ['openpyxl', 'xlrd'],
            })
        elif self.platform_info['system'] == 'windows':
            config.update({
                'file_encoding': 'utf-8',
                'line_ending': '\r\n',
                'max_file_size': 100 * 1024 * 1024,  # 100MB on Windows
                'memory_limit': 1024 * 1024 * 1024,  # 1GB on Windows
                'excel_engines': ['openpyxl', 'xlrd'],
            })
        elif self.platform_info['system'] == 'linux':
            config.update({
                'file_encoding': 'utf-8',
                'line_ending': '\n',
                'max_file_size': 100 * 1024 * 1024,  # 100MB on Linux
                'memory_limit': 1024 * 1024 * 1024,  # 1GB on Linux
                'excel_engines': ['openpyxl', 'xlrd'],
            })
        
        # PythonAnywhere specific configuration
        if self.platform_info['is_pythonanywhere']:
            config.update({
                'max_file_size': 50 * 1024 * 1024,  # 50MB limit on PythonAnywhere
                'memory_limit': 512 * 1024 * 1024,  # 512MB limit on PythonAnywhere
                'enable_caching': True,
                'enable_compression': True,
                'excel_engines': ['openpyxl'],  # Only openpyxl on PythonAnywhere
            })
        
        return config
    
    def get_path(self, path_type: str) -> str:
        """Get a platform-specific path."""
        return self.paths.get(path_type, "")
    
    def get_config(self, config_key: str) -> Any:
        """Get a platform-specific configuration value."""
        return self.config.get(config_key)
    
    def is_platform(self, platform_name: str) -> bool:
        """Check if running on specific platform."""
        platform_name = platform_name.lower()
        if platform_name == 'mac':
            return self.platform_info['system'] == 'darwin'
        elif platform_name == 'windows':
            return self.platform_info['system'] == 'windows'
        elif platform_name == 'linux':
            return self.platform_info['system'] == 'linux'
        elif platform_name == 'pythonanywhere':
            return self.platform_info['is_pythonanywhere']
        return False
    
    def get_safe_path(self, *path_parts: str) -> str:
        """Create a safe, platform-compatible file path."""
        # Normalize path separators
        normalized_parts = []
        for part in path_parts:
            if part:
                # Replace any platform-specific separators with the current platform's separator
                normalized_part = part.replace('/', os.path.sep).replace('\\', os.path.sep)
                normalized_parts.append(normalized_part)
        
        return os.path.join(*normalized_parts) if normalized_parts else ""
    
    def ensure_directory(self, directory_path: str) -> bool:
        """Ensure a directory exists, creating it if necessary."""
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}: {e}")
            return False
    
    def get_temp_file(self, suffix: str = "", prefix: str = None) -> str:
        """Get a temporary file path that works across platforms."""
        if prefix is None:
            prefix = self.config['temp_file_prefix']
        
        # Create temp file with platform-specific prefix
        temp_file = tempfile.NamedTemporaryFile(
            suffix=suffix,
            prefix=prefix,
            delete=False
        )
        temp_path = temp_file.name
        temp_file.close()
        
        return temp_path
    
    def cleanup_temp_files(self, pattern: str = None) -> int:
        """Clean up temporary files created by the application."""
        if pattern is None:
            pattern = f"{self.config['temp_file_prefix']}*"
        
        temp_dir = self.paths['temp_dir']
        cleaned_count = 0
        
        try:
            for temp_file in Path(temp_dir).glob(pattern):
                try:
                    temp_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
        
        return cleaned_count
    
    def get_file_size_limit(self) -> int:
        """Get the maximum file size limit for the current platform."""
        return self.config['max_file_size']
    
    def get_memory_limit(self) -> int:
        """Get the memory limit for the current platform."""
        return self.config['memory_limit']
    
    def get_excel_engines(self) -> List[str]:
        """Get the list of available Excel engines for the current platform."""
        return self.config['excel_engines'].copy()
    
    def normalize_line_endings(self, text: str) -> str:
        """Normalize line endings for the current platform."""
        target_ending = self.config['line_ending']
        
        # Convert all line endings to the target platform's line ending
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if target_ending != '\n':
            text = text.replace('\n', target_ending)
        
        return text
    
    def get_platform_summary(self) -> Dict[str, Any]:
        """Get a summary of platform information for logging/debugging."""
        return {
            'platform': self.platform_info,
            'paths': {k: v for k, v in self.paths.items() if not k.endswith('_dir')},
            'config': self.config,
            'capabilities': {
                'can_write_files': os.access(self.paths['temp_dir'], os.W_OK),
                'can_create_directories': os.access(self.paths['project_root'], os.W_OK),
                'has_sufficient_memory': True,  # Could add actual memory check
                'supports_multiprocessing': not self.platform_info['is_pythonanywhere'],
            }
        }

# Global platform manager instance
platform_manager = PlatformManager()

# Convenience functions
def get_platform() -> PlatformManager:
    """Get the global platform manager instance."""
    return platform_manager

def is_pythonanywhere() -> bool:
    """Check if running on PythonAnywhere."""
    return platform_manager.is_platform('pythonanywhere')

def is_mac() -> bool:
    """Check if running on macOS."""
    return platform_manager.is_platform('mac')

def is_windows() -> bool:
    """Check if running on Windows."""
    return platform_manager.is_platform('windows')

def is_linux() -> bool:
    """Check if running on Linux."""
    return platform_manager.is_platform('linux')

def get_safe_path(*path_parts: str) -> str:
    """Create a safe, platform-compatible file path."""
    return platform_manager.get_safe_path(*path_parts)

def ensure_directory(directory_path: str) -> bool:
    """Ensure a directory exists, creating it if necessary."""
    return platform_manager.ensure_directory(directory_path)

def get_temp_file(suffix: str = "", prefix: str = None) -> str:
    """Get a temporary file path that works across platforms."""
    return platform_manager.get_temp_file(suffix, prefix)

def normalize_line_endings(text: str) -> str:
    """Normalize line endings for the current platform."""
    return platform_manager.normalize_line_endings(text) 