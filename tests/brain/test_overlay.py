"""Unit tests for the Phase 4 overlay, speech queue, and carry-over fixes."""

import queue
import threading
import time
import unittest
from unittest.mock import MagicMock

import numpy as np

from src.brain.overlay import ChatBuffer, ChatLine, LineTag, OverlayMessage


# -----------------------------------------------------------------------
# ChatBuffer tests
# -----------------------------------------------------------------------

class ChatBufferTests(unittest.TestCase):
    def test_append_and_lines_returns_snapshot(self):
        buf = ChatBuffer(capacity=4)
        buf.append(LineTag.PLAYER, "hello")
        buf.append(LineTag.COPILOT, "yo back")

        lines = buf.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].tag, LineTag.PLAYER)
        self.assertEqual(lines[0].text, "hello")
        self.assertEqual(lines[1].tag, LineTag.COPILOT)
        self.assertEqual(lines[1].text, "yo back")

    def test_evicts_oldest_at_capacity(self):
        buf = ChatBuffer(capacity=3)
        buf.append(LineTag.PLAYER, "a")
        buf.append(LineTag.COPILOT, "b")
        buf.append(LineTag.REACTION, "c")
        buf.append(LineTag.STATUS, "d")

        lines = buf.lines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].text, "b")  # "a" was evicted
        self.assertEqual(lines[2].text, "d")

    def test_clear_empties_buffer(self):
        buf = ChatBuffer(capacity=5)
        buf.append(LineTag.PLAYER, "x")
        self.assertEqual(len(buf), 1)
        buf.clear()
        self.assertEqual(len(buf), 0)
        self.assertEqual(buf.lines(), [])

    def test_capacity_must_be_positive(self):
        with self.assertRaises(ValueError):
            ChatBuffer(capacity=0)

    def test_thread_safety_concurrent_appends(self):
        buf = ChatBuffer(capacity=100)
        barrier = threading.Barrier(4)

        def writer(tag, start):
            barrier.wait()
            for i in range(25):
                buf.append(tag, f"{tag.value}-{start + i}")

        threads = [
            threading.Thread(target=writer, args=(LineTag.PLAYER, 0)),
            threading.Thread(target=writer, args=(LineTag.COPILOT, 100)),
            threading.Thread(target=writer, args=(LineTag.REACTION, 200)),
            threading.Thread(target=writer, args=(LineTag.STATUS, 300)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(buf), 100)


# -----------------------------------------------------------------------
# SpeechQueue tests
# -----------------------------------------------------------------------

class FakeSpeaker:
    """Records speak calls without producing audio."""

    def __init__(self):
        self.spoken = []
        self._lock = threading.Lock()

    def speak(self, text, *, on_audio_ready=None):
        from src.brain.voice.speaker import SpeechResult
        if on_audio_ready is not None:
            on_audio_ready(1.0)
        with self._lock:
            self.spoken.append(text)
        return SpeechResult(text=text, tts_ms=1.0, play_ms=1.0)


class SpeechQueueTests(unittest.TestCase):
    def test_enqueue_serializes_speech(self):
        from src.brain.copilot import SpeechQueue

        speaker = FakeSpeaker()
        sq = SpeechQueue(speaker)

        sq.enqueue("first", LineTag.COPILOT)
        sq.enqueue("second", LineTag.REACTION)
        sq.shutdown()
        sq._thread.join(timeout=2)

        self.assertEqual(speaker.spoken, ["first", "second"])

    def test_no_crash_on_empty_shutdown(self):
        from src.brain.copilot import SpeechQueue

        speaker = FakeSpeaker()
        sq = SpeechQueue(speaker)
        sq.shutdown()
        sq._thread.join(timeout=2)

        self.assertEqual(speaker.spoken, [])


# -----------------------------------------------------------------------
# Transcriber samplerate assertion test
# -----------------------------------------------------------------------

class TranscriberSamplerateTests(unittest.TestCase):
    def test_rejects_non_16khz(self):
        from src.brain.voice.transcriber import Transcriber

        class FakeWhisper:
            def transcribe(self, audio_float32, *, samplerate):
                return "should not reach here"

        tx = Transcriber(backend=FakeWhisper())
        audio = np.zeros(16000, dtype=np.int16)

        with self.assertRaisesRegex(ValueError, "16 kHz"):
            tx.transcribe_audio(audio, samplerate=44100)

    def test_accepts_16khz(self):
        from src.brain.voice.transcriber import Transcriber

        class FakeWhisper:
            def transcribe(self, audio_float32, *, samplerate):
                return "ok"

        tx = Transcriber(backend=FakeWhisper())
        audio = np.zeros(16000, dtype=np.int16)

        result = tx.transcribe_audio(audio, samplerate=16000)
        self.assertEqual(result.text, "ok")


# -----------------------------------------------------------------------
# Fallback never-spoken test
# -----------------------------------------------------------------------

class FallbackNotSpokenTests(unittest.TestCase):
    def test_fallback_reply_is_not_enqueued_for_speech(self):
        """Simulates the voice loop logic: fallback replies should not be spoken."""
        from src.brain.voice.chat import CopilotChat, ChatResult

        class FailingBackend:
            endpoint = "fail://x"
            model = "fail"
            def generate(self, *, system, prompt):
                raise RuntimeError("boom")

        chat = CopilotChat(backend=FailingBackend())
        result = chat.reply("hello")

        # The copilot.py voice_loop only calls speech_queue.enqueue() when
        # chat_result.fallback is False.  Verify the flag is set.
        self.assertTrue(result.fallback)
        self.assertIn("FALLBACK", result.reply)


if __name__ == "__main__":
    unittest.main()
