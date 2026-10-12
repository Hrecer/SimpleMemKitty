from simplememkitty.core import stats


def test_format_gb():
    assert stats.format_gb(1024 ** 3) == 1.0
    assert stats.format_gb(0) == 0.0


def test_format_gb_str():
    assert stats.format_gb_str(1024 ** 3) == "1.00 GB"


def test_summarize():
    snap = {
        "total": 2 * 1024 ** 3,
        "used": 1 * 1024 ** 3,
        "available": 1 * 1024 ** 3,
        "percent": 50,
    }
    s = stats.summarize(snap)
    assert s["total_gb"] == 2.0
    assert s["used_gb"] == 1.0
    assert s["available_gb"] == 1.0
    assert s["percent"] == 50
