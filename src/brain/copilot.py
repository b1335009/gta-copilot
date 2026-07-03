"""GTA Copilot — single entrypoint orchestrator.

Runs the state-listener thread (TCP from the mod) and the PTT voice loop
in one process. Wanted-level reactions are also spoken through TTS.

Phase 4 changes:
- Tk mainloop owns the main thread; voice loop + listener are workers.
- ``--no-overlay`` preserves console-only behaviour.
- PTT default changed to ``right ctrl`` (F8 collided in-game).
- All events (transcripts, replies, reactions, status) feed the overlay queue.
- Serialized SpeechQueue prevents concurrent-speak clipping.
- time_to_audio_ms logged per voice exchange.
- Fallback text is never spoken aloud.

Usage::

    python -m src.brain.copilot [--ptt-key "right ctrl"] [--no-overlay]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .overlay import LineTag, OverlayMessage, OverlayWindow
from .state_listener import (
    HOST,
    PORT,
    WantedReaction,
    WantedTracker,
    append_raw_line,
    append_reaction,
    format_summary,
    parse_state_line,
    OllamaReactionClient,
)
from .voice.chat import CopilotChat, OllamaChatBackend
from .voice.recorder import PTTRecorder, Recording
from .voice.speaker import Speaker, SpeechResult
from .voice.transcriber import Transcriber, TranscriptionResult

DEFAULT_LOGS_DIR = Path(__file__).resolve().parent / "logs"


# ---------------------------------------------------------------------------
# Voice exchange log
# ---------------------------------------------------------------------------

def _today_text() -> str:
    return _dt.datetime.now().strftime("%Y%m%d")


def append_voice_log(entry: dict[str, Any], *, logs_dir: Path = DEFAULT_LOGS_DIR,
                     date_text: Optional[str] = None) -> Path:
    """Append a voice exchange timing entry to the dated JSONL log."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"voice-{date_text or _today_text()}.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Serialized speech queue — prevents concurrent-speak clipping
# ---------------------------------------------------------------------------

class SpeechQueue:
    """Single-threaded TTS executor: any thread can enqueue, one worker speaks.

    This guarantees that the listener thread and voice loop never clip each
    other's audio.  All TTS goes through ``enqueue()``; a daemon thread
    drains the queue and calls ``speaker.speak()`` sequentially.
    """

    def __init__(self, speaker: Speaker, *, overlay_queue: Optional[queue.Queue] = None):
        self._speaker = speaker
        self._overlay_queue = overlay_queue
        self._q: queue.Queue[Optional[tuple[str, LineTag]]] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="speech-queue")
        self._thread.start()

    def enqueue(self, text: str, tag: LineTag = LineTag.COPILOT) -> None:
        """Queue text for speaking. Non-blocking."""
        self._q.put((text, tag))

    def shutdown(self) -> None:
        self._q.put(None)

    def _worker(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                break
            text, tag = item
            try:
                result = self._speaker.speak(text)
                print(
                    f"[SPOKEN] ({tag.value}) \"{text}\" "
                    f"(tts={result.tts_ms:.0f}ms play={result.play_ms:.0f}ms)",
                    flush=True,
                )
            except Exception as exc:
                print(f"[TTS ERROR] {exc}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Shared state container (thread-safe)
# ---------------------------------------------------------------------------

class SharedGameState:
    """Thread-safe container for the latest game state summary."""

    def __init__(self):
        self._lock = threading.Lock()
        self._summary: str = ""
        self._raw: Optional[dict[str, Any]] = None

    def update(self, state: dict[str, Any]) -> None:
        summary = format_summary(state)
        with self._lock:
            self._summary = summary
            self._raw = state

    @property
    def summary(self) -> str:
        with self._lock:
            return self._summary

    @property
    def raw(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._raw


# ---------------------------------------------------------------------------
# Overlay helper — push to the queue if it exists
# ---------------------------------------------------------------------------

def _push_overlay(oq: Optional[queue.Queue], tag: LineTag, text: str) -> None:
    if oq is not None:
        try:
            oq.put_nowait(OverlayMessage(tag=tag, text=text))
        except queue.Full:
            pass  # overlay is backed up; drop silently


# ---------------------------------------------------------------------------
# State listener thread
# ---------------------------------------------------------------------------

def state_listener_thread(
    shared: SharedGameState,
    chat: CopilotChat,
    speech_queue: Optional[SpeechQueue],
    *,
    host: str = HOST,
    port: int = PORT,
    logs_dir: Path = DEFAULT_LOGS_DIR,
    stop_event: Optional[threading.Event] = None,
    overlay_queue: Optional[queue.Queue] = None,
) -> None:
    """Run the TCP state listener in a thread. Updates SharedGameState and
    triggers spoken wanted-level reactions."""
    import socket

    def _on_reaction(reaction: WantedReaction) -> None:
        append_reaction(reaction, logs_dir=logs_dir)

        # Never speak the literal [FALLBACK…] string aloud (console-only)
        if speech_queue and not reaction.fallback:
            speech_queue.enqueue(reaction.text, LineTag.REACTION)
            _push_overlay(overlay_queue, LineTag.REACTION,
                          f"★{reaction.previous_wanted}→{reaction.current_wanted}: {reaction.text}")
        elif reaction.fallback:
            print(
                f"[FALLBACK] wanted {reaction.previous_wanted}→{reaction.current_wanted}: "
                f"{reaction.text}",
                flush=True,
            )

    # Build the wanted tracker using CopilotChat's backend for reactions too
    reaction_client = _CPUOllamaReactionClient(
        endpoint=chat.endpoint,
        model=chat.model,
    )
    tracker = WantedTracker(reaction_client, reaction_log=_on_reaction)

    _push_overlay(overlay_queue, LineTag.STATUS, f"Listener starting on {host}:{port}")
    print(f"[LISTENER] starting on {host}:{port}", flush=True)

    while not (stop_event and stop_event.is_set()):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.settimeout(2.0)
                server.bind((host, port))
                server.listen(1)
                print(f"[LISTENER] waiting for mod connection on {host}:{port}", flush=True)

                while not (stop_event and stop_event.is_set()):
                    try:
                        conn, addr = server.accept()
                    except socket.timeout:
                        continue

                    _push_overlay(overlay_queue, LineTag.STATUS, f"Mod connected from {addr[0]}")
                    print(f"[LISTENER] connected from {addr[0]}:{addr[1]}", flush=True)
                    with conn, conn.makefile("r", encoding="utf-8", newline="\n") as stream:
                        for line in stream:
                            if stop_event and stop_event.is_set():
                                return
                            raw = line.rstrip("\r\n")
                            if not raw:
                                continue
                            append_raw_line(raw, logs_dir=logs_dir)
                            try:
                                state = parse_state_line(raw)
                            except ValueError as exc:
                                print(f"[LISTENER] bad line: {exc}", file=sys.stderr, flush=True)
                                continue

                            shared.update(state)
                            print(f"[STATE] {format_summary(state)}", flush=True)

                            reaction = tracker.process_state(state)
                            if reaction:
                                marker = "FALLBACK" if reaction.fallback else "REACTION"
                                print(
                                    f"[{marker}] wanted {reaction.previous_wanted}→{reaction.current_wanted}: "
                                    f"{reaction.text}",
                                    flush=True,
                                )

                    _push_overlay(overlay_queue, LineTag.STATUS, "Mod disconnected; waiting…")
                    print("[LISTENER] disconnected; waiting for reconnect", flush=True)

        except OSError as exc:
            if stop_event and stop_event.is_set():
                return
            print(f"[LISTENER] socket error: {exc}; retrying in 2s", file=sys.stderr, flush=True)
            time.sleep(2)


class _CPUOllamaReactionClient(OllamaReactionClient):
    """Override to force num_gpu=0 in wanted reactions (fixes the HTTP 500)."""

    def generate_wanted_reaction(self, *, previous_wanted: int, current_wanted: int, context: str):
        from .state_listener import ModelReply, clean_model_text
        if self.model == "<none>":
            return self._fallback("no Ollama model is installed")
        prompt = (
            "You are Hermes, a GTA V co-pilot watching live player state. "
            f"Police stars rose from {previous_wanted} to {current_wanted}. "
            f"Player context: {context} "
            "Reply with exactly one urgent sentence under 12 words, second person. "
            "No JSON, no markdown, no explanation."
        )
        import json, urllib.request, urllib.error
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 24,
                "num_gpu": 0,        # ← THE FIX: CPU-only inference
                "stop": ["\n"],
            },
            "keep_alive": -1,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return self._fallback(f"model endpoint error: {exc}")
        text = clean_model_text(str(payload.get("response") or ""))
        if not text:
            return self._fallback("model returned an empty response")
        return ModelReply(text=text, fallback=False, endpoint=f"{self.endpoint}/api/generate", model=self.model)


# ---------------------------------------------------------------------------
# Voice loop (runs in a worker thread)
# ---------------------------------------------------------------------------

def voice_loop(
    recorder: PTTRecorder,
    transcriber: Transcriber,
    chat: CopilotChat,
    speech_queue: SpeechQueue,
    shared: SharedGameState,
    *,
    logs_dir: Path = DEFAULT_LOGS_DIR,
    stop_event: Optional[threading.Event] = None,
    overlay_queue: Optional[queue.Queue] = None,
) -> None:
    """Main voice loop: PTT → STT → LLM → TTS, with per-stage timing."""
    print(f"[VOICE] ready — hold {recorder.ptt_key.upper()} to talk", flush=True)
    _push_overlay(overlay_queue, LineTag.STATUS, f"Voice ready — hold {recorder.ptt_key.upper()}")

    while not (stop_event and stop_event.is_set()):
        try:
            # Block until PTT pressed + released
            recording = recorder.wait_and_record()

            if recording.duration_s < 0.3:
                print("[VOICE] recording too short, ignoring", flush=True)
                continue

            if len(recording.audio_int16) == 0:
                print("[VOICE] no audio captured, ignoring", flush=True)
                continue

            total_start = time.perf_counter()
            print(f"[VOICE] captured {recording.duration_s:.2f}s audio ({len(recording.audio_int16)} samples)", flush=True)

            # STT
            tx_result = transcriber.transcribe_audio(recording.audio_int16, samplerate=recording.samplerate)
            print(f"[STT] \"{tx_result.text}\" ({tx_result.stt_ms:.0f}ms)", flush=True)

            if not tx_result.text.strip():
                print("[VOICE] empty transcript, ignoring", flush=True)
                continue

            # Push player transcript to overlay
            _push_overlay(overlay_queue, LineTag.PLAYER, tx_result.text)

            # LLM
            game_context = shared.summary
            chat_result = chat.reply(tx_result.text, game_state_summary=game_context)
            print(f"[LLM] \"{chat_result.reply}\" ({chat_result.llm_ms:.0f}ms fallback={chat_result.fallback})", flush=True)

            # time_to_audio = stt + llm (before TTS/playback starts)
            time_to_audio_ms = (time.perf_counter() - total_start) * 1000.0

            # TTS — via serialized speech queue; never speak fallback text
            if not chat_result.fallback:
                speech_queue.enqueue(chat_result.reply, LineTag.COPILOT)
                _push_overlay(overlay_queue, LineTag.COPILOT, chat_result.reply)
            else:
                # Fallback: log to console + overlay but do NOT speak
                print(f"[FALLBACK] {chat_result.reply}", flush=True)
                _push_overlay(overlay_queue, LineTag.STATUS, f"LLM fallback: {chat_result.reply}")

            total_ms = (time.perf_counter() - total_start) * 1000.0

            # Log
            entry = {
                "t": int(time.time() * 1000),
                "user_text": tx_result.text,
                "reply": chat_result.reply,
                "fallback": chat_result.fallback,
                "model": chat_result.model,
                "stt_ms": round(tx_result.stt_ms, 1),
                "llm_ms": round(chat_result.llm_ms, 1),
                "time_to_audio_ms": round(time_to_audio_ms, 1),
                "total_ms": round(total_ms, 1),
                "game_state": game_context,
            }
            append_voice_log(entry, logs_dir=logs_dir)
            print(
                f"[TIMING] stt={tx_result.stt_ms:.0f}ms llm={chat_result.llm_ms:.0f}ms "
                f"time_to_audio={time_to_audio_ms:.0f}ms total={total_ms:.0f}ms",
                flush=True,
            )
            print("=" * 72, flush=True)

        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"[VOICE ERROR] {exc}", file=sys.stderr, flush=True)
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="GTA Copilot — voice loop + state listener orchestrator.",
    )
    parser.add_argument("--ptt-key", default="right ctrl",
                        help="Push-to-talk key (default: right ctrl)")
    parser.add_argument("--host", default=HOST, help="Listener bind host")
    parser.add_argument("--port", type=int, default=PORT, help="Listener bind port")
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOGS_DIR)
    parser.add_argument("--ollama-endpoint", default=None)
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--no-voice", action="store_true", help="Disable voice loop (listener only)")
    parser.add_argument("--no-listener", action="store_true", help="Disable state listener (voice only)")
    parser.add_argument("--no-overlay", action="store_true",
                        help="Disable the transparent overlay (console-only mode)")
    args = parser.parse_args(argv)

    print("=" * 72, flush=True)
    print("  GTA COPILOT — Phase 4 Overlay + Voice", flush=True)
    print("=" * 72, flush=True)

    # Build components
    chat = CopilotChat(endpoint=args.ollama_endpoint, model=args.ollama_model)
    print(f"[INIT] Ollama model={chat.model} endpoint={chat.endpoint}", flush=True)

    # Preload model with keep_alive=-1
    print("[INIT] preloading model (keep_alive=-1, CPU-only)...", flush=True)
    if chat.preload():
        print("[INIT] model preloaded successfully", flush=True)
    else:
        print("[INIT] WARNING: model preload failed — first request may be slow", flush=True)

    shared = SharedGameState()
    stop = threading.Event()

    # Overlay queue — shared between all threads and the Tk mainloop
    overlay_q: Optional[queue.Queue] = None
    if not args.no_overlay:
        overlay_q = queue.Queue(maxsize=200)

    # Speaker + serialized speech queue
    speaker: Optional[Speaker] = None
    speech_q: Optional[SpeechQueue] = None
    if not args.no_voice:
        try:
            speaker = Speaker()
            speech_q = SpeechQueue(speaker, overlay_queue=overlay_q)
            print("[INIT] TTS speaker + speech queue ready", flush=True)
        except Exception as exc:
            print(f"[INIT] WARNING: TTS init failed ({exc}), spoken output disabled", flush=True)

    # Start listener thread
    if not args.no_listener:
        listener = threading.Thread(
            target=state_listener_thread,
            args=(shared, chat, speech_q),
            kwargs=dict(host=args.host, port=args.port, logs_dir=args.logs_dir,
                        stop_event=stop, overlay_queue=overlay_q),
            daemon=True,
            name="state-listener",
        )
        listener.start()
        print("[INIT] state listener thread started", flush=True)

    # Voice loop (worker thread when overlay is active, else main thread fallback)
    voice_thread: Optional[threading.Thread] = None
    if not args.no_voice:
        try:
            transcriber = Transcriber()
            print("[INIT] STT transcriber ready", flush=True)
        except Exception as exc:
            print(f"[INIT] ERROR: STT init failed ({exc})", file=sys.stderr, flush=True)
            print("[INIT] falling back to listener-only mode", flush=True)
            args.no_voice = True

    if not args.no_voice and speech_q:
        recorder = PTTRecorder(ptt_key=args.ptt_key)
        print(f"[INIT] PTT recorder ready (key={args.ptt_key.upper()})", flush=True)

        voice_thread = threading.Thread(
            target=voice_loop,
            args=(recorder, transcriber, chat, speech_q, shared),
            kwargs=dict(logs_dir=args.logs_dir, stop_event=stop, overlay_queue=overlay_q),
            daemon=True,
            name="voice-loop",
        )
        voice_thread.start()
        print("[INIT] voice loop thread started", flush=True)

    print("=" * 72, flush=True)

    # Main thread: Tk overlay or blocking wait
    if not args.no_overlay and overlay_q is not None:
        _push_overlay(overlay_q, LineTag.STATUS, "GTA Copilot started")
        try:
            overlay = OverlayWindow(overlay_q)
            print("[INIT] overlay window active — drag to reposition", flush=True)
            overlay.run()  # blocks (Tk mainloop)
        except KeyboardInterrupt:
            pass
        except Exception as exc:
            print(f"[OVERLAY] error: {exc} — falling back to console mode", file=sys.stderr, flush=True)
            # Fall through to console wait
            try:
                while not stop.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print("[COPILOT] running in console-only mode (no overlay)", flush=True)
        try:
            while not stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    stop.set()
    if speech_q:
        speech_q.shutdown()
    print("\n[COPILOT] shutting down", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
