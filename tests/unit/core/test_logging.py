"""Unit tests for core/logging.py — structlog JSON output, required fields, renderers."""

from __future__ import annotations

import json
import logging
from io import StringIO

import structlog

from trade_advisor.core.logging import configure_logging, get_logger


class TestConfigureLogging:
    def test_json_renderer(self):
        configure_logging(level=logging.DEBUG, json_logs=True)

        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        stdlib_logger = logging.getLogger("test.json.renderer")
        stdlib_logger.addHandler(handler)
        stdlib_logger.setLevel(logging.DEBUG)

        sl = structlog.get_logger("test.json.renderer")
        sl.info("hello json")

        output = buf.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["message"] == "hello json"
        assert parsed["level"] == "info"

    def test_console_renderer(self):
        configure_logging(level=logging.DEBUG, json_logs=False)
        logger = get_logger("test.console")
        assert logger is not None

    def test_default_fields_present(self):
        configure_logging(level=logging.DEBUG, json_logs=True)

        buf = StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
        )
        stdlib_logger = logging.getLogger("test.fields")
        stdlib_logger.addHandler(handler)
        stdlib_logger.setLevel(logging.DEBUG)

        sl = structlog.get_logger("test.fields")
        sl.info("test fields")

        output = buf.getvalue().strip()
        parsed = json.loads(output)
        assert "message" in parsed
        assert "level" in parsed
        assert "correlation_id" in parsed
        assert "logger" in parsed
        assert "timestamp" in parsed
        assert "module" in parsed


class TestGetLogger:
    def test_returns_logger_proxy(self):
        configure_logging(level=logging.INFO)
        logger = get_logger("test.module")
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_name_none(self):
        configure_logging(level=logging.INFO)
        logger = get_logger()
        assert logger is not None

    def test_named_logger(self):
        configure_logging(level=logging.INFO)
        logger = get_logger("trade_advisor.core.types")
        assert logger is not None
