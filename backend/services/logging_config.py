"""
Structured logging setup for Aether.

Every log line carries a request_id so a single /chat call can be traced
across router -> plugin_manager -> ollama_service -> storage, which was not
possible before (bare `except:` blocks swallowed errors with no trace at
all). Call configure_logging() once at startup (see main.py).
"""

import logging
import sys

import structlog


def configure_logging():
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "aether"):
    return structlog.get_logger(name)
