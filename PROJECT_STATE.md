# PROJECT STATE

Owner: Claude Code (Fable 5). Hermes reads this file, works the checklist, then writes results to HANDOFF.md. Hermes never edits this file.

## Current phase: 0

## Definition of done for this phase:
Script Hook V and ScriptHookVDotNet3 installed. A hello-world C# mod compiles, loads, and draws the player's current health on screen, updating live in-game.

## Hermes checklist (next tasks):
- [ ] NOTHING. Phase 0 is fully deployed; the gate is human-only: Beshr launches GTA V Enhanced single player and confirms "Health: <n>" draws top-left and updates live. Do NOT start Phase 1 work (state reader, JSON, sockets) under any circumstances until Claude Code advances the phase in this file.

Completed this phase:
- [x] GTA V Enhanced root found: C:\Program Files\Epic Games\GTAVEnhanced (in GAME_PATH.txt, gitignored).
- [x] Script Hook V v3788.0/1013.34 installed (Beshr); SHVDNE v1.1.0.5 full runtime set installed incl. MinHook.x64.dll (Hermes).
- [x] scripts/ created; GtaCopilot.Mod.dll copied in (hash-verified against reviewer's independent build).
- [x] BattlEye disabled via commandline.txt (-nobattleye).
- [x] Read docs/REFERENCE_NOTES.md end to end before touching code (decision 2026-07-01: build our own shell from scratch; no decompiling closed mods).
- [x] Create the C# project: net48 class library referencing ScriptHookVDotNet3.dll.
- [x] Write HelloCopilot.cs: Script subclass, OnTick handler, draw Game.Player.Character.Health as screen text.
- [x] Build the DLL (copy to scripts/ still pending — see checklist).

## Review log (newest first):
- 2026-07-01 CRASH #1 triaged and fixed — root cause: Claude Code's install instructions were written for Legacy. GTA V Enhanced does NOT load dinput8.dll; its ASI loader is xinput1_4.dll (shipped in the SHV zip, explicitly skipped on install). Evidence: zero ScriptHookV.log despite Users having FullControl on the game dir → SHV never loaded; game version 1.0.1013.34 exactly matches SHV 3788.0 → not version lag. Fix: extracted xinput1_4.dll + args.txt ("-nobattleye -noBE", the official Enhanced BattlEye disable per SHV's own HOW_TO_INSTALL) from the cached zip into the game root. dinput8.dll left in place (inert on Enhanced). commandline.txt left in place (harmless). NOTE: since SHV never loaded, the story-mode crash is NOT yet explained by our stack — if it recurs with SHV properly loaded, triage fresh; do not assume this fix covers it.
- 2026-07-01 Deploy session — PASS. Reviewer independently verified on-disk state: SHV + full SHVDNE v1.1.0.5 set (incl. MinHook.x64.dll, per SHVDNE README) in game root; deployed scripts/GtaCopilot.Mod.dll SHA256-matches reviewer's own clean build; commandline.txt contains -nobattleye. Full runtime set install approved. .gitignore additions (.downloads/, .hermes/) approved.
- 2026-07-01 Process note (not a FAIL): installing binaries into the game dir was assigned to Beshr; Hermes did it directly. Outcome was correct and matched the blocker instructions, so accepted — but Hermes: machine-level installs outside the repo should be flagged as a question first, not executed. Repo-internal work is yours; system state changes get a human or reviewer sign-off.
- 2026-07-01 HelloCopilot.cs — PASS. All natives and drawing confined to OnTick (main script thread rule respected). No async/tasks/timers/sockets. Unsubscribes on Aborted. Minor, non-blocking: TextElement allocated every tick; fine for Phase 0, cache it when this file grows up into the real overlay.
- 2026-07-01 GtaCopilot.Mod.csproj — PASS. Old-style MSBuild + ReferenceAssemblies.net48 accepted (no .NET SDK on machine; also means Beshr does NOT need the net48 dev pack). Compile-time SHVDN3 from NuGet 3.6.0 with Private=False is the permanent approach — runtime binds to the installed SHVDN in the game dir; we never switch to a GTA-root HintPath. x64 PlatformTarget approved. Note: the explicit HintPath Reference alongside PackageReference is redundant but harmless; leave it.
- 2026-07-01 Build verification — PASS. Claude Code wiped bin/obj and rebuilt Release from scratch independently: restore + compile clean, GtaCopilot.Mod.dll produced (4,608 bytes).
- 2026-07-01 Process compliance — PASS. Hermes touched only allowed files (checkboxes, HANDOFF.md, src/mod/*). Whitelist and roadmap untouched. Correctly left the build+copy item unchecked and reported blockers instead of guessing.
- 2026-07-01 Items 2/3/4 (install verification) — BLOCKED, not failed. No GTA V install exists on this machine yet. Blocker assigned to Beshr below.

## Blockers:
- PHASE GATE (Beshr, in-game): launch GTA V Enhanced single player, confirm "Health: <n>" top-left updates live (take damage / eat a snack to see it move). Report result to Claude Code, who then advances to Phase 1. If the game crashes after the Rockstar logo: first suspect is SHV/SHVDNE vs game-patch version lag, not our code (SHV installed today is v3788.0 for 1013.34).

## [RECORD] cues:
- Film the install steps for the setup montage (speed up in edit).
- When the health number first draws on screen and updates live: hold the shot. First win of the video.
