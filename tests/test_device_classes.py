from honeywell_radio_exporter.device_classes import describe_device_class


def test_describe_known():
    h, d = describe_device_class("01:123456")
    assert h == "01"
    assert d == "Controller"


def test_describe_trv():
    h, d = describe_device_class("04:000001")
    assert h == "04"
    assert "TRV" in d


def test_describe_unknown():
    h, d = describe_device_class("aa:111111")
    assert h == "aa"
    assert "Unknown" in (d or "")


def test_describe_empty():
    h, d = describe_device_class("")
    assert h == ""
    assert d is None
