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
| `$4E` ↔ `$4F` | red propeller creature | `$4E` walks 1 px in X every `((ent_angle >> 3) & 7) + 1` frames [verified: the three samples in area 0 moved every 4, 2 and 3 frames], turns at walls/ledges (`Ent_PatrolStep`); on its timer it becomes `$4F`, a pause animation, then back with a random timer |
| `$74` ↔ `$75` | purple dome blob | slow patroller (moves every 4th tick) that turns at special-tile markers; `$74`/`$75` are its two directions |
| `$51` → `$52` | white and black creature | `$51` saves its position as the centre and becomes `$52`, which orbits that centre (`SetEntityPolarPos`, `ent_angle += ent_param2`; verified: the stage 0 sample circles with a radius of about 33 px for `ent_radius` = `$80`); `$56` is a stationary variant that only hurts on touch |
| `$2E` | green butterfly | follows a scripted displacement table (`$9CA2`) [verified: moves left 1 px per frame while its Y follows the table] |
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

## Weapon pickup and toggle switches
- `$0D` is the **weapon pickup**: on touch it sets `powerup_shot`, plays the collect animation and sfx `$19`, and the player can then fire with B. It rests as `$0D`; `$0B`/`$0C` are the item
  popping out (moves left 1 px per tick along the arc table `$93C6`: `$7F` ends in `$0D`, `$80` switches `$0B` <-> `$0C`).
- The three **toggle switches** (`switch_1/2/3` = `$DC`/`$DD`/`$DE`) are flipped (`EOR #1`, sfx `$16`) when a falling hazard (`$54`) lands on tile `$CE`, `$CF` or `$D0`
  (`ToggleSwitch1/2/3`); `ApplySwitchN` updates the matching tile frame, and the stage loader loads extra tiles when a switch is set.

## Follow-on states and projectiles
| Types | Behaviour |
|-------|-----------|
| `$22` → `$24` → `$23` → 0 | the shooter's projectile: `$22` plays an appearance table then becomes the type stored in its `ent_radius` (`$24`); `$24` rises 1 px per tick (frames `$26`/`$27` alternate) for `ent_param2` = `$78` ticks or until the top of the map and hurts on touch; `$23` plays a 7-step fade and removes the entity |
| `$38` → `$39` → `$3A` | trap: `$39` plays an animation table (`$A1FE`) while hurting on touch, then becomes `$3A`, which removes itself once it is more than `$180` pixels below the camera focus |
| `$53` → `$54` → `$55` → `$53` | bouncing hazard: `$54` falls along a velocity table (`$ADFA`, up to 25 steps); on landing it reads the tile (`$CE`/`$CF`/`$D0` call `ToggleSwitch1/2/3`), plays sfx 0 on pulse 2 and becomes `$55`, which bobs along a table (`$ADAB`) and returns to `$53` |
| `$66` ↔ `$67` | periodic emitter: `$66` counts a timer, `$67` spawns effects (templates `$B0DB`, `$B0E6` by facing) once and returns to `$66` with a random timer |
| `$83` → `$84` → `$85` → `$86` | falling weight: `$83` waits for `switch_flag` (`$0731`, toggled by pecking tile `$DA`), `$84` follows it, `$85` falls 2 px per tick after a timer; landing on tile `$CE`/`$CF`/`$D0` toggles `switch_1/2/3`, then it rests as `$86` |
| `$31` | fuse and explode: sparks every `$40` ticks (template `$9D6F`); when the player enters its trigger box it plays sfx `$43` and runs a countdown table (`$9D9B`), then collect-animation, noise sfx `$05` and an explosion of effects (`$9DD4`) |

**Switch tiles** (pecked by the player in `PlayerState05`): `$D8` steps `switch_phase` (0-4, backwards if facing left) and `$DA` toggles `switch_flag`;
the track movers (`$50`) pick their direction from `switch_phase` and the falling weights (`$83`-`$85`) from `switch_flag`.

## Open questions
Types `$86` and `$5D` (collect animation after a table, `ent_param2` = `$0D`), and every type not used by the six stages' door-reachable areas.
