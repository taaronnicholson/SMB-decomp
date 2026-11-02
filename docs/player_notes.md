# Player notes (hand-written, verified against the code)

**Controls** (`buttons` bits: A `$01`, B `$02`, Select `$04`, Start `$08`, Right `$10`, Left `$20`, Up `$40`, Down `$80`):
- **A** starts a jump on the ground; holding it while airborne affects the jump (state `$02` tests it).
- **B** fires the player's attack projectile: it needs a free `shot_*` slot (`shot_state` = 0), sets the state to 1 or 6 and a cooldown in
  `zp_88`; there are two slots, drawn into OAM entries 19-20 by bank 1 `$802C`.
- **Down** alone (`buttons & $B1 == $80`) on the ground switches `PlayerState00` to state `$05`.
- **Start** (fresh press, only when the fade has finished) is handled by `CheckPause`.

**States** (`player_state`, `$63`; dispatch table `PlayerStateHandlers`, bank 2 `$B5AA`, 32 entries, 31 distinct handlers; see
`player_states.md` for the generated table): `$00` normal ground movement (`PlayerState00`, ~340 lines), `$02` airborne (jump/fall,
~470 lines; plays sfx `$0B`/`$1B` on pulse 1 and `$27` on noise), `$05` crouch (from Down), `$09` start-of-life/idle (set by the reset code),
`$0D` in water (entered when below `water_level`, splash sfx `$22`, leaves with Up), `$16` level complete (set when `balloons_left` reaches
0) and `$10`/`$11`, `$1C`-`$1F` longer sequences (death/ending/transition candidates, not verified).
States whose handlers are 4 lines long are stubs that set a timer and return; their effect is applied by shared code elsewhere.

**Hurt:** `HurtPlayer` is called by hazards (tile class 3), by entity touch handlers (`Ent_HurtOnTouch`) and by some states.
**Vulnerable enemies** (`$5E`) die when the player touches them in state `$02` with `zp_7C` set (the descending attack).
