# Memory — GTX 1650 (TU117M) on HP 88E4

Updated: 2026-11-13
Report: `~/gpu/docs/DIAGNOSIS.md` (authoritative). Raw: `~/gpu/FINDINGS.md`.
Shop handover: `~/gpu/docs/REPAIR-HANDOVER.md`; one-page card:
`~/gpu/docs/SHOP-ONE-PAGER.md`.
Runbook: `~/Desktop/GPU_LINUX_RUNBOOK.md`.

## Current state (verified)
- D0: `GGOV(PWG0)=1`, `DGPE=1`, `DGPS=0`. D3cold: `GGOV=0`, `DGPE=0`, `DGPS=0`.
  D0 again: `1/1/0`.
- SANV NVS: `HGMD=0x02`, `SGGP=0x01`, `PWG0=0x090b000d` (group 9 pin 13),
  `PWA0=0x01`, `RPBA=0xC0030000`, `PVID=0x8086`, `PDID=0x9a09`.
- `GPC0(PWG0)=0x84000201` -> `PMODE=0` (GPIO), TX not disabled.
- GPU in D0; `BAR0+0=0x167000a1`, `+0x10..=0xBADF5040`; PROM `0x52300000` = `0x00`.
- Full `_ON`/`_OFF` moves `DGPE` and the GPIO, never `DGPS`, never the rail.

## Conclusion
Fault is downstream of the ACPI GPIO: **B** (GPIO pad -> VRM EN trace/buffer),
**C** (VRM), **D** (GPU-side). **A** (NVS/board data) is eliminated. Needs the
multimeter per DIAGNOSIS §7.

## Burned / do not repeat
- "SGGP=0 disables HGPO" — false; `SGGP=1`, `PWG0` valid, `PVID` valid.
- `setpci -s 00:06.0 0.w` does **not** test `RPBA`; `CCHK` reads `PVID` via the
  NVS pointer `RPBA`.
- "Not a PCH-GPIO enable" — false; it is group 9 pin 13, and `GGOV` tracks
  D0/D3cold.
- "EC window dead" — false; window decodes, read path intermittent. Use EC I/O.
- "VBIOS erased" — false; PROM `0x00` = unpowered SPI, not erased (`0xFF`).
- Nouveau `bios ctor failed: -22`; three NVIDIA driver versions fail identically.
- `/dev/mem` blocked for NVS (`EPERM`); `/proc/kcore` skips it. Use
  `acpi_os_map_memory` (see `~/gpu/sanv_mod/`).
- Do **not** patch `SGGP`/`PWG0` in NVS; the values are already correct.

## Next action
Measure NVVDD resistance (power off), then NVVDD and VRM EN with the GPU in D0.
The enable pad is group 9 pin 13, pad DW0 at `0xFD6D0B20`. Report values.
