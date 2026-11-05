# Game states (`game_state`, `$072C`)

`DispatchGameState` (bank 4) jumps through `GameStateHandlers` (`$ADE1`, **28 entries**, `$00`-`$1B`; 24 distinct handlers named `GameStateNN`
with a one-line comment in `src/bank4.s`). `game_state` is separate from `player_state`: it drives screens and sequences around the level.

Verified in the emulator (`[v]`):
- `$00` normal play (the handler is a no-op; during a stage the value never changes).
- Level completion: `$08` (just after the move to area 4) -> `$09` (set-up: camera mode 1, timers; waits until `player_state` leaves `$09`) -> `$0D` (bonus ascent)
  -> `$0A` (bonus tally: appends rows of text from `$B074` to the PPU buffer at a steady pace) -> `$0B` (second tally phase; score and the extra life are added).
Read from the code: `$12` is the game-over state set after the "YOUR QUEST IS OVER" text; `$01` starts a sequence (it checks `powerup_shot`) and `$02`-`$06`, `$0C`
are intro/transition sequences that were not triggered in the runs; several states (`$06`/`$07`/`$08`) share handlers or jump to bank 6 through `FarCall`.
`camera_mode` (`$01A6`) is set by these states (`GameState0C` sets 3, `GameState09` sets 1).

## Initial `game_state` per area (area header byte 10)
Most areas start in `$00`. The special areas start in a sequence state. All of the arrivals below were verified by loading each area through the door loader
in the emulator (writing the destination into RAM and jumping to `F_F040`); the "looks like" column is the rendered picture, not behaviour.

| Area | Initial state | Verified progression | What the handler does (code) | Looks like |
|------|---------------|----------------------|------------------------------|------------|
| 2 | `$0F` | stays `$0F` | sets facing/timers and `collected_flags`; waits until the camera reaches `focus_x` = `$C0`, then `$10` | underwater cave (olive blocks, blue water, a star) |
| 4 | `$08` | `$08` -> `$09` -> `$0D` | the bonus ascent | night sky |
| 5 | `$01` | `$01` -> `$02` after about 47 frames | checks `powerup_shot` and continues to `$02`-`$05` | the same underwater cave as area 2 |
| 6 | `$0E` | stays `$0E` | calls bank 3 `$BF05` through `FarCall` | purple tiled wall |
| 10 | `$1A` | stays `$1A` | calls bank 6 `$BD5E` through `FarCall` | a workshop with shelves and hanging lamps |
| 14 | `$19` | `$19` -> `$00` after about 58 frames | sets bit 3 of `$0101` (a persistent flag) and returns to `$00` | a dark cave |
| 20 | `$17` | stays `$17`; the player starts in water (state `$0D`, water level 108) | blinks frame `$1C`/`$1D` with `zp_48` | the toy-block level with a clock face |
| 22 | `$1B` | stays `$1B` | calls bank 6 `$BD99` through `FarCall` | green factory with a "MONSTER MASHER" machine |
| 23 | `$18` | stays `$18`; the player starts in water (water level 156) | blinks frame `$20`/`$21` like `$17` | wide green factory section |

The set-up states `$01`-`$07` and `$0C` write their own timers (`ram_0735`-`ram_073E`) and `camera_mode`; `GameState06` falls into `GameState0C`
(`camera_mode` 3, then a bank 4 routine at `$B515`).

## Boss encounters (`game_state` `$06` -> `$0C`, verified)
These are the three boss encounters (the "story" scenes): a dialogue, then a fight with a health bar. Forcing `game_state` = `$06` in stage 1 and setting `stage_index`
(`zp_93`) in the emulator: `GameState06` clears `story_step` and moves to `$0C`, which runs `StateDispatch_0735` (nine bank 4 routines indexed by `story_step`).
Step 0 (`StoryBranchByStage`) reads a 5-byte table at `$B7B4` indexed by `stage_index`: `00 01 00 02 03`. A zero entry skips the encounter (`player_state` 9,
`game_state` 9: the level-complete chain); stages 1, 3 and 4 start `StartStoryScene` with `story_scene` = 1, 2 or 3 (boss 1-3), which plays song 6, hides the sprites and loads
the scene's 8-byte record from `$B7B1 + scene*8` (script pointer in `story_script_ptr`, text pointer in `credits_ptr`, three parameters).

Observed in stage 1 (frame numbers from forcing the state): step 1 at frame 2, step 2 at 361, step 3 at 363, `ram_01BE` (text step) 1 at 683 and 2 at 697, step 4 at 1363, steps 5 and 7 at 1475/1476.
| Step | Routine | What it does |
|------|---------|--------------|
| 0 | `StoryBranchByStage` | skip or start the encounter |
| 1 | `BossIntroScript` | steps through the sprite script: (delay, pointer to a sprite definition) entries each spawn a type `$3A` entity; a zero delay ends it |
| 2 | `BossSpawnSpeakers` | spawns the two speaker entities (types `$3B`, `$3C`), then step 3 |
| 3 | `BossDialogueType` | the text typing (`StepDispatch_01BE`); the speaker's mouth (`ent_param_9`) toggles while typing; when done plays sfx `$29` and a burst, then step 4 |
| 4 | `BossDialoguePause` | holds the pose for `ram_01B7` frames, then draws the rest of the queued text block; then step 5 |
| 5 | `BossFightStart` | gives the two combatants their entity types, sets `boss_health` = `$63`, goes to step 7 |
| 6 | `BossDialogueDelay` | counts `story_timer` down and returns to step 2 (next page of dialogue) |
| 7 | `BossFightHealthBar` | draws the 10-tile health bar at PPU `$274B` from `boss_health` while the fight runs |
| 8 | `BossDefeated` | after the boss: boss 3 fades out and enters stage 5 setup, otherwise the level-complete chain |
Steps 6 and 8 were not reached in the forced run; their description is from the code. The dialogue text is the boss speech listed in the README.

### The fight itself (boss 1, verified)
Forced as above, then with `powerup_shot` set and the player firing B (boss 1 at x `$78`, then tracking the player, invulnerable so the touch damage did not interfere):
- Only **player shots** damage the boss: `Ent_CheckPlayerOverlap` returns the shot's hit value in `tmp_a`; when it is 1 `Ent3D_Update` calls `DamageBoss` with `boss_hit_damage` (3 for boss 1, in the run `boss_health` went `$63` -> `$60` -> `$5D` ... one hit per shot that landed).
  `DamageBoss` clamps at 0 (`$04` -> `$01` -> `$00` with 3 per hit).
- At `boss_health` 0 the boss entities change type: `$3D` -> `$41` -> `$44` and `$3E` -> `$42` -> `$43` -> `$45` -> `$46`; the effect list of type `$47` fires, `$44` rises and disappears (it stops at y `$345`; for boss 3 y `$3A9`
  with a different effect list).
- A prize entity then appears: type `$47` at x `$78` rises/falls to y `$3DE` and becomes type `$48` (`Ent47_Update` -> `Ent48_Update`). Touching `$48` plays sfx `$19`, sets `story_step` 8 and `story_timer` `$28` (the player had to be placed by hand
  next to it in the run: its y is about 130 px above the ground).
- Step 8 (`BossDefeated`) then ended the encounter: `player_state` `$17`, `game_state` `$0D` (the bonus ascent) for boss 1; boss 3 goes to stage 5 setup instead (code-read).

### Bosses 2 and 3 (verified with the same method)
- **Boss 2** (`stage_index` 3, `story_scene` 2): body type `$3D` (slot 9), second part type `$98` (slot 8); the dialogue ran about 1,400 frames. The body bobs vertically around the player's x, so right-facing shots only hit when its y
  is near the player's. With the player placed beside it and firing every other frame, `boss_health` fell by 3 on about every second frame (`$63` -> 0 in about 120 frames); the defeat chain was the same as boss 1 (`$98` -> `$42` -> `$43` -> `$45` -> `$46`,
  `$3D` -> `$41` -> `$44`), then the prize (`$47` -> `$48`) and step 8 led to the bonus ascent (`player_state` `$18`, `game_state` `$0A`/`$0B`).
- **Boss 3** (`stage_index` 4, `story_scene` 3): body `$3D` (slot 9), head cycling `$87`/`$88`/`$89` (slot 8), an extra entity `$8F` appearing in slot 10 now and then. Each landed shot did 2 damage (`$63` -> `$61` -> `$5F`), but only two shots landed in 4,500 frames
  even with the player placed beside the body: the body jumps between fixed x positions (`$1A`, `$3A`, `$5A`, `$78`, `$91`, `$98`, `$B8`) and both hits came with the head at `$88` and the body at x `$91`, 1,000 frames apart.
  The code has `Ent8A_Update` adding 2 to `boss_health` (capped at `$64`) and `Ent8B_Update` calling `DamageBoss` with 10, but entities `$8A`/`$8B` never appeared in the run, so neither was observed. Boss 3 was not defeated in the emulator,
  so its defeat sequence and the stage 5 setup are code-read only.

### Boss 3's second phase and ending (verified by forcing `boss_health` to 0 at the start of the fight)
Shooting did not defeat boss 3 in the emulator (3-4 landed shots in about 5,600 frames at several firing heights), so `boss_health` was set to 0 directly at step 7:
- Phase 1 ends as for the other bosses: body `$3D` -> `$41` -> `$44` -> gone, head `$87` -> `$42` -> `$43` -> `$45`.
- Then the head becomes **`$8A`**, which raises `boss_health` by 2 per step (it reached 2: the heal in `Ent8A_Update`), and after about 65 frames it becomes **`$8B`**, the second, hittable form. A player shot overlapping `$8B` called `DamageBoss`
  with 10 (health back to 0), after which the head went `$8C` -> `$8D` -> `$8E` -> gone (frames 2896-3155 of the run).
- The same prize (`$47` -> `$48` at x `$78`, y `$3DE`; it landed in entity slot 42 this time) then appeared. Touching it started step 8 (`story_timer` `$28` counting down in steps of 2 frames),
  after which `story_scene` was cleared, `player_state` became `$09` (start of a life) and `game_state` `$0E`, the arrival state of area 6 listed in the table above, with the player dropping in (`$0E` -> `$02` -> `$04` -> `$00`).
  So boss 3 leads into the stage 5 setup (`stage_index` 5, code-read) rather than the bonus ascent.

### Stage-clear tally (`$0A` -> `$0B`, verified by forcing `game_state` = `$0A`)
`GameState0A` types the "STAGE CLEAR" text one row per `clear_text_ticks` countdown (5 ticks; `clear_text_row` 1..`$0E`) and then sets `game_state` `$0B` (frame 644 of the forced run).
`GameState0B` runs `tally_step` through a 10-entry word table; in the run it went 0, 1, 2, 3, 6, 7, 9 (step 3 jumped to 6 because the second tally was already `$3C`):
0 starts (spawns a pickup if `tally` < `$96`, sfx `$28`, popup), 1 counts `tally` up to `$0257` at 10 score per step, 2/5 are timed pauses (`state_delay`/`state_delay_outer`, blinking via the table at `$B0C4`),
3/4 count the second tally (`tally_small`) up to `$3C` at 50 score per step, 6-9 draw the final messages and hand over to `GameState0D`/the next stage (steps 7-9 read from the code and the table `GameState0B_Sequence`).

### Area 5 power-up scene (`$01`-`$05`, verified by loading area 5 through the door loader)
- `$01` (`GameState01`, frame 10): with `powerup_shot` = 0 it moves on to `$02` (frame 57, after the drop-in); with `powerup_shot` already set it goes straight to `$03` (a no-op) and sets `collected_flags` to 7 [both checked].
- `$02` (`GameState02`): `EnableCameraAtX`, then animates the orb with `orb_anim_frame` (0..`$3F`, `GameState02_FrameTable`, `ppu_job` `$11`+) until `orb_tile_taken` (`zp_A6`, set when the player touches tile `$D6`) is non-zero.
  In the run (I set `zp_A6` by hand at frame 150) it spawned a type `$04` item at x `$120`, y `$D0` (via `AwardPickup` kind 8) and went to `$05` at frame 151.
- `$05` (`GameState05`): types the dissolve one row per tick (`clear_text_row` 1 -> `$1F`, `ppu_job` `$14`/`$15`; frame 151 -> 459), then spawns a type `$0B` item at x `$76`, y `$9C` and sets `game_state` `$03`.
- The items spawned in that forced run were removed again after one frame (their fixed spawn position was apparently off-screen for the forced camera), so `$04` -> `$0B` -> `$0C` -> `$0D` (the hopping power-up, `ItemHopArc`; `Ent0D_Update` sets `powerup_shot` = 1, plays sfx `$19`, spawns a type `$04` entity and sets `game_state` `$04`) was not run in the emulator. `GameState04` (queue the text packets at `$AFB3` ("ALFRED ... HELP YOU:") and go to `$03`) is therefore code-read. `$07` is not reached from area 5 and remains code-read.
