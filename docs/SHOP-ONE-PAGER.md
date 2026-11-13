# SHOP CARD — HP Pavilion Gaming 15-dk2xxx / board 88E4

## GTX 1650 (TU117M) does not power up

**Machine:** HP Pavilion Gaming Laptop, board `88E4`, BIOS F.30, EC 76.41
**GPU:** `01:00.0` NVIDIA `10de:1f9d` (TU117M), audio `01:00.1`

---

## What is proven

- GPU enumerates, **Gen3 x4**, audio function works, `BOOT_0 = 0x167000A1`.
- Platform asserts the enables: EC `DGPE = 1`, ACPI GPIO `PWG0` high in D0.
- Rail still dead: EC `DGPS = 0`, VBIOS PROM `0x0000`, core poison `0xBADF5040`.
- **Not** a driver / BIOS / VBIOS / ACPI-NVS problem. Do not reflash or
  reinstall.

**Fault is board-level, between the enable signals and NVVDD.**
Prime suspect: work around the replaced EC/IO chip, then the dGPU VRM.

---

## Measure in this order

### 1. NVVDD → GND resistance — power off, AC + battery removed

| Reading (lead-corrected) | Meaning |
|---|---|
| `< 0.5 Ω` | Shorted rail — **do not power on** |
| `0.5–10 Ω` | Normal — continue |
| `> 100 Ω` / OL | No short — continue |

### 2. NVVDD voltage — powered, GPU in D0

`0.7–0.9 V` → rail alive. `0 V` → step 3.

### 3. VRM EN and GPIO/EC side

| EN at VRM | Enable net / pad | Conclusion |
|---|---|---|
| ≥ 1.8 V | — | VRM/FET fault (**C**) |
| ~0 V | 3.3 V | Open trace/R/buffer (**B**) |
| ~0 V | ~0 V | PCH pad or EC pin not driving (**B**) |

If the boardview shows the EC pin in the enable path, measure it too:
EC pin low while `DGPE = 1` → EC output/firmware (**B**).

---

## Fix by result

- **B — open enable path:** trace from PCH GPIO / EC pin to VRM `EN`; check
  series resistor, buffer, via, lifted pad. Jumper/reflow/replace. Inspect the
  EC rework area first. Do not hard-wire 3.3 V without boardview confirmation.
- **C — VRM fault (EN present, no NVVDD):** check controller `VIN`, `VCC`,
  `EN`, PWM, feedback, DrMOS/FETs, inductor, caps. Replace faulty IC/FET.
- **D — shorted NVVDD:** current-limited injection + thermal camera; remove
  FET to isolate. FET short = C; GPU short = D (reball/replace or board swap).

---

## Do not

- Do not reinstall drivers, reflash BIOS, or patch ACPI NVS.
- Do not replace the GPU/VRAM before proving the rail and enable path.
- Do not power on with NVVDD → GND `< 0.5 Ω`.
- Do not assume the previous EC replacement is good.

---

## Accept when

- NVVDD `0.7–0.9 V` in D0, 0 V in D3cold.
- EC `DGPS = 1`, `DGPE = 1` in D0.
- VBIOS reads `55 AA` + `NVIDIA` / `TU117`.
- Linux/Windows driver loads; no Code 43; stress test passes.

---

## Report back

1. NVVDD resistance (power off, lead-corrected).
2. NVVDD voltage in D0.
3. EN voltage at the VRM.
4. EN voltage at the pad/EC side.
5. Photos of the EC area and enable path, before/after.

Full evidence: `docs/DIAGNOSIS.md`. Full guide: `docs/REPAIR-HANDOVER.md`.
