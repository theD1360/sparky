"""Tests for embedding retry helpers."""

from unittest.mock import patch

import pytest

from database.embeddings import _call_with_embed_retry, _is_transient_embed_error


def test_is_transient_embed_error_detects_503_and_dns():
    assert _is_transient_embed_error(Exception("503 DNS resolution failed"))
    assert _is_transient_embed_error(Exception("failed to connect to all addresses"))
    assert not _is_transient_embed_error(Exception("invalid api key"))


def test_call_with_embed_retry_succeeds_after_transient_failures():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("503 failed to connect to all addresses")
        return "ok"

    with patch("database.embeddings.time.sleep") as sleep:
        assert _call_with_embed_retry(flaky, what="test", max_attempts=4) == "ok"
        assert attempts["n"] == 3
        assert sleep.call_count == 2


def test_call_with_embed_retry_does_not_retry_permanent_errors():
    def permanent():
        raise ValueError("invalid api key")

    with patch("database.embeddings.time.sleep") as sleep:
        with pytest.raises(ValueError, match="invalid api key"):
            _call_with_embed_retry(permanent, what="test", max_attempts=4)
        sleep.assert_not_called()
