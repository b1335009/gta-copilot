"""Unit tests for the voice subsystem — all with fakes, no network, no audio HW."""

import io
import json
import struct
import time
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import MagicMock

import numpy as np


# -----------------------------------------------------------------------
# Fake backends
# -----------------------------------------------------------------------

class FakeAudioBackend:
    """Simulates sounddevice capture: pushes a known sine wave chunk."""

    def __init__(self, chunks: int = 3, chunk_size: int = 1600):
        self._chunks = chunks
        self._chunk_size = chunk_size
        self.started = False
        self.stopped = False

    def start_stream(self, *, samplerate, channels, dtype, callback):
        self.started = True
        # Deliver fake audio chunks immediately
        for _ in range(self._chunks):
            chunk = np.zeros(self._chunk_size, dtype=np.int16)
            chunk[0] = 1000  # non-zero so we can verify capture
            callback(chunk.reshape(-1, 1), self._chunk_size, None, None)
        return self

    def stop_stream(self, stream):
        self.stopped = True


class FakeHotkeyBackend:
    """Simulates PTT key: pressed for ``hold_ticks`` polls then released."""

    def __init__(self, hold_ticks: int = 2):
        self._hold_ticks = hold_ticks
        self._tick = 0
        self._waited = False

    def is_pressed(self, key):
        self._tick += 1
        return self._tick <= self._hold_ticks

    def wait(self, key, *, suppress=False):
        self._waited = True


class FakeWhisperBackend:
    """Returns a canned transcript."""

    def __init__(self, transcript: str = "yo what's up"):
        self._transcript = transcript

    def transcribe(self, audio_float32, *, samplerate):
        return self._transcript


class FakeChatBackend:
    """Returns a canned reply."""

    def __init__(self, reply: str = "Watch out, cops incoming!"):
        self._reply = reply
        self.last_system = None
        self.last_prompt = None
        self.endpoint = "fake://ollama"
        self.model = "fake-chat"

    def generate(self, *, system, prompt):
        self.last_system = system
        self.last_prompt = prompt
        return self._reply


class FakeTTSBackend:
    """Returns a short silent audio buffer."""

    def synthesize(self, text):
        audio = np.zeros(4410, dtype=np.int16)  # 0.2s at 22050
        return audio, 22050


class FakePlaybackBackend:
    """Records what was played without producing sound."""

    def __init__(self):
        self.played = []

    def play(self, audio_int16, *, samplerate):
        self.played.append((len(audio_int16), samplerate))


# -----------------------------------------------------------------------
# Recorder tests
# -----------------------------------------------------------------------

class RecorderTests(unittest.TestCase):
    def test_wait_and_record_captures_audio_and_returns_recording(self):
        from src.brain.voice.recorder import PTTRecorder

        audio_backend = FakeAudioBackend(chunks=3, chunk_size=1600)
        hotkey_backend = FakeHotkeyBackend(hold_ticks=2)

        rec = PTTRecorder(
            ptt_key="f8",
            audio_backend=audio_backend,
            hotkey_backend=hotkey_backend,
        )
        recording = rec.wait_and_record()

        self.assertTrue(audio_backend.started)
        self.assertTrue(audio_backend.stopped)
        self.assertTrue(hotkey_backend._waited)
        self.assertEqual(recording.samplerate, 16000)
        self.assertGreater(len(recording.audio_int16), 0)
        # 3 chunks × 1600 samples = 4800
        self.assertEqual(len(recording.audio_int16), 4800)

    def test_recording_to_wav_bytes_produces_valid_wav(self):
        from src.brain.voice.recorder import Recording

        audio = np.array([100, -100, 200, -200], dtype=np.int16)
        rec = Recording(audio_int16=audio, samplerate=16000, duration_s=0.001)
        wav_bytes = rec.to_wav_bytes()

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertEqual(wf.getnframes(), 4)


# -----------------------------------------------------------------------
# Transcriber tests
# -----------------------------------------------------------------------

class TranscriberTests(unittest.TestCase):
    def test_transcribe_audio_returns_text_and_timing(self):
        from src.brain.voice.transcriber import Transcriber

        backend = FakeWhisperBackend("test transcription result")
        tx = Transcriber(backend=backend)
        audio = np.zeros(16000, dtype=np.int16)

        result = tx.transcribe_audio(audio, samplerate=16000)

        self.assertEqual(result.text, "test transcription result")
        self.assertGreater(result.stt_ms, 0)

    def test_transcribe_wav_bytes_works(self):
        from src.brain.voice.transcriber import Transcriber

        backend = FakeWhisperBackend("from wav")
        tx = Transcriber(backend=backend)
        # Build a valid WAV in memory
        audio = np.array([0, 1, 2, 3], dtype=np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio.tobytes())

        result = tx.transcribe_wav_bytes(buf.getvalue())

        self.assertEqual(result.text, "from wav")


# -----------------------------------------------------------------------
# Chat tests
# -----------------------------------------------------------------------

class ChatTests(unittest.TestCase):
    def test_reply_returns_cleaned_text_and_timing(self):
        from src.brain.voice.chat import CopilotChat

        backend = FakeChatBackend("Watch out, they see you!")
        chat = CopilotChat(backend=backend)

        result = chat.reply("are the cops after me", game_state_summary="wanted=2 hp=180/200")

        self.assertEqual(result.reply, "Watch out, they see you!")
        self.assertFalse(result.fallback)
        self.assertGreater(result.llm_ms, 0)
        self.assertIn("are the cops after me", backend.last_prompt)
        self.assertIn("wanted=2", backend.last_prompt)

    def test_reply_fallback_on_exception(self):
        from src.brain.voice.chat import CopilotChat

        class FailingBackend:
            endpoint = "fail://x"
            model = "fail"
            def generate(self, *, system, prompt):
                raise RuntimeError("boom")

        chat = CopilotChat(backend=FailingBackend())
        result = chat.reply("hello")

        self.assertTrue(result.fallback)
        self.assertIn("FALLBACK", result.reply)

    def test_reply_fallback_on_empty_response(self):
        from src.brain.voice.chat import CopilotChat

        backend = FakeChatBackend("")
        chat = CopilotChat(backend=backend)

        result = chat.reply("hello")

        self.assertTrue(result.fallback)

    def test_react_to_wanted(self):
        from src.brain.voice.chat import CopilotChat

        backend = FakeChatBackend("Get out of there now!")
        chat = CopilotChat(backend=backend)

        result = chat.react_to_wanted(previous=1, current=3, game_state_summary="hp=100/200")

        self.assertEqual(result.reply, "Get out of there now!")
        self.assertFalse(result.fallback)

    def test_clean_reply_keeps_first_sentence(self):
        from src.brain.voice.chat import _clean_reply

        self.assertEqual(
            _clean_reply('"Run now! They are closing in. Do not stop."'),
            "Run now!",
        )
        self.assertEqual(_clean_reply("no punctuation here"), "no punctuation here")


# -----------------------------------------------------------------------
# Speaker tests
# -----------------------------------------------------------------------

class SpeakerTests(unittest.TestCase):
    def test_speak_synthesizes_and_plays(self):
        from src.brain.voice.speaker import Speaker

        tts = FakeTTSBackend()
        playback = FakePlaybackBackend()
        spk = Speaker(tts_backend=tts, playback_backend=playback)

        result = spk.speak("Watch out for the cops!")

        self.assertEqual(result.text, "Watch out for the cops!")
        self.assertGreater(result.tts_ms, 0)
        self.assertGreater(result.play_ms, 0)
        self.assertEqual(len(playback.played), 1)
        self.assertEqual(playback.played[0], (4410, 22050))


# -----------------------------------------------------------------------
# Copilot orchestrator tests
# -----------------------------------------------------------------------

class CopilotOrchestratorTests(unittest.TestCase):
    def test_shared_game_state_is_thread_safe(self):
        from src.brain.copilot import SharedGameState

        shared = SharedGameState()
        self.assertEqual(shared.summary, "")
        self.assertIsNone(shared.raw)

        state = {
            "t": 1000, "health": 200, "max_health": 200, "armor": 0,
            "wanted": 1, "pos": {"x": 0.0, "y": 0.0, "z": 0.0}, "vehicle": None,
        }
        shared.update(state)

        self.assertIn("wanted=1", shared.summary)
        self.assertEqual(shared.raw, state)

    def test_append_voice_log_writes_jsonl(self):
        from src.brain.copilot import append_voice_log

        entry = {"t": 12345, "user_text": "hello", "reply": "hey there", "total_ms": 500.0}

        with TemporaryDirectory() as tmp:
            path = append_voice_log(entry, logs_dir=Path(tmp), date_text="20260703")

            self.assertEqual(path.name, "voice-20260703.jsonl")
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 1)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["user_text"], "hello")
            self.assertEqual(parsed["total_ms"], 500.0)


if __name__ == "__main__":
    unittest.main()
