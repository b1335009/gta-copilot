# HANDOFF — Hermes to Claude Code

## Session summary
Completed the Phase 0 install/copy path for GTA V Enhanced on this machine. Found the Enhanced install at `C:\Program Files\Epic Games\GTAVEnhanced`, installed Script Hook V .NET Enhanced v1.1.0.5 runtime files from Chiheb-Bacha/ScriptHookVDotNetEnhanced, created `scripts/`, rebuilt the hello-world DLL, and copied it into the game `scripts/` folder. BattlEye was disabled for local single-player mod loading via `commandline.txt`.

The remaining phase gate is human/in-game verification: Beshr needs to launch GTA V Enhanced single-player and confirm the on-screen health number appears and updates live.

## Checklist item results

1. `[x]` Wait for/find GTA V Enhanced game path.
   - `GAME_PATH.txt` was absent initially.
   - Autodiscovered Enhanced install by finding `GTA5_Enhanced.exe` at `C:\Program Files\Epic Games\GTAVEnhanced`.
   - Wrote ignored local `GAME_PATH.txt` with that path for future sessions.

2. `[x]` Verify Script Hook V files in the GTA V root.
   - `ScriptHookV.dll`: present, 1,986,560 bytes.
   - `dinput8.dll`: present, 131,072 bytes.

3. `[x]` Install/verify Script Hook V .NET Enhanced files.
   - Downloaded latest GitHub release metadata from `Chiheb-Bacha/ScriptHookVDotNetEnhanced`: `v1.1.0.5`.
   - Downloaded and inspected `ScriptHookVDotNetEnhanced-v1.1.0.5.zip`.
   - README says to copy root `ScriptHookVDotNet*.*` plus `MinHook.x64.dll` into the folder containing `GTA5_Enhanced.exe/GTA5.exe`.
   - Installed:
     - `ScriptHookVDotNet.asi`: present, 298,496 bytes.
     - `ScriptHookVDotNet.ini`: present, 1,955 bytes.
     - `ScriptHookVDotNet2.dll`: present, 982,528 bytes.
     - `ScriptHookVDotNet3.dll`: present, 1,437,696 bytes.
     - `MinHook.x64.dll`: present, 16,384 bytes.
   - Verified VC++ 2015–2022/2019-compatible x64 runtime is installed:
     - Registry `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64`: `Installed=0x1`, `Version=v14.50.35719.00`.
     - `C:\Windows\System32\vcruntime140.dll`, `vcruntime140_1.dll`, and `msvcp140.dll` are present.

4. `[x]` Verify/create `scripts/` folder.
   - Created/verified `C:\Program Files\Epic Games\GTAVEnhanced\scripts`.

5. `[x]` Build and copy DLL to GTA V `scripts/` folder.
   - Build command used full VS path because `MSBuild.exe` is not on PATH in this shell:
     - `'/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe' src/mod/GtaCopilot.Mod.csproj -restore -p:Configuration=Release -v:minimal`
   - Build succeeded:
     - `GtaCopilot.Mod -> C:\Users\beshr\Downloads\gta-copilot\src\mod\bin\Release\GtaCopilot.Mod.dll`
   - Verified output:
     - `src/mod/bin/Release/GtaCopilot.Mod.dll`: 4,608 bytes.
     - PE32+ x86-64 Mono/.NET assembly.
   - Copied to:
     - `C:\Program Files\Epic Games\GTAVEnhanced\scripts\GtaCopilot.Mod.dll`
   - Verified copied DLL is present, 4,608 bytes.

6. `[x]` Disable BattlEye for modded single-player launch.
   - Created `C:\Program Files\Epic Games\GTAVEnhanced\commandline.txt` with:
     - `-nobattleye`
   - Verified file exists and contains `-nobattleye`.

7. `[ ]` In-game Phase 0 verification.
   - Not yet verified in-game from Hermes.
   - Beshr should launch GTA V Enhanced single-player and confirm `Health: <number>` draws at the top-left and updates live.
   - Do NOT start Phase 1 until Beshr confirms the health number updates live in-game.

## Files touched
- `.gitignore` — restored existing ignore rules and added local cache ignores for `.downloads/` and `.hermes/`; `GAME_PATH.txt`, `bin/`, and `obj/` remain ignored.
- `GAME_PATH.txt` — ignored local file containing the discovered GTA V Enhanced root.
- `HANDOFF.md` — overwritten with this report.
- Game root `C:\Program Files\Epic Games\GTAVEnhanced\`:
  - Installed `ScriptHookVDotNet.asi`, `ScriptHookVDotNet.ini`, `ScriptHookVDotNet2.dll`, `ScriptHookVDotNet3.dll`, `MinHook.x64.dll`.
  - Created/verified `scripts/`.
  - Copied `scripts\GtaCopilot.Mod.dll`.
  - Created `commandline.txt` with `-nobattleye`.

## Notes / pitfalls
- The first Python install attempt used an MSYS path (`/c/...`) inside Windows Python, which resolved incorrectly as `\c\...`. Re-ran successfully with native Windows path `C:\Program Files\Epic Games\GTAVEnhanced`.
- `MSBuild.exe` is available at `C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe`, but not on PATH in this Git Bash shell.
- SHVDNE README requires `MinHook.x64.dll` and `ScriptHookVDotNet.ini` in addition to the `.asi`/`ScriptHookVDotNet3.dll`; installed the complete root runtime set from the release zip.
- `.downloads/ScriptHookV_3788.0_1013.34.zip` remains ignored/local.

## Reviewer focus
- Confirm installing the complete SHVDNE root runtime set (`ScriptHookVDotNet*.*` + `MinHook.x64.dll`) is acceptable versus only `.asi` + `ScriptHookVDotNet3.dll`.
- Confirm `.gitignore` addition for `.downloads/` and `.hermes/` is acceptable.
- Await Beshr's in-game Phase 0 confirmation before any Phase 1 work.
