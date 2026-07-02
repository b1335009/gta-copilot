# Reference Repo Research Notes

Owner: Claude Code (Fable 5). Compiled 2026-07-01 from direct source reads and mod-page documentation. Hermes: read this before writing any shell, action, or voice code. Items marked VERIFIED come from actual source or official pages; items marked INFERRED are standard modding knowledge, not confirmed from the mod's code.

## Verdicts (this changes the kickoff plan)

| Reference | Source available? | License | Verdict |
|---|---|---|---|
| Living World AI (SHVDN3) | NO — closed DLL on Nexus, no repo | none granted | Cannot fork. Replicate patterns only. |
| Living LSAIs V3.3 (SHVDN3) | NO — closed DLL on gta5-mods | none granted | Cannot port code. Reimplement actions from the native mapping below. |
| GTA 5 Enhanced Conversations (C++) | YES — GitHub, full source read | custom source-available (main), GPL-3.0 (audio), Apache-2.0 (configs) | Study freely. Do NOT vendor its code. |
| TalkToMeV (SHVDN3) — found during research | YES — GitHub | GPL-3.0 | Best open shell example. Study its structure; we still write our own shell to keep our license clean. |

**Decision (Claude Code): we write our own shell from scratch.** The two mods we planned to fork are closed-source. TalkToMeV proves the shell is small (one Script subclass, one backend seam, a few context providers) — forking it would GPL our whole repo for maybe 300 lines of savings. Not worth it. The phases don't change; Phase 0–1 were always from-scratch-sized anyway.

## 1. Living World AI — patterns to replicate

- Nexus page: https://www.nexusmods.com/gta5/mods/1708 (author MFiveM5, alpha 1.0.1)
- Backend boundary is localhost HTTP to the Player2 desktop app at `127.0.0.1:4315` — OpenAI-shaped `POST /chat/completions`, plus `/tts/speak`, `/stt/stream` (WebSocket), `GET /health`. VERIFIED from the Player2 API docs (https://player2.game/docs/api-reference). Our socket-to-Hermes boundary is architecturally identical; nothing to swap, we just build ours.
- Patterns worth copying (VERIFIED from mod page docs, not code):
  - Per-NPC persistent memory as flat files in `scripts\npc_memory\`
  - INI config + in-game settings menu
  - Request log file (`api_logs.txt`) — we should log all Hermes traffic the same way; free debugging and free B-roll
  - Dialogue-outcome → whitelisted action dispatcher (follow, wait, flee, surrender, arrest) — same shape as our Phase 5
  - Context bundle per exchange: district, weather, time, weapon, wanted level, vehicle, health/armor, combat state, nearby events

## 2. TalkToMeV — the open-source shell blueprint

- https://github.com/ItsMeDeli/TalkToMeV — GPL-3.0, SHVDN3 C#. Study, don't copy.
- Structure to mirror in our `src/mod/`:
  - `NPCConversationScript.cs` : inherits `GTA.Script`, overrides `OnTick` + `KeyDown` — the canonical SHVDN3 skeleton
  - Backend isolated in ONE file (`API/GeminiAPI.cs`, async `HttpClient` returning `Task<string>`) — our socket client gets the same single-seam isolation
  - Threading: network I/O via async/await off-thread; results consumed back inside `OnTick`. **This is the pattern that keeps natives on the script thread.**
  - `Context/EnvironmentContext.cs` + provider classes (location, weather, vehicle) — clean shape for our Phase 1 state reader

## 3. Living LSAIs V3.3 — action mechanics (reimplement, don't port)

- Mod page: https://www.gta5-mods.com/scripts/livinglsais-0706c201-ba7c-4e19-9c70-d77db561f835 (author ZEXIVA77). Closed DLL. Requires SHVDN nightly 3.7+/. NET 8 — note for our own toolchain choice.
- Its action trigger format (VERIFIED from docs): LLM emits inline square-bracket tags in reply text, e.g. `[FOLLOW]`, `[GIVEMONEY@500]`, `[LIFT]`. Parsed from the string, then executed. **We will NOT copy this** — brittle. Ours is a separate JSON action field from Hermes, validated against ACTION_WHITELIST.md. But the tag inventory is a good menu of what's feasible: lift-to-waypoint via native driving nodes, recruit-as-bodyguard (10x health + rifle), pull-over, flee, hands-up, call cops.
- Memory persistence (VERIFIED): local flat JSON under `scripts/`, decay by in-game hours, long-term memory only after 3+ conversations with the same NPC. Cloud backend is stateless; memory is injected into prompts from local files. Same design works for us.
- **Native mapping for our three whitelisted actions (INFERRED — standard SHVDN3 calls, to be used by Claude Code when writing the executor):**
  - `set_waypoint`: `World.WaypointPosition = pos` (→ `SET_NEW_WAYPOINT`); read back via `IS_WAYPOINT_ACTIVE` / `World.WaypointPosition`; clear via `World.RemoveWaypoint()`
  - `spawn_companion`: `World.CreatePed(model, pos)` → set `IsPersistent`, `RelationshipGroup = player's`, `BlockPermanentEvents = true`, add to `Game.Player.Character.PedGroup`, `SET_PED_NEVER_LEAVES_GROUP`, give weapon via `ped.Weapons.Give(...)`, combat attrs via `SET_PED_COMBAT_ATTRIBUTES(46)`
  - `heal_player`: `Game.Player.Character.Health = MaxHealth`, `ClearBloodDamage()`; armor via `SET_PED_ARMOUR` if we later approve it

## 4. Enhanced Conversations — the latency and GPU-contention playbook

- Source: https://github.com/Venator5824/GTA-5-EC-Mod-CPP-open-code (+ `Enhanced-Conversations-0.8.2`, configs repo). All VERIFIED from source read.
- Everything runs inside GTA5.exe as .asi plugins — fully offline, no external server. We differ (separate processes) but the latency lessons transfer:
  - **They hit sub-1.5s with small models + short outputs, NOT streaming.** Whisper base.en (~74M), Phi-3-mini Q4/Q6, Piper medium. Output hard-capped, 1–3 sentence responses enforced in the system prompt. That's our recipe for Phase 3: cap Hermes's spoken replies.
  - **GPU discipline: at most one AI workload on the GPU at a time.** LLM gets the GPU (Vulkan); Whisper transcribes on 4 CPU threads; TTS pinned to CPU (2 threads). GTA's renderer owns the rest. On the 4070 laptop we should do the same: Hermes LLM on GPU, faster-whisper small/base on CPU (or int8), Piper on CPU.
  - Push-to-talk replaces VAD entirely: capture 16 kHz mono f32 (Whisper's native input — no resample step), buffer while held, transcribe once on release. No streaming STT needed at this reply length.
  - Perceived-latency floor: they deliberately delay replies to 750 ms minimum so response timing feels natural and jitter is hidden. Steal this.
  - Threading model (their equivalent of our rule): all heavy work in `std::async` futures, polled with `wait_for(0ms)` from the game thread each frame, `.get()` only when ready; state machine gates transitions; timeouts discard stuck futures (LLM 30s, STT 10s). **This is exactly the shape of our C# shell: background I/O, poll from OnTick, natives only on the script thread.**
  - Their crash fix worth remembering: on fullscreen transitions they sleep 500 ms to let DirectX re-own the GPU before Vulkan resumes. If we see crashes alt-tabbing borderless GTA while Hermes generates, this is the first suspect.
  - Background summarization keeps prompts short: post-conversation async summarize replaces raw history; VRAM-headroom-driven live compression. Relevant for Hermes context management at Milestone 4+.
