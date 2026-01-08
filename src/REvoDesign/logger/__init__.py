"""
This module contains the logger setup.
"""

from .logger import LOGGER_CONFIG, ROOT_LOGGER, LoggerT, setup_logging

__all__ = ["setup_logging", "ROOT_LOGGER", "LoggerT", "LOGGER_CONFIG"]
