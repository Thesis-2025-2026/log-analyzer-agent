from detector.filters import similarity_filter


class DummyRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True


def test_similarity_first_time_passes(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(similarity_filter, "_redis", lambda: dummy)

    # First time: set nx=True succeeds -> returns True (publish)
    assert similarity_filter.run({"a": 1}) is True
    # Second time same-ish fingerprint: set nx=True fails -> returns False (drop)
    assert similarity_filter.run({"a": 1}) is False


def test_similarity_handles_unhashable(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(similarity_filter, "_redis", lambda: dummy)
    # Should not raise on weird payload; either returns None (on failure) or True if it hashes anyway
    result = similarity_filter.run({"a": object()})
    assert result in (None, True)
