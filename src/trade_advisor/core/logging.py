"""Structured JSON logging via structlog.

Configures structlog with:
- JSON renderer for production (``json_logs=True``)
- Console renderer with colors for development (``json_logs=False``)

Every log entry includes: ``timestamp``, ``level``, ``message``, ``logger``,
``correlation_id``, ``module``.  Optional context fields: ``run_id``,
``strategy_id``, ``symbol``.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog
from structlog.stdlib import BoundLogger


def _add_default_fields(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    event_dict.setdefault("correlation_id", "")
    logger_name = event_dict.get("logger", "")
    if logger_name and "module" not in event_dict:
        event_dict["module"] = logger_name.replace("trade_advisor.", "")
    return event_dict


def configure_logging(
    level: int = logging.INFO,
    json_logs: bool = False,
) -> None:
    """Configure structlog for the application.

    Parameters
    ----------
    level:
        Python logging level (e.g. ``logging.INFO``, ``logging.DEBUG``).
    json_logs:
        ``True`` for JSON output (production), ``False`` for colored console
        output (development).
    """
    logging.basicConfig(format="%(message)s", level=level, force=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _add_default_fields,
        structlog.processors.EventRenamer("message"),
    ]

    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str | None = None) -> BoundLogger:
    """Return a bound structlog logger.

    Parameters
    ----------
    name:
        Logger name (typically ``__name__`` of the calling module).
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
