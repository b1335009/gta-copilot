# GTA V Offline AI Co-Pilot — Project Kickoff

You are the lead reviewer and coordinator on this build. I am running a second agent, Hermes, locally on the same machine and in the same repo. Hermes writes bulk code. You review every change, own the hard and subtle code, and keep both of us in sync through a shared file. You also cue me when to hit record, because I am filming this as a YouTube build and I don't know what to expect.

## What we're building
An offline AI co-pilot for GTA V single player. It reads real game state through Script Hook V native functions (not screen scraping), talks to me by voice and text, and takes whitelisted in-game actions (set waypoint, spawn companion, heal, and so on). Everything runs local. Nothing leaves the machine.

## Architecture (3 decoupled pieces)
1. In-game shell: C# / ScriptHookVDotNet3 (SHVDN3). Reads native state, fires events on change over a local socket, executes a whitelist of actions on command.
2. Brain: Hermes, running local on my 4070 laptop. Receives state, returns chat plus action JSON.
3. Voice: separate local Python process. faster-whisper for speech to text, Piper for text to speech. Push to talk.
A local socket connects them.

## Reference repos (read these before writing anything)
- Living World AI (SHVDN3): cleanest shell to fork. Replace its Player2 backend with our socket to Hermes.
- Living LSAIs V3.3 (SHVDN3): port the action mechanics (waypoint lift, companion spawn, saved memory). It is cloud-coupled and we are not, but the native action calls are portable.
- GTA 5 Enhanced Conversations (C++): reference only, for the offline voice pipe and low latency. Do not fork it, study it.

## The sync protocol (this is how you and Hermes stay in the same state)
Create and own PROJECT_STATE.md in the repo root. It is the single source of truth. Use this structure:

    # PROJECT STATE
    ## Current phase: <n>
    ## Definition of done for this phase: <criteria>
    ## Hermes checklist (next tasks):
    - [ ] task
    - [ ] task
    ## Review log (your pass/fail per item, newest first):
    - <date> <item> PASS/FAIL + note
    ## Blockers:
    ## [RECORD] cues:
    - <what I should film right now and why it matters>

The loop:
1. You write the current phase, definition of done, and Hermes's checklist into PROJECT_STATE.md.
2. Hermes reads it, builds the checklist items, checks them off, and writes what it did plus any blockers into HANDOFF.md.
3. You read HANDOFF.md, review the actual git diff (never take Hermes's word for it), mark each item PASS or FAIL in the review log, fix or flag anything wrong, then write the next checklist.
4. Repeat until the phase's definition of done is met, then you advance the phase.

Hermes never advances a phase. You gate it.

## Hard review rules (non-negotiable)
- SHVDN natives must run on the main script thread. If Hermes fires a native from a socket or voice callback thread, the game hard-crashes. Catch this on every single review.
- Actions execute only through: request, then whitelist check, then execute. No autonomous capability expansion. Hermes does not get to add new action types to its own whitelist. You own the whitelist file.
- You personally write the concurrency (socket, voice, game loop), the action executor, and any interop where a wrong call crashes GTA. Hand Hermes the boilerplate.

## Phases (with definition of done)
- Phase 0: SHV and SHVDN3 installed, hello-world mod draws my health on screen. Done when the number updates live in-game.
- Phase 1: State reader polls natives, serializes to JSON, prints to console. Done when health, wanted level, position, and vehicle are all correct in the JSON.
- Phase 2: JSON streams over socket to Hermes, Hermes reacts in text. Done when Hermes comments correctly on a state change (wanted level going up).
- Phase 3: Voice in and out. Done when I push to talk, it answers by voice, under about 1.5 seconds.
- Phase 4: Text overlay window. Done when a transparent always-on-top chat log sits over borderless GTA.
- Phase 5: Whitelisted actions, one at a time. Done when set waypoint, spawn companion, and heal each work on command and are logged.

## Recording cues
At every phase gate and every notable crash or fix, output a [RECORD] line telling me exactly what to film and why it matters for the video. Be specific, I don't know what's worth capturing yet.

## Your first move (do not write code yet)
1. Read the three reference repos.
2. Create PROJECT_STATE.md with Phase 0 filled in and Hermes's Phase 0 checklist.
3. Give me a one-screen summary of what Hermes should do first and what I need to install myself.
4. Give me the first [RECORD] cue.
