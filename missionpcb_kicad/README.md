# MissionPCB cached ECG demo

The demo uses KiCad-exported 3D geometry in a small local replay viewer. KiCad remains the editable board source. Blender is retained as an optional presentation asset. Hypnos is unrelated and is never modified.

Run from the repository:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory missionpcb_kicad/demo
```

Open http://127.0.0.1:8766. Initial layout shows five cached failed checks. Apply cached improvement switches the viewer to zero failed / two skipped checks. Initial layout resets it. Both models, scripts and result snapshots are local. No LLM call or network download occurs in replay. Render only on camera/view changes to minimize compute.

## What is implemented

- One working board: `MissionPCB.kicad_pcb`, six core components, 72 × 38 mm outline.
- Local component STEP models with hashes and approximation notes in `cache/models.json`.
- Initial and improved board snapshots in `cache/`; these are replay assets, not separate working projects.
- Cached GLB geometry, red subject markers, result explanations, and explicitly scripted replay explanation.
- KiCad's Python loader successfully reopened both six-footprint boards. Browser test exercised initial → improved → initial.

## Remaining integration

- Connect the replay panel into the team's actual product UI.
- If needed after the demo, wire a guarded IPC apply operation to the exact MissionPCB board. The current button changes viewer state only.
- Replace AFE and regulator approximate packages. Regulator currently has an incorrect 10-pin proxy, clearly marked; do not fabricate. Charger is a generic package, not the height-adjusted Blender geometry.
- Add exact BOM support parts, nets, routing, enclosure/battery validation before presenting this as an actual PCB design.

The engine counts are existing Blender snapshot results, not a fresh KiCad DRC or physical simulation. Coordinates match the cached component centers, but imported geometry is not identical in all cases. Two checks remain skipped. Model manifest explains package limitations. No claim of complete ECG circuit or medical safety is made.

`build_cached_board.py` runs with KiCad's bundled Python and builds cache files only. The RF model needs X=-90° and its footprint is rotated 90° to align the 16×10 mm package with the existing cached placement. Cache models resolve via `../models`; the working board resolves via `models`.
