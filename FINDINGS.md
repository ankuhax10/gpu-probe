# GTX 1650 (TU117M) — diagnosis, consolidated

Date: 2026-11-12
Host: HP Pavilion Gaming Laptop / board 88E4, BIOS F.30 (10/27/2025)
OS: Kali GNU/Linux Rolling 2026.3, kernel 7.1.5+kali-amd64
GPU: 0000:01:00.0 NVIDIA TU117M [10de:1f9d] rev a1, subsystem 103c:88e4
Root port: 0000:00:06.0 Intel 11th Gen PCIe controller [8086:9a09]

This file replaces the session-1 notes. Two conclusions in session 1 were
wrong and are explicitly retracted in §4. Everything below is either a
measured value or labelled ASSUMPTION.

---

## 1. Verdict (what is actually proven)

**The dGPU's auxiliary domain is alive; its core/VRAM domain never powers up.**
**The EC accepts the "power on" request (DGPE=1) but the rail still does not
come up, and never reports power good (DGPS stays 0).**

Therefore the fault is **downstream of the EC's DGPE bit**, between the EC and
the NVVDD rail. It is not a driver, kernel, ACPI, VBIOS or EC-window problem.
The exact component (EC pin/trace vs. VRM vs. GPU) can only be decided with one
physical measurement — §6.

---

## 2. GPU state — measured

All reads are physical MMIO through `~/gpu/readphys.py` (mmap /dev/mem).

| Address | Value | Meaning |
|---|---|---|
| BAR0 + 0x000 | `0x167000a1` | NV_PMC_BOOT_0 = TU117, rev A1. Always-on block answers. |
| BAR0 + 0x010 … 0x020 | `0xbadf5040` repeated | NVIDIA poison marker — core partition not powered/clocked. |
| BAR0 + 0x300000 (PROM, = phys `0x52300000`) | `0x00000000` × 64 (1 KB earlier) | ROM aperture decodes, returns zeros. **Not `0xFF`.** |

- Config space works, PCIe link is Gen3 x4 (root port LnkCap is x4 — platform
  max), HDMI audio function 01:00.1 is bound and works.
- `power_state` = D0, `runtime_status` = active, PME has **no D3cold** support.
- The 0x0000 PROM data is a real bus response, not a master abort. A flash that
  had been erased would read `0xFF`; this reads `0x00`, i.e. the SPI/flash
  domain is unpowered/unclocked.
- ASSUMPTION: `0xBADF5040` is NVIDIA's response for an unpowered core
  partition. It is consistent with every other measurement and with nouveau's
  `bios ctor failed: -22`, but it is not vendor-documented.

## 3. EC state — measured through the EC's own I/O interface

Oracle: `/sys/kernel/debug/ec/ec0/io` (ACPI EC transactions over ports 0x62/0x66).
Reads are stable and repeatable. Bit layout from DSDT `PECM`, lines 80283-80346.

| Byte | Bit | Field | Value |
|---|---|---|---|
| 0x1D | 3 | DGPS (dGPU power status) | **0** |
| 0x1D | 4 | DGRS | 0 |
| 0x1D | 2 | BCDG | 0 |
| 0x1D | 1 | NGPS | 0 |
| 0x1D | 0 | FBST (feature-byte status?) | 0 |
| 0x1E | 0 | DGPE (dGPU power enable) | **1** |

Re-verified at 17:1x and 17:2x: `0x1D=0x00`, `0x1E=0x01` both times.

**DGPE write test (runbook §5.3), re-run clean at 17:2x:**

1. read 0x1E via EC I/O = `0x01`
2. write `0x00` to `0xFE0B081E` through the window
3. read 0x1E via EC I/O = `0x00` → the write reached EC RAM
4. poll 0x1D every second for 10 s → `0x00` every time (DGPS never sets)
5. write `0x01` back, read 0x1E = `0x01` → restored

Script: `~/gpu/dgpe_test.py`. Same result as the earlier 3-cycle run: **DGPE
toggles, DGPS never leaves 0.**

**DGPS did not move in any trial:** 3 × DGPE off/on cycles and a 10 s poll
after a fresh 0→1 transition all left 0x1D = 0x00.

**Full ACPI sequence also runs and also fails:**

```
echo auto > .../0000:01:00.0/power/control   -> D3cold, BAR0 = 0xffffffff, DGPE = 0  (_PS3/_OFF ran)
echo on   > .../0000:01:00.0/power/control   -> D0, BOOT_0 = 0x167000a1, DGPE = 1    (_PS0/_ON ran)
```

After the full `_ON`: **DGPS still 0, PROM still 0x0000, BAR0 still poisoned.**

- PCH GPIO diff across D3cold→D0: no output (TX) changed at all. Only RX on
  pin 17 (GSPI0_MISO), pin 104 (SRCCLKREQB_0), pins 183/184 (UART1). So the
  dGPU enable is not a PCH GPIO; it is the EC's DGPE. The RX changes are
  PCIe-link/clock side effects.
- EC RAM diff across 3 DGPE cycles: **no byte tracks DGPE** — the EC exposes no
  status/ADC mirror of the power sequence.

---

## 4. Retractions (session-1 errors)

**4.1 "EC shared-memory window is dead" — RETRACTED.**
The window at `0xFE0B0000` decodes. A 4 KB dump (`~/gpu/ecwin.bin`) matches
live EC RAM at 0x800..0x8FF in 249/256 bytes. The session-1 "all FF" reading
was an artifact.

**4.2 "VBIOS is erased/corrupt, that is why the ROM reads zero" — RETRACTED.**
The PROM reads `0x00`, not `0xFF`. Erased flash reads `0xFF`. The zero data is
the unpowered flash/SPI domain, i.e. a consequence of the dead rail, not a
cause.

**4.3 New caveat: the EC window is a good WRITE path but an unreliable READ
path. Use the EC I/O interface as the oracle.**
Observed this session:

- `ecwin.bin` (17:10): window[0x800+0x1D..0x1E] = `00 01` — matches EC RAM.
- 17:2x: window[0x800+0x1D..0x1E] reads `00 00`, window 0x800..0x83F reads all
  `00`, while EC I/O still reports `0x1E = 0x01`.
- 17:2x (later, same session): window read of 0x1E = `0x01` — coherent again.

The window behaves like a banked/shadowed shared-RAM view, not a live alias.
Writes demonstrably land (step 3 above); reads are intermittent. **Never use
window reads as evidence for DGPE/DGPS**; they can agree by luck. (The runbook
§5.3 script has been corrected accordingly.)

---

## 5. Proven causal chain

```
ACPI _ON / direct DGPE write
        |
        v
DGPE = 1 in EC RAM                         [measured, EC I/O]
        |
        v
EC does not assert DGPS                     [measured, 3 cycles + 10 s]
EC does not enable NVVDD                    [inferred from PROM 0x0000 + BAR0 poison]
        |
        v
GPU core/VRAM/SPI domain stays unpowered    [measured: PROM 0x0000, BAR0 0xBADF5040]
        |
        v
no VBIOS -> nouveau "bios ctor failed: -22"
no core  -> nvidia driver init fails identically on 3 driver versions
```

The remaining fault is in one of these, in order of what the evidence supports:

- **B. EC output → VRM enable path** (EC GPIO not driving, series resistor or
  trace open — consistent with work around the EC).
- **C. VRM/MOSFET/PWM fault** (rail never comes up even with EN present).
- **A. EC firmware/board-data config** (blank Feature Byte / generic DMI after
  the shop's rewrite means the EC may not route DGPE to the power GPIO). This
  would look exactly like B from software; only a probe separates them.
- **D. GPU-side** (shorted NVVDD causing the VRM to hiccup, or reset held).
  Folded into C until the resistance check in §6.

None of B/C/D is proven. They are the three ways the measured chain can end.

---

## 6. The measurement that decides it

Do these in order. Report values, not conclusions.

1. **Power off, AC and battery removed — NVVDD to GND resistance.**
   Probe an NVVDD output capacitor (near the GPU VRM inductors), not a
   fine-pitch component. Subtract your meter's lead resistance (short the
   probes first).
   - < 0.2 Ω → shorted rail (GPU die or VRM MOSFET). Do not power on again.
   - ~0.5–5 Ω → normal for a large core rail; a cheap DMM is not precise
     enough to call a fault here, so continue to step 2.
2. **Power on, GPU runtime-resumed to D0 (`power/control = on`), measure NVVDD.**
   Turing mobile core is typically 0.7–0.9 V.
   - NVVDD present → the rail is fine; the fault is GPU-side (VBIOS/SPI,
     reset, or die). Then check 1.8 V VDDIO and the SPI flash supply.
   - NVVDD absent → go to 3.
3. **Measure the VRM's EN pin (and the EC's dGPU-power output pin if reachable).**
   - EN high (≥1.8 V) but no NVVDD → VRM/MOSFET/PWM (C).
   - EN low at the VRM, EC pin high → open trace / series resistor (B).
   - EN low at both → EC not driving its pin: firmware/config (A) or dead EC
     output (B).
4. Only if EN is low at both: the EC-side question becomes "does this EC
   firmware drive the pin at all?" — i.e. board data / Feature Byte (A) vs.
   dead EC pin (B). That is the point where restoring correct board data is
   worth doing, and not before.

Rails to confirm while in there: NVVDD (~0.8 V), VDD_MEM (GDDR6, ~1.35 V),
1.8 V, 3.3 V aux, 5 V. If 3.3 V aux is missing the GPU would not enumerate at
all, and it does.

---

## 7. Software options that remain (do not change the verdict)

- **Read `DGPV`, `OPTF`, `NVGE` (HGOP @ `0x43CCDF18`) and `PWG0/PWE0/PWA0/SGGP`
  (SANV @ `0x44A52D18`).** Both are ACPI NVS.
  - `/dev/mem`: HGOP → EAGAIN, SANV → EPERM (`~/gpu/readnvs.py`).
  - `/proc/kcore`: NVS is not in the direct map.
  - Requires `linux-headers-7.1.5+kali-amd64` + `acpi-call-dkms` (not
    installed; needs operator sign-off). Value: tells whether BIOS POST
    recorded the dGPU as present. Does **not** change §1 or §6.
- `acpidbg` is unavailable (`CONFIG_ACPI_DEBUGGER` not set). No
  `/sys/kernel/debug/acpi/custom_method` (`CONFIG_ACPI_DEBUG` not set).
- Nothing else in software can distinguish B/C/D. Further EC poking is
  guesswork.

---

## 8. Files

- `~/gpu/FINDINGS.md` — this file
- `~/gpu/ecwin.bin` — 4 KB EC window dump (17:10, coherent sample)
- `~/gpu/readphys.py` — physical MMIO read helper
- `~/gpu/readnvs.py` — NVS read attempt (documents EPERM/EAGAIN)
- `~/gpu/probe_win.py` — window read-repeat probe
- `~/gpu/padread.py` — PCH pad read attempt (EPERM; use pinctrl debugfs)
- `~/gpu/kcore.py` — /proc/kcore physical reader
- `~/gpu/acpi/dsdt.dsl` — `PECM` @ 0xFE0B0800 (line 80282), field layout
  80283-80448, `ERAM` 80449, `EIDR/EIDW` 80835, `ECCD` 80852
- `~/gpu/acpi/SSDT18.dsl` — `PCRP._ON/_OFF`, `HGON/HGOF/HGPO/CCHK`
- `~/gpu/acpi/SSDT17.dsl` — `HGOP` field @ 0x43CCDF18, `GC6I/GC6O`, `GPS/NVOP`
- `/home/ankuha/Desktop/GPU_LINUX_RUNBOOK.md` — runbook (§5.3 corrected)
- `/sys/kernel/debug/ec/ec0/io` — EC RAM oracle (read via EC I/O ports)
