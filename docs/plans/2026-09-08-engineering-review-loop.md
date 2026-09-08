# Engineering review loop

Implement the user-requested sequence: current initial PCB → snapshot → flags and trade-offs → explicit proposed move → accept/reject with comment → recheck → revision history → downloadable brief/report → CAD handoff.

1. Add stdlib `src/constraint_engine/wearable.py`: envelope, complete mass budget, battery runtime and RMS signal/noise budget. Missing evidence stays SKIP; no inferred medical certification. Unit test missing, invalid, pass/fail inputs and trade-off diffs.
2. Add `kicad_bridge/design_workflow.py`: board-scoped immutable journal snapshots, preview-only proposed native moves, stale/pin/constraint guards, explicit decision, background saved-board DRC/ERC evidence, JSON/Markdown report. Test with fake CAD boundary, including rejected/stale proposals and apply failures.
3. Add workflow routes/page and link from companion/workspace. Test initial capture, proposal preview without board mutation, rejection, history/report, offline states. Existing live user design must not move during QA.
4. Build actual editable sample enclosure base/lid and chest reference exports in `wearable-cad/`, with dimensions/provenance manifest. Representative geometry only. Verify watertight enclosure components and dimensional bounds headlessly in Blender. Provide download links/import actions.
5. Research references from TI/FDA/KiCad official docs; show evidence-required checks separately from computed checks. Routing remains blocked until a schematic/netlist and configured router are available; do not fabricate copper connectivity.

User already specified and authorized this flow. Preserve concurrent edits; no broad branch reset or replacement of the open scene.
