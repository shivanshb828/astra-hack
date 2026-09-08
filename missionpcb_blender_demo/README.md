# MissionPCB ECG Blender demo

The canonical working file is **component_pass/missionpcb_three_cad_components.blend**. The historical filename is retained; the file now contains six imported core component models in each layout.

Both `Open ECG Demo.command` and `Open ECG Workbench.command` open that same file through Blender. No new scene variant is generated. If you open the file in a fresh Blender session and the MissionPCB panel is missing, open Scripting, select the embedded `runtime.py`, run it with Alt-P, and return to Layout. The scene and component meshes themselves open without running any script.

Press **N** in the viewport and select **MissionPCB**:

1. **Inspect imported parts** shows the component close-up.
2. **Workbench** shows both layouts on the desk.
3. **Demo: Move AFE Near Buck** moves the actual imported chip and recalculates.
4. **Restore Seeded Demo** restores the authored positions.

The MCU, ECG AFE, Bluetooth module, buck, charger and JST connector are independent imported meshes. The user accepted approximate geometry for the demo. AFE and buck substitutes, the adapted charger and source provenance are documented in [the working scene guide](component_pass/README.md). The 29-family candidate library is in `parts/library/`; it has 23 cached CAD assets and six unresolved family records.

The saved scene also embeds the pinned upstream constraint engine and catalog. Recalculation reads the live mesh placements. The additional **Optimize Core Placement** button solves core package placement only; patient-contact, battery, routing and mating coverage remain incomplete. Current results are in `component_pass/engine_validation_results.json`.

The scene, embedded scripts, source models and converted models are cached locally. The current file can be inspected offline without SnapMagic, KiCad or an API account. KiCad was used as a CAD source/converter. This remains a geometric placement prototype, not a routed or fabrication-ready ECG circuit or a physical thermal/EM solver.

## Verification

Run the numerical Blender-demo tests:

```sh
python3 -m pytest missionpcb_blender_demo/tests/test_constraints.py missionpcb_blender_demo/tests/test_ecg.py -q
```

Run the saved component scene checks:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b missionpcb_blender_demo/component_pass/missionpcb_three_cad_components.blend -t 4 --python-exit-code 1 --python missionpcb_blender_demo/tests/verify_active_components.py
```

Current artifacts and preview are in `component_pass/`. The root `missionpcb_lean_constraint_demo.blend`, `workbench/` and their reports are retained as historical baselines. Local unsaved-session backups, temporary logs, the unrelated Hypnos inspection export and downloaded datasheet PDFs are excluded from Git.
