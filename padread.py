#!/usr/bin/env python3
import mmap, os

def rd(addr, n=4):
    P = addr & ~0xFFF
    O = addr & 0xFFF
    span = (O + n + 0xFFF) & ~0xFFF
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    m = mmap.mmap(fd, span, offset=P)
    b = m[O:O+n]
    m.close(); os.close(fd)
    return int.from_bytes(b, 'little')

for name, addr in [
    ("G0P17 SBRG+0x6E0810", 0xFD6E0810),
    ("G9P17 SBRG+0x6D0B60", 0xFD6D0B60),
    ("G9P0  SBRG+0x6D0A50", 0xFD6D0A50),
]:
    v = rd(addr)
    print(f"{name} = 0x{v:08x}  TX={v & 1} RX={(v >> 1) & 1} TXDIS={(v >> 8) & 1} RXDIS={(v >> 9) & 1} PMODE={(v >> 10) & 0xf}")
