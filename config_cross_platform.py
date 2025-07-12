"""
Cross-platform configuration for AGT Designer.
Provides platform-specific settings and ensures consistent behavior.
"""

import os
import sys
from pathlib import Path

# Import cross-platform utilities
try:
    from src.core.utils.cross_platform import get_platform, platform_manager
    pm = get_platform()
except ImportError:
    # Fallback if cross-platform utilities aren't available
    pm = None

class CrossPlatformConfig:
    """Cross-platform configuration class."""
    
    def __init__(self):
        self.platform_info = self._get_platform_info()
        self.paths = self._get_paths()
        self.settings = self._get_settings()
    
    def _get_platform_info(self):
        """Get platform information."""
        if pm:
            return pm.platform_info
        else:
            import platform
            return {
                'system': platform.system().lower(),
                'machine': platform.machine().lower(),
                'python_version': sys.version,
                'is_pythonanywhere': os.path.exists("/home/adamcordova"),
                'is_venv': hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix),
                'is_development': os.path.exists(".env") or os.path.exists("requirements.txt"),
                'cwd': os.getcwd(),
                'home_dir': str(Path.home()),
            }
    
    def _get_paths(self):
        """Get platform-specific paths."""
        if pm:
            return pm.paths
        else:
            home = Path.home()
            cwd = Path.cwd()
            return {
                'project_root': str(cwd),
                'home_dir': str(home),
                'temp_dir': os.path.join(os.path.dirname(__file__), 'temp'),
                'uploads_dir': str(cwd / "uploads"),
                'data_dir': str(cwd / "data"),
                'output_dir': str(cwd / "output"),
                'logs_dir': str(cwd / "logs"),
                'cache_dir': str(cwd / "cache"),
                'downloads_dir': str(home / "Downloads"),
            }
    
    def _get_settings(self):
        """Get platform-specific settings."""
        if pm:
            return pm.config
        else:
            return {
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

# Global configuration instance
config = CrossPlatformConfig()

class Config:
    """Flask configuration class with cross-platform support."""
    
    # Basic Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'agt-designer-secret-key-2024'
    DEBUG = config.platform_info.get('is_development', False)
    TESTING = False
    
    # Cross-platform file settings
    MAX_CONTENT_LENGTH = config.settings['max_file_size']
    UPLOAD_FOLDER = config.paths['uploads_dir']
    OUTPUT_FOLDER = config.paths['output_dir']
    CACHE_FOLDER = config.paths['cache_dir']
    
    # Database settings
    DATABASE_PATH = os.path.join(config.paths['data_dir'], 'product_database.db')
    
    # Logging settings
    LOG_LEVEL = 'DEBUG' if config.platform_info.get('is_development') else 'INFO'
    LOG_FILE = os.path.join(config.paths['logs_dir'], 'agt_designer.log')
    
    # Performance settings
    ENABLE_CACHING = config.settings['enable_caching']
    ENABLE_COMPRESSION = config.settings['enable_compression']
    
    # Platform-specific settings
    IS_PYTHONANYWHERE = config.platform_info.get('is_pythonanywhere', False)
    IS_DEVELOPMENT = config.platform_info.get('is_development', False)
    IS_VENV = config.platform_info.get('is_venv', False)
    
    # Excel processing settings
    EXCEL_ENGINES = config.settings['excel_engines']
    CHUNK_SIZE = 1000 if config.platform_info.get('is_pythonanywhere') else 5000
    
    # Memory management
    MEMORY_LIMIT = config.settings['memory_limit']
    ENABLE_MEMORY_MONITORING = config.platform_info.get('is_development', False)
    
    # File processing
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    MAX_FILE_SIZE = config.settings['max_file_size']
    
    # Template settings
    TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), 'src', 'core', 'generation', 'templates')
    
    # Static file settings
    STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # CORS settings
    CORS_ORIGINS = ['*']  # Allow all origins for development
    
    # Cache settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    
    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Development settings
    if IS_DEVELOPMENT:
        TEMPLATES_AUTO_RELOAD = True
        SEND_FILE_MAX_AGE_DEFAULT = 0
        PROPAGATE_EXCEPTIONS = True
    else:
        TEMPLATES_AUTO_RELOAD = False
        SEND_FILE_MAX_AGE_DEFAULT = 3600
        PROPAGATE_EXCEPTIONS = False
    
    # PythonAnywhere specific settings
    if IS_PYTHONANYWHERE:
        MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB limit on PythonAnywhere
        MEMORY_LIMIT = 512 * 1024 * 1024  # 512MB limit on PythonAnywhere
        ENABLE_MEMORY_MONITORING = True
        CHUNK_SIZE = 500  # Smaller chunks for PythonAnywhere
    
    @classmethod
    def init_app(cls, app):
        """Initialize the Flask app with cross-platform configuration."""
        # Ensure required directories exist
        for dir_path in [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER, cls.CACHE_FOLDER, cls.LOGS_DIR]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Configure logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug and not app.testing:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler(
                cls.LOG_FILE, 
                maxBytes=10240000, 
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('AGT Designer startup')
    
    @property
    def LOGS_DIR(self):
        """Get logs directory path."""
        return os.path.dirname(self.LOG_FILE)

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0
    PROPAGATE_EXCEPTIONS = True
    ENABLE_MEMORY_MONITORING = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False
    SEND_FILE_MAX_AGE_DEFAULT = 3600
    PROPAGATE_EXCEPTIONS = False
    ENABLE_MEMORY_MONITORING = False

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False

# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration class based on environment."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config_map.get(config_name, config_map['default']) 