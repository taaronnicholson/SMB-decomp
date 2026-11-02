# Player notes (hand-written; items marked [verified] were checked by driving the emulator)

**Controls** (`buttons` bits: A `$01`, B `$02`, Select `$04`, Start `$08`, Right `$10`, Left `$20`, Up `$40`, Down `$80`; the emulator tool
uses read order instead: A, B, Select, Start, Up, Down, Left, Right = bits 0-7):
- **A** jumps from the ground [verified: `$00` -> `$01` rising for about 36 frames (Y `$44D` -> `$40C`), then `$02` falling, `$04` landing, back to `$00`].
- **Down** (alone) is the **peck**: `PlayerState00` switches to `$05` when `buttons & $B1 == $80` [verified: `$05` -> `$06` -> `$07`, back to `$00`
  on release]. `$05` looks at the tile in front of the beak (position depends on facing `zp_66`): tiles `$DA`/`$D8` call `F_F79D`/`F_F770`
  (they advance the global phase `ram_0730`), `$D1` plays noise sfx `$39` and breaks/changes it, a solid tile (`tile_props` bit 0) goes to
  `$07` (hit) with noise sfx `$0B`, anything else to `$06` (swing).
- **B** fires the player projectile (`shot_*` arrays, 2 slots, OAM entries 19-20) only when the power-up flag `powerup_shot` (`$DF`) is non-zero, there is
  a free slot and the cooldown `zp_88` is 0 [from the code; B did nothing in the emulator without the power-up].
- **Start** (fresh press, only when the fade has finished) is handled by `CheckPause`.

**States** (`player_state`, `$63`; dispatch table `PlayerStateHandlers`, bank 2 `$B5AA`: 31 entries `$00`-`$1E`; `player_states.md` is the generated table and the
`PlayerStateNN` labels in `src/fixed.s` carry the one-line meaning). Verified chains (forced or driven in the emulator, `[v]`):

| Sequence | Meaning |
|----------|---------|
| `$00` → `$01` → `$02` → `$04` → `$00` [v] | jump (A): rising about 36 frames, falling, landing recovery |
| `$00` → `$05` → `$06` → `$07` → `$00` [v] | peck (Down): `$05` inspects the tile at the beak, `$06` swings, `$07` = hit a solid tile |
| `$0F` → `$10` → `$11`..`$15` → `$0E` → `$02` → `$04` → `$00` [v] | hurt: death animation (~21 ticks), dead (~100 ticks, `lives--`), a ~150-frame respawn arc in bank 1 that returns to the spawn point, then a drop |
| `$1A` → `$1B` → `$11` [v] | knocked-out death (`HurtPlayerKnockout`, e.g. type `$30`), then the same respawn |
| `$09` → `$0E` → `$02` → `$04` → `$00` [v] | start of a life: drops in and lands |
| `$16` → `$17` → `$18` → `$19` [v] | level complete: balloon ride up, bonus ascent in area 4, tally, walk off |

**Level completion in detail** [v]: touching the last balloon (`balloons_left` reaches 0) sets `$16`; the player follows the popped balloon (type `$02`, `ride_balloon_slot`)
upward; at the top of the area `ride_timer` counts to `$30`, the player is moved to area 4 (Y `$03CD`, X `$78`) and `game_state` goes `$08` → `$09` → `$0D`.
`$17` is the **bonus ascent**: a night-sky area with stars and "50" score popups through which the player rises steadily (the score grew by 50 about every 200 frames);
at the top `$18` (`game_state` `$0A`/`$0B`) tallies the bonus (6120 points in the test and `lives` went 2 → 3, i.e. an extra life), `$19` walks to a "NEXT" sign and the next stage starts.
(The emulator hook that forced stage 0 each load restarted stage 0 afterwards; the real game advances `stage_index`.)

**Other states:** `$0D` in water (`water_level`, splash sfx `$22`, Up leaves it); `$03` is a 17-tick state back to `$00` (bank 2 `$B53A`); `$0A` returns to `$00` immediately;
`$08` is an assisted rise (19 ticks at 3 px per tick set up at `F_DD72`, then it continues as `$01`) whose trigger I could not reproduce (pressing A again while falling does
not enter it, so it probably needs a power-up); `$1C`-`$1E` are scripted cutscene states in bank 5 (`$BC47`: walk right until X = `$0140` then hold a pose; `$BC70`: stand still; `$BC75`: a hop along a Y-offset table with sfx `$29` and an effect burst), entered from boss/ending code (bank 5, around `STA player_state` with `$1D`/`$1E`); read from the code, not triggered; `$0C` and `$1B`
alone have no observable effect without their set-up variables.

**Hurt:** `HurtPlayer` does nothing while `hurt_flag` (`$C0`) or the invulnerability counter (`invuln_lo/hi`) is set, only hits in states `$00`-`$0D` (table `F_F4D5`), plays noise sfx `$06`, sets `player_state` = `$0F` and `hurt_flag` = `$0F`. It is called by hazards (tile class 3), by entity touch handlers (`Ent_HurtOnTouch`) and by some states; `HurtPlayerKnockout` (`$1A`) is the heavier variant.
**Vulnerable enemies** (`$5E`) die when the player touches them in state `$02` with `zp_7C` set.
