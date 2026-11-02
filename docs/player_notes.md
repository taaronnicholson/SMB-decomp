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

**States** (`player_state`, `$63`; dispatch table `PlayerStateHandlers`, bank 2 `$B5AA`, 32 entries, 31 distinct handlers; `player_states.md` is the
generated table): `$00` ground, `$01` rising (jump), `$02` falling [verified], `$04` landing [verified], `$05`-`$07` peck sequence [verified; `$05`,
`$06`, `$07` are trampolines into bank 6 `$A2BE`, `$A32E`, `$A3D6`], `$0D` in water (entered below `water_level`, splash sfx `$22`, Up leaves it),
`$16` level complete (set when `balloons_left` reaches 0), `$09` set by the reset code (idle/start of life). `$10`/`$11` and `$1C`-`$1F` are longer
sequences whose meaning is unverified.

**Hurt:** `HurtPlayer` is called by hazards (tile class 3), by entity touch handlers (`Ent_HurtOnTouch`) and by some states.
**Vulnerable enemies** (`$5E`) die when the player touches them in state `$02` with `zp_7C` set.
