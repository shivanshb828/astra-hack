# MissionPCB application layer

The engineering workspace: versioned design state, a web viewport, analysis
through the existing constraint engine, and history you can audit.

The constraint engine stays the sole authority on whether a design meets its
constraints. Nothing in `src/missionpcb_app/` re-implements a check or computes
a distance; it orchestrates around the engine and adapts its output.

## Running it

Two processes. Backend first:

```bash
python3 -m venv .venv
.venv/bin/pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9"
PYTHONPATH=src .venv/bin/python -m uvicorn missionpcb_app.api:app --port 8000
```

Then the frontend:

```bash
cd web && npm install && npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to port 8000,
so the browser never talks to a model provider directly and no credential is
ever shipped to the client.

State lives in `data/missionpcb.db` (SQLite) and survives a backend restart.
Delete that file to reseed from `layouts/ecg-patch-missionpcb.json`.

## Interaction sequence to test

1. Select **AFE** in the left component list; the inspector shows its catalogue
   dimensions and flags.
2. Set its **x** to `63` and **y** to `3`. Each edit commits one revision and
   schedules analysis.
3. The toolbar flips to **6 Fail**; the issue list shows the collision with REG
   and the noise-separation failures.
4. Open *AFE is clear of noise source MCU*: measured 13.5 mm against a 15 mm
   threshold, labelled **Heuristic (distance proxy)**.
5. **Undo** — the design returns to 45 pass as a *new* revision, not by erasing
   history.
6. Reload the page; revision, history and analysis are still there.

## Architecture

```
web/ (React + R3F)      ->  /api  ->  missionpcb_app
                                        ├── schema.py       versioned contracts
                                        ├── store.py        SQLite revisions + history
                                        ├── analysis.py     adapter -> constraint_engine
                                        ├── chat.py         proposals, demo mode
                                        ├── integrations.py KiCad + Blender
                                        └── api.py          FastAPI
blender/build_scene.py  ->  GLB + render  ->  web/public/assets/
```

`analysis.py` serialises design state to the engine's layout schema, writes it
to a temporary file and reads it back through the public `load_layout`. That
detour is deliberate: the engine's forgiving loader, its aliases and its
warnings all apply exactly as they do on the command line, instead of being
approximated by a second parser.

### Coordinate frames

Engineering data is millimetres, Z-up, in the engine's two frames (board-local
and enclosure). The only conversion happens in `web/src/Viewport.tsx`:

```
enclosure mm (x, y, z)  ->  three.js metres (x/1000, z/1000, -y/1000)
```

The GLB is exported with `export_yup`, so glTF's Y-up convention already matches
the renderer. Nominal part dimensions live in the parts catalogue and are never
writable from the viewport — dragging a box changes a transform, never a
manufacturer specification.

## Blender bridge

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  --python blender/build_scene.py -- \
  --results out/app_scene/validation_results.json \
  --layout  layouts/ecg-patch-missionpcb.json \
  --blend   blender/out/ecg_patch.blend \
  --glb     web/public/assets/ecg_patch.glb \
  --render  blender/out/render_iso.png
```

Or hit **Re-export from Blender** in the app, which runs the same command
against the current revision.

- **Object-to-component mapping.** Every product mesh is named for its stable
  component ref (`AFE`, `LIPO`, …), plus `BOARD` and `ENCLOSURE`. The web client
  keys off those names, so parts stay individually addressable rather than
  arriving merged.
- **Collections.** Only `01_Product` is exported. `02_Presentation` holds
  cameras and lights, which would otherwise clutter the web viewport; the app
  draws its own labels and dashboards as web UI.
- **Units.** The script consumes enclosure millimetres and scales by 0.001.
- **Not on drag.** Blender runs only as a background job. Transforms are applied
  in the viewport from design state, so re-export is needed only when geometry
  changes in a way a transform cannot express.
- **Fallback.** With no GLB present the viewport builds placeholder boxes from
  nominal catalogue dimensions. The asset adapter is ready for the Blender
  agent's real meshes without further changes.

A GLB carries geometry only. Blender scripts, constraints and simulation logic
do not travel with it — behaviours have to be ported deliberately.

## What is real, and what is not

**Real.** Every measured number comes from `constraint_engine.validate`. The
component positions, the 45 passing checks, the failures, the thresholds and the
rule-source prose are all engine output. The parts catalogue supplies real
dimensions and datasheet URLs.

**Labelled as approximate.** `analysis.py` marks each rule family with the
method that actually decided it. Families the engine computes exactly (fit,
overlap, courtyard, keep-out occupancy, connector registration) are
`geometric_check`. Families that rest on a declared threshold (thermal, noise,
RF separation, skin-contact temperature) are `heuristic`, and the UI says
*"a placement heuristic, not a validated physical model."*

**Explicitly not evaluated.** `trace_current_copper_geometry` and
`patient_connected_spacing` are reported as `not_applicable` with a reason.
Creepage needs a path along an insulating surface and clearance concerns
separation through air; neither is derivable from component-centre distances, so
no verdict is issued rather than a green one.

**Not connected.** KiCad reports `not_connected` — no `.kicad_pcb` and no
`kicad-cli` on this machine. It produces no checks at all. A viewport placement
edit is an application proposal and does not update routing or schematic
connectivity. Gerbers must come from a real PCB pipeline, never from Blender
geometry.

**Demo mode.** With no credentials configured, chat is a deterministic local
parser over a small command vocabulary. Its replies are labelled as such and are
never attributed to Astra. See `.env.example`.

Passing this demo establishes nothing about medical-device compliance.

## Integration guide for the team

**Ayush (parts).** Keep `parts/*.json` ids in sync with the `part_id` values in
`layouts/*.json`. When they diverge, the engine emits `data.unresolved_part`,
the adapter maps it to `unknown`, and the affected components are excluded from
every check — the app shows zero passes rather than a clean board. That is
intentional, but it means a rename in one file needs the matching rename in the
other. `GET /api/parts` serves the catalogue to the UI.

**Shivansh (engine).** The adapter consumes `Results.to_dict()` only. Adding a
rule family needs one entry in `CATEGORY_BY_FAMILY` and one in
`METHOD_BY_FAMILY` in `analysis.py`; without them a new family still renders,
defaulting to `geometric_check`, so add the method mapping deliberately rather
than letting a heuristic inherit that label. Overlay types map through
`_overlay_to_viz`, and unrecognised types are dropped rather than passed
through — that is what keeps the instruction set bounded.

**Blender agent.** Export to `web/public/assets/ecg_patch.glb` with one named
object per component ref. Keep product geometry in `01_Product`; anything else
is ignored. Real meshes replace the placeholder boxes with no client change,
because size comes from the node's world scale.

## API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/design` | current or `?revision=N` |
| POST | `/api/design/edit` | revision-checked; 409 on stale base |
| POST | `/api/design/analyze` | returns a job id |
| GET | `/api/jobs/{id}` | status, result, `stale` flag |
| GET | `/api/design/analysis` | latest, with staleness against current revision |
| GET | `/api/design/history` | applied changes only |
| POST | `/api/design/restore` | records a new revision |
| POST | `/api/design/undo` \| `/redo` | |
| POST | `/api/chat` | returns a proposal; changes nothing |
| POST | `/api/proposals/{id}/apply` \| `/reject` | |
| GET | `/api/design/export` | design + engine layout + analysis + history |
| POST | `/api/blender/export` | background job |
| POST | `/api/kicad/drc` | reports `not_connected` here |
| GET | `/api/integrations` | never returns credential values |

Edits carry `base_revision`. Two edits from the same base cannot both land: the
second gets a 409 and the client re-reads, which is what prevents a lost update.
Analysis results carry the revision they were computed against, and the client
discards any result older than the newest revision it has seen, so a slow job
cannot present itself as a verdict on the current design.
