# MissionPCB engineering design report

Single-lead ECG chest patch.

Sticks to the patient's chest with adhesive, worn continuously for up to 14
days — showers included, never removed. Two Ag/AgCl electrodes pick up the
biopotential; the patch records continuously and streams to the patient's phone
over BLE a few times a day.

Sealed enclosure, roughly 100 x 40 x 7 mm interior. Rechargeable — charged from
a cradle through a gasketed contact window. Must be thin enough to wear under a
shirt without catching. Shipping to a hospital pilot; it will go through a
regulatory review we do not control.


## Wearable budgets

Targets are engineer-authored. Missing evidence is not a pass.

- SKIP · Wearable length: Supply product_length_mm before evaluating.
- SKIP · Wearable width: Supply product_width_mm before evaluating.
- SKIP · Wearable height: Supply product_height_mm before evaluating.
- SKIP · Complete wearable mass: Include PCB, components, battery, enclosure, adhesive and electrodes; confirm completeness.
- SKIP · Battery runtime: Supply battery_capacity_mah, average_current_ma, usable_capacity_fraction before evaluating.
- SKIP · Input-referred signal/noise budget: Supply minimum_signal_uv_rms, input_noise_uv_rms, noise_bandwidth_hz, required_snr_db before evaluating.

## Design timeline

### 2026-09-08T23:26:54.714772+00:00 · design_change



### 2026-09-08T23:28:19.727827+00:00 · design_snapshot

Current design snapshot
Checks: {"PASS": 83, "FAIL": 0, "WARN": 0, "SKIP": 1}

| Component | X mm | Y mm | Rotation |
|---|---:|---:|---:|
| C1 | 140.3 | 125.7 | 0.0 |
| C2 | 127.8 | 119.7 | 0.0 |
| C3 | 119.8 | 118.2 | 0.0 |
| C4 | 135.8 | 114.7 | 0.0 |
| C5 | 137.8 | 115.7 | -90.0 |
| C6 | 143.3 | 118.7 | 0.0 |
| C7 | 130.3 | 122.2 | 0.0 |
| J1 | 138.0 | 119.0 | -90.0 |
| J2 | 133.5 | 118.5 | -90.0 |
| J3 | 136.0 | 126.0 | 0.0 |
| L1 | 136.15 | 108.35 | 0.0 |
| R1 | 130.3 | 119.2 | -90.0 |
| R2 | 128.3 | 118.2 | 0.0 |
| R3 | 143.3 | 120.2 | 0.0 |
| R4 | 136.3 | 129.199999 | 0.0 |
| U1 | 142.0 | 131.0 | 0.0 |
| U2 | 125.0 | 125.0 | 0.0 |
| U3 | 109.0 | 113.0 | 0.0 |
| U4 | 139.5 | 110.0 | 0.0 |
| U5 | 148.95 | 119.05 | 0.0 |

### 2026-09-08T23:28:19.947413+00:00 · validation_started



### 2026-09-08T23:28:38.774181+00:00 · validation_completed


- drc: FAIL · 48 violations
- erc: SKIP · No schematic exists for the active PCB.
- routing: SKIP · No configured autorouter or verified schematic-to-PCB netlist pipeline. Placement changes do not create copper connections.

### 2026-09-08T23:30:03.970865+00:00 · design_proposal

QA preview only: evaluate placement trade-offs without moving the live PCB.
- verdict: regresses
- fixed:
- introduced: mission.support_C3
- worsened: mission.support_C3
- improved:
- unverified: access.connector, fit.courtyard::C3|R2, fit.overlap::C3|R1

### 2026-09-08T23:30:50.396400+00:00 · proposal_decision

Rejected during workflow QA; preserve the live engineer placement.
Decision: reject — Rejected during workflow QA; preserve the live engineer placement.

### 2026-09-08T23:36:40.745569+00:00 · design_change



## Source requirements

- [TI ADS1292R layout guidance](https://www.ti.com/lit/ds/symlink/ads1292r.pdf): Review analog return paths, decoupling and digital-current isolation. Spacing alone does not validate noise performance.
- [FDA biocompatibility assessment](https://www.fda.gov/medical-devices/biocompatibility-assessment-resource-center/biocompatibility-evaluation-endpoints-contact-duration-periods): Assess contact materials and contact duration for the intended intact-skin use. No biological test result is inferred from CAD.
- [KiCad DRC and ERC tooling](https://docs.kicad.org/10.0/en/cli/cli.html): Validate routing/manufacturing rules with DRC and schematic electrical rules with ERC. Neither is a medical-safety certification.

## Scope
Geometry and declared budgets are evaluated. Clinical sensitivity, biocompatibility, electrical patient protection, ingress protection and manufacturing readiness require additional evidence. No automatic copper routing is implemented. Download the JSON report for complete snapshots, measurements and decisions.
