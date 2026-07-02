# GTA V Offline AI Co-Pilot

An offline AI co-pilot for GTA V single player. Reads real game state through Script Hook V natives (no screen scraping), talks by voice and text, executes whitelisted in-game actions. Everything runs local. Built by a two-agent workflow: a local Hermes agent writes, Claude Code (Fable 5) reviews and decides. Filmed as a YouTube build.

## Read these in order
1. ROADMAP.md — milestones, phase gates, decision authority. Owned by Claude Code.
2. PROJECT_STATE.md — live state: current phase, Hermes's checklist, review log. Owned by Claude Code.
3. HANDOFF.md — Hermes writes work reports here after each session.
4. ACTION_WHITELIST.md — the only actions the agent may execute in-game. Owned by Claude Code.
5. docs/CLAUDE_CODE_KICKOFF.md — the prompt that boots Claude Code into its role.
6. docs/SHOOTING_SCRIPT.md — when to hit record.

## Architecture
- src/mod/    — C# SHVDN3 in-game shell (state reader, socket, action executor)
- src/voice/  — Python voice pipe (faster-whisper STT, Piper TTS)
- Brain: Hermes agent, local, connects over socket (lives outside this repo)

## Rules that never bend
- SHVDN natives run on the main script thread only.
- Actions: request -> whitelist check -> execute. No agent expands its own capabilities.
- Nightly agents (v2) open PRs only. Nothing auto-merges. Human approves all merges to main.
