# GTX 1650 (TU117M) power-rail diagnosis — HP Pavilion Gaming 15-dk2xxx (board 88E4)

A board-level diagnosis of a laptop whose NVIDIA GTX 1650 enumerates on PCIe but
never powers up, after an EC/IO chip replacement and a BIOS rewrite.

**Verdict: the GPU is not dead. The board does not bring up its core power
rail.** The platform asserts the enables — EC `DGPE = 1`, ACPI GPIO `PWG0` high
in D0 — but the EC never reports power good (`DGPS = 0`), NVVDD never comes up,
and the VBIOS PROM reads `0x0000`.

The fault is between the enable signals and the NVVDD rail:

1. **Enable path** — open trace, series resistor, buffer, PCH pad, or EC output
   pin. Prime suspect: work around the replaced EC/IO chip.
2. **VRM** — controller, DrMOS/FET, PWM, feedback.
3. **GPU-side short** — least likely; the auxiliary domain is alive.

---

## Measured evidence

| Item | Value |
|---|---|
| dGPU | `10de:1f9d` TU117M, subsystem `103c:88e4`, at `01:00.0` |
| PCIe link | Gen3 x4, config space readable, audio function works |
| Always-on block | `NV_PMC_BOOT_0 = 0x167000A1` |
| Core partition | `0xBADF5040` poison (unpowered) |
| VBIOS PROM | `0x0000` (not erased `0xFF`) |
| EC `DGPE` | `1` in D0, `0` in D3cold |
| EC `DGPS` | `0` in every state |
| ACPI GPIO `PWG0` | high in D0, low in D3cold, high again in D0 |
| BIOS NVS `SGGP` | `1` — the GPIO method is enabled |
| `PWG0` pin | `0x090B000D` = group 9, pin 13 |
| `RPBA` / `PVID` | `0xC0030000` / `0x8086` — valid root port |

The GPIO register toggles correctly, so the firmware is doing its job. The
break is physical, downstream of the enable.

---

## Start here

| Document | Audience |
|---|---|
| [`docs/SHOP-ONE-PAGER.md`](docs/SHOP-ONE-PAGER.md) | Printable bench card: measurements, decision table, accept criteria |
| [`docs/REPAIR-HANDOVER.md`](docs/REPAIR-HANDOVER.md) | Full shop-facing diagnosis and repair guide |
| [`docs/DIAGNOSIS.md`](docs/DIAGNOSIS.md) | Technical report and evidence trail |

The decisive measurements, in order:

1. **NVVDD → GND resistance**, power off, lead-corrected.
   `< 0.5 Ω` = short (do not power on); `0.5–10 Ω` = normal.
2. **NVVDD voltage in D0** — expect `0.7–0.9 V`.
3. **VRM EN vs the enable net** — EN ≥ 1.8 V with no rail = VRM; EN 0 V with a
   high pad/EC side = open enable path.

---

## Repository layout

```
docs/            diagnosis, repair handover, one-page shop card
notes/           continuity notes
sanv_mod/        read-only ACPICA module used to read BIOS NVS
*.py             EC / MMIO / GPIO diagnostic helpers
lspci-*.txt      PCIe config/link dumps
FINDINGS.md      raw consolidated findings
sanv_result.txt  SANV and GPIO measurement record
```

The scripts are read-only unless stated otherwise. `dgpe_test.py` performs the
one controlled EC write used in the diagnosis and restores the original value.

---

## Scope and safety

This is a diagnosis of one specific machine, not a universal fix. The ACPI
addresses, EC fields, and GPIO pin are specific to this board and firmware.

- Do **not** write EC bytes other than the documented `DGPE` bit.
- Do **not** patch BIOS NVS — the measured values are already correct.
- Do **not** reflash the BIOS or reinstall drivers; both were ruled out.
- Do **not** power on with a confirmed NVVDD short.

The remaining step is physical: measure the rail and the enable path with a
multimeter, then repair the open trace or the VRM.

---

## Status

Unresolved hardware fault, localised to the dGPU power path. No warranty; use at
your own risk.
