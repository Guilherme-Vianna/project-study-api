import json
import logging
import sys
from typing import Any

from app.core.config import settings

LABELS_KEY = "logging.googleapis.com/labels"
RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "labels", "fields"}
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class CloudJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "revision": settings.k_revision,
        }
        entry.update(getattr(record, "fields", {}))
        labels = {key: str(value) for key, value in getattr(record, "labels", {}).items()}
        if labels:
            entry[LABELS_KEY] = labels
        if record.exc_info:
            entry["stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        extra = {**getattr(record, "labels", {}), **getattr(record, "fields", {})}
        if extra:
            text += " " + " ".join(f"{key}={value}" for key, value in extra.items())
        return text


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(CloudJsonFormatter())
    else:
        handler.setFormatter(TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


def log_event(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    labels: dict[str, Any] | None = None,
    **fields: Any,
) -> None:
    logger.log(level, message, extra={"labels": labels or {}, "fields": fields})
