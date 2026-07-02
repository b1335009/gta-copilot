# GTA V AI Co-Pilot — Shooting Script

The rule that runs the whole shoot: record everything as it happens. First-reaction moments cannot be recreated. It's cheap to delete footage, impossible to fake the first time the AI talks back or the first crash. When in doubt, roll.

## Setup before you film anything
- OBS with two sources: game capture (GTA in borderless windowed) and a display capture for the Claude Code + Hermes windows.
- Separate audio track for your mic so you can cut narration later.
- Optional webcam reaction cam. Even a small corner cam sells the crash and the first-voice moments.
- Run GTA borderless windowed the whole time so the overlay and OBS behave.

## The structure (film out of order, assemble in order)
Film the hook last. You cannot open on the payoff until the payoff exists.

### 1. Cold open / hook (film LAST, place FIRST)
The payoff shot. AI reacting live during a police chase, calling out your wanted level, you talking back, it sets a waypoint or spawns backup. 15 to 30 seconds, no talking over it, let it breathe. This is the thumbnail moment.

### 2. The premise (film after Phase 0)
You on camera or voiceover: what you're building and the twist. Two AIs building it together. One writes, one reviews and coordinates. Nobody's shown this workflow. Say the offline part out loud, it's a real differentiator.

### 3. Setup montage (film during install)
Screen record installing Script Hook V, SHVDN3, and pulling the reference repos. Speed it up in the edit. Show the hello-world mod drawing your health on screen for the first time. That first number updating live is your first small win, hold on it.

### 4. The two-agent reveal (film during Phase 1)
The differentiator. Split screen or picture-in-picture: Claude Code writing the checklist into PROJECT_STATE.md on one side, Hermes reading it and building on the other. Narrate what each one does. This is the part of the video people haven't seen before, give it room.

### 5. First JSON (film the moment, Phase 1 done)
The console printing real game state. Health, wanted level, position, vehicle. Point at each field on screen. It looks boring but it's the proof the whole thing is real and not fake, so say that plainly.

### 6. THE CRASH (film your reaction, do not skip)
The main-thread native crash is coming. When GTA hard-crashes because a native fired off the wrong thread, keep rolling. Film the crash, your face, the log, then Claude Code catching it on review and explaining why. This is the best beat in the video. The drama is real and the lesson is real. Do not edit it out to look competent. It's more watchable than a clean run.

### 7. First words (film raw, Phase 3)
The first time it answers you by voice. Do not script your reaction. Push to talk, ask it something about what's happening on screen, let your real response happen. If it's funny or it flubs, keep it.

### 8. Actions (film gameplay, Phase 5)
Capture each action working: waypoint set by voice, companion spawned and following, heal on command. Clean gameplay capture, callouts over the top.

### 9. Payoff run (film the full loop)
A real chase or firefight with the full stack running. State awareness, voice, and actions all live at once. This is where you pull the hook clip from.

### 10. Outro (film last)
What it took, what broke, what's next. Honest numbers. Latency, hardware, hours. Tease the next build if there is one.

## What to capture passively the whole time
- Every crash log and error, even the ones you fix in a minute.
- The PROJECT_STATE.md file evolving. Time-lapse of the checklist filling in is a clean visual.
- Your commit history. Screen-record a scroll through it at the end.

## Editing note
The three moments that carry the video: the two-agent reveal, the crash and fix, and the first-voice reaction. If you protect those three in the shoot, the rest is filler you can trim freely.
