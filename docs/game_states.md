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
Most areas start in `$00`. The special areas start in a sequence state:

| Area | Stage(s) | Initial state | What the handler does (read from the code; none of these was triggered in the emulator) |
|------|----------|---------------|------------------------------------------------------------------------------------------|
| 2 | 0 | `$0F` | sets facing/timers and `collected_flags`, then waits until the camera has scrolled to `focus_x` = `$C0` and moves on to `$10` |
| 4 | all (balloon ride target) | `$08` | the bonus ascent sequence (verified above) |
| 5 | 0-4 | `$01` | start of a sequence that checks `powerup_shot` and then switches to `$03`/`$04`/`$05` |
| 6 | 5 | `$0E` | calls bank 3 `$BF05` through `FarCall` |
| 10 | 3 | `$1A` | calls bank 6 `$BD5E` through `FarCall` |
| 14 | 3 | `$19` | sets bit 3 of `$0101` (a persistent flag) and returns to `$00` |
| 20 | 1 | `$17` | animates frame `$1C`/`$1D` (blinks with `zp_48`) |
| 22 | 4 | `$1B` | calls bank 6 `$BD99` through `FarCall` |
| 23 | 4 | `$18` | animates frame `$20`/`$21` like `$17` |

The set-up states `$01`-`$07` and `$0C` write their own timers (`ram_0735`-`ram_073E`) and `camera_mode`; `GameState06` falls into `GameState0C`
(`camera_mode` 3, then a bank 4 routine at `$B515`).
