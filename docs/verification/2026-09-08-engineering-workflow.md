# Engineering workflow verification — 2026-09-08

Verified the live local widget against the ECG20 KiCad project before the active project was changed externally to a new empty board.

- Browser startup failure reproduced: obsolete click handlers targeted removed layout-search controls. Removing those handlers restored the live 20-component board. Clicking Select U2 selected U2 in native KiCad, verified through its API.
- Browser Capture & recheck recorded the exact active revision: 82 placement checks passed, 1 failed, 1 not evaluated.
- Browser placement preview moved nothing. Proposed U2 X=125.0→125.1 mm and showed introduced/worsened checks. Browser acceptance applied and saved X=125.1 in native KiCad. A second reviewed proposal restored X=125.0. All 20 component placements exactly matched the saved pre-test snapshot afterward.
- Both acceptances recorded decisions and new snapshots, refreshed native review, opened native 3D, and started saved-board checks. The test decisions remain in the design transcript.
- A finding comment survived a refresh and remained bound to mission.afe_MCU. Its technical result remained FAIL.
- A real PDF upload extracted the ECG brief text without changing the adopted brief until Save. Report Markdown, complete JSON evidence and editable Blender assembly downloads returned HTTP 200 with download filenames.
- Reviewed device profile: ECG, chest, strap, interior 100×40×7 mm, 336-hour requirement. Profile adoption is pinned to the brief revision. Generic assembly requests cannot forge adoption; housing generation reads the adopted profile on the server and requires an observed Blender session.
- Screenshots were visually inspected in the browser at compact widget width. Tabs, finding measurements, notes, status and actions rendered without horizontal text overlap. Browser startup produced no JavaScript errors.

The electrical inspector reads native KiCad data: ECG20 has 20 footprints, 163 physical pads, 151 unique electrical pins, zero assigned electrical nets and zero copper. It is a placement design. A tested schematic attachment path compares references, pins and nets; it does not invent wiring or autoroute. A genuine KiCad template matched all 30 pins in the inspector's integration check.

Additional review corrected stale profile adoption after brief changes, inappropriate ECG requirements on non-ECG briefs, DRC counting of unconnected/parity results, validation freshness across schematic and rule changes, and annotation errors preventing save/check scheduling.

Latest widget Python suite: 104 tests passed. JavaScript syntax checks passed. A real Blender headless regression previously reproduced and then verified atomic transform rejection: invalid edits no longer partly move an object.

The active project later switched to NewProject-20260908-170110 with zero components. The workflow displays the active project and disables placement/handoff actions for an empty board. This verification does not claim an electrical design was generated in that new project. Native assembly rendering, model coverage, visibility and PCB handoff are documented by the collaborating assembly task.
