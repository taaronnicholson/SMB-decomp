"""Python port of the game's LZ-style decompressor (fixed bank $FDEF).

Bit stream: MSB first, refilled a byte at a time (sentinel bit scheme). The first byte only primes the
bit buffer and its first bit is discarded; the first token is always a literal.
Tokens:  flag 0 -> literal (8 bits)
         flag 1 -> match:  next bit 0        -> length 2
                           next bit 1, v = 3 bits:  v != 0 -> length v+2
                                                    v == 0 -> e = 8 bits; e == 0 ends the stream, else length e+9
                           then distance-1 = 2 bits (high) + 8 bits (low)   (10-bit, 1..1024 back)
"""
def decompress(data, pos=0):
    """Decompress from data[pos:]. Returns (output bytes, position just after the last byte consumed)."""
    first = data[pos]; pos += 1
    buf = ((first << 1) | 1) & 0xFF          # first bit (the MSB) is discarded
    def bit():
        nonlocal buf, pos
        buf <<= 1
        carry = buf >> 8; buf &= 0xFF
        if buf == 0:                         # sentinel shifted out: reload
            buf = data[pos]; pos += 1
            buf = (buf << 1) | carry
            carry = buf >> 8; buf &= 0xFF
        return carry
    def bits(n):
        v = 0
        for _ in range(n): v = (v << 1) | bit()
        return v
    out = bytearray()
    out.append(bits(8))
    while True:
        if bit() == 0:
            out.append(bits(8)); continue
        if bit() == 0: ln = 2
        else:
            v = bits(3)
            if v: ln = v + 2
            else:
                e = bits(8)
                if e == 0: break
                ln = e + 9
        dist = (bits(2) << 8 | bits(8)) + 1
        for _ in range(ln): out.append(out[-dist])
    return bytes(out), pos
