# Working ECG component scene

Use `missionpcb_three_cad_components.blend`. Its filename is retained to keep one working scene; it now contains all **six** major component models in both layouts.

The scene opens on a close-up. In **N → MissionPCB**, use **Inspect imported parts**, **Workbench**, **Demo: Move AFE Near Buck**, and **Restore Seeded Demo**. The last two act on the imported mesh and recalculate the geometric checks. The other `.blend` scenes are historical baselines. Do not reopen them to see current progress.

| Role | CAD geometry | Status |
|---|---|---|
| MCU / MSP430FR2433 | 4 × 4 × 0.8 mm, QFN24 | KiCad RGE0024H package matches selected drawing |
| AFE / ADS1292R | 4 × 4 × 0.92 mm, QFN32 | Approximation: 2.65 mm exposed pad versus 2.8 mm |
| BLE / MDBT42Q | 16 × 10 × 2.2 mm on board | Official simplified Raytac family outline, added display materials |
| Buck / TPS62740 | 2 × 1.975 × 0.8 mm, WSON10 | Visual substitute; actual DSS is 2 × 3 mm, 12 pins; not pin-compatible |
| Charger / MCP73831 | 2.8 × 2.9 × 1.4 mm, SOT23-5 | KiCad body height adapted to the package drawing |
| Battery connector / JST SH | 4 × 3.6 × 4.32 mm | Nominal KiCad family CAD, 0.02 mm standoff difference |

User accepted approximate models for this demo. Meshes remain native size, separately selectable and editable; no block-envelope stretching. The patient contacts, protection block, battery pouch, traces and enclosure are illustrative. No routed electrical design or physical thermal/EM solver is claimed.

The saved scene now uses the pinned upstream constraint engine and catalog. Naive: 21 PASS, 5 FAIL, 2 SKIP. MissionPCB: 26 PASS, 0 FAIL, 2 SKIP. Coverage is explicitly incomplete: patient-contact circuitry, the under-board battery, routing and connector mating are not fully modeled. Earlier 1/8 and 7/8 reports describe the previous embedded checker.

Current evidence: `active_import_verification.json`, `reopen_verification.json`, `engine_validation_results.json`, and `imported_parts.png`. `validation_results.json` and `validation_report.md` retain the preceding checker's report; `verification.json` and `cad_closeup.png` document the earlier three-part pass.

All working geometry is packed in the scene and cached in `../parts/`. No account, network or KiCad installation is needed to inspect it. To rebuild component placement, open this scene and execute `../update_working_components.py` in Blender. No new scene is created.
