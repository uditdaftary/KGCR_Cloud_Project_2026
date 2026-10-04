"""LLM access for the advisor: Gemini behind committed fixtures.

Tests and the demo replay recorded responses from ``results/llm_fixtures/``. A live
call happens only when both ``GEMINI_API_KEY`` is set and ``KGCR_LLM_LIVE=1`` is
opted into, and is capped per process so a bug cannot run up free-tier quota. A
recorded response stores a hash of the prompt it answered: if the prompt template
changes, replay fails loudly instead of returning a stale answer.

The key is read from the environment at call time and is never logged or written.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Protocol

__all__ = [
    "GEMINI_MODEL",
    "DEFAULT_FIXTURE_DIR",
    "LIVE_CALL_CAP",
    "LLMClient",
    "GeminiClient",
    "FixtureClient",
    "MissingFixtureError",
    "StaleFixtureError",
    "live_client_from_env",
]

logger = logging.getLogger(__name__)

# Verified 2026-10-04 against ai.google.dev/gemini-api/docs/models (listed stable).
GEMINI_MODEL = "gemini-3.7-flash"
DEFAULT_FIXTURE_DIR = Path("results/llm_fixtures")
# 4 sycophancy specs x 3 passes + 8 recall/false-positive estates, with headroom.
LIVE_CALL_CAP = 24


class LLMClient(Protocol):
    def complete(self, prompt: str, label: str) -> str:
        """Return the model's text response to ``prompt``; ``label`` names the call."""
        ...


class MissingFixtureError(LookupError):
    """No recorded response and live calls are not enabled."""


class StaleFixtureError(ValueError):
    """A recorded response answers a different prompt than the one now rendered."""


class GeminiClient:
    """Live Gemini calls through the ``google-genai`` SDK (the ``advisor`` extra)."""

    def __init__(self, model: str = GEMINI_MODEL) -> None:
        self.model = model

    def complete(self, prompt: str, label: str) -> str:
        # Imported here so the package imports and type-checks without the extra.
        from google import genai

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(model=self.model, contents=prompt)
        text = response.text
        if not isinstance(text, str) or not text:
            raise RuntimeError(f"empty Gemini response for {label}")
        return text


def live_client_from_env() -> LLMClient | None:
    """A live client if the key is set and ``KGCR_LLM_LIVE=1``; otherwise None."""
    if os.environ.get("KGCR_LLM_LIVE") != "1":
        logger.info("live LLM calls disabled (KGCR_LLM_LIVE != 1); replaying fixtures only")
        return None
    if not os.environ.get("GEMINI_API_KEY"):
        logger.warning("KGCR_LLM_LIVE=1 but GEMINI_API_KEY is unset; replaying fixtures only")
        return None
    return GeminiClient()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FixtureClient:
    """Replay recorded responses; record new ones through ``live`` when given."""

    def __init__(
        self,
        directory: Path = DEFAULT_FIXTURE_DIR,
        live: LLMClient | None = None,
        *,
        model: str = GEMINI_MODEL,
        max_live_calls: int = LIVE_CALL_CAP,
    ) -> None:
        self.directory = directory
        self.live = live
        self.model = model
        self.max_live_calls = max_live_calls
        self.live_calls = 0

    def _path(self, label: str) -> Path:
        return self.directory / f"{label}.json"

    def complete(self, prompt: str, label: str) -> str:
        path = self._path(label)
        digest = _sha256(prompt)
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["prompt_sha256"] != digest or record["model"] != self.model:
                raise StaleFixtureError(f"{path} was recorded for a different prompt or model")
            response: str = record["response"]
            return response
        if self.live is None:
            raise MissingFixtureError(f"no fixture at {path} and live calls are disabled")
        if self.live_calls >= self.max_live_calls:
            raise RuntimeError(f"live call cap of {self.max_live_calls} reached at {label}")
        self.live_calls += 1
        logger.info("live LLM call %d/%d: %s", self.live_calls, self.max_live_calls, label)
        response = self.live.complete(prompt, label)
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {
            "model": self.model,
            "label": label,
            "prompt_sha256": digest,
            "response": response,
        }
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return response
