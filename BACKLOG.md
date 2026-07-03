# Nightly backlog

Owned by Claude Code. The nightly agent picks the TOPMOST unclaimed item and
does exactly one per night (see docs/NIGHTLY_AGENT.md). Items are sized to be
finishable in one focused session, brain-side only.

## Nightly backlog (topmost first)
1. **Dead-companion persona fix** — when the state summary shows `companion=DEAD`,
   `_choose_system_prompt` still selects the embodied companion voice, so a dead
   man keeps narrating. Revert to the copilot persona when dead; keep embodied
   only while alive. Tests for both transitions. (`src/brain/voice/chat.py`)
2. **Gesture false-positive hardening** — bare "wave" fires on "crime wave" /
   "heat wave". Require an imperative shape: start-of-utterance "wave", "wave at
   me", "give (us|me) a wave", "say hi". Tests with the false-positive phrases.
   (`src/brain/actions.py`)
3. **Gazetteer expansion** — add ~15 more Los Santos places with verified world
   coords (grove street, observatory, prison, docks, mirror park, rockford hills,
   vinewood bowl, arena, pillbox hospital, LSC harbor…). Keep the longest-name-first
   matching property. Tests for each new place. (`src/brain/actions.py`)
4. **Session report tool** — `tools/session_report.py`: read a day's
   `src/brain/logs/*.jsonl` and emit a markdown summary (exchanges, actions with
   ack rates, latency percentiles, wanted arcs). Pure stdlib, unit-tested on
   fixture lines. Useful for the video and for latency tracking.
5. **Listener serve-loop integration test** — `state_listener.serve()` accept/
   reconnect loop has no test. Add one: real localhost socket, feed fixture lines,
   assert summaries + reaction trigger with a fake model client, assert clean
   reconnect after disconnect. (`tests/brain/`)
6. **Voice-model latency experiment** — add `--fast-voice` flag: voice replies use
   `qwen2.5:1.5b` (pull documented in README) while reactions stay on hermes3:3b.
   Measure llm_ms via the replay harness with both models; put the numbers in the
   PR description. NO default change. (`src/brain/voice/chat.py`, `copilot.py`)
7. **Overlay polish** — optional `HH:MM` timestamps per line (`--overlay-timestamps`),
   and cap line length with ellipsis so one long reply can't flood the panel.
   Buffer-logic tests only (no Tk in tests). (`src/brain/overlay.py`)
8. **Voice-commands cheat sheet** — `tools/gen_commands_doc.py` that generates a
   README "Voice commands" table from the actual pattern lists in `actions.py`
   (single source of truth), plus the README section it emits. Unit test that the
   generator output contains every action.
