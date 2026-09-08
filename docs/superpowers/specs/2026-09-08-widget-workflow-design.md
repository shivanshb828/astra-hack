# MissionPCB expanded widget workflow

User-approved direction: a floating widget over native KiCad/Blender expands into an interactive dashboard; native apps remain the editors. No new CAD viewport. Existing ECG demo is cached and deterministic.

## Parallel implementation

- Native UI owner: Swift expansion, embedded dashboard, finding cards, exact component selection, authenticated comments/pins endpoints.
- Journal owner: persistent board-scoped comments, pins, events, validation and tests.
- Workflow owner: engine snapshots, resolved/reopened findings, before/after design changes, pin enforcement, integration tests.
- Coverage reviewer: verify earlier requirements and list remaining gaps honestly.

## User sequence

1. Expand widget; show exact connected board, active target, cached/local mode.
2. Run full check to inspect live placements with the local compute engine; native DRC is explicitly saved-board-only.
3. Select a finding to highlight its referenced footprints. Read evidence and authored thresholds.
4. Comment on the finding; retain exact user text across reloads. Pin a component to prevent widget movement.
5. Apply an explicit cached improvement or requested move. Record before/after positions and mark old review stale. Reject moves of pinned components before native mutation.
6. Run review and annotate; preserve user comments, replace generated native markers, retain revision and engine outcome.
7. Show resolved and reopened finding IDs across reviews and chronological design/comment/pin activity.

## Constraints and errors

Only the canonical six-part MissionPCB board is connected. The separately opened blank MissionPCB-Test is not silently targeted. Unknown boards, stale proposals, disconnected native apps, invalid comment/pin payloads and failed checks must display errors without fabricating success. Comments are user notes; they are not silently interpreted as numerical engineering constraints. Local cached rules do not claim live Astra calls, full circuit validation, or medical compliance. Blender supports its existing inspect/check/focus adapter; KiCad-specific dashboard actions must be labeled.

## Acceptance

Unit coverage: journal isolation/persistence/validation, pinned move rejection, resolved/reopened history retaining comments, authored geometry scenarios. Integrated coverage: authenticated comment and pin roundtrip, rejected pinned move with identical native positions, successful unpinned move with before/after journal, rerun engine and annotate, restore exact original positions. Native UI: expand/collapse, visible findings, selected component confirmation, persisted comments and transcript. Report unverified steps as such.
