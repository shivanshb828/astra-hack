# Dhruva Handoff: MissionPCB As A Native-Tool Widget

MissionPCB should not be a separate CAD web app for this demo. The product is
an AI EE widget that sits on top of the tools electrical engineers already use:
Blender for the 3D/enclosure simulation view, and later KiCad for schematic,
PCB, ERC/DRC, and board-source workflows.

The user interacts with the widget in natural language. The native tool remains
the main workspace.

## Product Shape

Think:

```text
Blender / KiCad main window
└── MissionPCB widget
    ├── natural-language command box
    ├── short follow-up questions
    ├── constraint findings
    ├── highlighted objects in the native viewport
    └── apply / reject / export actions
```

The widget should feel like an AI teammate embedded in the EE workflow, not a
replacement editor.

## Demo Flow

1. User opens Blender scene.
2. MissionPCB widget is visible as a compact side panel or floating panel.
3. Widget asks: `What are we building?`
4. User types the natural-language mission.
5. Widget asks at most three short follow-up questions.
6. Advisor runs over the catalog and current scene.
7. Blender viewport highlights the relevant parts/volumes directly.
8. Widget lists grounded considerations and blockers.
9. User says a natural-language edit, for example:
   - `Move the regulator farther from the AFE.`
   - `Show me why the battery is failing.`
   - `Try a buck-boost instead of this regulator.`
   - `Keep the antenna edge clear.`
10. Widget proposes a change.
11. User applies or rejects.
12. Scene updates, constraints rerun, highlights update.
13. Export produces design state, advisor report, and model artifacts.

## What We Should Stop Building

- No standalone landing page.
- No separate browser-first PCB editor as the main demo.
- No fake Onshape clone unless it is only a backup visualization.
- No boxes pretending to be final CAD.

The existing `web/` app can remain as a debug/control surface, but it should not
be the hero demo.

## What Dhruva Should Build

### 1. Blender Widget Panel

Build a Blender add-on/sidebar panel for MissionPCB.

Minimum controls:

- Natural-language input box.
- `Run advisor` button.
- `Apply proposal` / `Reject` buttons.
- Findings list grouped by category:
  - safety
  - mechanical
  - thermal
  - conducted/noise
  - radiated/RF
- Object focus buttons: clicking a finding selects and frames involved objects.
- Export button.

Preferred location:

- Blender right sidebar `N-panel`, tab name `MissionPCB`.

### 2. Native Viewport Highlighting

The widget should drive Blender-native highlights, not draw an external overlay.

For each finding:

- Select involved objects by stable component ref.
- Add translucent volumes for keepouts, heat zones, enclosure headroom, or
  access windows.
- Use category colors consistently.
- Add short 3D labels only where they clarify the demo.

Examples:

- `CELL`: show 5.6 mm battery height against 4.0 mm enclosure headroom.
- `ANT`: show RF keep-out volume.
- `REG -> AFE`: show conducted/noise separation line.
- `REG`: show thermal plume.
- `CHG`: show charge-access window alignment.

### 3. Stable Object Contract

Every object in Blender must have a stable engineering identity:

- object name: component ref, e.g. `AFE`, `BUCK`, `CELL`, `ANT`
- custom property `component_ref`
- custom property `part_id`
- custom property `category`
- custom property `catalog_record_json` when available
- custom property `geometry_source`
- custom property `approximate`

The widget should never infer identity from object shape or display label.

### 4. Advisor Bridge

The widget should call or embed Shivansh's advisor/app layer.

Input:

- mission text
- short interview answers
- current component transforms from Blender
- catalog records
- optional current engine/advisor findings

Output:

- considerations
- blockers
- open questions
- proposed edits
- viewport highlight instructions
- report/export payload

The widget can start with local Python calls. A local HTTP bridge is fine if it
makes iteration easier, but it should not require cloud credentials for the demo.

### 5. Proposal Application

Natural-language edits should not mutate the scene immediately.

Flow:

1. User asks for a change.
2. Widget creates a structured proposal.
3. Widget previews affected objects/highlights.
4. User clicks `Apply`.
5. Blender transforms update.
6. Advisor/constraints rerun.

Every applied change should be written to a revision/history log.

### 6. Capture And Export

The browser/web layer, if used, should only consume artifacts. Blender remains
the source of the visual demo.

Export these artifacts:

- `out/widget/design_state.json`
- `out/widget/advisor_report.md`
- `out/widget/findings.json`
- `out/widget/highlights.json`
- `web/public/assets/ecg_patch.glb` if a web preview is needed
- optional viewport screenshot/render

## What Shivansh Owns

- Advisor call and schema.
- Natural-language-to-proposal logic.
- Grounded consideration/blocker output from catalog records.
- Constraint/advisor response shape for the widget.
- Keeping mock/demo mode available when no model credentials exist.

## What Dhruva Owns

- Blender panel/add-on.
- Native viewport selection, framing, highlighting, and labels.
- Realistic component geometry.
- Stable object metadata.
- Scene export/capture.
- Making the demo feel like an EE is using Blender/KiCad with an AI copilot.

## What Aayush/UI Should Own

- The natural-language interaction design.
- The exact three-question demo interview.
- Demo script and wording.
- Which findings are shown first.
- The judging story: MissionPCB catches real-world engineering constraints from
  mission + catalog, then acts inside the engineer's existing tools.

## Minimal Demo Cut

If time is tight, build only this:

1. Blender scene with realistic ECG patch parts.
2. MissionPCB side panel with:
   - `What are we building?` prompt
   - three follow-up questions
   - `Run advisor`
   - findings list
3. Highlight four blockers:
   - battery too tall for enclosure
   - charger/protection missing
   - regulator architecture issue
   - RF/AFE placement concern
4. One natural-language edit:
   - `Move noisy power away from the analog front end.`
5. Apply/reject proposal.
6. Export report.

