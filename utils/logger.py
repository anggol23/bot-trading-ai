"""
Logging Utility - Structured logging with file rotation.
"""

import os
import sys
import io
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# Custom TRADE log level (between INFO and WARNING)
TRADE_LEVEL = 25
logging.addLevelName(TRADE_LEVEL, "TRADE")


def trade(self, message, *args, **kwargs):
    if self.isEnabledFor(TRADE_LEVEL):
        self._log(TRADE_LEVEL, message, args, **kwargs)


logging.Logger.trade = trade

_configured = False


def setup_logging(level: str = "INFO", log_dir: str = "logs"):
    """Configure logging with console + rotating file handlers."""
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(log_dir, exist_ok=True)

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Format (use ASCII pipe | instead of Unicode box character)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (Only ERROR and above)
    console = logging.StreamHandler()
    if sys.platform == 'win32':
        console.stream = io.TextIOWrapper(console.stream.buffer, encoding='utf-8', errors='replace')
    console.setLevel(logging.ERROR)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler (daily rotation) - use UTF-8 encoding
    log_file = os.path.join(log_dir, "trading_agent.log")
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=30, encoding='utf-8'
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Trade-specific log file - use UTF-8 encoding
    trade_file = os.path.join(log_dir, "trades.log")
    trade_handler = TimedRotatingFileHandler(
        trade_file, when="midnight", interval=1, backupCount=90, encoding='utf-8'
    )
    trade_handler.setLevel(TRADE_LEVEL)
    trade_handler.setFormatter(fmt)
    root.addHandler(trade_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call setup_logging() first."""
    return logging.getLogger(name)
