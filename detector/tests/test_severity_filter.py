import pytest

from detector.filters import severity_filter


def test_drops_info_and_debug():
    assert severity_filter.run({"level": "info"}) is True
    assert severity_filter.run({"level": "INFO"}) is True
    assert severity_filter.run({"level": "debug"}) is True


@pytest.mark.parametrize("level", ["error", "warn", "warning", "critical", None, 123])
def test_passes_other_levels(level):
    # Returns None to let downstream filters decide
    assert severity_filter.run({"level": level}) is None
