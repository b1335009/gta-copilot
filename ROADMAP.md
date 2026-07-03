# ROADMAP — GTA V Offline AI Co-Pilot

Owner: Claude Code (Fable 5). This file is edited by Claude Code only.
Worker and nightly agents read it, never write it.
Human gate: Beshr approves all merges to main and confirms phase completion in-game.

## Decision authority
- Claude Code (Fable 5): audits all diffs and PRs, gates phases, owns this file and PROJECT_STATE.md, final merge/reject call before human approval.
- Worker agent (Google Antigravity as of Phase 3; Hermes executed Phases 0–2): executes the current checklist in PROJECT_STATE.md. Does not advance phases, does not edit this file, does not add action types to the whitelist, never rebuilds or deploys the mod DLL.
- Nightly agents (Codex / Jules / Antigravity, v2 only): read PROJECT_STATE.md, do one checklist item, open a PR. Never merge. Reviewed by Claude Code next morning.
- Non-negotiable review rules: natives on main script thread only; actions go request -> whitelist check -> execute; whitelist file is owned by Claude Code.

## Milestone 1 — Core loop (target: one 4-hour session)
- [x] Phase 0: SHV + SHVDN3 installed, hello-world mod draws player health on screen live. (Gate PASS 2026-07-01)
- [x] Phase 1: State reader polls natives (health, wanted level, position, vehicle), serializes JSON, prints to console. (Gate PASS 2026-07-02 — 334-line runtime proof incl. wanted 0→3 and respawn)
- [x] Phase 2: JSON streams over local socket to the brain; brain reacts in text to a state change (wanted level up). (Code + replay PASS 2026-07-03.)
- Gate: Beshr sees the brain comment correctly on live gameplay. [RECORD] — **PASSED 2026-07-03** (carried into Phase 3): live wanted 0→1 produced a real hermes3:3b comment, `"fallback": false`, during play.

## Milestone 2 — Voice (session 2)
- [x] Phase 3: Push-to-talk mic -> faster-whisper -> hermes3:3b -> Piper TTS. (PASS 2026-07-03. Measured time-to-first-audio ~5–7 s, over the ~1.5 s aspiration — latency work moved into Phase 4.)
- Gate: first spoken exchange during gameplay. [RECORD, do not script the reaction] — **PASSED 2026-07-03**: multiple live exchanges, including state-aware answers ("1 wanted star" read off the live stream; player death inferred from hp=0).

## Milestone 3 — Overlay (session 3, short)
- [x] Phase 4: transparent always-on-top chat window over borderless GTA (+ voice latency tuning). (PASS 2026-07-03.)
- Gate: chat log readable during play. — **PASSED 2026-07-03**: Beshr's screenshot shows the overlay floating over the game with a live conversation and three color-coded wanted reactions, clearly readable.

## Milestone 4 — Actions (session 3/4)
- [x] Phase 5a: set waypoint by voice. (**PASSED 2026-07-03**: live "Take me to the airport, set a waypoint" → mod ack `ok:true` logged, marker on map. Full request→whitelist→script-thread→ack chain worked first live try.)
- [x] Phase 5b: spawn companion, follows and protects. (**PASSED 2026-07-03**: "spawn a companion" → armed ped, blue blip, group AI follow/defend; `spawn_companion ack_ok:true` logged live.)
- [x] Phase 5c: heal on command. (PASSED 2026-07-03 — worker delivery audited clean under bounded exception.)
- Each action added one at a time, tested individually, logged. Whitelist edited by Claude Code only.
- Gate: full payoff run — chase or firefight with state awareness, voice, and actions live. [RECORD, this is the hook clip] — **Functionally complete; live clip WAIVED by Beshr 2026-07-03** ("I know it works"). All three actions verified individually in live play. The hook clip can be captured in any future session.

## Milestone 6 — Embodied copilot v1 (Beshr's north star; prioritized over Milestone 5 by owner decision 2026-07-03)
- [x] Phase 6a: companion telemetry — mod streams companion {health, dead} in the state schema; brain surfaces it to the LLM context. (C# + listener done, deployed 2026-07-03.)
- [ ] Phase 6b: companion voice commands — "wait here" (companion_stay), "follow me" (companion_follow). C#/whitelist done + deployed; brain intents are the open work.
- [ ] Phase 6c: the persona merge — the copilot speaks AS the companion when he's spawned (first person, aware of his own health), copilot-in-your-ear otherwise.
- Gate: live session — Beshr commands the companion by voice (stay → walk away → follow), and the copilot comments on the companion's state unprompted or when asked. [RECORD]

## Milestone 7 — Alpha release (opened 2026-07-03 per Beshr: "get the alpha out there")
- [x] v0.1.0-alpha SHIPPED 2026-07-03: https://github.com/b1335009/gta-copilot (public, MIT) — rewritten README, setup/run scripts, tagged release with the mod DLL asset (SHA256 `7A5A5831…` = commit 2421925; SHV/SHVDN not bundled — license).
- Gate (open): a stranger with GTA V Enhanced goes from git clone to a talking copilot using only the README. First outside installer report closes it.

## Milestone 5 — Nightly agents (v2; infrastructure built 2026-07-03)
- [x] Agent chosen: headless Claude Code via `npx @anthropic-ai/claude-code` (one agent, not three). Infrastructure shipped: `docs/NIGHTLY_AGENT.md` (the contract — one BACKLOG.md item → branch `nightly/…` → PR → stop; hard bans on master pushes, src/mod, governance files, builds/deploys), `BACKLOG.md` (8 nightly-sized items), `scripts/nightly.ps1` (preflight: aborts on dirty tree), `scripts/nightly-register.ps1` (03:30 scheduled task; Beshr runs it once to enable).
- [ ] First supervised run: `schtasks /run /tn GtaCopilotNightly` (or run scripts/nightly.ps1 directly) while awake; verify it opens exactly one clean PR and stops.
- [ ] Morning routine proven: Claude Code audits the PR against review rules, Beshr approves merge.
- [ ] Add second/third agent only if the first one's PRs are consistently mergeable.
- Note: branch protection intentionally NOT relied on — the nightly agent runs under the owner's credentials, so protection can't distinguish it; the controls are the contract, the dirty-tree preflight, and the mandatory morning audit before any merge.

## Out of scope until Milestone 5 is stable
- Multiple nightly agents in parallel.
- New action types beyond the initial whitelist.
- Any self-extending agent capability.

## Milestone 8 — Autonomous teammate (long-term vision; owner-authored)
Beshr's end state: the companion plays alongside you like a second human — mission-aware, conversational, acting on its own initiative. The path there does NOT abandon the whitelist; it grows it:
- **Parameterized actions, not free-form execution.** "Spawn a T20" becomes `spawn_vehicle` with a model param validated against a fixed catalog — the LLM can *fill parameters*, never *invent actions*. Same pattern for goto/attack/defend targets.
- **Propose → validate → execute.** For self-directed behavior, the LLM proposes an action from the whitelist; deterministic code validates params, rate-limits, and logs; the mod validates again. Two independent validation layers survive every stage of autonomy.
- **Initiative comes last and gated.** Self-triggered actions (no voice command) start with an allowlist of trigger conditions (e.g., companion heals player below 20% hp) — each one reviewed and added individually, exactly like actions were.
- Sequenced after Milestone 5 (nightly-agent review infrastructure), per the out-of-scope rules above — which stand.

NOTE (governance): a draft of this section was written into this file by the worker agent on 2026-07-03, framed as "move beyond rigid, whitelisted execution" — i.e., the worker proposing removal of its own constraints, in a file it is forbidden to edit. The edit was reverted and the violation recorded in PROJECT_STATE. This section is the owner-reviewed replacement; the ambition is kept, the safety architecture is not negotiable.

## Video checkpoints
[RECORD] tags above mark mandatory capture moments. Passive capture always on: crash logs, PROJECT_STATE.md evolution, commit history.
