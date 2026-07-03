# PROJECT STATE

Owner: Claude Code (Fable 5). Hermes reads this file, works the checklist, then writes results to HANDOFF.md. Hermes never edits this file.

## Current phase: 2

## Definition of done for this phase:
State JSON streams over a local TCP socket to the brain process, and Hermes-the-brain reacts in text to a state change. Done when Beshr raises his wanted level in-game and Hermes's comment about it appears in the brain console during live play (Milestone 1 gate — [RECORD]).

## Architecture decisions for this phase (Claude Code, binding):
- Transport: the mod is a TCP CLIENT; the brain is the SERVER listening on `127.0.0.1:48651`. Newline-terminated UTF-8 JSON lines, exactly the Phase 1 schema. The jsonl file + SHVDN console emits stay in place as debug fallback.
- Mod-side concurrency is DONE (Claude Code wrote it, per the kickoff rules): `src/mod/StateStreamClient.cs`. One background sender thread owns the socket and drains a bounded drop-oldest queue (256 lines); OnTick only enqueues pre-serialized strings. Reconnects throttled to one attempt per 2 s; the 5 s heartbeat doubles as the retry ticker. Natives never leave the script thread. Hermes does NOT edit any `src/mod/*.cs` this phase and does not add C# threading anywhere, ever.
- Delivery is lossy by design: while the brain is down, lines drop. The brain keys off the `t` field; it must not assume a gapless stream.
- Brain lives in `src/brain/` (Python, stdlib socketserver/socket is fine). It logs every received raw line to `src/brain/logs/state-<date>.jsonl` (add `src/brain/logs/` to .gitignore) — free debugging, free B-roll.
- Gate trigger: wanted level INCREASE vs the previous parsed line. The reaction is a short text comment produced by the local Hermes model, printed prominently in the brain console and logged. A canned fallback line (model endpoint down) must be clearly marked as fallback and does NOT pass the gate.
- New Phase 2 mod DLL is built and waiting: `src/mod/bin/Release/GtaCopilot.Mod.dll`, 13,312 bytes, SHA256 `8D838B5AB096C6E16B3C608FFC4FB9B1CA0277AF5DACBBB2753EEC3F582E98F7`. It was NOT deployed because GTA was running during the review session.

## Hermes checklist (next tasks):
- [ ] Create `src/brain/state_listener.py`: TCP server on `127.0.0.1:48651`; accepts one mod connection at a time and survives disconnect/reconnect (accept loop); parses each line as JSON; logs raw lines to `src/brain/logs/state-<date>.jsonl`; prints a compact one-line summary per state to console.
- [ ] Add wanted-level tracking: on increase, build a short context string (health/armor, vehicle or on foot, rough position) and get a text reaction from the local Hermes model; print it prominently and log it. State in HANDOFF.md exactly which model/endpoint you used.
- [ ] Replay harness: copy the captured session file `C:\Program Files\Epic Games\GTAVEnhanced\scripts\GtaCopilot.state.jsonl` (334 real lines including a wanted 0→3 arc and death/respawn) into `src/brain/fixtures/session-20260702.jsonl`, and add `src/brain/replay_client.py` that connects to the listener and replays it with small delays. Prove the listener + reaction path end-to-end with NO game running; paste the evidence in HANDOFF.md.
- [ ] Deploy the new mod DLL from `src/mod/bin/Release/` to `<GTA root>/scripts/` — ONLY with the game not running; back up the old DLL like last time; verify source/target SHA256 match against the hash above.
- [ ] Do NOT touch: `src/mod/*.cs` or the csproj (all Phase 2 C# is Claude Code's), the port/protocol, ACTION_WHITELIST.md, ROADMAP.md.

## Review log (newest first):
- 2026-07-02 PHASE GATE — PASS, advanced 1 → 2. Reviewer verified independently, not from HANDOFF claims: (a) line-by-line review of all five mod sources — natives confined to OnTick, no timers/tasks/threads/sockets in Phase 1 code, hand-rolled JSON correct (escaping, invariant culture, negative-zero normalization, `t` excluded from change detection); (b) repo Release DLL SHA256 `973120…c105` matched the deployed scripts DLL exactly; (c) independent MSBuild rebuild from the same sources compiled clean at identical 10,752 bytes; (d) all 334 runtime lines of `GtaCopilot.state.jsonl` parse with the exact schema keys and show vehicle null↔object flips, 75 km/h driving, wanted 0→3, health 200→0, and hospital respawn reset — matching Beshr's live-reported gameplay. Definition of done met.
- 2026-07-02 HANDOFF hash discrepancy — resolved, not an issue. The build-step hash in HANDOFF (`fb6237…`) predates Hermes's comment-only cleanup rebuild; the deployed binary matches the final committed sources (verified by reviewer hash + rebuild).
- 2026-07-02 Phase 0 rollback condition — cleared. Health visibly dropped on damage during the Phase 1 session (overlay draws from the same polled state whose values fell 200→177→146 in the jsonl while Beshr played).
- 2026-07-02 StateStreamClient.cs — written by Claude Code (kickoff rule: reviewer owns socket/concurrency). Release build clean; DLL hash recorded above; deployment pending game close.
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
- Deploy of the Phase 2 DLL is blocked while GTA is running (it was live at review time, pid 34344). First checklist session with the game closed: deploy, then verify.
- Hermes: declare in HANDOFF.md which local model/endpoint produces the reactions — the gate needs real model output, not a canned string.
- Note on the runtime actually installed: SHVDNE console reports "Script Hook V .Net Enhanced 3.9.0.5 (1.1.0.5)" — SHVDN3 v3 API level 3.9. Our NuGet 3.6.0 compile reference remains valid (older API surface, runs fine); do not upgrade the NuGet package without Claude Code sign-off.

## [RECORD] cues:
- MILESTONE 1 GATE money shot: two windows visible at once — the game and the brain console. Commit a crime on camera, and the instant the stars appear, Hermes's comment prints. Do not script or rehearse your reaction; the roadmap explicitly wants the genuine one.
- B-roll before the live test: the replay harness feeding the recorded death-by-cops session (334 lines) into the brain with no game running — the console narrating a chase that already happened is a great "the data is real" beat.
- Passive capture: the moment `GtaCopilot: stream connected to brain on 127.0.0.1:48651` appears in the SHVDN console — that's the two processes shaking hands for the first time.
