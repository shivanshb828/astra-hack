# MissionPCB ECG pass

## Current state — six imported components

Canonical file: `missionpcb_blender_demo/component_pass/missionpcb_three_cad_components.blend`. All six major roles now have imported CAD in both layouts. The user accepted approximate AFE and buck packages; charger is drawing-adapted, MCU uses the matching RGE0024H package, BLE uses the Raytac family outline, and JST uses nominal family CAD. The live Blender window shows the close-up with the MissionPCB controls. The unsaved previous scene was preserved in a local backup before loading this file.

Fresh verification: 14 unit tests, 12 saved/reopened CAD instances, native bounds and mounting, recalculation, UI failure/reset, and inspection/workbench visibility. The pinned upstream engine is now installed in the same scene: Naive 21 PASS / 5 FAIL / 2 SKIP; MissionPCB 26 PASS / 0 FAIL / 2 SKIP. Coverage remains incomplete and is visibly labeled. The previous checker's 1/8 and 7/8 results are historical. See component_pass/README.md for current facts; the following sections are historical.

Current workspace: /Users/dhruvavutukury/Documents/ChatGPT/astra.
Original generic baseline retained: /Users/dhruvavutukury/Documents/ChatGPT/astra 2.

User scope: one polished ECG chest-patch workflow, two-hour deadline, least intensive path, fully local/pre-seeded. The user subsequently authorized a 29-family CAD library, a selected ECG subset on the board, and a nicer desk environment in parallel. Full thermal/EM/electrical simulation is still outside the implemented scope.

- [x] Preserve existing component/PCB/camera/validator architecture.
- [x] Add ECG BOM identities and cached manufacturer context.
- [x] Migrate saved scene to rounded patch/adhesive, skin surface, electrode snaps, protection and under-board LiPo.
- [x] Extend validator to eight explicit ECG categories.
- [x] Keep original nine generic tests passing; add five ECG tests.
- [x] Verify naive 1/8 PASS and corrected 8/8 PASS using actual Blender geometry.
- [x] Verify movement, recalculation, restore, stale detection, root invariance and fixed RF clearance under resizing.
- [x] Add and test deterministic AFE-failure and seeded-reset buttons.
- [x] Inspect Blender UI: scene opens, top-down button works, AFE individually selectable, dimensions/part identity visible, orbit usable.
- [x] Create offline launcher and seed/results cache.
- [x] Finish final render inspection and verification provenance packaging.
- [x] Verify a copied .blend with embedded runtime in an isolated temporary folder, without adjacent source files.

Final verification: 14 unit tests passed; Blender integration passed, including the actual seeded failure and restore operators. Both 1920 × 1080 renders completed and were visually inspected. Verification notes are embedded in the scene and exported to the report and build manifest. The open GUI was left alone while the user inspected it; launch the latest saved version with Open ECG Demo.command.

Heat, patient-spacing and current/width categories are geometric proxies with example thresholds. No measured skin temperature, noise floor, electrical safety or clinical performance is claimed. Manufacturer part identities do not make the illustrative block dimensions footprint-accurate.

## CAD and environment pass — 2026-09-08

- Workbench variant saved at `missionpcb_blender_demo/workbench/missionpcb_ecg_workbench.blend`; cached image in `workbench/renders/workbench.png`. Adds desk, ESD mat and simple tools. Geometry/result invariance, original integration and seeded failure/restore checks pass. Board components still use the original illustrative envelopes.
- Artifact BOM cached in `parts/bom_source.json`: 29 families including alternative radios, chargers and regulators. User selected a library of all 29 with an ECG subset on the board.
- 22 installed KiCad STEP package/family candidates converted, plus the manufacturer's MDBT42Q STEP downloaded through the normal Raytac browser flow. 23 families now have candidate geometry; six remain unresolved. Exact orderable suffixes and package drawing matches are not yet confirmed.
- Asset library: `parts/library/MissionPCB_Package_Candidates.blend`. Standard metre-unit GLBs and measured bounds are cached alongside the library manifest. Fresh import round trips and normalization checks pass. Raytac's official file is a simplified mechanical outline (10 × 16 × 2.2 mm), not a detailed electronics assembly.
- SnapMagic required email verification, then phone verification after Download was clicked. User completed both; tab returned to home. A subsequent single access check encountered a browser-control connection failure. No successful SnapMagic download was confirmed. Stop repeated retries or any attempt to bypass the restriction; prefer cached/public manufacturer sources.
- The newly attached three-layer product UI brief is context, not an instruction to replace this active CAD/account troubleshooting task. No web app was built in this pass.

Remaining: source AFE4404, TPS62740, TPS63020, TPS22916, VARTA CP1254 and a fully specified JST ZH variant; select the exact ECG package variants; replace the board's illustrative geometry and rerun its geometric checks. Datasheet operating conditions and validated physical models remain separate from CAD appearance.
