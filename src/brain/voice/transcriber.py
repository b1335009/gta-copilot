"""Speech-to-text via faster-whisper (base.en, int8, CPU).

Transcribes a Recording (or raw WAV bytes) and returns the transcript
plus timing in milliseconds.
"""

from __future__ import annotations

import io
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import numpy as np

DEFAULT_MODEL_SIZE = "base.en"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_DEVICE = "cpu"
DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


# ---------------------------------------------------------------------------
# Whisper backend protocol (allows faking in tests)
# ---------------------------------------------------------------------------

class WhisperBackend(Protocol):
    """Minimal interface for STT."""

    def transcribe(self, audio_float32: np.ndarray, *, samplerate: int) -> str:
        ...


class FasterWhisperBackend:
    """Real backend using ``faster-whisper``."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
        device: str = DEFAULT_DEVICE,
        download_root: Optional[str] = None,
    ):
        from faster_whisper import WhisperModel
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=download_root or str(DEFAULT_MODELS_DIR / "whisper"),
        )

    def transcribe(self, audio_float32: np.ndarray, *, samplerate: int) -> str:
        segments, _info = self._model.transcribe(
            audio_float32,
            language="en",
            beam_size=1,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


# ---------------------------------------------------------------------------
# Transcription result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    stt_ms: float


# ---------------------------------------------------------------------------
# Transcriber
# ---------------------------------------------------------------------------

class Transcriber:
    """Wraps a WhisperBackend, converts int16→float32, times the operation."""

    def __init__(self, backend: Optional[WhisperBackend] = None):
        self._backend = backend or FasterWhisperBackend()

    def transcribe_audio(self, audio_int16: np.ndarray, *, samplerate: int = 16_000) -> TranscriptionResult:
        """Transcribe int16 audio samples. Returns text + stt_ms."""
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        start = time.perf_counter()
        text = self._backend.transcribe(audio_f32, samplerate=samplerate)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return TranscriptionResult(text=text, stt_ms=elapsed_ms)

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> TranscriptionResult:
        """Transcribe from in-memory WAV file bytes."""
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        audio_int16 = np.frombuffer(frames, dtype=np.int16)
        return self.transcribe_audio(audio_int16, samplerate=sr)
