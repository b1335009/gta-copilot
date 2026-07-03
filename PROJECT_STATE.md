# PROJECT STATE

Owner: Claude Code (Fable 5). Hermes reads this file, works the checklist, then writes results to HANDOFF.md. Hermes never edits this file.

## Current phase: 1

## Definition of done for this phase:
State reader polls natives, serializes to JSON, prints where we can see it. Done when health, wanted level, position, and vehicle are all correct in the JSON while Beshr plays (verified against what's actually happening on screen).

## Architecture decisions for this phase (Claude Code, binding):
- Poll cadence: inside OnTick, throttled to every ~250 ms via Game.GameTime comparison. NO Timers, NO Tasks, NO threads — every native read stays on the script thread.
- Schema (exact field names, all lowercase; emit one JSON object per line):
  `{"t":<unix_ms>,"health":<int>,"max_health":<int>,"armor":<int>,"wanted":<int>,"pos":{"x":<f1>,"y":<f1>,"z":<f1>},"vehicle":null|{"name":"<display>","speed_kmh":<f0>}}`
- JSON is hand-rolled with a small StringBuilder helper — NO Newtonsoft/System.Text.Json dependency (nothing extra to ship into scripts/).
- Output: append one line to `scripts/GtaCopilot.state.jsonl` AND write the same line to the SHVDN console (Console.WriteLine / SHVDN log). Emit only on change (any field differs from last emit) plus a 5 s heartbeat.
- File writes are tiny and infrequent; doing them on the tick thread is accepted FOR THIS PHASE ONLY. The socket sender in Phase 2 (Claude Code writes it) replaces this.
- Keep HelloCopilot's health overlay drawing; move shared state reads so natives are read once per poll.

## Hermes checklist (next tasks):
- [ ] Create `src/mod/GameState.cs`: plain data class matching the schema above, plus `Equals`-style change detection (write it explicitly, no reflection).
- [ ] Create `src/mod/GameStateReader.cs`: reads player ped, wanted level, position, current vehicle (null when on foot) — all reads assume they are called from OnTick only; document that in a class comment.
- [ ] Create `src/mod/JsonWriter.cs`: minimal serializer for exactly this schema (escape strings, invariant culture for floats — no locale commas).
- [ ] Wire into the existing script class: throttle, change-detect, emit to jsonl file + SHVDN console. Keep the on-screen health text working.
- [ ] Build Release, copy DLL to <GTA root>/scripts/ (game must not be running during copy), write HANDOFF.md.
- [ ] Do NOT touch sockets, threads, or Hermes-the-brain integration — that is Phase 2 and Claude Code writes the concurrency.

## Review log (newest first):
- 2026-07-01 PHASE 0 GATE — PASS. In-game screenshot verified by reviewer: "Health: 200" drawn top-left by GtaCopilot.Mod under SHVDNE 3.9.0.5, game stable in story mode. Live-update confirmation (number moving on damage) delegated to Beshr as a rollback condition, not a blocker. Phase advanced 0 → 1.
- 2026-07-01 CRASH #1 triaged and fixed — root cause: Claude Code's install instructions were written for Legacy. GTA V Enhanced does NOT load dinput8.dll; its ASI loader is xinput1_4.dll (shipped in the SHV zip, explicitly skipped on install). Evidence: zero ScriptHookV.log despite Users having FullControl on the game dir → SHV never loaded; game version 1.0.1013.34 exactly matches SHV 3788.0 → not version lag. Fix: extracted xinput1_4.dll + args.txt ("-nobattleye -noBE", the official Enhanced BattlEye disable per SHV's own HOW_TO_INSTALL) from the cached zip into the game root. dinput8.dll left in place (inert on Enhanced). commandline.txt left in place (harmless). NOTE: since SHV never loaded, the story-mode crash was never attributable to our stack; superseded by the gate PASS above.
- 2026-07-01 Deploy session — PASS. Reviewer independently verified on-disk state: SHV + full SHVDNE v1.1.0.5 set (incl. MinHook.x64.dll, per SHVDNE README) in game root; deployed scripts/GtaCopilot.Mod.dll SHA256-matches reviewer's own clean build; commandline.txt contains -nobattleye. Full runtime set install approved. .gitignore additions (.downloads/, .hermes/) approved.
- 2026-07-01 Process note (not a FAIL): installing binaries into the game dir was assigned to Beshr; Hermes did it directly. Outcome was correct and matched the blocker instructions, so accepted — but Hermes: machine-level installs outside the repo should be flagged as a question first, not executed. Repo-internal work is yours; system state changes get a human or reviewer sign-off.
- 2026-07-01 HelloCopilot.cs — PASS. All natives and drawing confined to OnTick (main script thread rule respected). No async/tasks/timers/sockets. Unsubscribes on Aborted. Minor, non-blocking: TextElement allocated every tick; fine for Phase 0, cache it when this file grows up into the real overlay.
- 2026-07-01 GtaCopilot.Mod.csproj — PASS. Old-style MSBuild + ReferenceAssemblies.net48 accepted (no .NET SDK on machine; also means Beshr does NOT need the net48 dev pack). Compile-time SHVDN3 from NuGet 3.6.0 with Private=False is the permanent approach — runtime binds to the installed SHVDN in the game dir; we never switch to a GTA-root HintPath. x64 PlatformTarget approved. Note: the explicit HintPath Reference alongside PackageReference is redundant but harmless; leave it.
- 2026-07-01 Build verification — PASS. Claude Code wiped bin/obj and rebuilt Release from scratch independently: restore + compile clean, GtaCopilot.Mod.dll produced (4,608 bytes).
- 2026-07-01 Process compliance — PASS. Hermes touched only allowed files (checkboxes, HANDOFF.md, src/mod/*). Whitelist and roadmap untouched. Correctly left the build+copy item unchecked and reported blockers instead of guessing.
- 2026-07-01 Items 2/3/4 (install verification) — BLOCKED, not failed (later resolved). No GTA V install existed on this machine at review time.

## Blockers:
- Beshr: confirm the health number moves when you take damage (rollback condition for the Phase 0 gate — 10 seconds, do it during the Phase 1 test session).
- Note on the runtime actually installed: SHVDNE console reports "Script Hook V .Net Enhanced 3.9.0.5 (1.1.0.5)" — SHVDN3 v3 API level 3.9. Our NuGet 3.6.0 compile reference remains valid (older API surface, runs fine); do not upgrade the NuGet package without Claude Code sign-off.

## [RECORD] cues:
- NOW: the health number on screen + damage test — hold the shot, let the number visibly drop. That plus the crash-fix footage completes the Phase 0 arc.
- Phase 1 money shot: the console/jsonl printing live JSON while you play — point at each field (health, wanted, pos, vehicle) matching what's on screen. Get in a car and show "vehicle" flip from null to a name. This is the proof-the-data-is-real beat (shooting script #5).
- Two-agent reveal (shooting script #4): film during this phase — split screen of PROJECT_STATE.md checklist on one side, Hermes building the state reader on the other.
