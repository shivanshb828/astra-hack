# Dhruva Handoff: MissionPCB Widget Only

> **Scope and ownership doc.** For the field-level data contract — exact JSON
> keys, current dimensions, the nine real refs, overlay shapes, and the live
> API — see [`renderer-contract.md`](renderer-contract.md). Where the two
> disagree on a number, that one is right; it is read off the committed
> `render/*.json`.

MissionPCB should not be a separate CAD web app for this demo. The product is
an AI EE widget that sits on top of the tools electrical engineers already use:
Blender for the 3D/enclosure simulation view, and later KiCad for schematic,
PCB, ERC/DRC, and board-source workflows.

The user interacts with the widget in natural language. The native tool remains
the main workspace. The intelligence/model layer lives in Astra, not inside the
widget.

Dhruva's scope is the widget and native-tool integration only:

- render the MissionPCB widget inside Blender
- collect user text and short answers
- send requests to Astra
- receive structured results/proposals from Astra
- select, frame, highlight, and update native Blender objects
- export widget/native-tool artifacts

Dhruva should not build a second advisor, LLM prompt path, or model reasoning
layer inside Blender.

## Product Shape

Think:

```text
Blender / KiCad main window
└── MissionPCB widget
    ├── natural-language command box
    ├── short follow-up questions
    ├── Astra-returned constraint findings
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
6. Widget sends mission, answers, and current scene state to Astra.
7. Astra runs the advisor/model layer and returns structured findings,
   proposals, and highlight instructions.
8. Blender viewport highlights the relevant parts/volumes directly.
9. Widget lists Astra-returned considerations and blockers.
10. User says a natural-language edit, for example:
   - `Move the regulator farther from the AFE.`
   - `Show me why the battery is failing.`
   - `Try a buck-boost instead of this regulator.`
   - `Keep the antenna edge clear.`
11. Widget sends the request to Astra.
12. Astra returns a structured proposal.
13. User applies or rejects.
14. Scene updates, widget asks Astra to rerun, highlights update.
15. Export produces design state, advisor report, and model artifacts.

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
- `Ask Astra` / `Run advisor` button.
- `Apply proposal` / `Reject` buttons.
- Findings list grouped by Astra-returned category:
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
Highlight geometry and labels should be created from Astra's structured
instructions. The widget should not decide which constraint failed.

For each finding:

- Select involved objects by stable component ref.
- Add translucent volumes for keepouts, heat zones, enclosure headroom, or
  access windows.
- Use category colors consistently.
- Add short 3D labels only where they clarify the demo.

Examples, using the nine refs that actually exist (`ELEC_A`, `ELEC_B`, `ESD`,
`AFE`, `BUCK`, `CHG`, `CELL`, `BATCON`, `BLE`):

- `BLE`: show the antenna keep-out volume — 6 × 10 mm rect at `[64.5, 17.0]`.
  The MDBT42Q has an integrated antenna, so the zone surrounds the module.
  There is no separate `ANT` object.
- `BUCK -> AFE`: show the conducted/noise separation line.
- `BUCK`: show the 6 mm thermal plume. `CHG`: 8 mm.
- `ELEC_A -> ELEC_B`: show the 35 mm lead-vector span. This is the most
  legible blocker on the naive board (measured 6 mm, needs 35 mm).
- `CELL`: show the coin cell against the enclosure lid.

Two corrections to earlier versions of this list: the regulator is `BUCK`, not
`REG`. And `CELL` (VARTA CP1254, 12.1 mm coin, 5.6 mm tall) now **fits** — the
enclosure was reconciled to 104 × 34 × 8.5 mm with a 6.5 mm component height
budget, so 5.6 mm passes. "Battery too tall" is no longer a blocker and should
not be demoed as one.

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

The widget should call Astra's advisor/model layer. It should not embed the
advisor, duplicate prompts, or locally decide engineering recommendations.

Input:

- mission text
- short interview answers
- current component transforms from Blender
- stable object metadata from Blender
- optional current findings/proposal state

Output:

- considerations
- blockers
- open questions
- proposed edits
- viewport highlight instructions
- report/export payload

Transport can be a local HTTP bridge or direct Python call for the hack demo,
but the contract should still read as `widget -> Astra -> widget`. The widget
must not require model credentials itself.

### 5. Proposal Application

Natural-language edits should not mutate the scene immediately.

Flow:

1. User asks for a change.
2. Widget sends request to Astra.
3. Astra creates a structured proposal.
4. Widget previews affected objects/highlights.
5. User clicks `Apply`.
6. Blender transforms update.
7. Widget asks Astra to rerun advisor/constraints.

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

- Astra advisor/model call and schema.
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
- Widget-to-Astra request/response plumbing.
- Making the demo feel like an EE is using Blender/KiCad with an AI copilot.

Dhruva does not own:

- advisor reasoning
- LLM calls
- prompt design for the model
- choosing engineering recommendations
- deciding whether a constraint passes or fails

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
   - `Ask Astra`
   - Astra-returned findings list
3. Highlight the failures the engine actually reports on the naive board.
   Do not invent blockers — these are read straight out of
   `render/naive.json`, which has exactly 7 fails and 1 skip:

   | `id` | severity | subjects |
   |---|---|---|
   | `mission.lead_vector` | blocker | `ELEC_A`, `ELEC_B` |
   | `safety.battery_thermal::CELL\|CHG` | blocker | `CELL`, `CHG` |
   | `mission.esd_at_the_boundary` | major | `ESD`, `ELEC_A` |
   | `sep.noise::AFE\|BUCK` | major | `AFE`, `BUCK` |
   | `sep.thermal::AFE\|BUCK` | major | `AFE`, `BUCK` |
   | `sep.thermal::AFE\|CHG` | major | `AFE`, `CHG` |
   | `zone.heat_overlap::BUCK\|AFE` | major | `BUCK`, `AFE` |

   Lead the demo with the two blockers. `access.connector` skips (top-entry
   BOM, no opening) — show it as "not checked", not as a pass.
4. One natural-language edit:
   - `Move noisy power away from the analog front end.`
5. Apply/reject proposal.
6. Export report.
