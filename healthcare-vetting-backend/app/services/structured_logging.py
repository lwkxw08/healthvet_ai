"""
Structured JSON logging for healthcare audit compliance.

Outputs JSON-formatted logs to stdout for ingestion by log aggregation
services (Datadog, BetterStack, Grafana Loki, etc.).

Usage:
    from app.services.structured_logging import setup_logging
    setup_logging()   # call once at app startup

Environment variables:
    LOG_LEVEL       — DEBUG / INFO / WARNING / ERROR (default: INFO)
    LOG_FORMAT      — "json" (default) or "text" for local development
    SERVICE_NAME    — identifies this service in aggregated logs (default: viperai-api)
    ENVIRONMENT     — production / staging / development (default: production)
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Emits one JSON object per log line — compatible with Datadog, BetterStack, etc."""

    def __init__(self, service: str, environment: str):
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service,
            "environment": self.environment,
        }

        # Add source location
        if record.pathname:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Exception",
                "message": str(record.exc_info[1]),
                "stack": traceback.format_exception(*record.exc_info),
            }

        # Add any extra fields passed via `logger.info("msg", extra={...})`
        for key in ("request_id", "user_id", "user_type", "agency_id",
                     "candidate_id", "action", "duration_ms", "status_code",
                     "method", "path", "ip", "http"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def setup_logging() -> None:
    """Configure root logger for structured JSON output."""
    service = os.environ.get("SERVICE_NAME", "viperai-api")
    environment = os.environ.get("ENVIRONMENT", "production")
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "json").lower()

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        handler.setFormatter(JSONFormatter(service=service, environment=environment))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))

    root.addHandler(handler)

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
