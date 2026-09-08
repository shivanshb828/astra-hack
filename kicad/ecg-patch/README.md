# MissionPCB KiCad Demo Project

This is a native KiCad target for the widget/control demo.

- `ecg-patch.kicad_pcb` contains one editable footprint per MissionPCB part.
- Footprint refs match the engine refs: `AFE`, `BUCK`, `CELL`, `BLE`, etc.
- Placement comes from `layouts/ecg-patch-solved.json`.
- Footprints are approximate demo geometry, not manufacturer land patterns.
- Each footprint carries a package-class KiCad 3D model where KiCad ships one.
  These are visual stand-ins, not exact vendor STEP files for every selected
  part.
- There is no schematic, netlist, routing, or fabrication-ready stackup yet.

Use this file to prove the widget can target and move real KiCad objects. Do
not present it as a build-ready board.

Demo control path:

```bash
python3 scripts/kicad_widget_control.py list
python3 scripts/kicad_widget_control.py move BUCK --x 52 --y 7.5
```

Then open or refresh `ecg-patch.kicad_pcb` in KiCad. The footprint moved in the
native board file, which is the bridge a chat widget can call.
