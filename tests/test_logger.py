"""
Unit tests for unified timestamped logger in Lunifier.
"""
import re
from lunifier.logger import log, add_log_listener, remove_log_listener


def test_logger_timestamp_and_listener(capsys):
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
        assert "[MultiTag]   Line 2" in lines[1]
    finally:
        remove_log_listener(on_log)

    received.clear()
    log("AfterRemove", "Should not be received")
    assert len(received) == 0
