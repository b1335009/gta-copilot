# HANDOFF — Phase 5a (Antigravity → Claude Code)

## Date: 2026-07-03

## Checklist status

### ✅ Item 1: `src/brain/actions.py` — gazetteer + intent matcher + whitelist mirror
Created. Three logical sections:

- **Gazetteer** — 20+ named Los Santos places with GTA V world X,Y coords, covering airports (LSIA), landmarks (Maze Bank Tower, Vinewood Sign, Del Perro Pier, Mount Chiliad), districts (Downtown, Vespucci, Sandy Shores, Paleto Bay), services (Hospital, Police Station, Los Santos Customs, Ammu-Nation), recreation (Golf Course, Casino, Strip Club), and notable locations (Fort Zancudo, character houses). Sorted longest-name-first for greedy matching.

- **Deterministic intent matcher** — `match_intent(transcript) → Optional[ActionRequest]`. Uses 5 regex patterns: "set a waypoint to X", "waypoint to X", "mark X [on the map]", "take me to X", "go/navigate/head/drive to X". Extracts noun phrase, matches against gazetteer (longest first). Case-insensitive. Returns `ActionRequest` with auto-incrementing thread-safe ID, action name, params dict, and human place name. Returns `None` on no match or unknown place — **no LLM involvement**.

- **Python whitelist mirror** — `WHITELISTED_ACTIONS = {"set_waypoint", "spawn_companion", "heal_player"}`, matching ACTION_WHITELIST.md exactly. `is_action_whitelisted()` checks before sending.

### ✅ Item 2: Action client plumbing
`ActionClient` class in `actions.py`:
- **`set_connection(file)` / `clear_connection()`** — owned by the listener thread when a mod connects/disconnects.
- **`send_line(line)`** — thread-safe write to the mod socket. Returns False if disconnected.
- **`send_action(request)`** — sends wire JSON, blocks up to 3s via threading.Event for ack correlation by ID. Returns `ActionAck` or `None` on timeout/disconnect.
- **`feed_ack(raw_line)`** — called by the listener thread for every inbound line. Parses ack JSON (`{"ack":<id>,"ok":true|false,"err":<str|null>}`), unblocks the corresponding `send_action()` waiter.
- **Logging** — every request+ack pair appended to `src/brain/logs/actions-<date>.jsonl`. Refused actions (non-whitelisted) also logged with `"refused": true`.

Wire schema matches PROJECT_STATE.md exactly:
```json
{"type":"action","id":42,"action":"set_waypoint","params":{"x":-1034.0,"y":-2733.0}}
```

### ✅ Item 3: Wired into the voice loop
`copilot.py` voice loop now checks `match_intent(transcript)` **before** the LLM chat path:
- **Action matched + ack OK** → speaks "Waypoint set — {place name}." via SpeechQueue.
- **Action matched + ack FAIL** → speaks "Couldn't set the waypoint — {error}."
- **Action matched + timeout** → speaks "No response from the mod — waypoint might not have landed."
- **No action matched** → falls through to normal LLM chat (unchanged Phase 4 path).

Listener thread integration:
- On mod connect: creates write file, calls `action_client.set_connection()`.
- On inbound lines: tries `action_client.feed_ack(raw)` first — if it's an ack, skips state parsing.
- On disconnect: calls `action_client.clear_connection()`.

### ✅ Item 4: Overlay ACTION lines (orange)
- Added `LineTag.ACTION = "action"` to the overlay enum.
- Orange color `#f4845f` in `TAG_COLOURS`.
- Prefix `→ ` in `_tag_prefix()`.
- Voice loop pushes two ACTION messages per intent: the initial "→ set_waypoint(airport)…" and the result "→ set_waypoint(airport) ✓ack" / "✗nack" / "timeout".

### ✅ Item 5: Tests
33 new tests in `tests/brain/test_actions.py`:
- **GazetteerTests** (2): ≥15 entries, all have numeric x,y.
- **IntentMatcherTests** (13): 7 match patterns (airport, hospital, mark, go, navigate, drive, head, case-insensitive), 3 no-match (random, empty, unknown place), partial name greedy match, unique IDs.
- **WhitelistTests** (2): set_waypoint/spawn_companion/heal_player approved; unknown rejected.
- **WireFormatTests** (1): JSON serialization matches spec.
- **ActionClientAckTests** (4): full round-trip over real localhost TCP, timeout on no ack, disconnected send, non-whitelisted refusal.
- **FeedAckTests** (4): valid ack, nack, non-ack state line, invalid JSON.
- **ActionLogTests** (1): file creation + entry format.
- **IDGeneratorTests** (2): monotonic, thread-safe (4 threads × 50).
- **OverlayActionTagTests** (2): tag exists, orange color correct.

**Full suite: 61 tests, all pass** (`python -m unittest discover -s tests`).

### ✅ Item 6: Frozen files
- `src/mod/**` — UNTOUCHED (verified: no files in mod/ were modified or created).
- `ACTION_WHITELIST.md` — UNTOUCHED.
- `ROADMAP.md` — UNTOUCHED.
- `PROJECT_STATE.md` — UNTOUCHED.
- Port/protocol — UNCHANGED (127.0.0.1:48651).

## Files changed
| File | Action | Lines |
|------|--------|-------|
| `src/brain/actions.py` | **NEW** | ~280 |
| `src/brain/copilot.py` | Modified | ~560 (Phase 5a wiring) |
| `src/brain/overlay.py` | Modified | added ACTION tag |
| `tests/brain/test_actions.py` | **NEW** | ~310 |

## Not done / Notes
- The action system is **fully testable without the mod DLL**. All 33 new tests pass with fake sockets.
- The listener thread now also creates a **write file** for the connection — this is the reverse channel the mod will read. Claude Code needs to build the C# side: reader loop, action validation, native execution, ack emission.
- Only `set_waypoint` is implemented as an intent. `spawn_companion` and `heal_player` actions are whitelisted but have no intent matcher patterns yet (Phase 5b+).
- The `--no-voice` mode note from Phase 4 (reactions skip overlay in speech-queue-gated push) is unchanged — still fine for `--no-overlay` testing.

## Pre-session checklist for Beshr
1. **Restart the copilot** to pick up Phase 5a.
2. The running instance still has Phase 4 code — it will not recognize action intents.
3. Run: `.venv\Scripts\python.exe -m src.brain.copilot --ptt-key "right ctrl"`
4. Say "set a waypoint to the airport" — the brain will match, send the wire JSON, and wait for ack. Without the new mod DLL, it will timeout after 3s and say "No response from the mod."
5. Once Claude Code builds the reverse channel DLL: game closed → deploy → game open → the waypoint should appear on the map.
