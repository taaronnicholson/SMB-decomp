; iNES header: 8 x 16KB PRG, CHR-RAM, mapper 2 (UxROM), horizontal mirroring
.segment "HEADER"
    .byte "NES", $1A
    .byte 8        ; PRG banks (16KB)
    .byte 0        ; CHR banks (0 = CHR-RAM)
    .byte $20      ; flags 6: mapper low nibble = 2
    .byte $00      ; flags 7
    .byte $00,$00,$00,$00,$00,$00,$00,$00
