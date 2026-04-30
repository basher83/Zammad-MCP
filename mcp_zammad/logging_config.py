"""Logging configuration helpers for Zammad MCP."""

import logging
import os
import sys


def configure_logging() -> None:
    """Configure root logging to avoid stdout corruption for MCP stdio transport."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if log_level_str not in valid_levels:
        invalid_level = log_level_str
        log_level_str = "INFO"
        logging.getLogger(__name__).warning(
            "Invalid LOG_LEVEL '%s', defaulting to INFO. Valid values: %s",
            invalid_level,
            ", ".join(valid_levels),
        )

    log_level = getattr(logging, log_level_str)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            stream = getattr(handler, "stream", None)
            if stream in {sys.stdout, sys.__stdout__}:
                handler.setStream(sys.stderr)

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root_logger.addHandler(handler)
