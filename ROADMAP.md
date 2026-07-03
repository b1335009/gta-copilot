# ROADMAP — GTA V Offline AI Co-Pilot

Owner: Claude Code (Fable 5). This file is edited by Claude Code only.
Hermes and nightly agents read it, never write it.
Human gate: Beshr approves all merges to main and confirms phase completion in-game.

## Decision authority
- Claude Code (Fable 5): audits all diffs and PRs, gates phases, owns this file and PROJECT_STATE.md, final merge/reject call before human approval.
- Hermes: executes the current checklist in PROJECT_STATE.md. Does not advance phases, does not edit this file, does not add action types to the whitelist.
- Nightly agents (Codex / Jules / Antigravity, v2 only): read PROJECT_STATE.md, do one checklist item, open a PR. Never merge. Reviewed by Claude Code next morning.
- Non-negotiable review rules: natives on main script thread only; actions go request -> whitelist check -> execute; whitelist file is owned by Claude Code.

## Milestone 1 — Core loop (target: one 4-hour session)
- [x] Phase 0: SHV + SHVDN3 installed, hello-world mod draws player health on screen live. (Gate PASS 2026-07-01)
- [x] Phase 1: State reader polls natives (health, wanted level, position, vehicle), serializes JSON, prints to console. (Gate PASS 2026-07-02 — 334-line runtime proof incl. wanted 0→3 and respawn)
- [ ] Phase 2: JSON streams over local socket to Hermes; Hermes reacts in text to a state change (wanted level up).
- Gate: Beshr sees Hermes comment correctly on live gameplay. [RECORD]

## Milestone 2 — Voice (session 2)
- [ ] Phase 3: Push-to-talk mic -> faster-whisper -> Hermes -> Piper TTS, round trip ~1.5s or better.
- Gate: first spoken exchange during gameplay. [RECORD, do not script the reaction]

## Milestone 3 — Overlay (session 3, short)
- [ ] Phase 4: transparent always-on-top chat window over borderless GTA.
- Gate: chat log readable during play.

## Milestone 4 — Actions (session 3/4)
- [ ] Phase 5a: set waypoint by voice.
- [ ] Phase 5b: spawn companion, follows and protects.
- [ ] Phase 5c: heal on command.
- Each action added one at a time, tested individually, logged. Whitelist edited by Claude Code only.
- Gate: full payoff run — chase or firefight with state awareness, voice, and actions live. [RECORD, this is the hook clip]

## Milestone 5 — Nightly agents (v2, only after Milestone 4 gate passes)
- [ ] Connect ONE nightly agent first (Antigravity scheduled task, or Codex, or Jules — pick one, not three).
- [ ] Overnight loop: read PROJECT_STATE.md -> one checklist item -> open PR. No merges, ever.
- [ ] Morning: Claude Code audits PR against review rules, Beshr approves merge.
- [ ] Add second/third agent only if the first one's PRs are consistently mergeable.

## Out of scope until Milestone 5 is stable
- Multiple nightly agents in parallel.
- New action types beyond the initial whitelist.
- Any self-extending agent capability.

## Video checkpoints
[RECORD] tags above mark mandatory capture moments. Passive capture always on: crash logs, PROJECT_STATE.md evolution, commit history.
