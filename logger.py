import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime


def get_logger(name: str = "tire_ai") -> logging.Logger:
    """
    Get a logger instance with Windows-compatible file handling.
    Uses RotatingFileHandler instead of TimedRotatingFileHandler to avoid
    Windows file permission errors when multiple processes access the log.
    
    Logging can be disabled by setting CAPTURE_LOGS=false in .env file.
    """    # Import config inside function to avoid circular import
    import config
    
    # Check if logging is enabled (handle both boolean and string values)
    capture_logs_value = config.get_config_value("CAPTURE_LOGS", "true")
    
    # Handle boolean values (True/False) or string values ("true"/"false")
    if isinstance(capture_logs_value, bool):
        capture_logs = capture_logs_value
    else:
        capture_logs = str(capture_logs_value).lower() in ('true', '1', 'yes')
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # If logging is disabled, use NullHandler
    if not capture_logs:
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger
    
    # If logging is enabled, proceed with file handler
    log_dir = config.get_config_value("LOG_FILE_DIR")
    log_prefix = config.get_config_value("LOG_FILE_PREFIX")
    os.makedirs(log_dir, exist_ok=True)
    
    # Use date-based filename (no rotation needed - new file each day)
    log_filename = os.path.join(
        log_dir, f"{log_prefix}_{datetime.now().strftime('%Y-%m-%d')}.log"
    )
    
    # Use RotatingFileHandler with large max size (100MB) instead of TimedRotatingFileHandler
    # This avoids Windows file locking issues during log rotation
    handler = RotatingFileHandler(
        log_filename,
        maxBytes=100 * 1024 * 1024,  # 100MB max file size
        backupCount=7,
        encoding="utf-8",
        delay=True  # Don't open file until first write (reduces lock contention)
    )
    
    formatter = logging.Formatter(
        '%(levelname)s | DateTime: %(asctime)s | File: %(name)s | Message: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Only add handler if not already present (avoid duplicate handlers)
    if not logger.handlers:
        logger.addHandler(handler)
        
    logger.propagate = False
    return logger