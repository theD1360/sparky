import logging.config
import os
import sys

from dotenv import load_dotenv
from rich.console import Console

# Load environment variables from .env file
load_dotenv()


def setup_logging():
    """
    Configures logging for the application.

    Reads configuration from environment variables:
    - LOG_DIR: Directory for log files (default: "logs")
    - LOG_LEVEL: Logging level (default: "INFO")
      Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL (case-insensitive)

    Creates the log directory if it doesn't exist, and sets up
    file-based logging with console output.
    """
    log_dir = os.getenv("LOG_DIR", "logs")
    log_file_path = os.path.join(log_dir, "sparky.log")

    # Get log level from environment, default to INFO
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Map string to logging constant
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level = log_level_map.get(log_level_str, logging.INFO)

    # Warn if invalid log level provided
    if log_level_str not in log_level_map:
        print(
            f"Warning: Invalid LOG_LEVEL '{os.getenv('LOG_LEVEL')}'. "
            f"Valid values: {', '.join(log_level_map.keys())}. Using INFO.",
            file=sys.stderr,
        )

    # Create the log directory if it does not exist
    os.makedirs(log_dir, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(message)s",
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file_path,
                "maxBytes": 1024 * 1024 * 5,  # 5 MB
                "backupCount": 5,
                "formatter": "detailed",  # Use detailed format for file
                "level": log_level,
            },
            "rich": {
                "class": "rich.logging.RichHandler",
                "rich_tracebacks": True,
                "formatter": "default",
                "console": Console(file=sys.stderr),
                "level": log_level,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["file", "rich"],
        },
    }

    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured successfully. Level: {log_level_str}")
