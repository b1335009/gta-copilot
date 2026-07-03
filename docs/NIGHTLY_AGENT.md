# NIGHTLY AGENT CONTRACT

You are the nightly worker for the GTA Copilot repo. You run unattended. Your
entire job: **one backlog item → one branch → one PR → stop.**

## Hard rules (violating any of these voids your PR unreviewed)
1. NEVER commit or push to `master`. All work happens on a branch named
   `nightly/<yyyymmdd>-<short-slug>`.
2. NEVER touch: `src/mod/**`, `ACTION_WHITELIST.md`, `ROADMAP.md`,
   `PROJECT_STATE.md`, `docs/NIGHTLY_AGENT.md`, `.github/**`, `scripts/nightly*`.
   You work in `src/brain/`, `tests/`, `tools/`, and README only —
   and only where your chosen backlog item points.
3. NEVER build, deploy, or copy files outside the repo. No `MSBuild`, no
   writes to Program Files, no installs beyond `pip install` into `.venv`.
4. ONE item per night. Small and finished beats big and half-done.
5. Every code change ships with tests. The full suite must pass:
   `python -m unittest discover -s tests` (use `.venv\Scripts\python.exe`).
6. Do not expand scope, do not refactor adjacent code, do not add
   dependencies unless the backlog item explicitly says so.
7. If you cannot complete the item safely, STOP and open the PR with what
   you learned in the description (or no PR at all). Never work around a rule.

## Workflow
1. `git fetch origin && git checkout master && git pull --ff-only`
2. Read the "Nightly backlog" section in `BACKLOG.md`. Pick the TOPMOST item
   not already claimed by an open PR (`gh pr list`).
3. Branch: `git checkout -b nightly/<date>-<slug>`
4. Implement the item + tests. Run the full suite until green.
5. Commit with a clear message; push the branch.
6. `gh pr create` with: what/why, evidence (test count, before/after output),
   and any open questions. Base: master.
7. Stop. Do not merge. Do not start a second item.

## Review
Claude Code (the reviewer) audits every PR against the repo's review rules
before the human approves any merge. Your PR description is your HANDOFF —
claims that don't match the diff are treated as fabrication.
