# HANDOFF — Hermes to Claude Code

## Session summary
Worked Phase 0 checklist only. Built the net48 SHVDN3 hello-world mod shell in `src/mod/` and verified it compiles locally. GTA install/mod-path verification and DLL copy remain blocked because no GTA V installation or Script Hook files were found on this machine.

## Checklist item results

1. `[x]` Read `docs/REFERENCE_NOTES.md` end to end before touching code.
   - Confirmed the current plan: build our own shell from scratch; do not decompile or copy closed mods.
   - Kept native/game-state access inside `OnTick` only.

2. `[ ]` Confirm GTA V install path and that the game launches clean with no mods.
   - Blocked. I checked common Steam/Epic/Rockstar paths, Steam `libraryfolders.vdf`, Epic manifests, and scanned likely locations (`C:/Program Files`, `C:/Program Files (x86)`, `C:/Games`, Beshr user Desktop/Documents/Downloads, and `D:/`). No `GTA5.exe` was found.
   - I did not launch GTA because no install path was found.

3. `[ ]` Verify `ScriptHookV.dll` and `dinput8.dll` are in the GTA V root.
   - Blocked by missing GTA root. Same scan found no `ScriptHookV.dll` or `dinput8.dll`.

4. `[ ]` Verify SHVDN3 files and `scripts/` folder.
   - Blocked by missing GTA root. Same scan found no `ScriptHookVDotNet.asi` or installed `ScriptHookVDotNet3.dll` outside the NuGet compile cache.

5. `[x]` Create C# project: net48 class library referencing `ScriptHookVDotNet3.dll`.
   - Added `src/mod/GtaCopilot.Mod.csproj`.
   - Uses old-style MSBuild project because this machine has VS/MSBuild but no .NET SDK.
   - Targets .NET Framework 4.8 and x64.
   - Restores `ScriptHookVDotNet3` 3.6.0 from NuGet and directly references its `lib/net48/ScriptHookVDotNet3.dll`.
   - Restores `Microsoft.NETFramework.ReferenceAssemblies.net48` 1.0.3 because the local net48 targeting pack is missing.

6. `[x]` Write `HelloCopilot.cs`.
   - Added `src/mod/HelloCopilot.cs`.
   - `HelloCopilot : GTA.Script` subscribes to `Tick` and draws `Game.Player.Character.Health` every tick with `GTA.UI.TextElement`.
   - No background work, socket callbacks, timers, tasks, async continuations, file I/O, or native reads outside the SHVDN tick path.

7. `[ ]` Build and copy DLL to GTA V `scripts/` folder.
   - Build portion succeeded:
     - Command: `MSBuild.exe src/mod/GtaCopilot.Mod.csproj -restore -p:Configuration=Release -v:minimal`
     - Output: `src/mod/bin/Release/GtaCopilot.Mod.dll`
     - Observed size: 4,608 bytes
   - Copy portion is blocked because no GTA V root / `scripts/` folder was found.
   - Left the checkbox unchecked because the item requires both build and copy.

## Files touched
- `PROJECT_STATE.md` — checklist checkbox updates only.
- `HANDOFF.md` — overwritten with this report.
- `src/mod/GtaCopilot.Mod.csproj` — new net48 SHVDN3 class library project.
- `src/mod/HelloCopilot.cs` — new Phase 0 proof-of-life script.

## Blockers / questions for Claude Code
- GTA V install path was not discoverable from this environment. Beshr may need to install GTA V or provide the actual root path before Hermes can verify clean launch, SHV/SHVDN placement, create/verify `scripts/`, or copy the DLL.
- Is using NuGet `ScriptHookVDotNet3` 3.6.0 as the compile reference acceptable for Phase 0 until the manually installed GTA-root `ScriptHookVDotNet3.dll` exists?
- Should the project eventually switch from the NuGet-cache `HintPath` to a reviewer-approved local GTA/SHVDN reference path once Beshr installs SHVDN3?
- This machine lacks the .NET SDK and the net48 targeting pack. The project compensates with old-style MSBuild plus `Microsoft.NETFramework.ReferenceAssemblies.net48`; please review whether that should stay or whether Beshr should install the developer pack instead.

## Reviewer focus
- Confirm the old-style `.csproj` + NuGet direct `HintPath` is acceptable for this repo.
- Confirm `HelloCopilot` is minimal enough for Phase 0 and respects the main-script-thread native rule.
- Confirm whether the `x64` platform target is the preferred default for SHVDN3/GTA V.
