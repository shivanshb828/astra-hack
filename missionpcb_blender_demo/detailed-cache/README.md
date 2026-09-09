# Cached ECG native assembly

Open `missionpcb_detailed_assembly.blend` in Blender. This is a separate ECG20 snapshot, not the currently selected empty KiCad project. `cache-manifest.json` identifies the source board, hash and adopted profile. Four 1800 × 1200 native Blender renders are cached alongside it.

The scene preserves 20 KiCad references and 19 native package models, pads, soldermask and silkscreen. Its editable concept housing includes a hollow base, separate inspection lid, gasket seat, PCB supports, labelled catalogue battery envelope, full peach MakeHuman CC0 body reference and sampled chest strap. Profile: ECG, chest, strap, 100 × 40 × 7 mm interior, 336 hours. This profile is an adopted example; it differs from the older adhesive brief text.

Native PCB, assembly, body and exploded views preserve assembled geometry for checks. Repeated component movement recomputes red/amber findings; notes remain in the Blender scene. The widget operates these native features.

Verified using `blender_widget/verify_detailed_cache.py`: all 20 references, declared interior size, reversible views and visibility, unchanged assembled-fit results when exploded, dynamic red component flags and native note persistence. Native render screenshots were visually reviewed.

Known unfinished engineering work: the sampled strap intersects the body and remains FAIL. PCB, battery envelope and enclosure fit their declared regions. This board is unrouted and has no meaningful net connectivity; L1 has no native 3D package model. The battery and electrodes are envelopes/concepts, not validated manufacturer CAD. Pogo charging access and sealing remain unresolved. No thermal field, physiological, comfort or patient-safety simulation is claimed.

Geometry and materials are embedded in the blend. Live checks and reimport need this repository's adapter plus the local source manifest recorded in `cache-manifest.json`; this is a local development cache, not a standalone engineering application.
