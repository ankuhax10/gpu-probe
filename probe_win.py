#!/usr/bin/env python3
import mmap, os, time
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
m = mmap.mmap(fd, 0x1000, offset=0xFE0B0000)
for r in range(3):
    print('pass', r, '0x1C..0x20:', m[0x1c:0x20].hex(' '),
          ' 0x00..0x08:', m[0:8].hex(' '),
          ' 0x800..0x804:', m[0x800:0x804].hex(' '))
    time.sleep(0.2)
m.close(); os.close(fd)
