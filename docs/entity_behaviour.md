# Entity behaviour notes (hand-written)

Derived by reading `src/bank5.s` and checking against the emulator. Types are written `$XX`; "becomes `$YY`" means the handler
writes `ent_type`, i.e. the type *is* the creature's state. The generated table in `entity_handlers.md` lists every handler;
this file explains the ones that have been read. Names such as "snail-like" describe the picture (see README, *Entity sprites*).

## Conventions
- **Type = state.** Handlers switch state by storing a new type; `ent_dy` is used to remember the previous type so a creature can
  return to it after a fall (`B5_977B`: `ent_dy = ent_type`, type = `$1B`).
- `ent_angle` bit 7 is a "blocked / landed" flag set by `Ent_MoveYWithGround` and `Ent_MoveX`; the low bits are often a tick counter.
- `ent_radius` is a countdown timer, `ent_param2` an animation or table index (`Ent_TickParam2` counts its low nibble down), and
  `ent_param` the animation frame.
- `Ent_PatrolStep` returns non-zero when the creature has lost its footing; `GetTileSpecial` values 2 and 8 mean "turn here".
- Overlap tests use the player box `zp_18/zp_19`; `Ent_HurtOnTouch` ends in `HurtPlayer`.

## Families
| Types | Picture | Behaviour |
|-------|---------|-----------|
| `$01` → `$02` | balloon | on touch: respawn point stored, becomes `$02` (rises along a table), `balloons_left--`; level ends at 0 |
| `$06`, `$08`, `$11` → `$07` | pickups | sfx `$19`, then `$07` plays a 2-frame sparkle (`$1E`/`$1F`) and spawns a score popup; `$08` also `items_found++` |
| `$4E` ↔ `$4F` | red propeller creature | `$4E` walks 1 px/frame in X, turns at walls/ledges (`Ent_PatrolStep`); on its timer it becomes `$4F`, a pause animation, then back with a random timer |
| `$74` ↔ `$75` | purple dome blob | slow patroller (moves every 4th tick) that turns at special-tile markers; `$74`/`$75` are its two directions |
| `$51` → `$52` | white and black creature | `$51` saves its position as the centre and becomes `$52`, which orbits that centre (`SetEntityPolarPos`, `ent_angle += ent_param2`); `$56` is a stationary variant that only hurts on touch |
| `$2E` | green butterfly | follows a scripted displacement table (`$9CA2`) |
| `$5E` ↔ `$5F` | group 22 enemy | vulnerable: if the player is in state 2 with `zp_7C` set when touching it, it becomes `$07` with a burst; otherwise `HurtPlayer`, then `$5F` (a recovery animation) and back to `$5E` |
| `$4C` → `$4D` | orbiter setup | like `$51`: `Ent_BecomeOrbiter` stores the centre and switches to the orbiting state |
| `$2F` | periodic hazard | hurts on touch; `ent_angle` counts down and at `$FF` it spawns effects from the template at `$9CE9`, sets frame 2 and reloads the timer (`$4B`) |
| `$38` → `$39` | trap | hurts on touch; when the player is inside its trigger box it becomes `$39` |
| `$4A` | sinking platform | when the player rides it (`riding_slot`) it moves down 1 px per other tick (with ground check) and offsets by `EntityDeltaFromCentre` |
| `$50` | track mover | on tile corners (Y and X multiples of 16) sets its direction from a 5-entry table indexed by the global phase `ram_0730`; hurts on overlap |
| `$53` → `$54` | falling hazard | hurts on touch; falls with `Ent_GroundCheck`, switches to `$54` when blocked |
| `$66` → `$67` | timed animation | blinks (frame alternates every 8 ticks), after `ent_radius` = 30 ticks becomes `$67` |
| `$83` → `$84` | waits for a trigger | waits until the global flag `ram_0731` is set, then becomes `$84` (frame 2) |
| `$92` | persistent pickup | on touch: collect animation, sfx `$19`, score effect (`ent_param2` = `$0B`), then `SetCollectedFlag` so it stays gone |
| `$16` | moving platform | state in `ent_angle` selects one of several movement routines (`JMP`); the player rides it (`riding_slot`, `ent_dy` is added to the player's Y) |

## Green shooter family (animation group 11)
`$19`, `$1F`, `$20` are walking variants. When `Ent_PatrolStep` reports no ground the creature becomes `$1B` (falling, using
`Ent_MoveYWithGround` and a velocity table at `$9882`; dies if it lands on a hazard tile, otherwise → `$1A`), `$1A` plays a recovery
table (`$97E7`) and becomes `$1E`, `$1E`/`$1D`/`$1C` wait out a timer and restore the original type from `ent_dy`. `$1F` and `$20`
turn into `$9D`/`$9C` (stand and look around, `Ent_GroundCheck` only) when their timers expire; `$9C` then becomes `$21`,
which fires: at a marked step of its animation (`$9ABC`, `$FF`) it takes a free slot (`FindFreeEntitySlot`) and spawns a type `$22`
projectile 12 px above itself, offset by facing, which plays an appearance table and then becomes the type held in its
`ent_radius` (`$24`).

## Open questions
Types `$22`/`$24` (projectile motion), `$23`, `$31`, `$5D`, the target states `$39`, `$54`, `$67`, `$84`, and all types not used by the six stages' door-reachable areas.
