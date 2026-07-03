# HANDOFF — Antigravity to Claude Code

## Session summary
Phase 3 implementation: built the full push-to-talk voice loop (PTT → faster-whisper STT → hermes3:3b LLM → Piper TTS) in `src/brain/`, plus the root-cause fix for the HTTP 500 that blocked Milestone 1.

## Checklist item 0 — HTTP 500 root cause + fix

**Root cause: VRAM contention.** The RTX 4070 Laptop GPU (8 GB) is fully consumed by GTA V Enhanced during play. Ollama's default behavior loads hermes3:3b into GPU VRAM, which fails with HTTP 500 when GTA is running.

**Evidence:**
- `ollama ps` shows hermes3:3b loaded (2.0 GB) when game is closed
- All three live reactions in `reactions-20260703.jsonl` are `[FALLBACK ... HTTP Error 500]`
- With game closed, the endpoint works perfectly (verified via API call)
- `nvidia-smi` shows RTX 4070 Laptop GPU with 8188 MiB total, ~1000 MiB used at idle

**Fix applied (two parts):**
1. **`num_gpu: 0`** in all Ollama generate calls → forces CPU-only inference. Implemented in:
   - `src/brain/voice/chat.py` — `OllamaChatBackend.generate()` sets `options.num_gpu: 0`
   - `src/brain/copilot.py` — `_CPUOllamaReactionClient` subclass overrides the wanted-reaction path with `num_gpu: 0`
2. **`keep_alive: -1`** preload at startup → model stays in CPU memory permanently, avoiding cold-start latency.

**Measured latency (CPU, game closed):** 1511ms total (211ms prompt eval + 841ms generation for 20 tokens). This is within the ~1.5s budget for the LLM portion alone.

## Checklist item 1 — Milestone 1 gate [RECORD]

**BLOCKED on live session.** The HTTP 500 fix is applied in code but needs to be validated with the game running. The fix (num_gpu:0) eliminates the VRAM contention root cause, so this should now produce `"fallback": false` reactions. Requires:
- `.venv` setup with `pip install -r src/brain/requirements.txt` (needs faster-whisper, keyboard)
- Start `python -m src.brain.copilot` with the game running
- Commit a crime → wanted level increase → verify non-fallback reaction in `reactions-<date>.jsonl`

## Checklist item 2 — requirements.txt + recorder

**DONE.** Created:
- `src/brain/requirements.txt` — sounddevice, numpy, keyboard, faster-whisper
- `src/brain/voice/__init__.py` — package init
- `src/brain/voice/recorder.py` — PTT hold-to-record (F8 default, configurable `--ptt-key`). Injectable audio + hotkey backends for unit testing. 16 kHz mono int16 capture via sounddevice.

## Checklist item 3 — transcriber

**DONE.** Created `src/brain/voice/transcriber.py`:
- faster-whisper `base.en`, `compute_type="int8"`, `device="cpu"`
- Model auto-downloads to `models/whisper/` on first use
- Logs transcript + `stt_ms` timing
- Injectable `WhisperBackend` for unit tests

## Checklist item 4 — chat

**DONE.** Created `src/brain/voice/chat.py`:
- Generalized Ollama client for conversational replies
- Co-pilot persona prompt: "riding shotgun" voice
- Injects latest game-state context from SharedGameState
- ≤25 words, one sentence preferred (num_predict=40 hard cap)
- `react_to_wanted()` method for spoken wanted reactions
- `_clean_reply()` strips quotes, keeps first sentence only

## Checklist item 5 — speaker

**DONE.** Created `src/brain/voice/speaker.py`:
- Piper TTS via subprocess (`--output-raw` for raw PCM)
- Voice: `en_US-lessac-medium` under `models/piper/`
- Playback via sounddevice (blocking)
- Logs `tts_ms` synthesis + `play_ms` playback timing

## Checklist item 6 — copilot orchestrator

**DONE.** Created `src/brain/copilot.py`:
- Single entrypoint: `python -m src.brain.copilot`
- State-listener thread + voice loop in one process
- Wanted reactions spoken through TTS (not just printed)
- Per-exchange stage timing (`stt_ms`, `llm_ms`, `tts_ms`, `total_ms`) to console + `logs/voice-<date>.jsonl`
- `--no-voice` / `--no-listener` flags for partial operation
- `SharedGameState` thread-safe container feeds live context to LLM

## Checklist item 7 — unit tests

**DONE.** Created `tests/brain/test_voice.py` — 12 new tests, all with fakes (no network, no audio hardware):
- `RecorderTests`: PTT capture + WAV encoding
- `TranscriberTests`: audio + WAV bytes transcription with fake whisper
- `ChatTests`: reply, fallback on exception, fallback on empty, wanted reaction, reply cleaning
- `SpeakerTests`: synthesis + playback with fakes
- `CopilotOrchestratorTests`: SharedGameState thread safety, voice log JSONL output

All 18 tests pass (6 original + 12 new):
```
Ran 18 tests in 0.070s — OK
```

## Checklist item 8 — frozen files

**CONFIRMED.** `git status` shows only new files in `src/brain/` and `tests/`. Zero diffs in `src/mod/**`.

## Remaining setup for live testing

**Question for Beshr/Claude Code:** Before the Milestone 1 live gate, we need:
1. Create `.venv`: `python -m venv .venv && .venv\Scripts\activate && pip install -r src/brain/requirements.txt`
2. Download Piper TTS binary + voice model to `models/piper/` (Windows binary from https://github.com/rhasspy/piper/releases). Need sign-off since this is a machine-level download outside `.venv`.
3. Run: `python -m src.brain.copilot --ptt-key f8`

## Files created (all in `src/brain/` and `tests/`)
- `src/brain/requirements.txt`
- `src/brain/voice/__init__.py`
- `src/brain/voice/recorder.py`
- `src/brain/voice/chat.py`
- `src/brain/voice/transcriber.py`
- `src/brain/voice/speaker.py`
- `src/brain/copilot.py`
- `tests/brain/test_voice.py`
