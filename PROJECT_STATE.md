# PROJECT STATE

Owner: Claude Code (Fable 5). Hermes reads this file, works the checklist, then writes results to HANDOFF.md. Hermes never edits this file.

## Current phase: 0

## Definition of done for this phase:
Script Hook V and ScriptHookVDotNet3 installed. A hello-world C# mod compiles, loads, and draws the player's current health on screen, updating live in-game.

## Hermes checklist (next tasks):
- [ ] Wait for GAME_PATH.txt to appear in the repo root (Beshr writes the GTA V install root into it, single line, after installing the game + SHV + SHVDN3). It is gitignored — never commit it.
- [ ] Using that path: verify ScriptHookV.dll and dinput8.dll are in the GTA V root, verify ScriptHookVDotNet.asi and ScriptHookVDotNet3.dll are in place, and that a scripts/ folder exists. Report exact findings in HANDOFF.md.
- [ ] Copy src/mod/bin/Release/GtaCopilot.Mod.dll into <GTA root>/scripts/.
- [ ] Do NOT start Phase 1 work (state reader, JSON, sockets). The phase gate is Beshr confirming the health number updates live in-game.

Completed this phase:
- [x] Read docs/REFERENCE_NOTES.md end to end before touching code (decision 2026-07-01: build our own shell from scratch; no decompiling closed mods).
- [x] Create the C# project: net48 class library referencing ScriptHookVDotNet3.dll.
- [x] Write HelloCopilot.cs: Script subclass, OnTick handler, draw Game.Player.Character.Health as screen text.
- [x] Build the DLL (copy to scripts/ still pending — see checklist).

## Review log (newest first):
- 2026-07-01 HelloCopilot.cs — PASS. All natives and drawing confined to OnTick (main script thread rule respected). No async/tasks/timers/sockets. Unsubscribes on Aborted. Minor, non-blocking: TextElement allocated every tick; fine for Phase 0, cache it when this file grows up into the real overlay.
- 2026-07-01 GtaCopilot.Mod.csproj — PASS. Old-style MSBuild + ReferenceAssemblies.net48 accepted (no .NET SDK on machine; also means Beshr does NOT need the net48 dev pack). Compile-time SHVDN3 from NuGet 3.6.0 with Private=False is the permanent approach — runtime binds to the installed SHVDN in the game dir; we never switch to a GTA-root HintPath. x64 PlatformTarget approved. Note: the explicit HintPath Reference alongside PackageReference is redundant but harmless; leave it.
- 2026-07-01 Build verification — PASS. Claude Code wiped bin/obj and rebuilt Release from scratch independently: restore + compile clean, GtaCopilot.Mod.dll produced (4,608 bytes).
- 2026-07-01 Process compliance — PASS. Hermes touched only allowed files (checkboxes, HANDOFF.md, src/mod/*). Whitelist and roadmap untouched. Correctly left the build+copy item unchecked and reported blockers instead of guessing.
- 2026-07-01 Items 2/3/4 (install verification) — BLOCKED, not failed. No GTA V install exists on this machine yet. Blocker assigned to Beshr below.

## Blockers:
- BESHR: install GTA V (Legacy), Script Hook V, and ScriptHookVDotNet3 (stable 3.6.x nightly not required), then write the GTA root path into GAME_PATH.txt in the repo root. Everything else in Phase 0 is queued behind this. You do NOT need the .NET 4.8 developer pack — the project restores reference assemblies from NuGet.

## [RECORD] cues:
- Film the install steps for the setup montage (speed up in edit).
- When the health number first draws on screen and updates live: hold the shot. First win of the video.
