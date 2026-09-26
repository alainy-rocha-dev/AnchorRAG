"""Logging estruturado JSON com request_id."""

from __future__ import annotations
import logging
import json
import sys
import uuid
from contextvars import ContextVar
from typing import Optional
from datetime import datetime
from pythonjsonlogger import jsonlogger


# Context variable para request_id
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Adiciona request_id aos logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "no-request"
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter JSON customizado."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    output: str = "stdout",
    include_request_id: bool = True,
) -> logging.Logger:
    """Configura logging estruturado."""
    logger = logging.getLogger("anchor_rag")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove handlers existentes
    logger.handlers.clear()

    # Handler
    if output == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    elif output == "stderr":
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.FileHandler(output)

    # Formatter
    if format == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(request_id)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s | %(message)s"
        )

    handler.setFormatter(formatter)

    # Filtro de request_id
    if include_request_id:
        handler.addFilter(RequestIdFilter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_logger(name: str = "anchor_rag") -> logging.Logger:
    """Obtém logger configurado."""
    return logging.getLogger(name)


def set_request_id(request_id: Optional[str] = None) -> str:
    """Define request_id para o contexto atual."""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    request_id_var.set(request_id)
    return request_id


def clear_request_id():
    """Limpa request_id do contexto."""
    request_id_var.set(None)


class LogContext:
    """Context manager para request_id."""

    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id
        self.previous = None

    def __enter__(self):
        self.previous = request_id_var.get()
        set_request_id(self.request_id)
        return self.request_id

    def __exit__(self, *args):
        if self.previous:
            request_id_var.set(self.previous)
        else:
            clear_request_id()