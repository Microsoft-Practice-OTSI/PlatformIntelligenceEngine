"""Structured logging and rich console presentation for PIE."""

import logging
import sys
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "bold magenta",
    "dim": "dim white",
})

console = Console(theme=custom_theme)


def setup_logger(name: str = "pie", level: str = "INFO") -> logging.Logger:
    """Configure and return a structured Rich logger."""
    logger = logging.getLogger(name)
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger


def get_logger(name: str = "pie") -> logging.Logger:
    """Retrieve an existing logger or return a newly configured one."""
    return logging.getLogger(name)
