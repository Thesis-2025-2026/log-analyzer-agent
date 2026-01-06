from detector.filters import regex_filter


def test_regex_filter_allows_error_terms():
    # Contains "error" term -> return None (continue pipeline)
    assert regex_filter.run({"msg": "fatal error occurred"}) is None
    assert regex_filter.run({"message": "timeout while connecting"}) is None


def test_regex_filter_drops_benign_logs():
    # No error-ish terms -> return False (drop)
    assert regex_filter.run({"msg": "all good"}) is False
    assert regex_filter.run({"something": "healthy status"}) is False
