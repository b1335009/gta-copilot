"""Conversational chat via Ollama (hermes3:3b).

Generates short co-pilot replies (≤ 25 words) with live game-state context.
Uses CPU inference (num_gpu: 0) to avoid VRAM contention with GTA V.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Protocol

DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "hermes3:3b"

SYSTEM_PROMPT = (
    "You are the player's co-pilot riding shotgun in GTA V. "
    "Answer the player directly in one punchy, street-smart sentence under 15 words. "
    "No markdown, no quotes, never describe or repeat the prompt."
)

COMPANION_SYSTEM_PROMPT = (
    "You are the player's embodied companion fighting alongside them in GTA V. "
    "You know your own health. "
    "Answer in one punchy, street-smart sentence under 15 words. "
    "No markdown, no quotes, never describe."
)

def _choose_system_prompt(game_state_summary: str) -> str:
    if "companion=" in game_state_summary or "companion_hp=" in game_state_summary:
        return COMPANION_SYSTEM_PROMPT
    return SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Chat backend protocol (allows faking in tests)
# ---------------------------------------------------------------------------

class ChatBackend(Protocol):
    """Minimal chat interface."""

    def generate(self, *, system: str, prompt: str) -> str:
        ...


class OllamaChatBackend:
    """Real backend using Ollama's /api/generate endpoint.

    Key decisions from PROJECT_STATE.md:
    - ``num_gpu: 0`` → CPU-only inference (GPU belongs to GTA)
    - ``keep_alive: -1`` → model stays loaded permanently
    - ``num_predict: 40`` → hard cap on reply length
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: float = 20.0,
    ):
        self.endpoint = (
            endpoint
            or os.environ.get("GTA_COPILOT_OLLAMA_ENDPOINT")
            or DEFAULT_OLLAMA_ENDPOINT
        ).rstrip("/")
        self.model = model or os.environ.get("GTA_COPILOT_OLLAMA_MODEL") or DEFAULT_MODEL
        self.timeout_s = timeout_s

    def preload(self) -> bool:
        """Preload the model with keep_alive=-1 so it stays resident.

        This is done at startup BEFORE the game runs to lock it in CPU memory.
        Returns True if preload succeeded.
        """
        body = json.dumps({
            "model": self.model,
            "keep_alive": -1,
            # Without num_gpu here the preload loads the GPU runner and pins
            # it (verified via ollama ps); the CPU option must match generate().
            "options": {"num_gpu": 0},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("done", False)
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return False

    def generate(self, *, system: str, prompt: str) -> str:
        body = json.dumps({
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 24,
                "num_gpu": 0,         # CPU-only — GTA owns the GPU
                "stop": ["\n"],
            },
            "keep_alive": -1,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("response") or "").strip()


# ---------------------------------------------------------------------------
# Chat result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChatResult:
    reply: str
    llm_ms: float
    fallback: bool
    model: str
    endpoint: str


def _clean_reply(text: str) -> str:
    """Strip quotes, collapse whitespace, keep first sentence."""
    cleaned = " ".join(text.strip().strip("\"'`\u201c\u201d\u2018\u2019").replace("\r", " ").replace("\n", " ").split())
    for i, ch in enumerate(cleaned):
        if ch in ".?!":
            return cleaned[: i + 1].strip()
    return cleaned


# ---------------------------------------------------------------------------
# Chat client (orchestrates backend + timing + fallback)
# ---------------------------------------------------------------------------

class CopilotChat:
    """Generate co-pilot replies with game-state context."""

    def __init__(self, backend: Optional[ChatBackend] = None,
                 endpoint: Optional[str] = None,
                 model: Optional[str] = None):
        if backend is not None:
            self._backend = backend
            self._endpoint = getattr(backend, "endpoint", "custom")
            self._model = getattr(backend, "model", "custom")
        else:
            real = OllamaChatBackend(endpoint=endpoint, model=model)
            self._backend = real
            self._endpoint = real.endpoint
            self._model = real.model

    @property
    def model(self) -> str:
        return self._model

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def preload(self) -> bool:
        """Preload the model if using the real Ollama backend."""
        if hasattr(self._backend, "preload"):
            return self._backend.preload()
        return True

    def reply(self, user_text: str, *, game_state_summary: str = "") -> ChatResult:
        """Generate a co-pilot reply to the player's spoken text.

        Parameters
        ----------
        user_text : str
            What the player said (STT transcript).
        game_state_summary : str
            One-line summary of current game state for context injection.
        """
        context_block = f"\n\nCurrent game state: {game_state_summary}" if game_state_summary else ""
        prompt = f"Player says: \"{user_text}\"{context_block}"
        system_prompt = _choose_system_prompt(game_state_summary)

        start = time.perf_counter()
        try:
            raw = self._backend.generate(system=system_prompt, prompt=prompt)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            reply = _clean_reply(raw)
            if not reply:
                return self._fallback("model returned empty response", elapsed_ms)
            return ChatResult(
                reply=reply,
                llm_ms=elapsed_ms,
                fallback=False,
                model=self._model,
                endpoint=self._endpoint,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return self._fallback(f"LLM error: {exc}", elapsed_ms)

    def react_to_wanted(self, *, previous: int, current: int,
                        game_state_summary: str) -> ChatResult:
        """Generate a reaction to a wanted-level increase (spoken via TTS)."""
        prompt = (
            f"Police stars just rose from {previous} to {current}. "
            f"Current game state: {game_state_summary}\n"
            f"React urgently in one sentence under 12 words."
        )
        system_prompt = _choose_system_prompt(game_state_summary)
        start = time.perf_counter()
        try:
            raw = self._backend.generate(system=system_prompt, prompt=prompt)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            reply = _clean_reply(raw)
            if not reply:
                return self._fallback("model returned empty response", elapsed_ms)
            return ChatResult(
                reply=reply,
                llm_ms=elapsed_ms,
                fallback=False,
                model=self._model,
                endpoint=self._endpoint,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return self._fallback(f"LLM error: {exc}", elapsed_ms)

    def react_to_companion_death(self, *, game_state_summary: str) -> ChatResult:
        """Generate a short cinematic reaction when the companion dies."""
        prompt = (
            f"You were just killed in action! "
            f"Current game state: {game_state_summary}\n"
            f"Say your last words in one short dramatic sentence under 10 words."
        )
        # Always use the embodied persona for the death reaction
        start = time.perf_counter()
        try:
            raw = self._backend.generate(system=COMPANION_SYSTEM_PROMPT, prompt=prompt)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            reply = _clean_reply(raw)
            if not reply:
                return self._fallback("model returned empty response", elapsed_ms)
            return ChatResult(
                reply=reply,
                llm_ms=elapsed_ms,
                fallback=False,
                model=self._model,
                endpoint=self._endpoint,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return self._fallback(f"LLM error: {exc}", elapsed_ms)

    def _fallback(self, reason: str, elapsed_ms: float) -> ChatResult:
        return ChatResult(
            reply=f"[FALLBACK: {reason}]",
            llm_ms=elapsed_ms,
            fallback=True,
            model=self._model,
            endpoint=self._endpoint,
        )
