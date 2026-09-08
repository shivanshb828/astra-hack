# Review Contract

The interface between the MissionPCB workflow and the constraint engine.

```python
import sys; sys.path.insert(0, "<repo>/src")
from constraint_engine.review import review, SubmissionError

findings = review(submission)   # dict in, dict out
```

**In-process, not HTTP.** Your service already imports this repository, so
there is no port, no auth, and no serialization between us. Nothing is
deployed and nothing needs to be exposed. Adding a network hop between two
processes on the same machine would buy nothing and cost a class of failures.

`review()` is a pure function. Same submission, same findings. No state, no
disk writes, no network. It does not mutate the dict you pass it.

Runnable copies of both sides of this contract:
[`examples/review-request.json`](examples/review-request.json) ·
[`examples/review-response.json`](examples/review-response.json). A test
asserts the response file is exactly what the code produces, so they cannot
drift.

---

## Division of labour

| You own | This engine owns |
|---|---|
| KiCad parsing and writing | Geometric checks |
| Reference and UUID mapping | Clearance and keep-out evaluation |
| Coordinate conversion | Measured values and thresholds |
| Package export and import | Method and limitation labelling |
| Native annotation | Overlay geometry |

The engine never opens a board file and never guesses a mapping.

---

## Stable identifiers

**`catalog_id` is the filename stem in `parts/catalog/`** — `ads1292r`,
`varta_cp1254`, `mdbt42q`, `bq24040`, `jst_zh_electrode`, `bm02b_srss`,
`tpd4e1b06`, `tps62740`. These are stable: they are Aayush's records, they
carry page-level datasheet provenance, and `missions/*-constraints.json`
references them by exactly these strings.

**`ref` is whatever you call the instance** — `AFE`, `U1`, `CELL`. It only has
to be unique within one submission. Two instances of the same part get two
refs and one shared `catalog_id`.

**`kicad_ref` is your designator** — `U1`, `BT1`, `J3`. Echoed back on every
finding so you never need a lookup table.

---

## Request

```jsonc
{
  "design_id": "ecg-patch",              // required
  "revision": 7,                         // required; any JSON type, echoed verbatim
  "source_board_hash": "sha256:02f2cc…", // optional but recommended — see Round trip

  "brief": "Single-lead ECG chest patch, 14-day wear, sealed.",
  "distance_metric": "edge",             // "edge" (default) or "center"

  // Part properties. Either supply a catalog and reference it by id, or inline
  // a `properties` object per component. Inline wins, and is reported as a
  // warning because it is you asserting a physical fact over the record.
  "catalog": {
    "ads1292r": {
      "category": "analog_frontend",
      "dimensions_mm": { "length": 4.0, "width": 4.0, "height": 1.0 },
      "sensitive": "high",
      "required_clearance_mm": { "from_hot_components": 10, "from_noisy_components": 15 }
    }
  },

  "components": [                        // required, non-empty
    {
      "ref": "AFE",                      // required, unique in this submission
      "catalog_id": "ads1292r",          // required unless `properties` is inline
      "kicad_ref": "U1",                 // optional but needed for annotation
      "position_mm": [26, 13],           // required — board-local mm, component CENTRE
      "rotation_deg": 0,                 // 0 / 90 / 180 / 270; others round down
      "anchored": false                  // hint for the solver, ignored by review()
    }
  ],

  "geometry": {                          // required
    "enclosure": {
      "interior_mm": { "length": 104, "width": 34, "height": 8.5 },
      "wall_thickness_mm": 1.5,
      "wall_keepout_mm": 2.0,
      "openings": [                      // omit entirely for top-entry-only designs
        { "id": "charge_window", "face": "-x", "center_mm": 20,
          "size_mm": { "width": 20, "height": 5 }, "max_reach_mm": 12 }
      ]
    },
    "board": {
      "id": "PCB",
      "size_mm": { "length": 94, "width": 26, "thickness": 1.0 },
      "origin_mm": [5, 4, 1],            // board min-corner in enclosure coords
      "edge_margin_mm": 1.5,
      "max_component_height_mm": 6.5,
      "min_component_gap_mm": 0.5        // IPC-7351 courtyard
    },
    "traces": [                          // optional; used only for keep-out crossing
      { "id": "vbat", "net": "VBAT", "path_mm": [[10,5],[30,5]], "width_mm": 1.0 }
    ]
  },

  "constraints": {                       // the judgment half — you supply these
    "mission_profile": {
      "skin_contact_clearance_mm": 0,    // 0 disables the rule entirely
      "battery_thermal_clearance_mm": 8
    },
    "mission_rules": [
      { "id": "lead_vector", "type": "min_separation",
        "between": ["ELEC_A", "ELEC_B"], "distance_mm": 35,
        "metric": "center", "severity": "blocker",
        "title": "…", "rationale": "…" }
    ],
    "rationales": {                      // per-family prose, product-specific
      "sep.noise": "The signal at the front end is roughly 1 mV…"
    }
  }
}
```

**Units are millimetres throughout.** Positions are board-local and refer to
the component **centre**, not a corner. Rotation is a multiple of 90°;
anything else is rounded down and warned about, because arbitrary angles would
need oriented-box math the engine does not do.

`mission_rules[].type` is `min_separation` or `max_separation`. The type
decides the `comparison` operator in the response — see below.

---

## Response

```jsonc
{
  "schema_version": "review/1",
  "engine_version": "0.1.0",

  // Echoed verbatim, never inferred.
  "design_id": "ecg-patch",
  "revision": 7,
  "source_board_hash": "sha256:02f2cc…",
  "brief": "Single-lead ECG chest patch…",

  "coordinate_frame": {
    "frame": "enclosure", "units": "mm",
    "origin": "enclosure interior minimum corner"
  },

  "summary": { "total": 58, "blocking": 2, "fail": 7, "pass": 44, "unknown": 7 },

  "findings": [
    {
      "rule_id": "mission.lead_vector",
      "family": "mission",
      "title": "Electrode leads exit far enough apart to resolve the lead vector",
      "status": "fail",                  // pass | fail | warning | unknown
      "severity": "blocker",             // blocker | major | minor | info
      "components": [
        { "ref": "ELEC_A", "catalog_id": "jst_zh_electrode", "kicad_ref": "J1" },
        { "ref": "ELEC_B", "catalog_id": "jst_zh_electrode", "kicad_ref": "J2" }
      ],
      "kicad_refs": ["J1", "J2"],
      "method": "declared",              // exact | heuristic | declared | unsupported
      "measured":  { "value": 6.0,  "unit": "mm" },
      "threshold": { "value": 35.0, "unit": "mm",
                     "comparison": ">=", "reads_as": "measured >= 35.0 mm" },
      "margin":    { "value": -29.0, "unit": "mm" },   // negative = violation
      "metric": "center_distance",
      "both_metrics": { "edge_gap_mm": 1.5, "center_distance_mm": 6.0 },
      "limitation": "Threshold declared in the submitted constraints, not derived.",
      "explanation": "ELEC_A and ELEC_B are only 6.00 mm apart, 35 mm required.",
      "rationale": "A single-lead ECG measures the potential difference…",
      "suggested_action": "Adjust ELEC_A/ELEC_B spacing by 29.00 mm.",
      "overlay": { "type": "measure_line", "from": […], "to": […],
                   "color": [0.9,0.15,0.15], "label": "6.0 mm ✗ (needs 35.0)" }
    }
  ],

  // Same facts, component-keyed. Every submitted part appears, including clean
  // ones — absence would be ambiguous.
  "components": [
    { "ref": "CELL", "catalog_id": "varta_cp1254", "kicad_ref": "BT1",
      "checked": true, "worst_status": "fail", "worst_severity": "blocker",
      "counts": { "fail": 1, "warning": 0, "unknown": 0, "pass": 5 },
      "rule_ids": ["safety.battery_thermal::CELL|CHG", "…"] }
  ],

  "coverage": {
    "families_evaluated": ["fit.board", "sep.noise", "…"],
    "not_evaluated": ["electrical_connectivity", "thermal_field", "…"],
    "note": "A category in not_evaluated produced no verdict at all. Its absence from the findings is not a pass."
  },

  "warnings": ["…"]
}
```

### Two things to render carefully

**`comparison` is not decorative.** Half the families test *at least* and half
test *at most*. `mission.esd_at_the_boundary` is a `max_separation` rule — the
clamp must be *within* 10 mm. Rendering it as "needs ≥ 10 mm" tells the
engineer to move it further away, the exact opposite of the fix. Use
`reads_as` if you want the sentence pre-composed.

**`method` decides how much a number means.**

| `method` | Render as | Meaning |
|---|---|---|
| `exact` | a measurement | Bounding boxes, distances, containment, collisions, keep-out occupancy |
| `heuristic` | a threshold somebody chose | Distance standing in for a physical effect; `limitation` says which |
| `declared` | a rule you set | Straight from your `mission_rules` |
| `unsupported` | not checked | Returned so silence is never read as a pass |

---

## Status vocabulary

| status | meaning |
|---|---|
| `pass` | Evaluated and satisfied |
| `fail` | Evaluated and violated |
| `warning` | Evaluated, not a violation, but worth surfacing |
| `unknown` | **Not evaluated.** Missing input, unresolved part, or unsupported category |

`unknown` never means `pass`. A component whose `catalog_id` did not resolve
reports clean precisely because nothing looked at it, and that distinction has
to survive into your UI — surface it as "not checked", not as a green tick.

---

## Coverage

**Exact** — `fit.board`, `fit.enclosure_xy`, `fit.height`, `fit.overlap`,
`fit.courtyard`, `zone.rf_keepout`, `access.connector`

**Heuristic** — `sep.thermal`, `sep.noise`, `sep.rf`, `zone.heat_overlap`,
`safety.skin_contact_temp`, `safety.battery_thermal`

**Declared** — everything under `mission.*`

**Not evaluated at all**, returned explicitly on every response:
`trace_current_copper_geometry`, `patient_connected_spacing`,
`electrical_connectivity`, `thermal_field`, `radiated_emissions`,
`manufacturability`

---

## Round trip

Send `source_board_hash` and check it on the way back:

1. Hash the `.kicad_pcb` at submit time; put it in `source_board_hash`.
2. `review()` echoes it untouched.
3. Before loading annotations, re-hash the board on disk. If it differs, the
   engineer edited during review — **do not apply**. Re-submit instead.

Without this a round trip silently reverts work. `revision` is echoed with its
JSON type preserved, so string revisions like `"v7.2-rc1"` compare cleanly.

---

## Errors

`SubmissionError` means the submission is unusable — a missing field, an
unknown `catalog_id`, a component with no position. It is **not** raised for a
design that fails its checks; that is a successful review with findings.

Anything the engine had to assume goes in `warnings` rather than failing.
