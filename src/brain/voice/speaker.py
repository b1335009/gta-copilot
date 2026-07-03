"""Text-to-speech via Piper (subprocess) + sounddevice playback.

Voice model: ``en_US-lessac-medium`` under ``models/piper/``.
Piper is run as a subprocess that reads text from stdin and writes
raw 16-bit 22050 Hz mono PCM to stdout.
"""

from __future__ import annotations

import io
import os
import struct
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np

DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
DEFAULT_PIPER_DIR = DEFAULT_MODELS_DIR / "piper"
DEFAULT_VOICE = "en_US-lessac-medium"
PIPER_SAMPLE_RATE = 22050


# ---------------------------------------------------------------------------
# TTS backend protocol (allows faking in tests)
# ---------------------------------------------------------------------------

class TTSBackend(Protocol):
    """Minimal interface for TTS synthesis."""

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Return (audio_int16, samplerate)."""
        ...


class PiperTTSBackend:
    """Real backend using Piper TTS as a subprocess."""

    def __init__(self, piper_dir: Optional[Path] = None, voice: str = DEFAULT_VOICE):
        self._piper_dir = piper_dir or DEFAULT_PIPER_DIR
        self._voice = voice
        self._piper_exe = self._find_piper_exe()
        self._voice_model = self._piper_dir / f"{voice}.onnx"
        self._voice_config = self._piper_dir / f"{voice}.onnx.json"

    def _find_piper_exe(self) -> Path:
        """Locate the piper executable."""
        # Check common locations
        candidates = [
            self._piper_dir / "piper.exe",
            self._piper_dir / "piper",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Fallback: assume it's on PATH
        return Path("piper")

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        cmd = [
            str(self._piper_exe),
            "--model", str(self._voice_model),
            "--output-raw",
        ]
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Piper TTS failed (rc={proc.returncode}): {proc.stderr.decode('utf-8', errors='replace')[:500]}")
        audio = np.frombuffer(proc.stdout, dtype=np.int16)
        return audio, PIPER_SAMPLE_RATE


# ---------------------------------------------------------------------------
# Audio playback backend protocol
# ---------------------------------------------------------------------------

class PlaybackBackend(Protocol):
    """Minimal interface for audio playback."""

    def play(self, audio_int16: np.ndarray, *, samplerate: int) -> None:
        ...


class SounddevicePlaybackBackend:
    """Real playback via sounddevice."""

    def play(self, audio_int16: np.ndarray, *, samplerate: int) -> None:
        import sounddevice as sd
        # Convert to float32 for playback
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        sd.play(audio_f32, samplerate=samplerate, blocking=True)


# ---------------------------------------------------------------------------
# Speaker result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SpeechResult:
    text: str
    tts_ms: float   # synthesis time
    play_ms: float  # playback time


# ---------------------------------------------------------------------------
# Speaker
# ---------------------------------------------------------------------------

class Speaker:
    """Synthesize text to speech and play it."""

    def __init__(
        self,
        tts_backend: Optional[TTSBackend] = None,
        playback_backend: Optional[PlaybackBackend] = None,
    ):
        self._tts = tts_backend or PiperTTSBackend()
        self._playback = playback_backend or SounddevicePlaybackBackend()

    def speak(self, text: str) -> SpeechResult:
        """Synthesize *text* and play it. Returns timing info."""
        # Synthesis
        t0 = time.perf_counter()
        audio, sr = self._tts.synthesize(text)
        tts_ms = (time.perf_counter() - t0) * 1000.0

        # Playback
        t1 = time.perf_counter()
        self._playback.play(audio, samplerate=sr)
        play_ms = (time.perf_counter() - t1) * 1000.0

        return SpeechResult(text=text, tts_ms=tts_ms, play_ms=play_ms)
