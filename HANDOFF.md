# HANDOFF — Phase 6 (Antigravity)

## Date: 2026-07-03

## Phase 6 Checklist status

### ✅ 1. Intents
- Added `_STAY_PATTERNS` ("wait here", "stay here", "hold position", "stay put") and `_FOLLOW_PATTERNS` ("follow me", "on me", "come with me", "keep up").
- Hardened logic to explicitly not match bare "let's go".

### ✅ 2. Confirmation/failure phrases
- Added `companion_stay` → "Holding position."
- Added `companion_follow` → "Right behind you."
- Added nacks for no companion ("I'm not out there yet — call backup first.") and dead companion ("He didn't make it, boss.").

### ✅ 3. Persona 6c in chat.py
- Created `COMPANION_SYSTEM_PROMPT` in `chat.py`. 
- Modified `reply` and `react_to_wanted` to detect companion presence (`companion=` or `companion_hp=`) in the game-state summary. If a companion is present or dead, the persona organically shifts to the first-person embodied companion.

### ✅ 4. Companion-death awareness
- Inserted companion death detection in `state_listener_thread` (`src/brain/copilot.py`). Triggers when `companion.dead` flips from false to true.
- Automatically pushes `STATUS` tag to the overlay and speaks a short dramatic line by generating via `chat.react_to_companion_death()`, keeping the existing reaction/speech loop.

### ✅ 5. Gesture intent
- Implemented `_GESTURE_PATTERNS`. Captures "wave", "say hi", "wave at me" -> `name="wave"` and "nod" -> `name="nod"`. (No false positive on "waive the fee").
- Added spoken confirmation.

### ✅ 6. Tests
- Total Brain unit test suite passed successfully with **86/86** tests green. Added test classes handling Phase 6 intent matcher and Chat persona transitions.

### ✅ 7. Frozen constraints
- Carefully avoided touching `src/mod/**`, builds, deployments, or modifying `PROJECT_STATE.md` and whitelists. Adhered strictly to the Phase 6 constraints. No crashes or deployment changes performed.

## Files Changed
- `src/brain/actions.py` - Setup patterns and string templates.
- `tests/brain/test_actions.py` - False positives, missing intents testing and string assertions.
- `src/brain/voice/chat.py` - `COMPANION_SYSTEM_PROMPT`, state injection, `react_to_companion_death()`.
- `tests/brain/test_voice.py` - Chat persona generation tests.
- `src/brain/copilot.py` - Overlay trigger integration for companion death.

Ready for Milestone 6!
