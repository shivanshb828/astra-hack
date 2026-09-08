# MissionPCB Demo UI

Open `index.html` directly or serve this folder locally.

This is a front-end prototype for the hack demo: a minimal black/white
engineering workspace with natural-language intake, a capped interview, an
Onshape-style editable viewport, AI considerations, constraint findings, human
comments, Auto mode, and export actions.

## Product Flow

1. User enters the mission in natural language.
2. UI asks up to three high-leverage interview questions.
3. Constraint API returns mission considerations and findings.
4. Model API returns board, enclosure, placements, zones, keep-outs, and object
   IDs for selection.
5. User can click parts, add comments, pin intent, or let Auto mode continue.
6. LLM revision API proposes the next placement.
7. Model API regenerates or updates the scene.
8. Export button packages state for downstream tools.

## API Slots

The current UI uses mocked adapters in `app.js`:

- `constraintApi(state)`
- `modelApi(state)`

Replace those functions with real calls when Shivansh and Dhruva push.

Expected constraint response:

```json
{
  "considerations": [
    ["Skin contact", "Heat near electrodes becomes a patient-safety constraint."]
  ],
  "findings": [
    {
      "id": "rf-keepout",
      "status": "fail",
      "title": "Antenna keep-out obstructed",
      "target": ["ANT"],
      "message": "Charge trace crosses the antenna clearance volume.",
      "action": "Rotate antenna toward free space and reroute charge."
    }
  ],
  "summary": { "pass": 35, "fail": 2 },
  "stage": "Review",
  "note": "I found two mission-critical issues."
}
```

Expected model response:

```json
{
  "board": { "x": 0, "y": 0, "w": 92, "h": 30 },
  "enclosure": { "x": -4, "y": -5, "w": 100, "h": 40 },
  "placements": [
    { "id": "ANT", "label": "ANT", "type": "rf", "x": 46.1, "y": 24.6, "w": 3.2, "h": 1.6 }
  ],
  "heatZones": [
    { "partId": "REG", "radius": 10 }
  ],
  "keepouts": [
    { "partId": "ANT", "w": 8, "h": 8, "direction": "up" }
  ]
}
```

Human comments export as:

```json
{
  "anchor": "ANT",
  "text": "Human note: preserve this placement in the next revision."
}
```

Anchors should map to model object IDs, constraint IDs, or a workspace-level
comment until Dhruva exposes point picking.
