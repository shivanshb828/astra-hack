# KiCad project review round trip

Run from the repository root using the bridge virtual environment:

```sh
missionpcb_blender_demo/kicad_bridge/.venv/bin/python missionpcb_review/roundtrip.py cycle ecg-r005
```

Choose a NEW revision name each time. The exact MissionPCB board must be open with IPC enabled. This command saves the current board, packages it, reviews locally with the real engine, validates the return, applies review text in one undo transaction, and saves. It does not move components.

Individual handoff steps:

```sh
missionpcb_blender_demo/kicad_bridge/.venv/bin/python missionpcb_review/roundtrip.py submit ecg-r005
missionpcb_blender_demo/kicad_bridge/.venv/bin/python missionpcb_review/roundtrip.py review missionpcb_review/exchange/ecg-r005.zip
missionpcb_blender_demo/kicad_bridge/.venv/bin/python missionpcb_review/roundtrip.py apply missionpcb_review/exchange/ecg-r005-return.zip
```

Outbound ZIP contains the native board/project, available schematic/custom rules/libraries,
all six local model dependencies, brief.json, engineering.json, parts.json and manifest.json.
Engineering metadata includes the full structured engine layout/rules, part property snapshot,
KiCad UUID/reference/catalog binding, coordinate conversion, board hash and limitations.
There is currently no schematic to include. Package dimensions/enclosure are demo assumptions.

Returned ZIP retains the manifest and dependencies, adds findings.json, and carries an
annotated native board. Findings preserve source hash and revision. Native review text is
on User.Comments (serialized Cmts.User), with a numbered label by each affected component
and matching detail beneath the board. These are annotations, not native DRC violations.
Their color follows your KiCad layer theme. True KiCad DRC remains a separate check.

Importer rejects changes to placement/electrical content, model files, brief or metadata;
checks the exact current saved source; and saves a temporary copy of the LIVE board to
check unsaved changes against the source hash. It updates only generated review text,
not by replacing the working board. Existing user comments and component UUIDs remain.
An import is one Undo; save again after undo to persist that undo.

External reviewers must retain manifest.json, return findings.json with revision,
source_board_sha256, findings array and annotations [{text,x,y}]. Text must start with
"MissionPCB review: ", positions use absolute KiCad mm. At most100 annotations of500
characters. Board edits must be generated review text on Cmts.User only. Engineering
changes belong to the next engineer-approved revision, not the reviewer response.

Current support is deliberately scoped to the six known MissionPCB parts. Unknown parts,
nonrectangular board geometry, different coordinate origins, full electrical review,
thermal fields, and clinical safety are not supported by this demo adapter. Do not treat
zero failures as design certification. The service is local; no remote ZIP transfer,
public endpoint or pet/chat transport is implied.
