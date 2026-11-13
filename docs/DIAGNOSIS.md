# GTX 1650 (TU117M) does not power up — diagnostic report

| | |
|---|---|
| **Date** | 2026-11-12 (report written 2026-11-13; NVS/GPIO update 2026-11-13) |
| **Host** | HP Pavilion Gaming Laptop, board `88E4`, SKU `5C1R5EA#A2N` |
| **Firmware** | Insyde BIOS F.30 (2025-10-27), EC 76.41 |
| **OS** | Kali GNU/Linux Rolling 2026.3, kernel `7.1.5+kali-amd64` |
| **dGPU** | `0000:01:00.0` NVIDIA TU117M [GTX 1650 Mobile / Max-Q] `10de:1f9d` rev a1, subsystem `103c:88e4` |
| **Root port** | `0000:00:06.0` Intel 11th Gen PCIe controller `8086:9a09` |
| **Status** | Unresolved — fault localised downstream of the ACPI GPIO enable; the enable line is driven high, the rail still does not come up |
| **Repair guide** | `docs/REPAIR-HANDOVER.md` (shop-facing fix guide) |

---

## 1. Verdict

> **The GPU's auxiliary domain is alive. Its core / VRAM / SPI domain never
> powers up. The EC accepts the "power on" request (`DGPE = 1`), the ACPI GPIO
> enable (`PWG0`) is driven high in D0 and released in D3cold, but the rail
> never comes up and never reports power good (`DGPS` stays `0`).**

The fault is **downstream of the ACPI GPIO enable**. It is not a driver,
kernel, ACPI, BIOS-NVS, VBIOS, or EC-window problem. The BIOS-NVS / `SGGP`
hypothesis is disproven by measurement: `SGGP = 1`, `PWG0` is a valid pin, and
`RPBA`/`PVID` are valid (see §4.9).

Three candidates remain, and only a multimeter can separate them:

1. **B — GPIO / EC → VRM enable path** (open trace, series resistor, dead
   buffer, or an EC output pin that does not drive; the PCH pad itself toggles
   correctly, but the EC pin is not measured).
2. **C — VRM / MOSFET / PWM** (rail does not start even with EN present).
3. **D — GPU-side** (shorted NVVDD making the VRM hiccup, or reset held) —
   currently folded into C until the resistance check.

**Do not replace the GPU or VRAM.** The die enumerates, trains a Gen3 x4 link,
answers on its always-on block, and its HDMI-audio function runs.

---

## 2. Symptom and history

The laptop's keyboard was repaired at a shop. The repair replaced the **EC / IO
chip** and rewrote the **BIOS**. Since then the GTX 1650 has been dead.

Windows-side evidence (read-only, collected before this Linux session):

| Item | Value |
|---|---|
| Device status | Code 43 (`CM_PROB_FAILED_POST_START`), ProblemStatus `0xC0000490` (`STATUS_DEVICE_POWERED_OFF`) |
| Power state | **D3** — never leaves it |
| PCIe link | Gen3 **x4** (max x16, platform-limited) |
| Sibling function | `01:00.1` HDMI audio, status OK, **D1** |
| Driver stack | `\Driver\ACPI,\Driver\pci` — `nvlddmkm` never attaches |
| Drivers tried | HP 27.21.14.6230 (462.30), 32.0.15.9191, 32.0.16.1088 — all fail identically |
| BIOS / EC | F.30 (was F.21) / 76.41 |
| DMI | Product name generic, **Feature Byte blank**, board CT placeholder `12222334455666` |
| `DEVPKEY_PciDevice_D3ColdSupport` | 258 |

The blank Feature Byte is a real DMI/board-data defect, but it did **not**
leave the dGPU power GPIO unconfigured: `SGGP = 1` and `PWG0 = 0x090B000D`
are correct (§4.9). It may matter for other board functions; it is not the
cause of this fault.

---

## 3. Method

1. **Read-only first.** Identity, config space, link state, kernel log, ACPI
   tables, EC RAM.
2. **Controlled writes only.** The only byte written was `0xFE0B081E` (the EC
   `DGPE` bit). The original value was restored every time. No other EC byte was
   modified.
3. **Correct oracle.** EC state was read through the EC's own I/O interface
   (`/sys/kernel/debug/ec/ec0/io`, ACPI EC transactions on ports `0x62/0x66`),
   **not** through the memory window — the window's read path is intermittent
   (see §4.8).
4. **Negative controls.** Every positive result was paired with a check that the
   expected *non*-effect did not occur (for example, EC RAM diff across `DGPE`
   cycles).

All addresses below are physical unless stated otherwise.

---

## 4. Measurements

### 4.1 The device enumerates and trains a link

```
0000:01:00.0  10de:1f9d  rev a1  subsystem 103c:88e4
0000:01:00.1  10de:10fa          NVIDIA HDMI audio, bound to snd_hda_intel
```

| Property | Value |
|---|---|
| `power_state` | **D0** |
| `power/runtime_status` | active |
| `current_link_speed` | 8.0 GT/s (Gen3) |
| `current_link_width` | **x4** |
| `d3cold_allowed` | 1 |
| PM capability | `PME(D0+,D1-,D2-,D3hot+,D3cold-)` → **no D3cold PME** |
| Expansion ROM BAR | `53080000`, 512 KB, disabled |

BARs: `BAR0` 16 MB @ `0x52000000`, `BAR1` 256 MB @ `0x6000000000`,
`BAR3` 32 MB @ `0x6010000000`.

The link training to x4 is the platform maximum (root port `LnkCap` is x4), not
a degradation caused by the fault. AER reports no uncorrected errors.

### 4.2 The always-on block answers; the core partition does not

Read through `/dev/mem` (`~/gpu/readphys.py`):

| Address | Value | Meaning |
|---|---|---|
| `BAR0 + 0x000` | `0x167000a1` | `NV_PMC_BOOT_0` = TU117, rev A1. **The GPU is there and its always-on block works.** |
| `BAR0 + 0x010 … 0x020` | `0xBADF5040` repeated | NVIDIA poison marker — core partition unpowered / not clocked |
| `BAR0 + 0x300000` (PROM, phys `0x52300000`) | `0x00000000` | ROM aperture decodes but returns zeros |

The PROM returning `0x00` rather than `0xFF` is important: erased flash reads
`0xFF`, a bus that does not respond reads `0xFF`, but zeros are a **real
response from an unpowered/unclocked SPI domain**.

> ASSUMPTION: `0xBADF5040` is NVIDIA's "core partition not powered" response.
> It is vendor-undocumented but consistent with every other measurement and with
> nouveau's failure mode.

### 4.3 Nouveau independently reaches the same conclusion

```
nouveau 0000:01:00.0: NVIDIA TU117 (167000a1)
nouveau 0000:01:00.0: gsp: RM version: 570.144
nouveau 0000:01:00.0: bios: trying PRAMIN...   ... not enabled
nouveau 0000:01:00.0: bios: trying PROM...     ROM signature (0000) unknown
nouveau 0000:01:00.0: bios: trying ACPI...     (no image)
nouveau 0000:01:00.0: bios: trying PCIROM...   expecting 0xaa55, got 0x0000
nouveau 0000:01:00.0: bios: trying PLATFORM... (no image)
nouveau 0000:01:00.0: bios ctor failed: -22
```

Nouveau sees the chip identity, but every VBIOS source is empty. This is a
*consequence* of the dead rail, not a cause.

### 4.4 The ACPI power path is present and correct

From the real tables (`~/gpu/acpi/dsdt.dsl`, `SSDT18.dsl`):

```
PECM  OperationRegion (SystemMemory, 0xFE0B0800, 0x1000)    # DSDT line 80282
      DGPE field at byte 0x1E, bit 0                        # DSDT line 80339

PCRP._ON   ->  If (OSYS != 0x07D9) { DGPE = 1 ... }         # SSDT18 line 74
PCRP._OFF  ->  DGPE = 0
PEGP._PS0  ->  IR3D(), NVD0()
PEGP._PS3  ->  NVD3()
GC6I/GC6O  ->  DGPE = 0/1 with sleeps
GPS_       ->  reads RG12/SPBI, computes DGPS
```

**The firmware's software sequence is intact.** `OSYS != 0x07D9` is the Windows
branch; Linux takes a different `OSYS` value, which is why the Linux state can
differ from Windows (see §4.7) — and that difference itself points at the
platform power path, not at the GPU.

### 4.5 Live EC state — measured through the EC I/O oracle

| Byte | Bit | Field | Value |
|---|---|---|---|
| `0x1D` | 3 | `DGPS` (dGPU power status) | **0** |
| `0x1D` | 4 | `DGRS` | 0 |
| `0x1D` | 2 | `BCDG` | 0 |
| `0x1D` | 1 | `NGPS` | 0 |
| `0x1D` | 0 | `FBST` | 0 |
| `0x1E` | 0 | **`DGPE` (dGPU power enable)** | **1** |

Raw bytes: `0x1D = 0x00`, `0x1E = 0x01`. Re-verified at multiple points in the
session. The EC has been told to power the GPU, and it shows no power-good.

### 4.6 Direct `DGPE` toggle — the decisive software test

Script: `~/gpu/dgpe_test.py`. Writes go through the MMIO window; reads are
verified through EC I/O.

| Step | `0x1E` via EC I/O | `DGPS` |
|---|---|---|
| before | `0x01` | 0 |
| write `0x00` to `0xFE0B081E` | `0x00` — **the write lands** | 0 |
| poll every second, 10 s | `0x00` | **0 at every poll** |
| write `0x01` back | `0x01` | 0 |

Three full off/on cycles gave the same result: **`DGPE` toggles, `DGPS` never
leaves 0.**

### 4.7 The complete ACPI sequence also fails

```
echo auto > .../0000:01:00.0/power/control
    -> D3cold, BAR0 = 0xffffffff, DGPE = 0      (_PS3/_OFF ran)

echo on  > .../0000:01:00.0/power/control
    -> D0, BOOT_0 = 0x167000a1, DGPE = 1        (_PS0/_ON ran)
```

After the full `_ON`: **`DGPS` still 0, PROM still `0x0000`, BAR0 still
poisoned.** The firmware executed correctly and the hardware did not follow.

### 4.8 Cross-checks and negative controls

**The dGPU enable *is* a PCH GPIO.** The earlier pad diff across D3cold → D0
did not capture this pad; its "no TX change" result is not evidence against a
PCH GPIO. The actual enable is group 9 pin 13, and its `GGOV` value follows the
power state exactly (`1 → 0 → 1`, §4.9). The EC's `DGPE` is a parallel signal,
not the only enable.

**The EC exposes no status mirror.** Diffing EC RAM across three `DGPE` cycles:
**no byte tracks `DGPE`**. There is no ADC/status register to read the rail
state from.

**The EC window is a good write path but an unreliable read path.** The 4 KB
window at `0xFE0B0000` decodes, and a dump (`~/gpu/ecwin.bin`) matched live EC
RAM at `0x800..0x8FF` in 249/256 bytes. But later the same window read all
zeros while EC I/O still reported `0x1E = 0x01`; it became coherent again later.
It behaves like a banked/shadowed view. **Never use window reads as evidence;
use EC I/O.** Writes demonstrably land.

### 4.9 BIOS NVS and ACPI GPIO — measured (2026-11-13)

A later hypothesis claimed `SGGP = 0` in BIOS NVS disables `HGPO`, so the dGPU
power GPIO is never driven. That was checked directly.

The NVS page is not reachable through `/dev/mem` (`EPERM`) or `/proc/kcore`
(the direct map skips the ACPI-NVS range), so it was read through ACPICA's own
exported mapping (`acpi_os_map_memory`) from a read-only module
(`~/gpu/sanv_mod/`). No writes were made.

| Field | Address | Value | Meaning |
|---|---|---|---|
| `HGMD` | `0x44A52DA0` | `0x02` | hybrid-graphics mode 2 |
| `SGGP` | `0x44A52DA2` | **`0x01`** | GPIO method **enabled** |
| `PWE0` | `0x44A52DA9` | `0x00` | |
| `PWG0` | `0x44A52DAA` | **`0x090B000D`** | GPIO group 9, pin 13 |
| `PWA0` | `0x44A52DAE` | `0x01` | active-high |
| `RPBA` | `0x44A52E47` | `0xC0030000` | root-port ECAM pointer |
| `PVID` | `RPBA + 0x00` | `0x8086` | valid Intel root port |
| `PDID` | `RPBA + 0x02` | `0x9A09` | valid root port |

So `HGPO()` is **not** a no-op and `CCHK()` does not bail: the BIOS-NVS /
board-data theory is false.

The pad itself was then checked:

- `PWG0` decodes to group 9, pin 13; pad DW0 at `0xFD6D0B20`.
- `GPC0(PWG0) = 0x84000201` → `PMODE` bits `7:4 = 0` (GPIO mode), TX not
  disabled.
- `GGOV(PWG0)` follows the power state exactly:

| GPU state | `GGOV(PWG0)` | `DGPE` | `DGPS` |
|---|---|---|---|
| D0 | **1** | 1 | 0 |
| D3cold | **0** | 0 | 0 |
| D0 again | **1** | 1 | 0 |

The enable line is asserted in D0 and released in D3cold. The platform is
doing exactly what `HGON()` / `HGOF()` ask; the rail still never reports power
good.

**Caveat:** `GGOV` reads the pad register, not the voltage at the VRM. A
broken trace after the pad would look identical. That is exactly what the
multimeter step (§7) resolves.

Note on a common mis-test: `setpci -s 00:06.0 0.w` returns `8086`, but `CCHK`
reads `PVID` through `RPBA` (an NVS pointer), not through the live root port.
The `setpci` check alone cannot rule that branch out; reading `RPBA` and
`PVID` (above) does.

---

## 5. Proven causal chain

```
ACPI _ON  /  direct DGPE write
        |
        v
DGPE = 1 in EC RAM                        [measured, EC I/O]
        |
        v
ACPI GPIO PWG0 driven high                [measured: GGOV=1 in D0, 0 in D3cold]
        |
        v
EC does not assert DGPS                   [measured, 3 cycles + 10 s poll]
EC does not enable NVVDD                  [inferred: PROM 0x0000, BAR0 poison]
        |
        v
GPU core / VRAM / SPI domain unpowered    [measured: PROM 0x0000, BAR0 0xBADF5040]
        |
        v
no VBIOS  ->  nouveau "bios ctor failed: -22"
no core   ->  nvidia driver init fails identically on 3 driver versions
```

Everything up to `GGOV(PWG0) = 1` is proven by measurement. Everything after
it is proven by the absence of `DGPS` and by the GPU's poisoned MMIO response.

---

## 6. Differential diagnosis

| # | Hypothesis | Prediction if true | How to prove |
|---|---|---|---|
| **B** | GPIO pad → VRM enable path open (trace, series resistor, buffer) | pad high (`GGOV=1`), EN low at the VRM | Probe the pad and the VRM EN pin |
| **C** | VRM / MOSFET / PWM fault | EN high at the VRM, no NVVDD | Probe EN and NVVDD |
| **D** | GPU-side short / reset held | NVVDD collapses or VRM hiccups; low resistance to GND | Resistance check with power off |

**A — ACPI NVS / board data is eliminated.** `SGGP = 1`, `PWG0` is a valid
pin, `RPBA`/`PVID` are valid, and the pad is in GPIO mode and toggles with the
power state (§4.9). No reflash or NVS patch is indicated.

**The EC's own firmware/GPIO configuration is *not* eliminated.** Only its RAM
bit (`DGPE = 1`) was read; the physical EC output pin was not measured. If the
EC pin is the final VRM enable, a wrong EC firmware/board configuration or a
damaged output belongs to **B** and must be probed. The EC was replaced by the
previous shop, so this is a live possibility.

The evidence now favours **B or C**. `GGOV` proves the pad is driven, but not
that the voltage reaches the VRM. **C remains possible** and is the reason for
the resistance check before powering on again.

---

## 7. The measurement that decides it

Do these in order. Record values, not conclusions.

1. **Power off; unplug AC and battery — NVVDD → GND resistance.**
   Probe an NVVDD output capacitor near the GPU VRM inductors; short the probes
   first and subtract lead resistance.
   - `< 0.2 Ω` → shorted rail (die or MOSFET). **Do not power on again.**
   - `0.5–5 Ω` → normal for a large core rail; a cheap DMM cannot call a fault
     here, continue.
2. **Power on, GPU runtime-resumed to D0 (`power/control = on`) — measure
   NVVDD.** Turing mobile core is typically `0.7–0.9 V`.
   - Present → rail is fine; fault is GPU-side (VBIOS/SPI, reset, die). Check
     1.8 V VDDIO and SPI flash supply.
   - Absent → step 3.
3. **Measure the VRM EN pin** (and the GPIO pad, group 9 pin 13, if reachable).
   - EN high (≥1.8 V), no NVVDD → **C** (VRM/MOSFET/PWM).
   - EN low at the VRM, pad high → **B** (open trace / series resistor / buffer).
   - EN low at both → the pad readback is not reaching the pin (**B**).
4. Only if EN is low at both: the board data is already proven correct, so this
   is a broken GPIO→VRM connection (**B**), not a firmware/config issue.

Also confirm: `NVVDD ~0.8 V`, `VDD_MEM ~1.35 V`, `1.8 V`, `3.3 V aux`, `5 V`.
If 3.3 V aux were missing the GPU would not enumerate at all — it does.

---

## 8. Ruled out

| Claim | Status | Evidence |
|---|---|---|
| NVIDIA driver bug | **Ruled out** | Three driver versions fail identically; Linux nouveau fails the same way |
| VBIOS erased / corrupt as root cause | **Ruled out** | PROM reads `0x00`, not `0xFF`; zero is a consequence of the dead SPI domain |
| ACPI `_PS0` / `PCRP._ON` broken | **Ruled out** | `_ON` runs, `DGPE` goes 1, BAR0 comes back after D3cold→D0 |
| BIOS-NVS / `SGGP` gate disables the GPIO | **Ruled out** | `SGGP=1`, `PWG0=0x090B000D`, `RPBA`/`PVID` valid (§4.9) |
| ACPI GPIO never driven | **Ruled out** | `GGOV(PWG0)=1` in D0, `0` in D3cold (§4.9) |
| EC shared-memory window dead | **Ruled out** | Window decodes; 4 KB dump matches EC RAM 249/256 bytes |
| PCH GPIO is the dGPU enable | **Confirmed** | Group 9 pin 13; `GGOV` tracks D0/D3cold; `PMODE=0` (GPIO) (§4.9) |
| PCIe link / root port fault | **Ruled out** | Gen3 x4 trained, no AER uncorrected errors, config space readable |
| Dead GPU die | **Unlikely** | `BOOT_0 = 0x167000a1`, HDMI audio runs, config space answers |
| Dead EC entirely | **Unlikely** | EC I/O transactions work, `DGPE` writes land, `0x1D/0x1E` state coherent |

---

## 9. Corrections to earlier session notes

Two earlier conclusions and two later hypotheses were wrong and are retracted:

1. **"The EC shared-memory window is dead."** False. The window decodes at
   `0xFE0B0000`; the "all `0xFF`" reading was an artifact. However, its **read**
   path is intermittent — use EC I/O as the oracle.
2. **"The VBIOS is erased, that is why the ROM reads zero."** False. Erased
   flash reads `0xFF`; this reads `0x00`. The zero data is the unpowered
   flash/SPI domain, i.e. a symptom of the dead rail, not a cause.
3. **"The dGPU enable is not a PCH GPIO."** False. It **is** PCH GPIO group 9
   pin 13. `SGOV` drives it, `GGOV` reads it, and it follows D0/D3cold exactly
   (§4.9). The earlier pad diff looked at other pads and missed it.
4. **"SGGP = 0 / blank board data disables the power GPIO."** False.
   `SGGP = 1`, `PWG0 = 0x090B000D`, `PWA0 = 1`, `RPBA`/`PVID` valid (§4.9).
   Reflashing the BIOS or patching ACPI NVS is **not** indicated.

These corrections matter because each would have pointed at the wrong repair or
the wrong probe.

---

## 10. Software options — exhausted

- **SANV read: done (2026-11-13).** `/dev/mem` returns `EPERM` and
  `/proc/kcore` skips the ACPI-NVS range; ACPICA's exported
  `acpi_os_map_memory` works. Read-only module in `~/gpu/sanv_mod/`; values in
  §4.9 and `~/gpu/sanv_result.txt`.
- **ACPI GPIO read: done.** `GGOV`/`GPC0` through `acpi_call`: the pad is in
  GPIO mode and toggles with the power state.
- **`HGOP` (`DGPV`) read:** still blocked by the same NVS mapping issue. It
  would only confirm what `HGON` already proves — `HGON` runs and drives the
  GPIO. No decision depends on it.
- `acpidbg` unavailable (`CONFIG_ACPI_DEBUGGER` not set); `custom_method`
  unavailable (`CONFIG_ACPI_DEBUG` not set).

No software fix remains. In particular, do **not** patch `SGGP`/`PWG0` in NVS:
the measured values are already correct, and a blind write to NVS/GPIO is
risky.

---

## 11. Reproduce

Work folder: `~/gpu`. Root required for `/dev/mem`, EC debugfs, `lspci -xxx`.

```bash
# identity
uname -r
cat /sys/class/dmi/id/bios_version /sys/class/dmi/id/board_name
lspci -nnk -s 01:00

# GPU state
cat /sys/bus/pci/devices/0000:01:00.0/power_state
sudo lspci -vvv -s 01:00.0 | tee ~/gpu/lspci-gpu.txt

# BAR0 / PROM reads (physical MMIO)
sudo python3 ~/gpu/readphys.py 0x52000000 0x0 0x40      # BOOT_0 + poison
sudo python3 ~/gpu/readphys.py 0x52300000 0x0 0x40      # VBIOS PROM

# EC state (oracle)
sudo python3 - <<'PY'
with open('/sys/kernel/debug/ec/ec0/io','rb') as f:
    f.seek(0x1D); b1d = f.read(2)
print(f'0x1D=0x{b1d[0]:02x} 0x1E=0x{b1d[1]:02x} DGPS={(b1d[0]>>3)&1} DGPE={b1d[1]&1}')
PY

# full ACPI power cycle
echo auto | sudo tee /sys/bus/pci/devices/0000:01:00.0/power/control
cat /sys/bus/pci/devices/0000:01:00.0/power_state
echo on   | sudo tee /sys/bus/pci/devices/0000:01:00.0/power/control
cat /sys/bus/pci/devices/0000:01:00.0/power_state

# DGPE toggle test (restores the original value)
sudo python3 ~/gpu/dgpe_test.py

# BIOS NVS (read-only; /dev/mem is blocked for this page)
sudo insmod ~/gpu/sanv_mod/sanv_read.ko && sudo dmesg | grep sanv_read
sudo rmmod sanv_read

# ACPI GPIO state (read-only)
sudo modprobe acpi_call
printf '\\_SB.GGOV 0x090b000d\n' | sudo tee /proc/acpi/call >/dev/null
sudo cat /proc/acpi/call
```

**Do not** write any EC byte other than `0xFE0B081E` bit 0. That window also
holds fan, battery and keyboard state. **Do not** flash the BIOS from Linux.

---

## 12. Evidence index

| File | Contents |
|---|---|
| `~/gpu/FINDINGS.md` | Raw consolidated findings from the diagnostic session |
| `~/gpu/docs/DIAGNOSIS.md` | This report |
| `~/gpu/docs/REPAIR-HANDOVER.md` | Shop-facing diagnosis and repair guide |
| `~/gpu/lspci-gpu.txt` | Full `lspci -vvv` for `01:00.0` |
| `~/gpu/lspci-gpu-hex.txt` | 256-byte config-space dump |
| `~/gpu/lspci-audio.txt` | `01:00.1` audio function |
| `~/gpu/dmesg-acpi.txt`, `dmesg-full.txt` | Kernel log, ACPI/nouveau/PCIe |
| `~/gpu/acpi/dsdt.dsl`, `dsdt.aml` | DSDT; `PECM` @ line 80282, `DGPE` @ 80339 |
| `~/gpu/acpi/SSDT17.dsl` | `HGOP`, `GC6I/GC6O`, `GPS/NVOP` |
| `~/gpu/acpi/SSDT18.dsl` | `PCRP._ON/_OFF` @ line 74 |
| `~/gpu/ecwin.bin` | 4 KB EC window dump (coherent sample) |
| `~/gpu/ec.py`, `dgpe_test.py` | EC read/oracle and DGPE toggle test |
| `~/gpu/sanv_result.txt` | SANV NVS + GPIO measurements (2026-11-13) |
| `~/gpu/read_sanv.py` | `/dev/mem` SANV reader (documents the EPERM wall) |
| `~/gpu/sanv_mod/sanv_read.c` | Read-only ACPICA-mapped NVS module |
| `~/gpu/readphys.py`, `readnvs.py`, `kcore.py`, `padread.py` | MMIO / NVS / kcore / PCH-pad helpers |
| `~/gpu/notes/memory.md` | Short continuity notes |
| `/home/ankuha/Desktop/GPU_LINUX_RUNBOOK.md` | Original runbook |

---

## 13. Confidence

| Claim | Confidence | Basis |
|---|---|---|
| GPU enumerates and is not dead | **High** | Config space, `BOOT_0`, link trained, audio function bound |
| `DGPE = 1` and `DGPS = 0` | **High** | EC I/O reads, repeated; write verified |
| ACPI GPIO enable is asserted in D0 | **High** | `GGOV(PWG0)=1` in D0, `0` in D3cold, `1` again in D0 |
| BIOS NVS / `SGGP` is not the fault | **High** | `SGGP=1`, `PWG0` valid, `RPBA`/`PVID` valid (§4.9) |
| Fault is downstream of the ACPI GPIO | **High** | Enable toggles with power state; no `DGPS`, no PROM |
| Not a driver/ACPI/VBIOS/EC-window problem | **High** | Independent failures on Windows and Linux; `_ON` runs correctly |
| `0xBADF5040` = unpowered core partition | **Medium** | Vendor-undocumented but consistent (labelled ASSUMPTION) |
| B vs C vs D | **Unresolved** | Requires physical probes (§7) |

---

## 14. Bottom line

- The firmware power path is correct and executes: `PCRP._ON` → `DGPE = 1` →
  ACPI GPIO `PWG0` high.
- The enable line follows D0/D3cold, but the EC never asserts `DGPS` and NVVDD
  never comes up.
- The GPU's auxiliary domain is alive; its core/VRAM/SPI domain is not.
- **The next step is one physical measurement, not more software:** NVVDD
  resistance with power off, then NVVDD and VRM EN with `DGPE = 1`.
- BIOS NVS / `SGGP` is correct; do **not** reflash or patch NVS.
- Do **not** replace the GPU or VRAM. Do **not** reinstall drivers again. Do
  **not** flash the BIOS from Linux.

For a repair shop, the short version is:

> The platform drives the dGPU power-enable GPIO high (group 9 pin 13) and
> releases it on power-down, but the NVVDD rail never comes up and the EC never
> reports power good. Check the GPIO-to-VRM enable path and the VRM itself; the
> GPU die is not dead.
