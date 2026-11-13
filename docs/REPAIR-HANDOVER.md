# Repair handover — HP Pavilion Gaming 15-dk2xxx (board 88E4)

## GTX 1650 (TU117M) does not power up — board-level diagnosis and fix guide

| | |
|---|---|
| **Prepared** | 2026-11-13 |
| **Machine** | HP Pavilion Gaming Laptop, board `88E4`, SKU `5C1R5EA#A2N` |
| **BIOS / EC** | Insyde F.30 (2025-10-27) / EC 76.41 |
| **dGPU** | NVIDIA TU117M GTX 1650 Mobile `10de:1f9d`, subsystem `103c:88e4`, at `01:00.0` |
| **Root port** | Intel `8086:9a09` at `00:06.0` |
| **Companion report** | `docs/DIAGNOSIS.md` (full evidence) |
| **One-page shop card** | `docs/SHOP-ONE-PAGER.md` (print this for the bench) |
| **Status** | Hardware fault, localised to the dGPU power-enable / NVVDD rail |

---

## 0. One-page summary for the technician

**The GPU is not dead. The board is not switching on its core power rail.**

What has been proven by measurement:

- The GPU enumerates on PCIe, trains **Gen3 x4**, and its HDMI-audio function runs.
- Its always-on block answers: `NV_PMC_BOOT_0 = 0x167000A1` (TU117, rev A1).
- The platform executes the power-on sequence:
  - EC `DGPE = 1` (dGPU power enable),
  - ACPI GPIO `PWG0` is driven **high in D0** and **low in D3cold**.
- The GPU still does not come up:
  - EC `DGPS` (power good) stays **0**,
  - NVVDD does not come up (inferred from PROM/poison; confirm with the DMM),
  - VBIOS PROM reads `0x0000`,
  - core registers return `0xBADF5040` (unpowered core).

**Therefore the break is between the enable signals and the NVVDD rail.** It is
not a driver, Windows, BIOS-NVS, or VBIOS problem. The EC's RAM bit is set, but
its physical output pin is not yet measured — if the EC pin is the final VRM
enable, its firmware/output is still in scope.

### The three possible breaks

```
PCH GPIO group 9 pin 13  ──[ trace / series R / buffer ]──►  VRM EN
EC DGPE (EC RAM 0x1E.0)  ──[ EC pin / trace ]──────────────►  VRM / switch
                                                               │
                                                               ▼
                                                        NVVDD ~0.8 V
                                                               │
                                                               ▼
                                                        GPU core / VRAM / SPI
```

| # | Break | Likelihood | Fix |
|---|---|---|---|
| **B** | Open enable path (trace, series resistor, buffer, PCH ball, EC pin) | **Most likely**, given the EC repair | Reflow / jumper / replace the open component |
| **C** | VRM controller / MOSFET / PWM / feedback fault | Possible | Replace VRM IC / FETs |
| **D** | GPU-side short holds the rail down | Less likely (aux domain alive) | Isolate FET vs GPU; reball/replace only if proven |

### Prime suspects given the repair history

1. **Work around the replaced EC/IO chip** — a cut or missed trace, lifted pad,
   solder ball, or an incorrectly programmed EC. The fault appeared immediately
   after that repair; inspect and continuity-test the enable net first.
2. **dGPU VRM** — heat/rework damage, a shorted DrMOS/FET, or a cracked joint.
3. **GPU die** — least likely: the auxiliary domain enumerates, the always-on
   block answers, and the HDMI-audio function runs.

### First measurement — do this before anything else

**NVVDD → GND resistance, power off, AC and battery removed.**

- `< 0.5 Ω` → shorted rail. **Do not power on.** Go to D/C isolation.
- `0.5–10 Ω` → normal for a large core rail. Continue to voltage checks.
- `> 100 Ω` / OL → no short; continue to voltage checks.

Then: NVVDD voltage in D0 (expect **0.7–0.9 V**), then **VRM EN** and the GPIO
net. The decision table is in §6.

> **Do not** reinstall drivers, reflash the BIOS, patch ACPI NVS, or replace the
> GPU/VRAM before the enable path and rail are measured. All of those have
> already been ruled out or would be wasted work.

---

## 1. Machine identification and photos to take

Record before disassembly:

- Board silkscreen model: `88E4` (confirm revision).
- EC marking and date code (the EC/IO chip was replaced by a previous shop).
- dGPU VRM area: inductors, controller IC, DrMOS/FETs, output capacitors.
- Any repair marks, flux residue, lifted pads, jumper wires, missing components
  around the EC and the GPU VRM.

Take clear, well-lit photos of:

1. Whole board, top and bottom.
2. EC area (both sides if accessible).
3. dGPU VRM area (inductors and controller).
4. GPU package and its decoupling capacitors.
5. Any area that looks reworked.

These photos are part of the handover and help if the repair is escalated.

---

## 2. What is already proven — do not repeat

| Check | Result | Evidence |
|---|---|---|
| GPU visible on PCIe | Yes, `01:00.0`, link Gen3 x4 | `lspci -vvv` |
| GPU audio function | Works, bound to `snd_hda_intel` | `01:00.1` |
| GPU always-on block | `0x167000A1` (TU117 A1) | BAR0 + 0x000 |
| Core partition | Poison `0xBADF5040`, unpowered | BAR0 + 0x010… |
| VBIOS PROM | `0x0000` (not `0xFF`) | BAR0 + 0x300000 |
| EC `DGPE` | `1` in D0, `0` in D3cold | EC RAM `0x1E` bit 0 |
| EC `DGPS` | **`0` in every state** | EC RAM `0x1D` bit 3 |
| ACPI GPIO `PWG0` | **`1` in D0, `0` in D3cold, `1` again** | `GGOV(PWG0)` |
| BIOS NVS `SGGP` | `1` (GPIO method enabled) | SANV `0x44A52DA2` |
| `PWG0` pin | `0x090B000D` = group 9, pin 13 | SANV `0x44A52DAA` |
| `RPBA` / `PVID` | `0xC0030000` / `0x8086` (valid) | SANV `0x44A52E47` |
| Drivers | 3 NVIDIA versions + nouveau all fail identically | Windows + Linux |

**Conclusion:** all software-visible enables are asserted. The missing item is
the physical rail. The EC output pin is the one enable that software cannot
confirm; measure it if the boardview shows it in the VRM enable path.

---

## 3. Power chain and signals to probe

| Signal | Where to probe | Expected in D0 | Expected in D3cold | Notes |
|---|---|---|---|---|
| PCH GPIO `PWG0` | PCH ball / net per boardview; pad register `0xFD6D0B20` | **3.3 V** (verify) | 0 V | ACPI `GGOV` proves the register toggles |
| EC `DGPE` | EC RAM `0x1E` bit 0; physical EC pin per EC datasheet | 1 | 0 | EC was replaced; inspect its work |
| `DGPS` | EC RAM `0x1D` bit 3; EC sense pin per datasheet | **1 after rail good** | 0 | If rail is good but `DGPS=0`, the sense path is broken |
| **NVVDD** | Output capacitor / inductor near GPU VRM | **0.7–0.9 V** | 0 V | The decisive rail |
| VDD_MEM (GDDR6) | Output capacitor near VRM | ~1.35 V | 0 V | Usually follows NVVDD |
| 1.8 V VDDIO | Test point per boardview | 1.8 V | 0 V | SPI/IO supply |
| 3.3 V aux | Test point per boardview | 3.3 V | 3.3 V | Present — GPU enumerates |
| 5 V | Test point per boardview | 5 V | 5 V | VRM input |

> **Important:** `GGOV` reads the pad register, not the voltage on the board.
> The pad register toggling is strong evidence, but the DMM/scope measurement at
> the pad/via is what proves the voltage actually leaves the PCH.

Two enables are asserted together in the ACPI sequence: the EC's `DGPE` and the
PCH GPIO `PWG0`. Which one lands on the VRM `EN` — or whether they are in
series — must be confirmed with the boardview and continuity. Probe both.

---

## 4. Tools and prerequisites

- DMM with 0.1 Ω / 1 mV resolution, fine probes.
- Oscilloscope or logic probe (for the pad/via and PWM).
- Hot air station, soldering iron, 0.1 mm jumper wire, flux, microscope.
- **Boardview / schematic for HP `88E4`** (Pavilion Gaming 15-dk2xxx). This is
  the single most useful document for the repair; source it before probing.
- Donor board of the same `88E4` revision, if a controller/EC is faulty.
- Thermal camera or freeze spray (for short isolation), current-limited bench
  supply.
- ESD protection.

**Safety:** remove AC and battery before resistance checks; discharge rails;
never inject voltage into NVVDD without a current limit.

---

## 5. Visual inspection first

Before any measurement:

1. Inspect the **EC area** for disturbed traces, lifted pads, solder balls,
   flux residue, or a misaligned EC. The EC/IO chip was replaced — this is the
   highest-risk area.
2. Inspect the **dGPU VRM area** for burnt/missing components, cracked
   inductors, damaged FETs, or rework.
3. Check board flex/cracks near the hinge and around the EC.
4. Check that the dGPU enable net (per boardview) is continuous from the PCH
   ball / EC pin to the VRM `EN`.
5. Look for a missing series resistor or buffer on the enable line — a common
   casualty of board rework.

If the boardview is unavailable, trace continuity from the VRM `EN` pin
backwards; the first component it reaches is the series element (resistor,
buffer, or via).

---

## 6. Measurement procedure and decision table

### Step 1 — resistance, power off

Short the probes, note lead resistance, subtract it.

| Measurement | Normal | Short | Open |
|---|---|---|---|
| NVVDD → GND | 0.5–10 Ω | `< 0.5 Ω` | `> 100 Ω` / OL |
| VDD_MEM → GND | few Ω–tens of Ω | `< 0.5 Ω` | OL |
| 1.8 V → GND | tens of Ω–kΩ | `< 5 Ω` | OL |
| 3.3 V aux → GND | tens of Ω–kΩ | `< 5 Ω` | OL |

- **NVVDD `< 0.5 Ω`** → do not power on. Go to §7-D (short isolation).
- Otherwise continue.

### Step 2 — NVVDD voltage, powered, GPU in D0

```bash
echo on > /sys/bus/pci/devices/0000:01:00.0/power/control
cat /sys/bus/pci/devices/0000:01:00.0/power_state    # expect D0
```

| NVVDD reading | Meaning | Next |
|---|---|---|
| **0.7–0.9 V** | Rail is alive | §7-E: GPU-side / SPI / reset / VBIOS |
| ~0 V | Rail never comes up | Step 3 |

### Step 3 — EN at the VRM vs the GPIO pad

Measure the VRM `EN`/`ENABLE` pin and the enable net at the pad/via side.

| EN at VRM | Pad / net side | Conclusion | Action |
|---|---|---|---|
| **≥ 1.8 V** | — | EN reaches the VRM, rail still dead → **C** | §7-C: VRM/FET/PWM |
| ~0 V | **3.3 V** | Open between pad and VRM → **B** | §7-B: trace/R/buffer |
| ~0 V | ~0 V | Pad not driving, or net shorted low → **B upstream** | Check PCH ball/pad, scope the pad; §7-B |
| ~0 V | ~0 V, but `GGOV=1` | Readback vs pin discrepancy | Inspect PCH ball/pad, series element |

If the boardview shows the **EC pin** in the enable path, measure it as well:

- EC pin high, EN low at the VRM → open trace between EC and VRM (**B**).
- EC pin low while `DGPE = 1` → EC output/firmware problem (**B**, EC-side).

### Step 4 — if EN is dead at both ends

Scope the PCH ball/via and the EC pin. `GGOV` proves the register toggles; a
failed PCH ball, missing bypass, or damaged pad can still prevent the voltage
from leaving the chip. This is still fault **B**, just upstream of the trace.

### Step 5 — if NVVDD is present but the GPU still fails

- Check **1.8 V VDDIO** and the **SPI flash supply**.
- Check the GPU reset signal (per boardview) and the PCIe reset.
- Re-read the VBIOS: a real image starts `55 AA` and contains `NVIDIA` /
  `TU117`.
- If VBIOS is still `0x0000` with NVVDD present, the SPI/flash domain or its
  supply is the next suspect.

---

## 7. Repair actions by result

### 7-B — Open enable path (most likely)

1. Use the boardview to identify the net from the PCH GPIO / EC pin to the VRM
   `EN`. Likely names: `DGPU_PWR_EN`, `GPU_PWR_EN`, `NV_PWR_EN`, `PEX_PWR_EN`,
   `DGPU_VRM_EN`.
2. Check continuity end-to-end. The first series component (0 Ω resistor,
   ferrite, buffer/level shifter) is the prime suspect.
3. Inspect around the replaced EC and along the board edge for a cut trace,
   lifted pad, or cold joint.
4. If the EC pin is in the enable path: measure it. `DGPE = 1` in EC RAM does
   **not** prove the pin is high. If the pin stays low, the replacement EC's
   firmware/board data is suspect — verify the EC part/firmware, or replace it
   with a correctly programmed unit.
5. Repair with a 0.1 mm jumper wire, reflow the series component, or replace
   the buffer/level shifter.
6. Re-check continuity and the voltage at both ends before applying power.
7. **Do not** hard-wire the enable permanently to 3.3 V unless the boardview
   confirms it is a simple static enable and the rail sequencing is safe.

### 7-C — VRM fault (EN present, no NVVDD)

1. Identify the dGPU VRM controller near the inductors. Record its marking;
   common mobile controllers are uPI `uP9512`/`uP9511` and MPS `MP2949A`, with
   `MP86941`/`MP86945`-class DrMOS — **verify against the boardview and the
   actual markings, do not guess.**
2. Check the controller's `VIN`, `VCC`, `EN`, `PWM`, feedback divider, current
   sense, and bootstrap components.
3. Check for a shorted high-side/low-side FET or DrMOS. Remove the FET to
   isolate the rail from the GPU if needed.
4. Replace the controller/DrMOS/FET, or reball if a joint is cracked.
5. Check output capacitors and the inductor for damage.
6. Power up with a current-limited supply first; confirm NVVDD before
   connecting the GPU load if the FET was replaced.

### 7-D — Shorted NVVDD (D or C)

1. With power off, confirm `< 0.5 Ω` on NVVDD.
2. Use a current-limited injection (≤1 V, low current) and a thermal camera or
   freeze spray to locate the hot component.
3. Remove the suspect DrMOS/FET and re-measure. If the short clears, the FET
   was the fault (**C**).
4. If the short remains after removing the FET, the GPU die or its decoupling
   is the fault (**D**). Reball/replace the GPU only if the board is otherwise
   economically repairable; otherwise replace the motherboard.
5. **Do not** power on with a confirmed short.

### 7-E — Rail alive, GPU still not initialising

- Check 1.8 V VDDIO, SPI supply, and the GPU reset.
- Read the VBIOS: `55 AA` + `NVIDIA` / `TU117` strings. If empty, repair the
  SPI/flash supply or reflash the VBIOS with the correct 88E4 image.
- Check the PCIe reset and the root-port link.
- Only then consider GPU reball/replacement.

---

## 8. Post-repair acceptance test

### Electrical

- NVVDD = **0.7–0.9 V** in D0, 0 V in D3cold.
- VDD_MEM ≈ 1.35 V, 1.8 V VDDIO = 1.8 V, 3.3 V aux = 3.3 V.
- EC `DGPS = 1` when the rail is good; `DGPE = 1` in D0.
- PCH GPIO `PWG0` = high in D0, low in D3cold.

### Linux (this machine)

```bash
lspci -nnk -s 01:00
cat /sys/bus/pci/devices/0000:01:00.0/power_state        # D0
sudo lspci -vvv -s 01:00.0 | grep -A2 'LnkSta'           # Gen3 x4
sudo sh -c 'echo 1 > /sys/bus/pci/devices/0000:01:00.0/rom'
sudo cat /sys/bus/pci/devices/0000:01:00.0/rom | head -c 2 | xxd   # 55 aa
sudo python3 ~/gpu/ec.py                                  # DGPS=1, DGPE=1
```

`nouveau` or the NVIDIA driver must load without `bios ctor failed: -22`.

### Windows

- Device Manager: no Code 43; GPU listed normally.
- `nvidia-smi` reports the GPU and driver version.
- Run a GPU stress test (FurMark/OCCT) for 15–30 minutes; watch temperatures and
  rail stability.
- Verify keyboard, fan control, battery charging, and audio still work (the EC
  controls all of them).

---

## 9. Parts and donor-board guidance

- **Boardview/schematic for `88E4`** is required for a reliable repair.
- **Donor board:** same `88E4` revision. If the EC is faulty, the donor EC must
  carry the correct firmware/board data; a generic EC may reproduce the fault.
- **VRM controller/DrMOS:** match the exact marking on the board. Do not
  substitute a different controller without checking the feedback and current
  sense network.
- **Motherboard replacement:** if the GPU is shorted or the board is not
  economically repairable, a known-good `88E4` board is the fallback. Keep the
  SSD/RAM and verify the replacement board's BIOS/EC pairing.

---

## 10. What not to do

- Do **not** reinstall or downgrade the NVIDIA driver again.
- Do **not** reflash the BIOS or patch ACPI NVS; `SGGP=1`, `PWG0` and `RPBA`
  are correct.
- Do **not** replace the GPU or VRAM before proving the rail and enable path.
- Do **not** power on if NVVDD → GND is `< 0.5 Ω`.
- Do **not** inject voltage into NVVDD without a current limit.
- Do **not** assume the previous EC replacement is good; inspect it first.
- Do **not** hard-wire the enable to 3.3 V without boardview confirmation.

---

## 11. Handover checklist / measurement log

Fill this in and return it with the laptop.

| Item | Value / result |
|---|---|
| Date / technician | |
| Board revision / serial | |
| BIOS / EC version | |
| Visual findings (EC area) | |
| Visual findings (VRM area) | |
| NVVDD → GND resistance (Ω, lead-corrected) | |
| VDD_MEM → GND resistance | |
| 1.8 V → GND resistance | |
| 3.3 V → GND resistance | |
| NVVDD voltage in D0 (V) | |
| VDD_MEM voltage (V) | |
| 1.8 V VDDIO (V) | |
| 3.3 V aux (V) | |
| VRM EN voltage (V) | |
| Pad/net voltage at GPIO side (V) | |
| EC `DGPE` / `DGPS` | |
| Continuity of enable net | |
| Component replaced / reworked | |
| Result (pass/fail) | |
| Notes / photos | |

**Minimum data to report back:** NVVDD resistance with power off, NVVDD voltage
in D0, and EN voltage at the VRM and at the pad. Those three separate B, C and
D unambiguously.

---

## 12. Evidence appendix

### Key measured values

```
GPU              10de:1f9d  TU117M A1   subsystem 103c:88e4
Root port        8086:9a09  at 00:06.0
BAR0 + 0x000     0x167000A1
BAR0 + 0x010..   0xBADF5040  (unpowered core)
PROM 0x52300000  0x00000000  (not 0xFF)
EC 0x1D          0x00        DGPS=0
EC 0x1E          0x01        DGPE=1
SANV SGGP        0x01
SANV PWG0        0x090B000D  group 9, pin 13
SANV PWA0        0x01        active-high
SANV RPBA        0xC0030000
SANV PVID        0x8086
GPC0(PWG0)       0x84000201  PMODE=0 (GPIO)
GGOV(PWG0)       D0=1, D3cold=0, D0=1
```

### Addresses

```
0xFE0B0800   PECM window (EC RAM)
0xFE0B081D   DGPS/DGRS/BCDG/NGPS/FBST
0xFE0B081E   DGPE/DGHR/FBPC/EC6I/EC6O/GC6E/RG12
0x44A52D18   SANV ACPI NVS base
0x44A52DA2   SGGP
0x44A52DAA   PWG0
0x44A52E47   RPBA
0xFD6D0B20   GPIO group 9 pin 13 pad DW0 (software address)
```

### Files

| File | Contents |
|---|---|
| `docs/DIAGNOSIS.md` | Full technical report and evidence |
| `docs/REPAIR-HANDOVER.md` | This document |
| `sanv_result.txt` | SANV/GPIO measurements |
| `ec.py`, `dgpe_test.py` | EC state oracle and DGPE toggle test |
| `readphys.py` | BAR0/PROM physical reads |
| `sanv_mod/` | Read-only ACPICA NVS reader |
| `notes/memory.md` | Continuity notes |

---

## 13. Plain-language summary (for the customer)

> The graphics chip itself is not dead — the laptop can see it on the PCIe bus
> and its audio function works. The problem is that the board does not appear to
> switch on the GPU's main power rail (NVVDD), even though the enable signals are
> being sent. The fault is in the board-level enable path or the voltage
> regulator, most likely around the area that was reworked when the EC chip was
> replaced. A repair shop should measure the rail resistance, the rail voltage,
> and the regulator's enable pin; that will identify the exact component. No
> software, driver, or BIOS change will fix it.

---

## 14. Handover terms — agree before work starts

Give the shop this document **and** `docs/DIAGNOSIS.md`. Ask them to:

1. Confirm they have a **boardview/schematic for HP `88E4`** (or an equivalent
   donor board) before probing.
2. Record the four key values **before any rework**:
   NVVDD resistance (power off), NVVDD voltage (D0), VRM EN voltage, and the
   voltage on the GPIO/EC side of the enable net.
3. Photograph the EC area and the enable path before and after rework.
4. Diagnose first, quote second: no parts replacement until the open/VRM/short
   branch is identified.
5. State the warranty on the rework (especially around the replaced EC).
6. Confirm the fallback: if board-level repair is not economic, what is the
   price of a known-good `88E4` motherboard, and is the EC/BIOS pairing
   guaranteed?
7. **Not** reflash the BIOS, reinstall drivers, or patch ACPI NVS — those are
   already ruled out.

### Suggested cover note

> This laptop's GTX 1650 enumerates on PCIe and its audio function works, but the
> dGPU core rail never comes up. The platform asserts the EC `DGPE` bit and the
> ACPI power GPIO, but `DGPS` stays 0. The fault is board-level, between the
> enable signals and NVVDD. Please measure NVVDD resistance with power off,
> then NVVDD and the VRM EN voltage with the GPU in D0, and record the values.
> Do not reflash the BIOS or replace the GPU before those measurements. Full
> evidence is in the attached report.
