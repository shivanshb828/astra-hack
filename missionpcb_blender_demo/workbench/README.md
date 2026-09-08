# MissionPCB ECG workbench

A decorative warm oak electronics desk around the unchanged ECG demonstration.

Open `missionpcb_ecg_workbench.blend`, or use `Open ECG Workbench.command` in the parent folder to activate embedded controls. The scene and code work offline.

The mat, meter in standby, tools, solder reel, and notebook are decorative objects, excluded from every validation rule. No additional lights, textures, physics simulation, or online dependencies are used.

The original saved demo remains unchanged. The component envelopes and geometric proxy limitations from that demo still apply.

See `verification.json`, `validation_report.md`, and `renders/workbench.png`.

Verification completed: original Blender integration and dedicated workbench integration both pass. The embedded runtime registers, recalculates, demonstrates the AFE failure, and restores the seeded PASS state. Geometry signatures, snapshots, and results remain identical to the baseline. Moving decorative props does not invalidate results.

Environment budget: 120 decorative objects, 1,688 raw mesh vertices plus simple curve geometry, zero extra lights. The 1920×1080 Eevee render uses 64 samples. First render on this machine took 41.14 seconds.
