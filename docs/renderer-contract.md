# Renderer Contract

What the constraint engine hands the 3D layer, field by field. Companion to
[`dhruva-simulation-handoff.md`](dhruva-simulation-handoff.md), which covers
scope and ownership; this file covers the data.

Everything here was read off the committed files, not from memory:
[`render/naive.json`](../render/naive.json) (the failing board) and
[`render/solved.json`](../render/solved.json) (the passing board). Both are
byte-stable — same engine, same layout, same bytes — so they are safe to
develop against while the rest of the pipeline moves.

Regenerate both with `./run_demo.sh` (writes `out/{naive,solved}/` then copies
into `render/`).

---

## Current geometry

These numbers changed when the demo layout was reconciled against Aayush's real
catalog parts. **Anything built against the older 90×50×18 enclosure or the
4.0 mm height budget is out of date.**

| | Value |
|---|---|
| Enclosure interior | 104 × 34 × 8.5 mm |
| Wall thickness | 1.5 mm |
| Wall keep-out | 2.0 mm |
| Openings | none — this build is top-entry only |
| Board | 94 × 26 × 1.0 mm |
| Board origin (min corner, enclosure coords) | `[5, 4, 1]` |
| Board edge margin | 1.5 mm |
| Max component height above board | 6.5 mm |
| Min component gap (IPC-7351 courtyard) | 0.5 mm |

Board top surface therefore sits at **z = 2.0 mm** (origin z 1.0 + thickness
1.0), which is the z every component reports.

## The nine refs

`ELEC_A`, `ELEC_B`, `ESD`, `AFE`, `BUCK`, `CHG`, `CELL`, `BATCON`, `BLE`.

There is no `ANT` and no `REG`. The radio is `BLE` (MDBT42Q, antenna
integrated into the module, which is why the keep-out is a zone around the
module rather than a separate antenna object). The regulator is `BUCK`
(TPS62740); `CHG` (BQ24040) is the charger and is a separate part.

Ref strings are stable and are what every finding references. Match on them,
never on object shape or display label.

---

## `component_positions[]`

Nine entries, one per placed component.

```jsonc
{
  "ref": "ELEC_A",              // stable identity — match on this
  "part_id": "ELEC_A",
  "part_name": "B2B-ZR (JST)",
  "category": "electrode",      // drives your colour lookup
  "board_xy_mm": [40.75, 18.25],      // board-local, component CENTRE
  "enclosure_xyz_mm": [45.75, 22.25, 2.0],
  "size_mm": [4.5, 3.5, 4.5],
  "rotation_deg": 0,
  "heat_source": false,
  "noise_source": false,
  "sensitivity": "high",        // high | medium | low | none
  "skin_contact": false
}
```

### Two things that will bite you

**1. `size_mm` is already rotated. Do not rotate the box again.**

`size_mm` comes from `Placement.footprint()`, which swaps the x/y extents when
`rotation_deg % 180 == 90`. `ELEC_A` and `ELEC_B` are the same physical part:

| ref | `rotation_deg` | `size_mm` |
|---|---|---|
| `ELEC_A` | 0 | `[4.5, 3.5, 4.5]` |
| `ELEC_B` | 90 | `[3.5, 4.5, 4.5]` |

`rotation_deg` is there so you can orient a *detailed mesh* (pin 1, connector
mouth, silkscreen). If you are drawing a box, scale by `size_mm` and leave
`rotation_euler` at zero. Setting both double-rotates the footprint.

`build_scene.py` already does this correctly — it uses `size_mm` as scale and
never touches `rotation_euler` on a component. Keep it that way.

**2. XY is the centre, Z is the base.**

`enclosure_xyz_mm` is the component **centre** in x and y, but the **bottom
face** in z (it is the board top surface for all nine parts). A centred cube
needs `z + size_mm[2] / 2`, which is exactly what `build_scene.py` line 137
does. Treating z as a centre buries half of every part inside the PCB.

---

## `checks[]`

52 entries. Each is one rule against one set of subjects.

```jsonc
{
  "id": "mission.lead_vector",
  "title": "Electrode leads exit far enough apart to resolve the lead vector",
  "status": "FAIL",             // PASS | FAIL | WARN | SKIP
  "severity": "blocker",        // blocker | major | minor | info
  "subjects": ["ELEC_A", "ELEC_B"],   // refs — what to select and frame
  "metric": "center_distance",
  "message": "ELEC_A and ELEC_B are only 6.00 mm apart, 35 mm required.",
  "rationale": "A single-lead ECG measures the potential difference between…",
  "measured_mm": 6.0,
  "required_mm": 35.0,
  "margin_mm": -29.0,           // negative = violation, magnitude = shortfall
  "center_distance_mm": 6.0,    // both metrics always reported
  "edge_gap_mm": 1.5,
  "suggestion": "Adjust ELEC_A/ELEC_B spacing by 29.00 mm.",
  "overlay": { … }              // may be null
}
```

`subjects` is the highlight list. `message` is the one-liner for the panel,
`rationale` is the why (this is the text that makes it read like an engineer
rather than a linter), `suggestion` is the fix.

**`SKIP` is not `PASS`.** One check skips on this board: `access.connector`,
because both headers are top-entry and there is no opening to align to.
Render skips as "not checked" — never as a green tick. Silence about a
category is not a pass.

Status counts:

| file | PASS | FAIL | WARN | SKIP | `passed` |
|---|---|---|---|---|---|
| `naive.json` | 44 | 7 | 0 | 1 | `false` |
| `solved.json` | 51 | 0 | 0 | 1 | `true` |

---

## Overlays

Two independent sources. Both are in **enclosure world mm** — apply one
mm→m scale and paste. Both carry `collection: "03_Constraint_Overlays"`.

**`checks[].overlay`** — per-finding, appears only when there is something to
draw. 16 `measure_line` + 1 `zone_rect` in `naive.json`.

```jsonc
{
  "type": "measure_line",
  "from": [13.0, 17.0, 5.0],
  "to":   [19.0, 17.0, 5.0],
  "color": [0.9, 0.15, 0.15],       // linear RGB 0-1
  "label": "6.0 mm ✗ (needs 35.0)",
  "label_at": [16.0, 17.0, …],
  "collection": "03_Constraint_Overlays"
}
```

**`zone_overlays[]`** — always three, independent of pass/fail, because a
keep-out exists whether or not it is currently violated.

```jsonc
{"type": "zone_circle", "center": [52.0, 7.5, 2.4], "radius_mm": 6.0,
 "color": [0.95, 0.45, 0.1], "label": "BUCK thermal 6 mm", "label_at": […]}
{"type": "zone_circle", "center": [52.0, 12.5, 2.4], "radius_mm": 8.0,
 "color": [0.95, 0.65, 0.1], "label": "CHG thermal 8 mm", "label_at": […]}
{"type": "zone_rect",   "center": [64.5, 17.0, 2.4], "size_mm": [6.0, 10.0],
 "color": [0.6, 0.3, 0.85], "label": "BLE antenna keep-out", "label_at": […]}
```

Radii come from Aayush's catalog records, not from the renderer. Never
hardcode 6 mm or 8 mm — they move when the parts data moves.

Overlay types in play: `measure_line`, `zone_circle`, `zone_rect`.

### Who draws them

The web viewport draws its own overlays from this JSON —
`web/src/Viewport.tsx` builds them from `checks[].viz` plus `zone_viz`. That
is why `build_scene.py` exports only the `01_Product` collection: Blender's
cameras, lights, and overlay gizmos would otherwise clutter the GLB.

So overlay geometry inside Blender is for **Blender's own render**, not for the
web client. Two consumers, one JSON source. If you add an overlay type,
nothing breaks in the web app until it learns the type — it just isn't drawn.

---

## Calling the engine

Geometry path. `render/naive.json` is a plain `validate`; `render/solved.json`
is the **solver's** output, so its matching layout file is
`layouts/ecg-patch-solved.json`, not the hand-authored target.

```bash
export PYTHONPATH=src

# the failing board
python3 -m constraint_engine validate \
  --parts parts/ecg-patch-parts.json \
  --layout layouts/ecg-patch-naive.json \
  --out out/naive

# the fixed board — writes both the layout and the results
python3 -m constraint_engine solve \
  --parts parts/ecg-patch-parts.json \
  --layout layouts/ecg-patch-naive.json \
  --out layouts/ecg-patch-solved.json \
  --name "ECG Patch - MissionPCB Solved" \
  --report-dir out/solved
```

**Pair the right layout with the right results** — `build_scene.py` folds the
enclosure and board extents out of `--layout` and the components out of
`--results`. Mismatching them gives you a correct board in the wrong shell.

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python blender/build_scene.py -- \
  --results render/solved.json \
  --layout  layouts/ecg-patch-solved.json \
  --blend out/scene.blend --glb out/scene.glb --render out/iso.png
```

Verified end to end on Blender 5.2.1 LTS: `scene.blend` 108K, `scene.glb`
20K, `iso.png` 1.0M. Measured object bounds came back
`ENCLOSURE x[0, 104] y[0, 34] z[0, 9]`, `BOARD x[5, 99] y[4, 30] z[1, 2]` mm —
board inside the shell, nothing outside it.

Worth knowing: the solver, run from the naive board, lands on component
positions **identical** to the hand-authored `ecg-patch-missionpcb.json`
target. The only difference between that run and `render/solved.json` is the
`layout` name string. So either layout renders the same geometry.

In-process, no CLI:

```python
import sys; sys.path.insert(0, "<repo>/src")
from constraint_engine import load_parts, load_layout, validate

parts, _  = load_parts("parts/ecg-patch-parts.json")
layout, _ = load_layout("layouts/ecg-patch-missionpcb.json")
results   = validate(layout, parts)
```

For the KiCad round trip use `review()` instead — JSON in, JSON out, with
method and limitation labelling per finding. See
[`review-api.md`](review-api.md).

---

## Live app endpoints

The `web/` app's FastAPI backend, `127.0.0.1:8000`, local only, no auth, not
exposed. Relevant routes:

| Route | Purpose |
|---|---|
| `GET /api/health` | `{ok, schema_version, design_id}` |
| `GET /api/design` | current design + revision + revision list |
| `GET /api/design/analysis` | last analysis result |
| `POST /api/design/analyze` | rerun → `{analysis_job_id}` |
| `POST /api/design/edit` | apply transform changes → `{analysis_job_id}` |
| `POST /api/design/undo` · `/redo` · `/restore` | revision history |
| `GET /api/jobs/{job_id}` | poll: `running` → `done`, carries `result` |
| `POST /api/blender/export` · `GET /api/blender/render.png` | Blender bridge |
| `GET /api/design/export` | full design state |

Analysis is a **job**, not a synchronous return: `POST` gives you an
`analysis_job_id`, then poll `GET /api/jobs/{id}` until `status != "running"`.

`POST /api/design/edit` only accepts transforms — `pos_mm` (`[x, y]`) and
`rotation_deg`. Dimensions belong to the catalog and are deliberately
unreachable from here, so dragging a box cannot rewrite a manufacturer spec.
Send `base_revision`; a mismatch is rejected rather than silently merged.

```bash
curl -X POST http://127.0.0.1:8000/api/design/edit \
  -H 'Content-Type: application/json' \
  -d '{"base_revision": 0,
       "changes": [{"ref": "AFE", "field": "pos_mm", "after": [47.0, 7.5]}]}'
```

Verified: that edit produces 7 failures with `highlight_components` and
`distance_measurement` viz attached; `POST /api/design/undo` restores the
clean board.
