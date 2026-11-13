#!/usr/bin/env python3
import mmap, os, sys

def rdphys(base, off=0, n=16):
    at = base + off
    P = at & ~0xFFF
    O = at & 0xFFF
    span = (O + n + 0xFFF) & ~0xFFF
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    m = mmap.mmap(fd, span, offset=P)
    b = m[O:O+n]
    m.close(); os.close(fd)
    return b

if __name__ == '__main__':
    base = int(sys.argv[1], 0)
    off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 16
    b = rdphys(base, off, n)
    print(' '.join(f'{x:02x}' for x in b))
    words = [f'0x{int.from_bytes(b[i:i+4],"little"):08x}' for i in range(0, len(b)//4*4, 4)]
    print('u32 LE:', ' '.join(words))
