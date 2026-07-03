"""Push-to-talk audio recorder.

Hold the PTT key (default F8) to capture 16 kHz mono int16 audio via sounddevice.
The recorder is unit-testable: audio capture is behind an injectable backend.
"""

from __future__ import annotations

import io
import struct
import threading
import time
import wave
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

import numpy as np

# ---------------------------------------------------------------------------
# Audio capture backend protocol (allows faking in tests)
# ---------------------------------------------------------------------------

class AudioBackend(Protocol):
    """Minimal interface for audio capture."""

    def start_stream(self, *, samplerate: int, channels: int, dtype: str,
                     callback: Callable[..., None]) -> Any:
        ...

    def stop_stream(self, stream: Any) -> None:
        ...


class SounddeviceBackend:
    """Real backend using the ``sounddevice`` library."""

    def start_stream(self, *, samplerate: int, channels: int, dtype: str,
                     callback: Callable[..., None]) -> Any:
        import sounddevice as sd
        stream = sd.InputStream(
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
            callback=callback,
        )
        stream.start()
        return stream

    def stop_stream(self, stream: Any) -> None:
        stream.stop()
        stream.close()


# ---------------------------------------------------------------------------
# Hotkey backend protocol (allows faking in tests)
# ---------------------------------------------------------------------------

class HotkeyBackend(Protocol):
    """Minimal interface for PTT key detection."""

    def is_pressed(self, key: str) -> bool:
        ...

    def wait(self, key: str, *, suppress: bool) -> None:
        """Block until *key* is pressed."""
        ...


class KeyboardHotkeyBackend:
    """Real backend using the ``keyboard`` library."""

    def is_pressed(self, key: str) -> bool:
        import keyboard
        return keyboard.is_pressed(key)

    def wait(self, key: str, *, suppress: bool = False) -> None:
        import keyboard
        keyboard.wait(key, suppress=suppress)


# ---------------------------------------------------------------------------
# Recording result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Recording:
    """A completed PTT recording."""
    audio_int16: np.ndarray          # shape (N,), dtype int16
    samplerate: int
    duration_s: float

    def to_wav_bytes(self) -> bytes:
        """Return a complete in-memory WAV file."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.samplerate)
            wf.writeframes(self.audio_int16.tobytes())
        return buf.getvalue()


# ---------------------------------------------------------------------------
# PTT Recorder
# ---------------------------------------------------------------------------

SAMPLERATE = 16_000
CHANNELS = 1
DTYPE = "int16"


@dataclass
class PTTRecorder:
    """Hold-to-record push-to-talk recorder.

    Usage::

        rec = PTTRecorder(ptt_key="f8")
        recording = rec.wait_and_record()  # blocks until PTT pressed + released
    """

    ptt_key: str = "f8"
    samplerate: int = SAMPLERATE
    audio_backend: AudioBackend = field(default_factory=SounddeviceBackend)
    hotkey_backend: HotkeyBackend = field(default_factory=KeyboardHotkeyBackend)

    def _record_core(self) -> Recording:
        """Shared capture logic: record while PTT is held, return on release."""
        chunks: list[np.ndarray] = []
        lock = threading.Lock()

        def _audio_callback(indata: np.ndarray, frames: int,
                            time_info: Any, status: Any) -> None:
            with lock:
                chunks.append(indata.copy().flatten())

        stream = self.audio_backend.start_stream(
            samplerate=self.samplerate,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=_audio_callback,
        )

        start = time.perf_counter()
        try:
            # Poll for key release at ~100 Hz
            while self.hotkey_backend.is_pressed(self.ptt_key):
                time.sleep(0.01)
        finally:
            self.audio_backend.stop_stream(stream)
        elapsed = time.perf_counter() - start

        with lock:
            if chunks:
                audio = np.concatenate(chunks)
            else:
                audio = np.array([], dtype=np.int16)

        return Recording(
            audio_int16=audio,
            samplerate=self.samplerate,
            duration_s=elapsed,
        )

    def wait_and_record(self) -> Recording:
        """Block until PTT is pressed, record while held, return on release."""
        self.hotkey_backend.wait(self.ptt_key, suppress=False)
        return self._record_core()

    def record_once(self) -> Optional[Recording]:
        """Non-blocking variant: record if PTT is currently pressed, else None."""
        if not self.hotkey_backend.is_pressed(self.ptt_key):
            return None
        return self._record_core()
