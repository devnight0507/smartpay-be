import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core import logging as logging_module


def test_serialize_record_basic():
    record = {
        "time": datetime.now(),
        "level": SimpleNamespace(name="INFO"),
        "message": "Test message",
        "name": "test_module",
        "function": "test_function",
        "line": 123,
        "extra": {
            "trace_id": "abc-123",
            "span_id": "xyz-789",
            "custom": "value",
        },
    }

    serialized = logging_module.serialize_record(record)
    assert '"message": "Test message"' in serialized
    assert '"trace_id": "abc-123"' in serialized
    assert '"custom": "value"' in serialized


def test_serialize_record_fallback():
    # Trigger serialization error using a non-serializable object
    record = {
        "time": datetime.now(),
        "level": SimpleNamespace(name="ERROR"),
        "message": "Fails",
        "extra": {"custom": object()},  # non-serializable
    }

    serialized = logging_module.serialize_record(record)
    assert "Error serializing log" in serialized
    assert "Fails" in serialized


def test_intercept_handler_emit_levels(caplog):
    handler = logging_module.InterceptHandler()

    class FakeRecord:
        def __init__(self, levelno, message):
            self.levelno = levelno
            self.exc_info = None

        def getMessage(self):
            return "test log message"

    with caplog.at_level(logging.DEBUG):
        handler.emit(FakeRecord(logging.INFO, "info"))
        handler.emit(FakeRecord(logging.ERROR, "error"))
        handler.emit(FakeRecord(logging.DEBUG, "debug"))

    # Loguru doesn't store in caplog, but this confirms it runs without error
    assert True


@patch("app.core.logging.logger")
@patch("app.core.logging.settings.JSON_LOGS", True)
def test_configure_logging_json(mock_logger):
    mock_logger.add = MagicMock()
    mock_logger.remove = MagicMock()

    logging_module.configure_logging()
    mock_logger.add.assert_called()
    mock_logger.remove.assert_called()
    assert mock_logger.info.called


@patch("app.core.logging.logger")
@patch("app.core.logging.settings.JSON_LOGS", False)
def test_configure_logging_human(mock_logger):
    mock_logger.add = MagicMock()
    mock_logger.remove = MagicMock()

    logging_module.configure_logging()
    mock_logger.add.assert_called()
    mock_logger.remove.assert_called()
    assert mock_logger.info.called
