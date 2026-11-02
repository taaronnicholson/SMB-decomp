# NES ROM reverse engineering (ca65 project)

Disassembly of a 128 KB NES game (mapper 2 / UxROM, 8 × 16 KB PRG banks, CHR-RAM).
**This is not Super Mario Bros.** It is *Alfred Chicken* (Twilight, © 1993, published by Mindscape, licensed by
Nintendo) — the title screen renders it when run in `tools/emu.py`. The on-screen text identifies a Mindscape-published, Nintendo-licensed
title with an egg/balloon theme (credits: "BILLY EGG AND BROS", "MEKA MONSTER INC", "PETE TATTERSALL",
"MUSIC AND SFX BY JAMES THORNTON III"; copyright line "… 1993"). The repository name is misleading.
The code is back-translated
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

## Stage records (bank 0 `$8263`) and areas
`stage_index` (0-5) selects one of 6 stage records through a pointer table. A stage is a set of **areas**
(24 in total) joined by doors. Each record is:

| Offset | Size | Meaning |
|--------|------|---------|
| 0 | 4 | spawn **Y**, **X** (16-bit each) → `player_y/x_lo/hi`, copied to `spawn_*` |
| 4 | 1 | starting area number (≥ `$E0` = go to stage `code-$E0`) |
| 5 | 1 | parameter (`$0E` in every entry) |
| 6 | 1 | unknown per-record byte (skipped by the loader) |
| 7… | 6 each | door entries: Y, X (16-bit), destination area, parameter — indexed as `6*n` from `entry_list` |

Records 0–3 have 11 entries, record 4 has 3, record 5 has none. The six starting areas are 0, 16, 3, 10, 21 and 6.

**Areas** (`LoadArea` = `F_D05C`, A = area number): `AreaHeaderPtrLo/Hi` (`$83B9`/`$83D1`) point to a 6-byte
12-byte `AreaHeaderN` (song number, map address, log2 width, height, palette set, collectible-table pointer, two more bytes, initial `game_state`, tileset id) and `AreaMapBank` (`$83E9`) gives the PRG
bank of the map. A map is one byte per 16×16 tile, `8 << log2width` tiles wide (16, 32, 64 or 128), `height` rows tall,
row-major, and the levels scroll **vertically**. The address of tile (x, y) is `map_ptr + (x>>4) + (y>>4)*width`
(`MapPtrFromPos`); `GetMapTile` reads it. The first two rows are phantom (above the playfield, not stored), so the real
data starts at `base + 2*width` (area 23's base is `$7F80`, just below its bank). Maps live in bank 3 (areas 0-5, 7-10,
12-20), bank 1 (6, 11), bank 4 (21, 23) and bank 6 (22). `tools/extract_maps.py` dumps them to `build/maps/`.
**Collectibles:** header bytes 6-7 point (in bank 0) to a `CollectTableN`: one word per map row from row 2 (an offset
from the table start, 0 = none), then per-row lists of (column, flag index) pairs. Tile ids `$80`-`$BB` are collectible
tiles; `GetCollectibleBit` finds the flag index for a map cell and the game keeps collected state in `collected_flags`
(`$0100`, per placement) and `collected_by_kind` (`$9D`, per tile kind), so picked-up items stay gone (`ApplyCollectedFlag`).
Enemy/object placement is not decoded yet.
`tile_props` (`$03A4`, 120 bytes, loaded per tileset) holds tile flags; bit 0 means solid.

**Tileset records** (bank 0, 8 bytes at `$8C9B + 8*t`, `t` = header byte 11, bank of the compressed blocks in `B0_8C95[t]`):
tile-properties block (LZ → RAM `$03A4`), tile-graphics block (LZ → PPU `$1530`), the metatile planes, and an attribute plane.
Each map byte is a 16×16 metatile: four 240-entry planes (top-left, top-right, bottom-left, bottom-right) in bank 0 give its
four 8×8 tile numbers, drawn by the code at `F_D37F`. The background pattern table is `$1000`: the shared block at
`$88A7` (tiles 0-82), then the tileset block from tile `$53`, and the font at `$C4` (ASCII + `$94`).
`tools/render_maps.py` draws every area to `build/maps/area_NN.png` (placeholder colours, git-ignored).
The area header's song number is played by `PlaySong` when the area loads.

## Sound engine (bank 6)
`$8000` is a jump table: `Sound_PlaySong` (A = song 0-8), `Sound_Update` (`$8003`, once per frame),
`Sound_Silence` (`$8006`), `Sound_Resume` (`$8009`), plus three more entry points.
Per-channel state lives in four 19-byte blocks from `$0759` (`snd_sq1_*`, `snd_sq2_*`, `snd_tri_*`, `snd_noi_*`);
`$074B-$074D` mark sound effects that temporarily own a channel.

**Song table** (`SongTable`, 9 bytes per song): tempo, then pattern-list pointers for pulse 1, pulse 2,
triangle, noise. A **pattern list** is a list of pattern pointers ended by `$0000` (which loops back to the start).
A **pattern** is a byte stream:

| Byte | Meaning |
|------|---------|
| `$00-$5F` | note (index into `PeriodTable`, 79 NES timer periods; noise uses the low nibble); plays for the current length |
| `$60-$7F` | set note length to (byte-`$5F`) ticks |
| `$F4 n` | set tempo | 
| `$F5 lo hi` | switch to another pattern list |
| `$F6 n` | volume envelope n (tables `$930D`/`$9322`) |
| `$F7 n` | pitch modulation table n (`$93CB`/`$93D4`) |
| `$F8` / `$F9` | key off / hold (re-trigger envelope without a new note) |
| `$FA n` | duty/volume high bits | 
| `$FB n` / `$FC n` | song / channel transpose |
| `$FD n` | pulse sweep register |
| `$FE` | end of song |
| `$FF` | next pattern from the list |

**Instrument tables**
- `EnvelopePtrLo/Hi` → 21 `EnvelopeN` volume envelopes: speed byte, then volume nibbles; a final byte with bit 7 set holds that volume.
- `PitchModPtrLo/Hi` → 9 `PitchModN` signed period-offset tables (vibrato); `$80` loops.

**Sound effects**: `Sound_PlaySfxSq1/Sq2/Noise` (A = id 0-74) copy a 14-byte `SfxDefN` (via `SfxDefPtrs`) into that
channel's SFX state and set `snd_sfx_*` so music stops writing that channel. SFX volume shapes are `SfxSeq0-15`
(via `SfxSeqPtrs`, `$FF`-terminated). The meaning of each definition byte is not yet decoded.

`tools/gen_sound_hints.py` walks the song table and emits `tools/hints_sound.txt`
(lists, 72 streams, and the `snd_*` RAM names); `make regen` runs it.

## PPU update buffer and text
`FlushPPUBuffer` (called from NMI with bank 0 mapped) executes commands queued at `ppu_buffer` (`$0300`):
`[addr_hi][addr_lo][len][data…]`, `addr_hi = 0` ends the list; `len = 1` writes one byte, `len` bit 7 selects
horizontal (+1) increment, otherwise vertical (+32). Multi-byte copies jump into an unrolled copy chain in the
fixed bank through `PPUCopyLo/Hi` (`PPUCopy1`…`PPUCopy32`).
Text appears as ASCII strings (44 found by `tools/gen_text_hints.py`, rendered as `.byte "…"`).
Bank 4's title/credits strings are stored **reversed** (a trailing comment shows the readable form); bank 1's
messages are forward and printed with tile = char + `$94`. `PaletteFadeStep` (bank 0) fades the palette.

## Emulator and graphics tooling
`tools/emu.py` is a small (not cycle-accurate) 6502+PPU emulator used to inspect graphics:
`python3 -I tools/emu.py <frames> <out> [--press=START@n,...]` writes `<out>.screen.png` and `<out>.chr.png`.
`tools/chrtrace.py` reports which code writes CHR-RAM; `tools/decomptrace.py` / `tools/gfx_scan.py` list the
calls to the game's LZ-style decompressor (`F_FDEF`, source in `ptr_lo/hi`, destination in `$55/$56`, carry set = RAM
target, clear = VRAM). Rendered images are not committed.
`tools/gfx_scan.py` (slow, ~2.5 min) walks every stage and caches the result in `tools/gfx_blocks.json`;
`tools/gen_gfx_hints.py` turns it into labelled `Gfx_B<bank>_<addr>` blobs (26 LZ-compressed blocks: shared title/font
graphics in banks 0/1, per-stage background tile sets and `tile_props` tables in bank 4, sprite tile sets in bank 6).

## Compression
`tools/lzdec.py` is a Python port of the game's decompressor, validated against the emulator (all calls match, bytes
and end pointer). MSB-first bit stream; the first byte only primes the bit buffer and the first token is a literal.
Flag `0` = literal byte. Flag `1` = match: next bit `0` → length 2; else 3 bits `v`: `v≠0` → length `v+2`, `v=0` → 8 bits
`e`: `e=0` ends the stream, else length `e+9`; then a 10-bit distance-1. The routine stores the offset's high bits at the
output position as scratch and reads them back for 16-bit address arithmetic.
`tools/extract_gfx.py` decompresses all 26 blocks to `build/gfx/*.bin` and grayscale tile sheets
(derived from the ROM, not committed); `tools/check_decomp.py` re-validates the port.

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
