"""
Unit tests for unified timestamped logger in Lunifier.
"""
import re
from lunifier.logger import (
    log, log_debug, add_log_listener, remove_log_listener,
    set_log_level, get_log_level, is_debug_enabled,
    LOG_LEVEL_NONE, LOG_LEVEL_NORMAL, LOG_LEVEL_DEBUG
)


def test_logger_timestamp_and_listener(capsys):
    set_log_level(LOG_LEVEL_NORMAL)
    received = []

    def on_log(msg: str):
        received.append(msg)

    add_log_listener(on_log)

    try:
        log("TestTag", "Hello from test")
        assert len(received) == 1
        msg = received[0]

        # Verify format: [YYYY-MM-DD HH:MM:SS.mmm] [TestTag] Hello from test
        pattern = r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\] \[TestTag\] Hello from test$"
        assert re.match(pattern, msg) is not None

        out = capsys.readouterr().out.strip()
        assert out == msg

        # Test multiline
        received.clear()
        log("MultiTag", "Line 1\nLine 2")
        assert len(received) == 1
        lines = received[0].splitlines()
        assert len(lines) == 2
        assert "[MultiTag] Line 1" in lines[0]
        assert "Line 2" in lines[1]
    finally:
        remove_log_listener(on_log)

    received.clear()
    log("AfterRemove", "Should not be received")
    assert len(received) == 0


def test_logger_levels(capsys):
    received = []

    def on_log(msg: str):
        received.append(msg)

    add_log_listener(on_log)

    try:
        # 1. Normal Level
        set_log_level("normal")
        assert get_log_level() == LOG_LEVEL_NORMAL
        assert is_debug_enabled() is False

        received.clear()
        log("Test", "Normal message")
        assert len(received) == 1
        log_debug("Test", "Debug message should be ignored")
        assert len(received) == 1

        # 2. Debug Level
        set_log_level("debug")
        assert get_log_level() == LOG_LEVEL_DEBUG
        assert is_debug_enabled() is True

        received.clear()
        log("Test", "Normal message")
        assert len(received) == 1
        log_debug("Test", "Debug message")
        assert len(received) == 2
        assert "[DEBUG] [Test] Debug message" in received[1]

        # 3. None / Off Level
        set_log_level("none")
        assert get_log_level() == LOG_LEVEL_NONE
        assert is_debug_enabled() is False

        received.clear()
        log("Test", "Should not log")
        log_debug("Test", "Should not log debug")
        assert len(received) == 0
    finally:
        set_log_level(LOG_LEVEL_NORMAL)
        remove_log_listener(on_log)

