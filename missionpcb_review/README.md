# MissionPCB review handoff

Local service: `http://127.0.0.1:8769`. Start with `python3 missionpcb_review/service.py`.
Runs until its process exits; not installed as a login/background daemon.

POST `/review`, Content-Type `application/json`, from your backend.
Use `example-request.json` as the exact contract:
- design_id: stable identifier
- revision: increasing integer, immutable after submission
- brief: original product brief (context, not automatically parsed)
- layout: engine layout with board, enclosure, placements, mission rules and optional traces
- kicad_refs: layout reference -> native KiCad reference mapping

Coordinates are engine board-local mm for placements; board origin is enclosure-local.
Do not submit absolute KiCad coordinates without conversion. Current six-part board:
board-local x = KiCad x - 100; board-local y = 138 - KiCad y.
The example is the engine's separate ECG fixture, not the current six-part native board.
Its partial reference mapping is illustrative; unmapped subjects remain explicit.

Response preserves design_id/revision and returns result.checks, findings and ui_annotations.
Each check carries measured/required values where supported, component references, and
engine overlay. Apply findings only when response revision equals the displayed revision.
Unknown/unmapped parts must never be displayed as passing.

Identical retries return the same result. Changed inputs under an existing revision or
older revisions return409. Malformed requests return422. Results persist under runs/.
No callback URL is followed. Loopback only; a teammate's remote backend needs an explicitly
configured transport. This service does not expose your Mac publicly.

This endpoint does not move footprints or add native KiCad annotations. Its annotation
instructions are the handoff to the frontend/native adapter. Keep review and approved
placement application separate. Existing widget move commands are a separate route.

Thermal/noise thresholds are authored proxies. Brief NLP, actual temperature solving,
electrical completeness, routing and medical compliance are not implemented here.
The checked-in ECG parts library is the property source; arbitrary CAD files are not accepted.

Verified: initial fixture35PASS/10FAIL, improved fixture45PASS/0FAIL; immutable revisions
and identical retries. These counts are not clinical or fabrication approval.

3D export from current native board: ../missionpcb_kicad/exports/MissionPCB.glb.
Contains all six component nodes. U2 and U4 remain approximate package models.

## Live six-component KiCad review

The floating widget's KiCad **Full check** invokes `kicad_bridge/native_review.py`.
It reads the exact MissionPCB board via IPC, maps U1–U5/J1 to engine references,
converts absolute positions to board-local millimeters, and submits `/review`
with the fixed `part_library: native-six` option. That local library uses cached
representative model dimensions; it does not measure arbitrary imported geometry.
The 72×38 board and 90×50×10 enclosure assumptions are fixed demo inputs.
A board-position revision check rejects results if placements change mid-review.

Results are returned directly into widget chat and persisted to
`missionpcb_kicad/verification/live-review.json`. It includes native reference
annotations but does not draw them inside KiCad yet. Native CLI DRC is separately
run on the saved file and labeled as such; unsaved edits are not claimed checked.
The board is never saved or moved by this review.

Verified via actual floating widget: live initial layout 20 PASS / 5 FAIL / 1 SKIP;
saved native board DRC two U3 keepout violations. All engine finding references
mapped and before/after live board snapshots matched. These counts differ from
Blender because the native review has a narrower configured rule set.
