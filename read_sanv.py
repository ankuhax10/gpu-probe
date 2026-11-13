#!/usr/bin/env python3
"""Read-only SANV (BIOS NVS) hybrid-graphics configuration.

Offsets derived from DSDT.dsl:
  Name (SANB, 0x44A52D18) / OperationRegion (SANV, SystemMemory, SANB, 0x1BC)
  Field (SANV, AnyAcc, Lock, Preserve) at DSDT line 381.

No writes. Read-only open, PROT_READ mapping.
"""
import mmap
import os
import struct
import sys

SANV = 0x44A52D18
SANV_LEN = 0x1BC

# Field offsets inside SANV, computed from the DSDT field list.
F = {
    "HGMD": (0x088, 1),
    "HGFL": (0x089, 1),
    "SGGP": (0x08A, 1),
    "HRE0": (0x08B, 1),
    "HRG0": (0x08C, 4),
    "HRA0": (0x090, 1),
    "PWE0": (0x091, 1),
    "PWG0": (0x092, 4),
    "PWA0": (0x096, 1),
    "RPBA": (0x12F, 4),
}


def rd(fd, addr, n):
    page = addr & ~0xFFF
    off = addr & 0xFFF
    span = (off + n + 0xFFF) & ~0xFFF
    m = mmap.mmap(fd, span, mmap.MAP_PRIVATE, mmap.PROT_READ, offset=page)
    try:
        return m[off:off + n]
    finally:
        m.close()


def u(b):
    return int.from_bytes(b, "little")


def main():
    try:
        fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    except OSError as e:
        sys.exit(f"open /dev/mem: {e}")

    try:
        raw = rd(fd, SANV, SANV_LEN)
    except OSError as e:
        sys.exit(f"mmap SANV 0x{SANV:08X}: {e}")

    print(f"SANV base 0x{SANV:08X}  len 0x{SANV_LEN:X}")
    print()

    vals = {}
    for name, (off, width) in F.items():
        v = u(raw[off:off + width])
        vals[name] = v
        print(f"{name:5s} @ +0x{off:03X} (0x{SANV + off:08X}) = 0x{v:0{width * 2}X}  ({v})")

    print()
    print("--- interpretation ---")
    sggp = vals["SGGP"]
    pwg0 = vals["PWG0"]
    pwe0 = vals["PWE0"]
    pwa0 = vals["PWA0"]
    rpba = vals["RPBA"]

    if sggp == 0:
        print("SGGP=0  -> HGPO() is a no-op: the dGPU power GPIO is never driven.")
        print("           This makes the fault BIOS-NVS/board-data, not the rail.")
    elif sggp == 1 and pwg0 == 0:
        print("SGGP=1 but PWG0=0 -> GPIO method enabled, no pin configured.")
        print("           Still board-data, not the rail.")
    elif sggp == 1 and pwg0 != 0:
        print(f"SGGP=1 and PWG0=0x{pwg0:08X} -> GPIO configured. Software path is")
        print("           complete; the fault is downstream (trace/VRM/GPU).")
    else:
        print(f"SGGP=0x{sggp:02X} -> unexpected value, do not interpret blindly.")

    print()
    print(f"PWE0=0x{pwe0:02X}  PWA0=0x{pwa0:02X}  "
          f"(PWA0=0 means active-low: value is inverted before SGOV)")
    print(f"RPBA=0x{rpba:08X}")

    if rpba:
        try:
            cfg = rd(fd, rpba, 4)
            pvid = u(cfg[0:2])
            pdid = u(cfg[2:4])
            print(f"RPBA+0x00: PVID=0x{pvid:04X}  PDID=0x{pdid:04X}")
            if pvid == 0xFFFF:
                print("PVID=0xFFFF -> CCHK() returns 0 -> HGON() bails before HGPO().")
            elif pvid == 0x8086:
                print("PVID=0x8086 -> CCHK's vendor check passes.")
            else:
                print("PVID is neither 0x8086 nor 0xFFFF; RPBA may point elsewhere.")
        except OSError as e:
            print(f"RPBA read at 0x{rpba:08X} failed: {e}")
    else:
        print("RPBA=0 -> PVID reads from physical 0; CCHK's check is meaningless.")


if __name__ == "__main__":
    main()
