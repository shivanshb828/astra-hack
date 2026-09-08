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
