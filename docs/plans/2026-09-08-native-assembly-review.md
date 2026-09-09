# Native assembly workflow completion

The widget must reliably control editable native Blender/KiCad scenes and show how brief requirements, actual measurements, component flags and review notes relate.

## Ownership
- Continue current work: adapter lifecycle, scene-bound commands, assembly widget layout and all control paths; browser verification.
- Continue current work (2): native model completeness, view presets, annotations, native screenshots and scene save/reload.
- Choose local or hosted engine: brief consistency, circuit/evidence readiness, persistent decisions and engineering review APIs.
- Fix widget chat interaction: native FloatingPanel lifetime, navigation and native panel screenshots.

## Widget design
Retain the existing light sage visual language. A compact connection/file header and native view controls stay at the top. Review, Components, Build and Brief buttons reveal focused sections. Review separates fit issues, component flags, missing evidence and model coverage. Each finding exposes affected references, measurements, reason and persistent notes. Components show value, model status, position and associated findings. Build offers native assembly actions and actual editable transforms. Brief presents readable requirements and the saved brief editor with explicit interpretation status. No embedded 3D renderer.

## Acceptance checks
| Area | Required visible result |
| --- | --- |
| Disconnected adapter | No stale PASS results; native mutations disabled; brief/navigation usable; reconnect action available |
| File reload | Timer survives; scene identity changes; stale commands rejected before edits |
| Native controls | Board, assembly and chest views visibly different; focus preserves relevant geometry and flag context |
| Fit and editing | Body import and chest fit visible; transform read fills fields; edit changes native transform; recheck changes relevant finding |
| Model coverage | All 20 references accounted for; missing L1 model and approximate packages explicit; no invented electrical routing |
| Notes | Comment survives refresh/recheck/save, associated with stable finding and affected native component |
| UI | 410px and desktop widths readable; no horizontal clipping or polling that erases entered notes/selection |
| Save/reopen | Native file actually saved; reconnect opens current saved assembly; other Blender work preserved |
| Verification | Python contract tests, native adapter reload test, browser control audit and reviewed screenshots |
