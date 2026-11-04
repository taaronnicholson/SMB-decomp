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
| `$00` → `$05` → `$06` → `$07` → `$00` [v] | peck (Down): `$05` inspects the tile at the beak (pecking in state `$07` also pops balloons [v]), `$06` swings, `$07` = hit a solid tile |
| `$0F` → `$10` → `$11`..`$15` → `$0E` → `$02` → `$04` → `$00` [v] | hurt: death animation (~21 ticks), dead (~100 ticks, `lives--`), a ~150-frame respawn arc in bank 1 that returns to the spawn point, then a drop |
| `$1A` → `$1B` → `$11` [v] | knocked-out death (`HurtPlayerKnockout`, e.g. type `$30`), then the same respawn |
| `$09` → `$0E` → `$02` → `$04` → `$00` [v] | start of a life: drops in and lands |
| `$16` → `$17` → `$18` → `$19` [v] | level complete: balloon ride up, bonus ascent in area 4, tally, walk off |

**Level completion in detail** [v]: pecking the last balloon (`balloons_left` reaches 0) sets `$16`; the player follows the popped balloon (type `$02`, `ride_balloon_slot`)
upward; at the top of the area `ride_timer` counts to `$30`, the player is moved to area 4 (Y `$03CD`, X `$78`) and `game_state` goes `$08` → `$09` → `$0D`.
`$17` is the **bonus ascent**: a night-sky area with stars and "50" score popups through which the player rises steadily (the score grew by 50 about every 200 frames);
at the top `$18` (`game_state` `$0A`/`$0B`) tallies the bonus (6120 points in the test and `lives` went 2 → 3, i.e. an extra life), `$19` walks to a "NEXT" sign and the next stage starts.
The exit walk (`ExitWalkStep`, table `ExitWalkAnim`) ends in `AdvanceStage`: fade out, `INC stage_index`, `JMP StageSetup` [code-read; the stage restart seen in the run was the emulator hook forcing stage 0]. `BonusAscentEndAnim` (bank 1 `$B272`) animates the end of the ascent.
(The emulator hook that forced stage 0 each load restarted stage 0 afterwards; the real game advances `stage_index`.)

**Dive attack** [v]: pressing Down while in the air sets `dive_mode` (`zp_7C`) to 4; landing then enters `$03` instead of `$04`. If the fall lasted at least `$8C` ticks (`fall_ticks`, `zp_85`)
the landing also sets `camera_mode` 5 (screen shake) and calls `ShockwaveKillEnemies`, which turns every entity whose type is flagged in `KillableTypeTable` (bank 6 `$A21E`) into `$5D` and removes it
(tested by holding `zp_85` at `$A0`: all five `$4E` creatures in area 0 vanished). `$5E` is also vulnerable to a diving player.

**Other states:** `$0D` in water (`water_level`, splash sfx `$22`, Up leaves it); `$03` is the **dive landing** [v] (a 17-tick state back to `$00`, bank 2 `$B53A`); `$0A` returns to `$00` immediately;
`$08` is the **spring bounce** [v]: landing on a spring tile (tile `$D2`; in area 0's map it is the coil at the bottom-left) enters `$08` automatically (sfx `$27` on pulse 1); it rises 19 ticks at 3 px per tick
(`zp_8F`/`zp_8B`) and then continues as `$01`/`$02`, so the player bounces repeatedly, higher (peak Y `$3FD`) than a normal jump (`$40C`). Jumping with A while `touch_kind` (`zp_57`) is 1 or 4 also starts `$08` (a boosted jump).
`touch_kind` is set every frame from the tile at the player's position (`F_F3B5`: tiles below `$B4` give 0, others are mapped through `TileKindTable`, `$C1EF`: kind 4 = tile `$CD`, kind 1 = `$D2`-`$D5`, kind 3 = `$DB`, a collectible).
Jump height depends on how long A is held [v]: a 30-frame hold peaked at Y `$40C` and 4-frame taps at `$433`.
`$1C`-`$1E` are scripted cutscene states in bank 5 (`$BC47`: walk right until X = `$0140` then hold a pose; `$BC70`: stand still; `$BC75`: a hop along a Y-offset table with sfx `$29` and an effect burst), entered from boss/ending code (bank 5, around `STA player_state` with `$1D`/`$1E`); read from the code, not triggered; `$0C` and `$1B`
alone have no observable effect without their set-up variables.

**Death animation** (`DeathAnimFrame`, `F_F57A`, used by states `$0F`/`$10` with `death_timer` 0-98): the figure is drawn as six sprites in OAM entries 15-20.
`DeathAnimTiles` (bank 3 `$8000`, 49 steps of 3 bytes) packs two sprites per byte (tile index and flip bits, tile = `$F9 + 2*index`), and `DeathAnimPath`
(`$8093`, 100 steps of 6 bytes) gives their positions; the routine copies a 12-byte window (`$8093 + 6*(death_timer+1)`) so the six sprites trail one another.

**Hurt:** `HurtPlayer` does nothing while `hurt_flag` (`$C0`) or the invulnerability counter (`invuln_lo/hi`) is set, only hits in states `$00`-`$0D` (table `F_F4D5`), plays noise sfx `$06`, sets `player_state` = `$0F` and `hurt_flag` = `$0F`. It is called by hazards (tile class 3), by entity touch handlers (`Ent_HurtOnTouch`) and by some states; `HurtPlayerKnockout` (`$1A`) is the heavier variant.
**Vulnerable enemies** (`$5E`) die when the player touches them in state `$02` with `zp_7C` set.

## Player sprite assembly (`DrawPlayer`, bank 6 `$A4E1`)
`PlayerToScreen` converts the player position to screen coordinates (`player_box_x/y`). `DrawPlayer` then maps `player_draw_frame` through `PlayerFrameShape` (80 bytes, bank 6 `$A653`)
to one of 11 **shapes**; `PlayerShapeRecordLo/Hi` point to 3-byte `PlayerShapeRecords` (offset-list pointer, sprite count), and each list holds signed `(dy, dx)` offsets that are added
to the screen position to fill OAM entries 15 and up (`$023C`...). Facing left (`zp_67`) mirrors X (`8 - dx`) and sets the horizontal-flip attribute, and `zp_4F` mirrors Y. The shapes are mostly
2x2 or 2x3 metasprites; shape 6 points at RAM `$0398`, the six trailing positions written by `DeathAnimFrame`. This loop does not write the tile-number bytes (OAM byte 1); where they are set has not been traced.
