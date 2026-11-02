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

## Status
Code is found by (1) tracing from the vectors with bank-context and constant tracking,
(2) far-call resolution, and (3) a conservative speculative decode (blocks are accepted only
if every path decodes to a terminator with no illegal opcodes). Everything else is `.byte` data.
~29% of PRG is classified as code (bank 7 ≈ 91%); banks 0, 3, 4 are mostly data
(levels/graphics/music, not yet split). Speculatively-found code may include a few false
positives – harmless for the byte-exact build, but treat labels as provisional.
Next steps: name more RAM/routines, split data tables (`words`/`lohi` hints), decode the
music/level formats, convert data to `.incbin`/structured tables.

Regenerate sources after editing `tools/hints.txt`: `make regen` (overwrites `src/*.s`).
