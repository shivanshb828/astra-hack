# Engine integration

The canonical component_pass/missionpcb_three_cad_components.blend now embeds engine_bridge.py, Aayush's 29-record catalog and Shivansh's engine pinned to 1acd264792f1. No network or pip is required when reopening. Runtime reconstructs the bundled Python package in a content-addressed temporary directory.

In the existing MissionPCB sidebar use Recalculate Constraints, Optimize Core Placement, Demo: Move AFE Near Buck, and Restore Seeded Demo. Select a component to see its catalog identity and cited mechanical facts. Full source conditions remain in its catalog_record_json property. Existing model geometry remains intact; attaching a catalog record does not certify approximate CAD.

Results: naïve 21 PASS / 5 FAIL / 2 SKIP; corrected 26 PASS / 0 FAIL / 2 SKIP. Skips include unsupported connector access and the explicitly excluded patient/battery/routing coverage. Overall coverage remains incomplete. Heat radii and separation policies remain authored examples, not physics-derived thresholds.

Geometry is quantized to 0.001 mm for deterministic float32 Blender / Python engine round trips. Only upright, board-top core packages and multiples of 90 degrees are supported. Unknown/duplicate IDs and invalid geometry are rejected. The solver only optimizes the six core packages and does not route copper or check excluded auxiliary parts. Applying an inconsistent solver candidate rolls back component transforms.

Export Validation Report writes engine_validation_results.json atomically, including the engine hash, geometry signature, revision, bindings, source metadata and native engine results. Old validation_results.json and validation_report.md are historical legacy-checker artifacts; do not present them as current engine results.

Verification:

    /Applications/Blender.app/Contents/MacOS/Blender --background component_pass/missionpcb_three_cad_components.blend --python-exit-code 1 --python install_engine_bridge.py -- --verify-only
    /Applications/Blender.app/Contents/MacOS/Blender --background component_pass/missionpcb_three_cad_components.blend --python-exit-code 1 --python tests/verify_active_components.py

This delivers the application-side data/engine integration. No embedded desktop stream, browser viewport, network control server or web UI synchronization is implemented yet.
