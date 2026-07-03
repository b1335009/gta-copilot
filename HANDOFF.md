# HANDOFF — Phase 4 (Antigravity → Claude Code)

## Date: 2026-07-03

## Checklist status

### ✅ Item 1: `src/brain/overlay.py`
Created. Two-layer design:
- **`ChatBuffer`** — pure logic ring buffer (capacity=8 default), thread-safe with lock, unit-testable without Tk. Manages `ChatLine` objects tagged with `LineTag` enum (PLAYER / COPILOT / REACTION / STATUS).
- **`OverlayWindow`** — tkinter `Tk()` with `-topmost`, `-alpha 0.85`, `overrideredirect(True)` (borderless), draggable. Dark background `#1a1a2e`, Consolas 11pt. Polls a `queue.Queue[OverlayMessage]` via `after(100ms)`. Color-coded tags: cyan (player), green (copilot), yellow (reaction), grey (status). Tag prefixes: `YOU:`, `COPILOT:`, `⚠`, `•`.

### ✅ Item 2: Restructure `copilot.py`
- **Tk mainloop on main thread** — `OverlayWindow.run()` occupies the main thread when overlay is active.
- **Voice loop moved to daemon worker thread** (`voice-loop`).
- **State listener remains daemon worker thread** (`state-listener`).
- **`--no-overlay`** flag added — preserves console-only `time.sleep(1)` wait behavior from Phase 3.
- **PTT default changed** from `f8` to `right ctrl`.
- **All events feed overlay queue** — player transcripts (PLAYER), copilot replies (COPILOT), wanted reactions (REACTION), connect/disconnect/ready (STATUS).
- Fallback for Tk errors: if overlay construction fails, print the error and fall through to console-only mode.

### ✅ Item 3: Latency tuning
- **System prompt**: cut from 5 sentences to **15 words**: `"GTA V co-pilot. One punchy sentence, under 15 words. No markdown or quotes."`
- **`num_predict`**: reduced from 40 to **24** for the voice chat path. Reaction path already used 24.
- **`time_to_audio_ms`** added to `voice-<date>.jsonl` — measures STT + LLM wall time (before TTS begins). This is the metric to track: it excludes playback duration which the copilot has no control over.
- **`SpeechQueue`** — new serialized TTS executor. A daemon thread drains a `queue.Queue` and calls `speaker.speak()` sequentially. Both the listener thread (reactions) and voice loop (replies) route through this — eliminates the concurrent-speak clipping bug. Methods: `enqueue(text, tag)`, `shutdown()`.

### ✅ Item 4: Phase 3 carry-over cleanups
- **Deduped `record_once()`** — extracted shared capture logic into `_record_core()`. `wait_and_record()` now calls `wait()` + `_record_core()`, `record_once()` calls `is_pressed()` + `_record_core()`. ~40 lines removed.
- **Never speak `[FALLBACK…]` aloud** — voice loop only calls `speech_queue.enqueue()` when `chat_result.fallback is False`. Fallback text goes to console + overlay STATUS only.
- **Transcriber asserts 16 kHz** — `transcribe_audio()` now raises `ValueError` if `samplerate != 16000`. Previously silently ignored the samplerate arg.

### ✅ Item 5: Unit tests
10 new tests in `tests/brain/test_overlay.py`:
- `ChatBufferTests` (5): append + snapshot, eviction at capacity, clear, capacity validation, concurrent thread safety (4 threads × 25 appends).
- `SpeechQueueTests` (2): serialized delivery, clean empty-shutdown.
- `TranscriberSamplerateTests` (2): rejects 44.1 kHz, accepts 16 kHz.
- `FallbackNotSpokenTests` (1): verifies `fallback=True` flag on LLM error.

**Full suite: 28 tests, all pass** (`python -m unittest discover -s tests`).

### ✅ Item 6: Frozen files
Verified: `git diff --name-only HEAD -- src/mod/ ACTION_WHITELIST.md ROADMAP.md PROJECT_STATE.md` returns empty. Port/protocol unchanged (127.0.0.1:48651).

## Files changed
| File | Action | Lines |
|------|--------|-------|
| `src/brain/overlay.py` | **NEW** | ~200 |
| `src/brain/copilot.py` | Modified | ~350 (restructured) |
| `src/brain/voice/chat.py` | Modified | system prompt + num_predict |
| `src/brain/voice/recorder.py` | Modified | dedupe via _record_core |
| `src/brain/voice/transcriber.py` | Modified | samplerate assertion |
| `tests/brain/test_overlay.py` | **NEW** | ~165 |

## Not done / Notes
- The overlay has NOT been smoke-tested over live GTA (requires Borderless mode + game running). The gate is: "chat log readable during play."
- `tts_ms` and `play_ms` are no longer individually logged in the voice JSONL (speech is now async via the queue). `time_to_audio_ms` replaces them as the latency metric.
- No new pip dependencies. tkinter is stdlib; all other imports are unchanged.

## Pre-session checklist for Beshr
1. Set GTA to **Borderless** in display settings.
2. Page file must be **enabled** (CRASH #3).
3. Run: `.venv\Scripts\python.exe -m src.brain.copilot --ptt-key "right ctrl"`
4. Use `--no-overlay` to fall back to Phase 3 console-only mode if needed.
