> **DELETE THIS FILE once you have read it.** It is a one-time handoff note, not living documentation. If anything here needs to persist, fold it into HANDOFF.md, README.md, or docs/ — do not leave this file around after reading.

# MissionPCB — Handoff

**Demo target: 1 minute.** Everything below is written for that constraint, not the full product vision (see `docs/missionpcb-product-build-brief.md` for that).

## Where things stand

**Data layer (Aayush) — DONE.** 29-part BOM for a single-lead ECG chest patch, fully extracted, 0 schema errors.

- `parts/schema/part.schema.json` — the contract. Every part is an emitter and a receiver across 4 channels (thermal, conducted, radiated, mechanical), same units both sides.
- `parts/catalog/*.json` — 29 real parts, every number cited to a datasheet page. Run `python3 parts/validate.py` to check.
- `parts/sources.json` — datasheet URLs / BOM manifest.
- `parts/REVIEW.md` — human-readable summary, grouped by subsystem.

**Constraint engine (Shivansh) — IN PROGRESS.** Owns turning catalog facts into pass/fail + a corrected layout.

**Blender sim (Dhruva) — IN PROGRESS.** Owns the 3D scene, naive vs. corrected layout, renders.

## The one-minute demo cut

Do not build all 5 constraints for the 1-min version. Build **2, deep**, and cut the rest to "future work" on a slide:

1. **Heat → sensor accuracy** — MCP73831 (charger) too close to TMP117 (body-temp sensor). *"The device reports a fever the patient doesn't have."* Clean one-liner, needs no EE explanation.
2. **RF keep-out** — antenna (2450AT18A100) too close to metal (VARTA battery). *"Range collapses even though every trace is correct."*

Both have real cited numbers in the catalog already. Skip noise/creepage/access for the video — real, but need more setup to land in 60 seconds.

## 60-second beat sheet

| Time | Beat |
|---|---|
| 0:00–0:08 | One line of mission text on screen: *"ECG patch, worn 7 days, rechargeable, BLE."* |
| 0:08–0:20 | Naive layout, red X's on the 2 chosen failures. State the plain-English consequence, not the mm number. |
| 0:20–0:45 | **The fix loop** — this is the whole pitch. Show it iterate (even 2-3 steps) and converge to green. A revision counter ("converged in 3 revisions") sells more than a static before/after. |
| 0:45–0:60 | Corrected layout, green, Blender hero shot of naive vs. fixed side by side in the enclosure. |

If the loop isn't wired in time, **a scripted/recorded version that looks live is fine for a demo video.** Judges are watching the video, not live-debugging your backend.

## Integration contract — read this before writing UI/engine code

Nobody calls anybody's function directly. Everyone reads/writes one shared file, `design.json`:

```json
{
  "mission": { "device": "ECG patch", "duty": "continuous", "patient_contact": true },
  "enclosure": { "l": 90, "w": 50, "h": 18, "wall": 2 },
  "placements": [ { "part_id": "mcp73831", "x": 21.0, "y": 8.5, "rot": 0 } ],
  "results": [
    { "check": "thermal", "pair": ["mcp73831", "tmp117"],
      "measured_mm": 9.4, "required_mm": 12.0, "status": "FAIL" }
  ],
  "revision": 3
}
```

- Parts catalog (`parts/catalog/*.json`) is static input — read-only for everyone downstream.
- Shivansh's engine reads `catalog + placements`, writes `results` + next `placements`.
- Dhruva's Blender script reads `placements + results`, renders.
- UI just displays whatever's in the file — including a scrubber over past revisions if there's time.

This means all three pieces can be built and tested independently right now without waiting on each other. If you're an agent picking this up cold: **do not invent a different contract** — check whether `design.json` or its schema already exists in the repo before adding fields.

## Known constraints on the data (read before generating checks)

- **ISO7741's rated >8mm creepage requires the HV/isolation footprint** — TI's default IPC-7351 land pattern only achieves 7.3mm. If the demo touches creepage, use this as the headline example: correct part, wrong footprint, silent failure.
- **ISO1541 has no IEC 60601-1 cert** (basic insulation only) — don't present it as a patient-safety barrier equivalent to ISO7741.
- **TPS62740's switching frequency drops toward DC at light load** — don't assume "2MHz, therefore far from the 0-150Hz ECG band" is always true.
- **VARTA CP1254 has zero thermal data** (1-page datasheet) — any heat check on the battery is a stated assumption, not a citation. Say so on screen if it comes up.
- Full findings: see the commit message on the schema+catalog PR, or `parts/REVIEW.md`.

## Not done / explicitly cut for the demo

- Real physics-derived separation distances (engine currently would need to compute these from catalog facts — check with Shivansh on status)
- Noise/creepage/connector-access checks wired end-to-end
- Live LLM calls on stage — **cache every LLM call used in the demo path**; don't depend on a live API call during recording or presentation
- UI polish beyond what's needed to read the two chosen checks clearly

## Quick commands

```bash
python3 parts/validate.py        # confirm catalog is still schema-valid after edits
cat parts/REVIEW.md              # human-readable part summary
```
