# MissionPCB feature coverage and acceptance contract

Audit snapshot: 2026-09-08. This is a source-and-evidence audit, not a new live UI test. Parallel work can change these statuses; update a row only with the corresponding test evidence. “Implemented” means the source path exists; “verified” refers to the explicit artifacts below.

## Product direction retained from the conversation

The product is one floating assistant over the existing KiCad or Blender application. Expanding it should expose the complete interactive review dashboard. KiCad owns PCB editing; Blender owns the later device/enclosure view. The dashboard ties the mission, parts, constraints, exact flagged components, user comments, design changes, and transcript together. The ECG demo uses cached inputs and reproducible placements with actual local engine evaluation. Do not replace this with a new CAD editor, work on Hypnos, or imply that an unrelated blank project is already supported by the fixed MissionPCB adapter.

## Current coverage

| Requirement | Status at audit | Evidence and gap |
|---|---|---|
| Floating widget stays above the native app | Implemented | `kicad_bridge/FloatingPanel.swift` uses an `NSPanel` with floating level and spaces behavior. Verify interaction on actual KiCad and Blender windows. |
| Expand widget into full dashboard; collapse back | Implemented, UI verification pending | Swift now opens the embedded dashboard directly from the compact card. Native expansion, collapse, display bounds and state retention still need actual UI acceptance evidence. |
| Clear KiCad / Blender target | Partial | Swift chat selector routes Blender-prefixed commands. Embedded dashboard hardcodes KiCad and does not inherit the selected target. It must never show KiCad findings while suggesting it controls Blender. |
| One known project, no accidental edits to another | Implemented with scope limit | `bridge.py` selects the exact MissionPCB board. Blender adapter checks the canonical scene. New blank projects require explicit binding support; do not silently retarget. |
| Mission interview → cached parts/constraints → flagged board → explanation → improvement → comparison | Partial | Engine/package payload contains brief and rules; native widget supports inspect, review, improve and reset. Main dashboard has no complete intake/interview, mission editing, selected BOM review, or before/after comparison sequence. Old web UI is not completion of the native dashboard requirement. |
| Real component library and provenance | Partial | `parts/library/README.md`: 29 family records, 23 CAD assets, six unresolved families. Native demo contains six core parts, U2/U4 approximate. Dashboard shows ref/value, not provenance or exact-vs-candidate status. Do not call all 29 exact components. |
| Full structured part properties | Partial | Review packages include `parts.json` and engineering metadata. Dashboard has no mechanical/thermal/electrical/EMI/sensitivity/safety detail panel with conditions and citations. Unknown values need to stay unknown. |
| Live engine evaluation on native placements | Verified baseline | `native_review.py` maps live footprint positions into the local engine. `verification/widget-e2e.json` records initial 21 PASS / 5 FAIL / 1 SKIP → improved 26 / 0 / 1 → restored. Rule updates can change counts; rerun before citing new totals. |
| More constraints and deliberate failing scenarios | Partial | `test_constraint_scenarios.py` defines overlap, board edge, height, wall, and antenna cases. These are isolated engine scenarios, not evidence that each is user-triggerable in the widget. |
| Native flags at exact affected components | Verified live API/native cycle | `roundtrip.py` groups numbered `[MPCB]` labels per native ref on `Cmts.User`; `verification/dashboard-cycle-e2e.json` verifies six markers applied with positions/models restored. Dashboard cards map `kicad_refs` and select native footprints. Labels use the layer theme; they are not native DRC markers or guaranteed red zones. |
| Every problem has exact explanation and measured / required values | Partial | Dashboard renders finding title/message, available measurements, native refs and FAIL/SKIP. PASS checks are summarized, not listed. Findings without mapped refs need explicit “unmapped” presentation. Rule provenance and assumptions are not per-card. |
| Native selection ↔ relevant dashboard card | Partial | Clicking dashboard ref selects KiCad. Server exposes `selected_refs`; current dashboard does not consume them for reverse highlighting. Native annotation click does not navigate to the exact dashboard finding. |
| User comments tied to specific issue/component/revision | Implemented; live API persistence verified | `review_journal.py` stores board-scoped exact text, finding ID and timestamp; `/comment` and the dashboard composer exist. Live cycle proves comments survive reviews. Finding IDs link to refs through review history, but explicit comment author/source revision fields and widget-restart UI verification remain absent. |
| User pins / overrides become constraints | Component pin guard verified | Journal pins, `/pin`, card buttons and widget-command mutation guard exist. Live cycle proves pin rejects move and unpin permits it. Pins constrain supported widget moves; they are not native KiCad locks or arbitrary engine-rule overrides. Free-text comments are not automatically interpreted as constraints. |
| Change transcript and durable audit trail | Implemented backend; UI partial | Journal persists comments, pin changes, engine reviews and design-change before/after snapshots with moves/source. Live cycle verifies design events; workflow unit tests assert snapshots. Dashboard renders recent journal events and command log. Complete history browsing, readable before/after diff and persisted Swift conversation still need work. |
| Full flag → comment → change → rerun cycle | Live API/native cycle verified; embedded UI pending | `dashboard-cycle-e2e.json` proves full check, persisted comment, blocked pinned move, unpin/move, stale indication, engine rerun/native annotation and exact restoration. This tests authenticated HTTP and actual KiCad, not clicking the embedded dashboard. |
| Resolved / reopened findings across iterations | Implemented and unit-tested | `widget_command.record_review` computes new/resolved/reopened check IDs across stored review events; `test_widget_workflow.py` verifies resolution, reopening and retained comment. Dashboard shows event counts. Dedicated resolved issue cards/history navigation and native end-to-end lifecycle presentation remain unverified. |
| Native DRC / ERC integrated honestly | Partial | Full check runs KiCad CLI DRC on the saved board and labels that limitation. Existing artifact has two saved-board violations despite zero improved engine FAILs. No complete schematic/netlist/ERC/routing workflow. Dashboard roundtrip findings do not integrate the separate DRC result. |
| Stale review / disconnected / wrong document errors | Partial | Dashboard has a stale placement banner and disconnected message. Native package apply guards the full live board hash; bridge guards revisions. Dashboard now reads board-scoped journal review events; cross-target/project presentation still needs verification. Failed commands return text with HTTP 200; mutation outcome must be rendered as failure rather than inferred from HTTP alone. |
| Cached vs live source is obvious | Partial | Swift says no live Astra; dashboard labels cached dimensions/authored policies. Live geometry and live local engine must be distinguished from cached placements and properties. There is no Astra assembly/model call in the audited command path. |
| Blender flags and focus | Implemented / separately verified | `blender_widget/addon.py`: inspect/check/focus, red rings around failed subjects, session heartbeat and scene guard. README describes adapter tests and live check. Expanded dashboard integration, comments and cross-stage shared history are absent. |
| Drop CAD files; auto-place electronics in device | Missing | No arbitrary CAD drop/import/automatic alignment in this pass. Fixed canonical scene and board are used. This remains a later-stage requirement, not a claim for the current demo. |
| Nice and usable dashboard, no hidden controls | Partial | Styled responsive HTML exists; requires native embedded viewport test, small-screen reachability, keyboard focus, accessible labels, and expansion behavior verification. Source styling alone is not UI acceptance. |

Paths above are relative to `missionpcb_blender_demo/` unless prefixed `missionpcb_review/`, `docs/`, or `verification/`; verification artifacts live under `missionpcb_kicad/verification/`.

## End-to-end acceptance scenarios

Each scenario needs a dated result and, where practical, a saved JSON record plus native screenshot. Test the actual embedded dashboard, not only its standalone browser URL. Restore placements after destructive-to-demo scenarios and confirm all six model definitions remain intact.

1. **Expand and retain context.** Open compact widget over KiCad, expand once into dashboard, choose a finding, draft a comment, collapse and reopen. Target, selected finding, saved comments and transcript survive. All controls fit the visible display; the parent application remains usable.
2. **Initial full review.** Run review on the canonical initial board. Record exact source revision, rule/property version, engine totals, unknowns, native DRC saved-file source, and timestamps. Every displayed finding maps to the right refs. Unmapped checks are explicit. Native markers agree with the dashboard.
3. **Exact selection.** Click each finding's component button and read back KiCad selection. Select a footprint inside KiCad and verify matching dashboard cards highlight. Clicking a native marker either opens its exact finding or clearly presents the supported manual navigation path.
4. **Persisted discussion.** Add a comment to a named finding with two refs. Reload dashboard and restart the widget. Text, refs, finding ID, author/time and source revision survive. User text is rendered as text, not HTML. Commenting does not move or save geometry unintentionally.
5. **Pin enforcement.** Pin U2 or an explicit constraint; apply improvement. U2 stays fixed, or the change is rejected with the conflict explained. The pin is included in review inputs and history. Unpin, rerun and record the changed decision. A visual-only pin does not pass this test.
6. **Resolve and reopen.** Review initial → comment on a failing check → apply cached improvement → review → restore initial → review. Same logical finding transitions open → resolved → reopened with its comment history intact. Change transcript shows before/after position and source/result revisions. New failures remain separate.
7. **Deliberate edge cases.** Exercise overlap, edge clearance, antenna obstruction, excessive height and enclosure wall policy. Each produces the expected check IDs and affected refs. Restore and prove those introduced failures clear. Unknown inputs never become PASS.
8. **Preserve user content.** Add a manual KiCad comment, run annotate twice, and verify the manual text survives while generated markers are replaced without duplicates. One Undo reverses the annotation transaction; save semantics are visible.
9. **Stale and failed operations.** Submit a review, change geometry before applying, and verify rejection with no annotation/move side effects. Disconnect IPC, switch to Hypnos/blank project, send an unsupported command, and simulate bridge timeout. No success UI; pending/uncertain action is distinguishable from known failure. Reconnect and inspect before retrying.
10. **Cross-target isolation.** Switch KiCad → Blender, expand, inspect/check/focus. Dashboard displays the selected application's document and supported controls. No KiCad mutation is sent from Blender context. Inactive adapters show unavailable state without stale counts masquerading as current results.
11. **Demo reproducibility.** Disable external network after local services are ready. Run the cached workflow fully. Clearly label cached placement/properties, local engine calculation and disconnected Astra. Export or inspect a reproducible bundle with source hashes and assumptions; no fresh external API is required.
12. **Accessible and complete surface.** Keyboard through target switch, expand/collapse, finding filters, comment field, pin, review and history. Check busy state, empty state, long comments, many findings, scroll containers and the smallest supported native window. No control is obscured or unreachable.

## Parallel implementation boundaries

- **Native UI owner:** Swift expansion and sizing, target propagation, embedded dashboard navigation, finding/detail/comment/history controls and visual QA.
- **Workflow/backend owner:** persisted finding/ref/revision comments and pins, structured audit events, current/review revision contract, effective rules, issue lifecycle, scenario actions and deterministic reset.
- **Verification owner:** run the scenarios against actual apps after both surfaces agree on their API; retain exact evidence and update this matrix. Avoid mutating a shared board concurrently with UI verification.

Highest-priority closure is now actual embedded-UI acceptance of the implemented loop: expand → review → exact finding → persisted comment/pin → constrained change → rerun → resolved/reopened history. Additional parts or scenery do not substitute for this loop.

## Updated verification evidence

- `missionpcb_kicad/verification/dashboard-cycle-e2e.json`: PASS against the live KiCad board and authenticated dashboard API. Persistent comment, pin rejection, unpin/move, review-stale assertion, review/annotation and exact placement/model restoration are exercised by `verify_dashboard_cycle.py`. Final annotated baseline has six markers and 21 PASS / 5 FAIL / 1 SKIP.
- `missionpcb_kicad/verification/widget-e2e.json`: refreshed PASS; initial 21 / 5 / 1 → improved 26 / 0 / 1 → restored. Saved-file native DRC still reports two violations.
- Parent integration run reports 17 bridge tests and six review tests passing; the scenario test includes five geometric subcases. `test_widget_workflow.py` explicitly covers resolved/reopened IDs with retained comment and the pin/before-after event guard. This document did not rerun those tests or native mutations.
- Direct expansion, comment/pin cards, marker toggle and journal transcript are visible in current UI source. Source presence and API verification do not establish native click-path, visual, keyboard or restart acceptance.

## Remaining closure checklist

- [ ] Click the full sequence inside the rebuilt Swift widget; verify direct expansion, collapse, reopened state and reachable controls.
- [ ] Verify comment save, pin failure, unpin, improve/reset and rerun through UI buttons; verify errors cannot look successful and unsaved drafts survive polling.
- [ ] Demonstrate resolved → reopened history and access to retained discussion for resolved findings, beyond event counts.
- [ ] Make target ownership explicit in the expanded dashboard; do not imply the KiCad review dashboard controls Blender.
- [ ] Complete native selection-to-dashboard reverse highlight and prove compact markers remain readable with multiple findings.
- [ ] Add complete transcript browsing/readable before-after changes and explicit comment revision/author metadata if those are part of demo promises.
- [ ] Preserve earlier-stage requirements as explicit follow-up: intake, structured part provenance/properties, arbitrary CAD import/alignment, full electrical coverage. They remain outside the verified six-part cycle.
