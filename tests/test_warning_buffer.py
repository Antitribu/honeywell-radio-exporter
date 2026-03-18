import logging

from honeywell_radio_exporter.warning_buffer import (
    WarningBufferHandler,
    get_recent_warnings,
)


def test_warning_buffer_captures_warning():
    root = logging.getLogger()
    root.handlers = [
        h for h in root.handlers if not isinstance(h, WarningBufferHandler)
    ]
    root.addHandler(WarningBufferHandler())
    root.setLevel(logging.DEBUG)
    log = logging.getLogger("test.warnbuf")
    log.warning("hello %s", "world")
    recent = get_recent_warnings()
    assert len(recent) >= 1
    assert recent[0]["message"] == "hello world"
    assert recent[0]["level"] == "WARNING"
    root.handlers = [
        h for h in root.handlers if not isinstance(h, WarningBufferHandler)
    ]
