# NES ROM reverse engineering (ca65 project)

Disassembly of a 128 KB NES game (mapper 2 / UxROM, 8 × 16 KB PRG banks, CHR-RAM)
back into buildable ca65 assembly. `make verify` rebuilds the ROM and checks that it is
**byte-identical** to the original (SHA-1 `c1bc357fce0aee0973e8d1f7aac75a68d52bea02`).

## Layout
- `src/bank0.s … bank6.s` – switchable banks, mapped at `$8000-$BFFF` (labels `B<bank>_<addr>`)
- `src/fixed.s` – fixed bank 7 at `$C000-$FFFF` (labels `F_<addr>`; reset/NMI/IRQ, bank switching)
- `src/hardware.inc` – PPU/APU registers and named RAM
- `nes.cfg` – linker config, `Makefile` – build
- `tools/` – the disassembler (`decomp.py`, `dis6502.py`) and analysis `hints.txt`
- `rom/game.nes` – the original ROM (git-ignored; needed only for `make regen`)

## Build
    sudo apt install cc65
    make verify

## Engine notes
- Bank switch: `LDA #bank / JSR SwitchBank` (writes through a bus-conflict table at `$C000`).
- `FarCall` (`$CEEE`): A=high, X=low, Y=bank – calls a routine in another bank and restores the bank.
- NMI dispatches through a state table at `$C825` indexed by `$00`.

## What each bank does (from reading the code)
| Bank | Role |
|------|------|
| 0 | Controller input (`ReadController` → `buttons*`), `ClearRAM`, stage record pointer table at `$8263` (indexed by `stage_index`, `$93`) and the stage data it points to |
| 1 | Sprite/OAM management (`HideSprites`), per-frame object code |
| 2 | Nametable/PPU drawing (≈800 `PPUDATA` writes), `ResetGameState`, `ResetLevelState` |
| 3 | Mostly data (tile/pattern and map-like tables) with a little code |
| 4 | Game-state machine: `DispatchGameState` jumps through a 16-entry table indexed by `game_state` (`$072C`) |
| 5 | Entity movement code: per-entity arrays indexed by X (`ent_x_lo/hi`, `ent_y_lo/hi`, `ent_angle`, `ent_radius`, `ent_dx/dy` …, 48 slots, stride `$30`); `SetEntityPolarPos` places an entity at a polar offset from a centre point |
| 6 | **Sound engine** – owns almost all APU writes; `$8000` is a jump-table API, `Sound_Update` (`$8003`) runs every frame |
| 7 | Fixed: vectors, `Reset`, `NMI`, bank switching/`FarCall`, main loop (`F_C700`–`F_C6FD`) |

Main loop per frame: `WaitForNMI`, then (state 3) bank 1 sprite clear → `ReadController` → game-state
dispatch (bank 4) → object/collision updates → `Sound_Update`. The NMI handler does OAM DMA,
applies the `ppuctrl_shadow`/`ppumask_shadow` values and calls one of 6 state handlers.

## Shared helpers
- `SineTable` (bank 0 `$BE8A`): 256 signed entries, amplitude ±64, index = angle (256 = full turn).
  `SinLookup`/`CosLookup` read it from fixed code (cos = index + `$40`); `ScaledMultiply` scales by a radius.
- `SwitchBankKeepX` (`$C919`) is `SwitchBank` that preserves X.

## Status
Code is found by (1) tracing from the vectors with bank-context and constant tracking,
(2) far-call resolution, and (3) automatic detection of code-pointer tables (emitted as `.word label`), and (4) a conservative speculative decode (blocks are accepted only
if every path decodes to a terminator with no illegal opcodes). Everything else is `.byte` data.
~33% of PRG is classified as code (bank 7 ≈ 88%, bank 5 ≈ 52%); banks 0 and 3 are mostly data
(levels/graphics/music, not yet split). Speculatively-found code may include a few false
positives – harmless for the byte-exact build, but treat labels as provisional.
Next steps: name more RAM/routines, split data tables (`words`/`lohi` hints), decode the
music/level formats, convert data to `.incbin`/structured tables.

Regenerate sources after editing `tools/hints.txt`: `make regen` (overwrites `src/*.s`).
