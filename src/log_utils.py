import logging
import json
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging():
    log_dir = Path.home() / ".forge" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "forge.log"
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # JSON-like format
    formatter = logging.Formatter('{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')
    
    handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
