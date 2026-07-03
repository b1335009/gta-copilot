# HANDOFF — Hermes to Claude Code

## Phase 1 status

Implemented the Phase 1 state reader in the repo, built it successfully, and deployed the new DLL to the GTA `scripts/` folder after confirming GTA V Enhanced was no longer running.

Definition of done for Phase 1 is still **not complete yet**: Beshr must now verify live JSON fields against the screen while playing.

## Files changed in repo

- `src/mod/GameState.cs`
  - Plain data container matching the Phase 1 schema keys: `t`, `health`, `max_health`, `armor`, `wanted`, `pos`, `vehicle`.
  - Explicit `HasSameObservedValues(...)` change detection; timestamp `t` is intentionally ignored so heartbeat controls time-only emissions.
- `src/mod/GameStateReader.cs`
  - Reads player ped, health, max health, armor, wanted level, position, and current vehicle.
  - Class comment documents the OnTick/script-thread-only rule.
  - Rounds position to `F1` precision and vehicle speed to `F0` km/h so change detection matches emitted JSON.
  - Uses `Game.GetLocalizedString(vehicle.DisplayName)` with fallback to the raw display name.
- `src/mod/JsonWriter.cs`
  - Hand-rolled serializer for exactly the required schema.
  - Escapes strings and uses invariant culture for floats; no Newtonsoft/System.Text.Json dependency.
- `src/mod/HelloCopilot.cs`
  - Keeps the top-left health overlay using the last polled state, so health natives are read once per poll.
  - Polls inside `OnTick`, throttled with `Game.GameTime` every 250 ms.
  - Emits on observed-state change plus 5 s heartbeat.
  - Appends each JSON line to `scripts/GtaCopilot.state.jsonl` and writes the same line with `Console.WriteLine` for the SHVDN console/log.
  - Resolves the actual game root via the GTA process main module, then writes under `<game root>\scripts\GtaCopilot.state.jsonl`; this avoids SHVDN shadow-copy paths.
  - Uses no timers, tasks, threads, sockets, async, or extra runtime dependencies.
- `src/mod/GtaCopilot.Mod.csproj`
  - Added the three new `.cs` files to the old-style MSBuild compile item list.

## Verification performed

1. JSON/change-detection smoke test
   - First compile attempt failed before `GameState.cs`/`JsonWriter.cs` existed, as expected.
   - After implementation, the smoke test compiled and ran successfully:
     - Command: `csc -target:exe -out:.hermes/tmp/StateWriterSmokeTest.exe .hermes/tmp/StateWriterSmokeTest.cs src/mod/GameState.cs src/mod/JsonWriter.cs && .hermes/tmp/StateWriterSmokeTest.exe`
     - Exit code: `0`
   - Covered exact JSON ordering/escaping/float formatting and confirmed change detection ignores `t` but detects vehicle changes.

2. Release build
   - Command:
     - `'/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe' src/mod/GtaCopilot.Mod.csproj -restore -p:Configuration=Release -v:minimal`
   - Result:
     - `GtaCopilot.Mod -> C:\Users\beshr\Downloads\gta-copilot\src\mod\bin\Release\GtaCopilot.Mod.dll`
     - Exit code: `0`
   - Output DLL:
     - Path: `src/mod/bin/Release/GtaCopilot.Mod.dll`
     - Size: `10,752` bytes
     - SHA256: `fb6237bf848e720bb9a4e04639c3f3ac7fd0c622e4ffc22f7384f0516a7d0450`
     - File type: `PE32+ executable for MS Windows 6.00 (DLL), x86-64 Mono/.Net assembly`

3. Ad-hoc verification script
   - Created a focused temporary verifier at `C:\Users\beshr\AppData\Local\Temp\hermes-verify-74eafag7.py` using a `hermes-verify-` temp-file prefix.
   - First run correctly failed because the source constraint scan found `async` in a comment; Hermes removed that comment-only forbidden term from `HelloCopilot.cs`.
   - Second run passed. Scope was ad-hoc, not a canonical suite: source constraint checks, csproj compile-item checks, serializer/change-detection smoke compile+run, and MSBuild Release.
   - The verifier script and repo-local scratch files under `.hermes/tmp/` were removed after the passing run.

4. Dependency/concurrency scan within the ad-hoc verifier
   - Searched `src/mod/*.cs` for forbidden Phase 1 items:
     - `Newtonsoft`, `System.Text.Json`, `Timer`, `Task`, `Thread`, `Socket`, `async`, `await`
   - Result after comment cleanup: no matches.

## Deployment status

Target game root from `GAME_PATH.txt`:

- `C:\Program Files\Epic Games\GTAVEnhanced`

Hermes rechecked processes after Beshr said the game was gone; no `GTA5_Enhanced.exe`, `GTA5.exe`, or `PlayGTAV.exe` process was running.

Deployed:

- From: `C:\Users\beshr\Downloads\gta-copilot\src\mod\bin\Release\GtaCopilot.Mod.dll`
- To: `C:\Program Files\Epic Games\GTAVEnhanced\scripts\GtaCopilot.Mod.dll`
- Backup of previous deployed DLL: `C:\Program Files\Epic Games\GTAVEnhanced\scripts\.backup-phase1\GtaCopilot.Mod.dll.before-phase1-20260702-202424`

Verification:

- Source size/SHA256: `10,752` bytes / `973120271824cafffa6a3aeea87523b62e6e4ac9a6367b9fe4c34af4587ec105`
- Target size/SHA256 after copy: `10,752` bytes / `973120271824cafffa6a3aeea87523b62e6e4ac9a6367b9fe4c34af4587ec105`
- Source/target hash match: `True`
- `C:\Program Files\Epic Games\GTAVEnhanced\scripts\GtaCopilot.state.jsonl`: not present yet; expected to be created on first successful Phase 1 runtime emit.

## Next required action

Launch story mode and verify:

- health matches the top-left overlay / player damage state;
- wanted level changes correctly;
- position updates while moving;
- `vehicle` is `null` on foot;
- `vehicle` flips to an object with name and `speed_kmh` when entering/driving a car;
- JSON lines appear both in SHVDN console/log and in `scripts\GtaCopilot.state.jsonl`.

## Runtime evidence — first Phase 1 in-game run

Beshr started the script manually from the SHVDN console because `ScriptHookVDotNet.ini` has `AutoLoadScripts=false`:

- SHVDN log line: `AutoLoadScripts is set to false, skipping auto loading scripts. You can start scripts with specific console commands such as StartAllScripts().`
- After `StartAllScripts`, `C:\Program Files\Epic Games\GTAVEnhanced\scripts\GtaCopilot.state.jsonl` was created and parsed successfully.
- Watcher first line:
  - `{"t":1783038755681,"health":200,"max_health":200,"armor":0,"wanted":0,"pos":{"x":-22.6,"y":-1439.1,"z":30.3},"vehicle":{"name":"Buffalo S","speed_kmh":0}}`
- Parsed keys: `armor,health,max_health,pos,t,vehicle,wanted`.
- Follow-up inspection found 70 lines, including:
  - vehicle flip from `vehicle:null` while on foot to `vehicle:{"name":"Bagger","speed_kmh":0}` after entering another vehicle;
  - moving vehicle speed from `10` up to `75` km/h;
  - health drop after the crash/fall from `200/200` to `177/200`, then `146/200`.
- At the time Beshr reported "I crashed", Windows still showed `GTA5_Enhanced.exe` and `PlayGTAV.exe` running, and `ScriptHookVDotNet.log` showed the script started cleanly with no managed exception logged.

Final watcher evidence completed the remaining Phase 1 proof points:

- `SAW_VEHICLE_OBJECT`: `{"t":1783038755681,"health":200,"max_health":200,"armor":0,"wanted":0,"pos":{"x":-22.6,"y":-1439.1,"z":30.3},"vehicle":{"name":"Buffalo S","speed_kmh":0}}`
- `SAW_VEHICLE_NULL`: `{"t":1783038761666,"health":200,"max_health":200,"armor":0,"wanted":0,"pos":{"x":-21.3,"y":-1439.1,"z":30.7},"vehicle":null}`
- `SAW_VEHICLE_SPEED`: `{"t":1783038827899,"health":200,"max_health":200,"armor":0,"wanted":0,"pos":{"x":-22.9,"y":-1435.2,"z":30.1},"vehicle":{"name":"Bagger","speed_kmh":10}}`
- `SAW_HEALTH_DROP`: `{"t":1783038836459,"health":177,"max_health":200,"armor":0,"wanted":0,"pos":{"x":-91.0,"y":-1475.1,"z":32.8},"vehicle":null}`
- `SAW_WANTED`: `{"t":1783039181392,"health":150,"max_health":200,"armor":0,"wanted":1,"pos":{"x":-152.4,"y":-1517.7,"z":34.0},"vehicle":null}`
- Watcher exited with `ALL_REMAINING_PHASE1_PROOF_SEEN`.

Additional death/respawn evidence after Beshr got cops and died:

- Wanted escalation captured: `wanted:1` → `wanted:2` → `wanted:3`.
- Damage/death captured: `health:150` → `145` → `137` → `123` → `114` → `0` while `wanted:3`.
- Respawn/reset captured: position jumped to hospital-area coordinates around `{x:342,y:-1398,z:32.5}`, `health` reset to `200/200`, and `wanted` reset to `0`.
- Latest inspected file state: `GtaCopilot.state.jsonl` had 334 valid JSONL entries and continued writing through death/respawn.

Phase 1 runtime data proof is complete from Hermes' side: health, wanted level, position, and vehicle state all appeared correctly in parsed JSON while Beshr played. Reviewer/Beshr should only confirm the recording visually matches the captured game actions.
