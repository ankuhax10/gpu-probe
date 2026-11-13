#!/usr/bin/env python3
import mmap, os, sys

BASE = 0xFE0B0800
PAGE = BASE & ~0xFFF
OFF  = BASE & 0xFFF

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
m  = mmap.mmap(fd, 0x1000, offset=PAGE)

def dump():
    b = m[OFF:OFF + 0x40]
    for row in range(0, 0x40, 16):
        chunk = b[row:row+16]
        print(f'0x{row:02x}  ' + ' '.join(f'{v:02x}' for v in chunk))

def flags(byte, bit, width=1):
    return (m[OFF + byte] >> bit) & ((1 << width) - 1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'dump':
        dump()
    else:
        print('byte 0x1D = 0x%02x   (DGPS=%d DGRS=%d BCDG=%d NGPS=%d FBST=%d)'
              % (m[OFF+0x1D], flags(0x1D,3), flags(0x1D,4), flags(0x1D,2), flags(0x1D,1), flags(0x1D,0)))
        print('byte 0x1E = 0x%02x   (DGPE=%d DGHR=%d FBPC=%d EC6I=%d EC6O=%d GC6E=%d RG12=%d)'
              % (m[OFF+0x1E], flags(0x1E,0), flags(0x1E,1), flags(0x1E,2), flags(0x1E,3), flags(0x1E,4), flags(0x1E,5), flags(0x1E,6)))
