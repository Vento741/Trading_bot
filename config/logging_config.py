import logging
import logging.handlers
from pathlib import Path
from .settings import LOG_LEVEL, LOG_FORMAT, LOG_DIR

def setup_logging(name: str) -> logging.Logger:
    """Setup logging configuration for the application"""
    
    # Create logs directory if it doesn't exist
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Create handlers
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger