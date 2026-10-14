"""Transient Gemini trouble is retried a bounded number of times; the rest is raised at once."""

from __future__ import annotations

import pytest

pytest.importorskip("google.genai")

from google.genai import errors  # noqa: E402

from kgcr.advisor import llm  # noqa: E402


class _Response:
    text = "ok"


class _Models:
    def __init__(self, failures: list[int]) -> None:
        self.failures = failures
        self.calls = 0

    def generate_content(self, **_: object) -> _Response:
        self.calls += 1
        if self.failures:
            code = self.failures.pop(0)
            raise errors.ServerError(code, {"error": {"code": code, "message": "x"}})
        return _Response()


def _client(models: _Models) -> type:
    class Client:
        def __init__(self, **_: object) -> None:
            self.models = models

    return Client


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(llm.time, "sleep", slept.append)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return slept


def test_a_transient_503_is_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, _no_sleep: list[float]
) -> None:
    models = _Models([503, 429])
    monkeypatch.setattr("google.genai.Client", _client(models))
    assert llm.GeminiClient().complete("p", "label") == "ok"
    assert models.calls == 3 and _no_sleep == list(llm.RETRY_DELAYS_SECONDS)


def test_it_gives_up_after_the_bounded_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    models = _Models([503, 503, 503, 503])
    monkeypatch.setattr("google.genai.Client", _client(models))
    with pytest.raises(errors.ServerError):
        llm.GeminiClient().complete("p", "label")
    assert models.calls == len(llm.RETRY_DELAYS_SECONDS) + 1


def test_a_non_transient_error_is_raised_at_once(
    monkeypatch: pytest.MonkeyPatch, _no_sleep: list[float]
) -> None:
    models = _Models([400])
    monkeypatch.setattr("google.genai.Client", _client(models))
    with pytest.raises(errors.APIError):
        llm.GeminiClient().complete("p", "label")
    assert models.calls == 1 and _no_sleep == []
