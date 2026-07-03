"""
app/core/logging_config.py
--------------------------
Configures stdlib logging to emit structured JSON lines in production
and human-readable colored output in development.
Every log record includes: timestamp, level, logger name, message,
and any extra key=value fields passed by the caller.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any


class _JSONFormatter(logging.Formatter):
    """
    Emits each log record as a single-line JSON object.
    Used in staging/production where log aggregators (Datadog, Loki, etc.)
    expect machine-parseable output.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach any extra fields the caller provided
        skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in skip:
                try:
                    json.dumps(value)  # only include JSON-serializable extras
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


class _DevFormatter(logging.Formatter):
    """
    Human-readable output for local development.
    Includes caller location (module:lineno) to speed up debugging.
    """

    LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        location = f"{record.module}:{record.lineno}"
        line = (
            f"{color}[{record.levelname:<8}]{self.RESET} "
            f"\033[90m{ts} {location:<30}{self.RESET} "
            f"{record.getMessage()}"
        )
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(level: str = "INFO", use_json: bool = False) -> None:
    """
    Call once at application startup (in main.py lifespan or celery_app.py).
    Configures the root logger; all module-level loggers inherit this config.

    Args:
        level: Logging level string ("DEBUG", "INFO", etc.)
        use_json: True in staging/production; False for local dev.
    """
    formatter: logging.Formatter = (
        _JSONFormatter() if use_json else _DevFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy third-party loggers
    for noisy in ("httpx", "httpcore", "yfinance", "urllib3", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("aureus").setLevel(level)
