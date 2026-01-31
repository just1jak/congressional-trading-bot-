"""Logging configuration for the trading bot"""

import sys
from pathlib import Path
from loguru import logger
import yaml


def setup_logger(config_path: str = "config/config.yaml") -> None:
    """
    Configure the logger based on config settings.

    Args:
        config_path: Path to configuration file
    """
    # Load config
    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        log_config = config.get('logging', {})
    else:
        # Default config
        log_config = {
            'level': 'INFO',
            'log_to_file': True,
            'log_file': 'logs/trading_bot.log',
            'max_log_size_mb': 100,
            'backup_count': 5
        }

    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_config.get('level', 'INFO'),
        colorize=True
    )

    # Add file handler if enabled
    if log_config.get('log_to_file', True):
        log_file = log_config.get('log_file', 'logs/trading_bot.log')
        # Ensure logs directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
            level=log_config.get('level', 'INFO'),
            rotation=f"{log_config.get('max_log_size_mb', 100)} MB",
            retention=log_config.get('backup_count', 5),
            compression="zip"
        )

    logger.info("Logger initialized")


def get_logger():
    """Get the configured logger instance"""
    return logger
