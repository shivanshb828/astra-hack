# MissionPCB — single-lead ECG chest-patch demo

One offline workflow: compare a plausible first-pass layout against mission constraints, move the ECG AFE to cause a real geometric failure, and restore the verified placement.

## Start the demo

Double-click **Open ECG Demo.command**. It launches the installed Blender with the saved scene and activates the embedded MissionPCB panel. No login, network call, additional installation, or global script-auto-run setting is needed.

If you open the .blend directly, open Scripting, select the embedded runtime.py text, and run it with Alt-P. Return to Layout and press N over the viewport. Select the MissionPCB sidebar tab if it is not already active.

## The 60-second presentation

1. Show the top-down or isometric view. Left: **1/8 PASS**. Right: **8/8 PASS**.
2. Point out the ECG AFE, electrode snaps, protection area, BLE antenna, buck converter, charger, skin-facing patch surface and under-board LiPo outline.
3. Click **Demo: Move AFE Near Buck**. The actual AFE object moves next to the current buck location and the engine recalculates failures.
4. Click **Restore Seeded Demo**. It restores configured component positions/scales and recalculates the eight passes.
5. Optionally select ECG_AFE_MissionPCB, drag it, and click **Recalculate Constraints**. The sidebar marks results stale after a geometry edit.

Suggested narration: “The board can look electrically plausible and still fail its mission. This ECG patch demo checks placement around sensitive biosignals, patient-connected circuitry, heat influence zones, RF keep-outs, fit, copper width, and assembly access before an engineer reviews the design.”

PASS means the configured example geometric rules passed. Do not present it as a medically certified, electrically simulated, or fabrication-ready device.

## Pre-seeded and cached

- Both layouts and geometry: missionpcb_lean_constraint_demo.blend.
- Runtime, validator and overlay source embedded as Blender Text datablocks.
- Part identities and references: scene_config.json and part_metadata.md.
- Seed positions and measured fixture results: cache/verified_seed.json.
- Full-precision current geometry/results: validation_results.json and validation_report.md.
- Final 1920×1080 images: renders/top_down.png and renders/isometric.png.
- Build/version/geometry provenance and artifact hashes: build_manifest.json.

The cache is for authored fixtures. Edited geometry always runs through the validator; cached PASS text is never substituted for recalculation. Restore resets placements and object scales, not arbitrary mesh-topology edits. Use Blender Undo for those edits.

## Scope and interpretation

- One Blender unit = one millimeter; metric unit scale 0.001.
- PCB: 72 × 38 × 1.6 mm; plastic enclosure air volume: 90 × 50 × 10 mm.
- The six original component mesh identities are preserved and relabeled for the candidate ECG BOM. They are **functional placement envelopes, not package-accurate CAD models**.
- Two electrode snaps, a protection-area block and a thin LiPo envelope are separately editable in each layout.
- Heat rows use source-to-contact-region and source-to-AFE distances. No skin temperature or temperature compliance is calculated.
- Patient-connected spacing uses conservative XY envelopes. It does not model leakage current, insulation, or certified creepage paths.
- Copper width is measured against a configurable 0.6 mm example rule. It does not calculate current capacity; the illustrative 0.15 A property is context only.
- Antenna clearance remains 22 mm when the RF module is resized. The plastic shell is nonconductive; the exact BLE module antenna specification remains unspecified.
- MCP73831 is treated as a linear charger and heat source, not a switching regulator. Charging while worn is not validated.
- Electrode spacing, protection circuitry, physiological performance, biocompatibility and full manufacturability are not validated.

Numeric rules are authored examples. “Standards-informed” describes review categories; no IEC compliance or medical certification is claimed.

## Reproduce and verify

From the repository root:

    python3 -m unittest discover -s missionpcb_blender_demo/tests -p 'test_*.py' -v

    /Applications/Blender.app/Contents/MacOS/Blender --background missionpcb_blender_demo/missionpcb_lean_constraint_demo.blend --python-exit-code 1 --python missionpcb_blender_demo/tests/verify_blend.py

    /Applications/Blender.app/Contents/MacOS/Blender --background missionpcb_blender_demo/missionpcb_lean_constraint_demo.blend --python-exit-code 1 --python missionpcb_blender_demo/build_missionpcb_demo.py -- --mode render --quality final

The upgrade-ecg mode applies ECG configuration to an existing saved scene while preserving core component/PCB/root/camera objects. It resets fixture placements; use it for development, not to retain manual edits.

Recalculate and render modes preserve edited placements. The CLI fails if the corrected fixture has genuine violations; the interactive panel can display/export intentional failures.

Build mode in a factory-startup process can reconstruct the demo if needed, using the retained generic builder and ECG migration. This ECG pass was applied to the existing .blend, not started from a new architecture.

The original generic build remains in the sibling astra 2 workspace. This ECG version is built in astra.
