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
