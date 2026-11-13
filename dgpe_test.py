#!/usr/bin/env python3
"""Runbook 5.3: toggle DGPE through the EC window, read back through the EC's
own I/O interface (the only coherent read path). Files at 0xFE0B081D/0x1E."""
import mmap, os, time

EC = '/sys/kernel/debug/ec/ec0/io'
WIN = 0xFE0B0800
OFF = WIN & 0xFFF


def ec_byte(off):
    with open(EC, 'rb') as f:
        f.seek(off)
        return f.read(1)[0]


def win():
    fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
    return fd, mmap.mmap(fd, 0x1000, offset=WIN & ~0xFFF)


def show(tag):
    b1d, b1e = ec_byte(0x1D), ec_byte(0x1E)
    print(f'{tag}: 0x1D=0x{b1d:02x} 0x1E=0x{b1e:02x} '
          f'DGPS={(b1d >> 3) & 1} DGPE={b1e & 1}')


show('before')
fd, m = win()
print(f'window read (informational only): 0x1E=0x{m[OFF + 0x1E]:02x}')
m[OFF + 0x1E] = 0x00
show('after DGPE<-0')
for i in range(10):
    print(f'  poll {i}: 0x1D=0x{ec_byte(0x1D):02x} DGPS={(ec_byte(0x1D) >> 3) & 1}')
    time.sleep(1)
m[OFF + 0x1E] = 0x01
show('restored DGPE<-1')
m.close()
os.close(fd)
