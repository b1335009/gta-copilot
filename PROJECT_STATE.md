# PROJECT STATE

Owner: Claude Code (Fable 5). Hermes reads this file, works the checklist, then writes results to HANDOFF.md. Hermes never edits this file.

## Current phase: 0

## Definition of done for this phase:
Script Hook V and ScriptHookVDotNet3 installed. A hello-world C# mod compiles, loads, and draws the player's current health on screen, updating live in-game.

## Hermes checklist (next tasks):
- [ ] Read docs/REFERENCE_NOTES.md end to end before touching code. Key decision recorded there (2026-07-01): both fork candidates are closed-source, so we build our own shell from scratch, mirroring TalkToMeV's structure — Script subclass, single backend seam, provider classes for state. Do not decompile or copy code from the closed mods.
- [ ] Confirm GTA V install path and that the game launches clean with no mods.
- [ ] Verify ScriptHookV.dll and dinput8.dll are in the GTA V root (Beshr installs these manually, Hermes verifies paths).
- [ ] Verify SHVDN3 files (ScriptHookVDotNet.asi, ScriptHookVDotNet3.dll) are in place and a scripts/ folder exists.
- [ ] Create the C# project: net48 class library referencing ScriptHookVDotNet3.dll.
- [ ] Write HelloCopilot.cs: Script subclass, OnTick handler, draw Game.Player.Character.Health as screen text.
- [ ] Build and copy the DLL to the GTA V scripts/ folder.

## Review log (newest first):
- (empty — Claude Code fills this after first handoff)

## Blockers:
- (none yet)

## [RECORD] cues:
- Film the install steps for the setup montage (speed up in edit).
- When the health number first draws on screen and updates live: hold the shot. First win of the video.
