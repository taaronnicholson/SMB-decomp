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

## Story scenes (`game_state` `$06` -> `$0C`, verified)
Forcing `game_state` = `$06` in stage 1 and setting `stage_index` (`zp_93`) in the emulator: `GameState06` clears `story_step` and moves to `$0C`, which runs `StateDispatch_0735`
(nine bank 4 routines indexed by `story_step`). Step 0 (`StoryBranchByStage`) reads a 5-byte table at `$B7B4` indexed by `stage_index`: `00 01 00 02 03`.
A zero entry skips the story (`player_state` 9, `game_state` 9: the level-complete chain); stages 1, 3 and 4 start `StartStoryScene` with `story_scene` = 1, 2 or 3,
which plays song 6, hides the sprites, loads the scene's 8-byte record from `$B7B1 + scene*8` (script pointer into `story_script_ptr`, a text pointer into `credits_ptr`, three parameters) and
steps through the script: each entry is (delay, pointer to a sprite definition) and spawns an entity of type `$3A` per sprite. Stage 1's script ran for the 900 frames watched.
