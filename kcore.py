#!/usr/bin/env python3
# Read physical memory through /proc/kcore (ELF core) - read-only.
import struct, sys, os

KCORE = '/proc/kcore'

def load_phdrs(f):
    f.seek(0)
    hdr = f.read(64)
    if hdr[:4] != b'\x7fELF':
        raise SystemExit('not ELF')
    e_phoff = struct.unpack_from('<Q', hdr, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', hdr, 0x36)[0]
    e_phnum = struct.unpack_from('<H', hdr, 0x38)[0]
    f.seek(e_phoff)
    ph = []
    for _ in range(e_phnum):
        b = f.read(e_phentsize)
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
            struct.unpack_from('<IIQQQQQQ', b, 0)
        if p_type == 1:  # PT_LOAD
            ph.append((p_vaddr, p_memsz, p_offset, p_filesz))
    return ph

def direct_map_base(ph):
    # lowest large PT_LOAD in the 0xffff8... direct-map range
    cands = [v for (v, m, o, fs) in ph
             if 0xffff800000000000 <= v < 0xffffc00000000000 and m > (1 << 40)]
    return min(cands) if cands else None

def read_va(f, ph, va, n):
    for (v, m, o, fs) in ph:
        if v <= va < v + m:
            off = o + (va - v)
            f.seek(off)
            return f.read(n)
    raise SystemExit(f'VA {va:#x} not in any PT_LOAD')

if __name__ == '__main__':
    phys = int(sys.argv[1], 0)
    n = int(sys.argv[2], 0) if len(sys.argv) > 2 else 64
    f = open(KCORE, 'rb')
    ph = load_phdrs(f)
    base = direct_map_base(ph)
    if base is None:
        raise SystemExit('no direct map segment found')
    b = read_va(f, ph, base + phys, n)
    print(f'direct_map_base={base:#x}  phys={phys:#x}')
    for i in range(0, len(b), 16):
        chunk = b[i:i+16]
        hexs = ' '.join(f'{x:02x}' for x in chunk)
        asc = ''.join(chr(x) if 32 <= x < 127 else '.' for x in chunk)
        print(f'{i:04x}: {hexs:<47} {asc}')
