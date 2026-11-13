#!/usr/bin/env python3
import mmap, os, sys

def try_read(addr, n=16, label=""):
    P = addr & ~0xFFF
    O = addr & 0xFFF
    span = (O + n + 0xFFF) & ~0xFFF
    try:
        fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
        m = mmap.mmap(fd, span, offset=P)
        b = m[O:O+n]
        m.close(); os.close(fd)
        print(f"{label} 0x{addr:08x}: {b.hex(' ')}")
    except Exception as e:
        print(f"{label} 0x{addr:08x}: FAIL {type(e).__name__}: {e}")

if __name__ == '__main__':
    try_read(0x43CCDF18, 17, "HGOP")
    try_read(0x44A52D18, 32, "SANV")
