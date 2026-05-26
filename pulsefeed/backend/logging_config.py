"""
Structured JSON logging for PulseFeed.

All log records are emitted as newline-delimited JSON objects — ready for
any log aggregator (Loki, CloudWatch, Datadog, ...) without a parsing step.

Usage
-----
  from logging_config import configure_json_logging
  configure_json_logging()          # at process startup

JSON fields
-----------
  ts       ISO-8601 UTC timestamp
  level    DEBUG / INFO / WARNING / ERROR / CRITICAL
  logger   dotted module path
  msg      rendered log message
  exc      formatted traceback (only when exc_info is set)

Any extra= fields passed to logger.info(..., extra={key: val}) are merged
in verbatim.  Raw document bodies and user PII must never appear in extra.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime


class _JsonFormatter(logging.Formatter):
    _SKIP: frozenset[str] = frozenset({
        "msg", "args", "exc_info", "exc_text", "levelname", "levelno",
        "pathname", "filename", "module", "name", "created", "msecs",
        "relativeCreated", "thread", "threadName", "processName", "process",
        "funcName", "lineno", "stack_info", "taskName", "message",
    })

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key not in self._SKIP and not key.startswith("_"):
                entry[key] = val
        return json.dumps(entry, default=str)


def configure_json_logging(level: str = "INFO") -> None:
    """
    Replace all root-logger handlers with a single JSON stream handler.

    Safe to call multiple times.  Respects the LOG_LEVEL environment variable
    so operators can dial up DEBUG without a code change.
    """
    effective_level = os.environ.get("LOG_LEVEL", level).upper()
    formatter = _JsonFormatter()

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(effective_level)

    # Suppress high-volume library loggers that add noise without signal
    for noisy in (
        "uvicorn.access",
        "httpx",
        "httpcore",
        "openai",
        "openai._base_client",
        "apscheduler",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
