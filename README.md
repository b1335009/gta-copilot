# GTA V Offline AI Co-Pilot

An **offline AI co-pilot for GTA V (Enhanced) single player**. It reads real game state through Script Hook V natives (no screen scraping), comments on your gameplay out loud, answers your voice in ~real time, and executes a small whitelist of in-game actions — including spawning an embodied companion who follows you, fights for you, **lip-syncs while the AI talks**, and waves on command.

Everything runs **100% local**: no cloud, no API keys, no telemetry.

```
 GTA V Enhanced ──SHVDN3 mod (C#)──► TCP socket ──► Python brain
   state: hp/wanted/pos/vehicle/companion        │  faster-whisper (STT, CPU)
   actions: waypoint/companion/heal/gestures ◄───┘  hermes3:3b via Ollama (CPU)
                                                    Piper (TTS)
                                                    tkinter overlay (chat over the game)
```

## What it does

- **Live commentary** — wanted level jumps and the co-pilot reacts aloud within ~1.5 s.
- **Voice chat** — hold Right Ctrl, talk, release. It answers with full awareness of your live game state ("Is the cops after me?" → *"the po-leez have you in their sights; 1 wanted star"*). It has inferred player death from raw `hp=0` telemetry, unprompted.
- **Voice actions** (all whitelist-gated, deterministic matching — the LLM never invents actions):
  - "set a waypoint to the airport" / "take me to maze bank" — 25+ known places
  - "call backup" / "spawn a companion" — one armed bodyguard, follows + protects
  - "wait here" / "follow me" — companion positioning
  - "heal me" / "patch me up"
  - "wave" — he waves at you
- **The embodied bit** — when the companion is spawned, his mouth moves in sync with the AI's actual speech audio and he turns to look at you while talking.
- **Overlay** — translucent always-on-top chat panel over borderless GTA showing the conversation and actions.

## Requirements

- GTA V **Enhanced** (tested on 1.0.1013.34, Epic) — **story mode only**
- Windows 10/11, 16 GB+ RAM (**page file enabled** — the game will OOM at boot without one)
- A mic and speakers
- [Ollama](https://ollama.com) (the setup script pulls `hermes3:3b`, ~2 GB)
- Python 3.11+
- [Script Hook V](http://www.dev-c.com/gtav/scripthookv/) and [SHVDN Enhanced](https://github.com/crosire/scripthookvdotnet) (v3.9+) — **not bundled** (their licenses prohibit redistribution); install per their instructions
- LLM inference runs **on CPU by design** — the GPU belongs to the game. A modern 8-core CPU gives ~1.5–3 s replies with the 3B model.

> ⚠️ **Single player only.** The install disables BattlEye (`-nobattleye`), which means GTA Online is unavailable while installed. Never use mods with GTA Online.

## Install

1. Install Script Hook V into the GTA root. **GTA V Enhanced loads `xinput1_4.dll` as its ASI loader, not `dinput8.dll`** — copy it from the SHV zip (this is the #1 install mistake). Add `args.txt` containing `-nobattleye`.
2. Install SHVDN Enhanced (all its DLLs incl. `MinHook.x64.dll`) into the GTA root, with `AutoLoadScripts=true`.
3. Copy `GtaCopilot.Mod.dll` (from [Releases](../../releases), or build from `src/mod` with MSBuild) into `<GTA root>\scripts\`.
4. Clone this repo and run the brain setup:
   ```powershell
   .\scripts\setup.ps1
   ```
   This creates `.venv`, installs Python deps, downloads Piper TTS + a voice, and pulls the Ollama model.

## Run

```powershell
.\scripts\run.ps1        # or: .venv\Scripts\python.exe -m src.brain.copilot
```

Start the brain **first**, then launch GTA (story mode, **Borderless** display mode). You'll see `Mod connected` in the overlay when the game hooks up. Hold **Right Ctrl** to talk (`--ptt-key` to change).

## Troubleshooting (learned the hard way)

| Symptom | Cause / fix |
|---|---|
| Game "out of memory" at boot | Page file disabled. Re-enable it (Settings → virtual memory) and reboot. |
| Ollama HTTP 500 during play | Model loaded on GPU, fighting the game for VRAM. The brain forces CPU (`num_gpu:0`) — make sure you launched via `copilot.py` so the preload runs. |
| No ScriptHookV.log after launch | SHV isn't loading — you installed `dinput8.dll` instead of `xinput1_4.dll` (Enhanced quirk). |
| Overlay hidden behind game | Set GTA display mode to **Borderless**. |
| PTT does something in-game | Pick an unbound key: `--ptt-key "right ctrl"` (default). Avoid F4–F8. |

## Architecture & repo map

- `src/mod/` — C# SHVDN3 mod: state reader → JSON over TCP (127.0.0.1:48651), bidirectional action channel (request → **compiled-in whitelist check** → script-thread execution → ack)
- `src/brain/` — Python: TCP listener, wanted-level reactions, PTT → STT → LLM → TTS loop, deterministic intent matcher, overlay
- `ACTION_WHITELIST.md` — the only actions that can ever execute; everything else is refused at two layers (Python mirror + compiled into the DLL)
- `ROADMAP.md` / `PROJECT_STATE.md` — the build is run by an AI two-agent workflow (a worker agent implements, Claude Code reviews and gates phases); these files are its state
- `tests/` — 76 unit tests, no game or model needed: `python -m unittest discover -s tests`

## Safety model

Actions follow a hard trust ladder: the LLM **never** chooses actions, parameters, or coordinates. Voice → deterministic regex/gazetteer → whitelist check in Python → whitelist check compiled into the C# mod → single action per game tick on the script thread → ack + JSONL audit log of every request. Adding a new action requires editing two whitelists and a review gate.

## Status

**v0.1.0-alpha.** Milestones shipped: live telemetry, voice loop, overlay, three world actions, embodied companion with lip-sync. See [ROADMAP.md](ROADMAP.md) for what's next (companion persona merge, then voice-directed companion behaviors).

Built in ~3 days as a human + multi-agent AI collaboration. Expect sharp edges.

## License

MIT — see [LICENSE](LICENSE). Not affiliated with Rockstar Games. GTA V is a trademark of Take-Two Interactive.
