from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.config import LOG_LEVEL


_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in (
            "service",
            "operation",
            "attempt",
            "target",
            "event_type",
            "correlation_id",
            "duration_ms",
            "error_type",
        ):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
