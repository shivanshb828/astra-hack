# Official KiCad IPC client

Installed locally in `.venv`: kicad-python 0.8.0. The library imports as `kipy`.

Official reference: https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/

## Connect

In the running PCB Editor open Preferences → Plugins → Enable API server → OK.
This creates a local IPC socket. It is not a cloud API and does not require a purchased API key.

From this directory:

    .venv/bin/python probe.py

The probe reads the KiCad version and footprint count only. It never changes the active project. Connection verified on 2026-09-08 after enabling the API server: KiCad 10.0.6 responded and the read-only probe returned 23 footprints. No board changes were made.

## Reinstall

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.lock.txt

## KiCad 10 compatibility

Installed KiCad: 10.0.6. IPC supports live PCB-editor interaction. Use `kicad-cli pcb export glb` for 3D export: IPC plotting/export and headless methods in the development documentation require KiCad 11. Do not infer support merely because a client method exists.

This is the transport client only. Astra invocation, the simulation UI, and applying validated agent changes to an ECG board are separate integration work. The currently open Hypnos board is not the ECG source board.

## Launch the floating widget

Run `.venv/bin/python launch.py` from this directory after installing the pinned
requirements. It compiles the Swift panel, creates a local token if absent, and
starts the loopback review/command services if their ports are available. It does
not enable KiCad's API server or install Blender's session adapter automatically.

## Verified E2E

`verify_e2e.py` exercises the actual widget HTTP route: inspect → Full check →
apply cached improvement → Full check → restore original positions/models →
Full check. Run with `.venv/bin/python verify_e2e.py` while MissionPCB is open.
It creates undo entries but does not save the board; it restores the starting
placement in a finally block. Latest result: `missionpcb_kicad/verification/widget-e2e.json`.
Native review assumes the demo board outline and cached package dimensions.
Native DRC is separately labeled saved-file-only. Zero placement failures is
not a complete electrical or manufacturing pass.

## Interactive review cycle

Expand the widget into the KiCad dashboard. Run **Full check** for a read-only
engine review, or **Review & annotate** to save a review package and replace
generated component markers in KiCad. Each finding can retain a user comment.
Component pins prevent widget placement commands from moving that component;
these are assistant-enforced pins, not KiCad native locks.

Explicit cached improvement/reset and individual move commands record before/after
positions. A new review records resolved and reopened finding IDs. User notes are
retained across those revisions and never silently converted into numeric rules.
Runtime history is local under `runtime/review-journal` and excluded from git.

`verify_dashboard_cycle.py` tests authenticated HTTP comments/pins, blocked and
permitted moves, stale review, native annotations, and exact placement/model
restoration. It saves the reviewed board and leaves labeled E2E audit records;
use the canonical demo, not a personal design. It preserves the initial U1 pin.
Evidence: `missionpcb_kicad/verification/dashboard-cycle-e2e.json`.

The separate blank `MissionPCB-Test` project is not bound to this adapter. The
expanded dashboard identifies its supported KiCad target. Blender's existing
inspect/check/focus session adapter is a separate stage; arbitrary CAD assembly
and live Astra calls are not part of this cached cycle.

## Brief-derived constraint workflow

The expanded widget displays the ECG brief as requirement cards and a constraint list. Placement policies show affected references, minimum/maximum limits, current measurements and pass/fail/stale status. Runtime, ingress, patient protection and the brief’s enclosure are explicitly not evaluated. The distance policies are authored engineering assumptions; this is not live model extraction from arbitrary briefs.

Save limit persists an engineering threshold locally and invalidates the prior review. Full check evaluates the new limit; Review & annotate updates visible component labels on KiCad’s Cmts.User layer. Show components selects the affected native footprints.

Verified on the six-component live board: 24 bridge unit tests, 6 package/review tests, dashboard-cycle-e2e (comments, pins, native moves, annotations, restoration), and constraint-limits-e2e (save limit, stale status, engine measurement, recheck, restored limit). The 18-component support profile is supported by source/tests; its board candidate is not installed in the active editor.

The floating app uses a borderless panel and remains running if its window is closed; opening the app restores the panel. Rebuild through launch.py after Swift changes.
