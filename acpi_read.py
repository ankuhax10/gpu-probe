#!/usr/bin/env python3
"""Read-only ACPI NVS values via acpi_call. No methods are invoked."""
import sys

PATHS = [
    r'\SGGP',
    r'\PWE0', r'\PWG0', r'\PWA0',
    r'\HRE0', r'\HRG0', r'\HRA0',
    r'\_SB.PC00.DGPV',
    r'\_SB.PC00.OPTF',
    r'\_SB.PC00.NVGE',
    r'\_SB.PC00.DSSV',
    r'\_SB.PC00.DISM',
    r'\_SB.PC00.TDGC',
    r'\_SB.PC00.DGCX',
]

for p in PATHS:
    try:
        with open('/proc/acpi/call', 'w') as f:
            f.write(p)
        with open('/proc/acpi/call') as f:
            v = f.read().strip()
    except Exception as e:
        v = f'EXC {type(e).__name__}: {e}'
    print(f'{p:24s} = {v}')
