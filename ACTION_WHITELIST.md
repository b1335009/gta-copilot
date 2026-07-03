# ACTION WHITELIST

Owned and edited by Claude Code (Fable 5) ONLY. Hermes and nightly agents may implement handlers for actions listed here, but may never add, remove, or modify entries. Any diff touching this file from any agent other than Claude Code is an automatic FAIL on review.

Every action executes as: request -> whitelist check -> execute on main script thread -> log.

## Approved actions (Milestone 4 initial set):
| id              | description                                  | params                  |
|-----------------|----------------------------------------------|-------------------------|
| set_waypoint    | Set map waypoint to named place or coords    | place_name OR x,y       |
| spawn_companion | Spawn one armed ped, follow + protect player | none                    |
| heal_player     | Restore player health to max                 | none                    |

## Approved actions (Milestone 6 — embodied copilot, added by Claude Code 2026-07-03 per Beshr's re-scope):
| id               | description                                        | params |
|------------------|----------------------------------------------------|--------|
| companion_stay   | Companion leaves group, holds current position     | none   |
| companion_follow | Companion rejoins player group (follow + defend)   | none   |

## Explicitly not approved (do not implement):
- Anything modifying this file programmatically
- Anything spawning more than one entity per call
- Wanted level manipulation (revisit after Milestone 4)
- Weather/time control (revisit after Milestone 4)
