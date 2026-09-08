# Data → engine → existing Blender scene

Audited 2026-09-08 after fetching origin. Pinned main: `1acd264792f1`.
Aayush catalog commit: `30aa034`; engine merge: `ec69c4a`; handoff: `2082c04`.
Read-only upstream snapshot: `missionpcb_blender_demo/cache/upstream/1acd264792f1`.
No upstream files checked out over the local scene, no scene modified, no push.

## Verified findings

- Engine test suite: 238 passed in 46.53 seconds. Catalog validator ran without jsonschema installed, so its OK output is not a full schema-validation result.

- 29 catalog records. Numbers carry unit, qualifier, conditions, source and review status. Extracted does not mean independently verified. Charger MCP73831 and TPS63020 lack complete mechanical dimensions.
- Directly running all 29 catalog records through engine parse_part produces 29 dimension warnings, 29 unknown categories, 29 default 1x1x1 mm boxes, zero heat sources and zero noise sources. A catalog JSON file alone also is not the expected parts array. Direct integration is unsafe.
- Engine fixture validation: naive 35 PASS / 10 FAIL; missionpcb and solved each 45 PASS / 0 FAIL. Each still carries two loader warnings. Repeated validation results are identical. These are upstream fixtures, not our CAD scene.
- Main and check-project-branches have identical src/constraint_engine contents.
- Engine does not consume theta_ja, dissipation_model, emissions or susceptibility fields. Its thermal/noise checks measure against declared distances; they do not compute heat transfer or interference from catalog physics.
- HANDOFF.md proposes design.json, but no design.json or corresponding schema is committed. Implemented engine contract is layouts + parts → validation_results.json. Treat handoff scope suggestions as proposals, not user instructions. Do not depict prerecorded results as live computations.
- Current Blender runtime still loads its own embedded constraints.py. Wiring the external engine requires an explicit adapter; merely fetching code changes nothing in the scene.

## Recommended integration

Keep a pinned catalog and engine revision locally. The only active visual artifact remains component_pass/missionpcb_three_cad_components.blend.

1. Explicit instance registry: Blender component_id → catalog part_id → CAD asset and package variant. Use references to distinguish repeated instances of the same part. Proposed six core mappings: MCU→msp430fr2433, Sensor→ads1292r, RF→mdbt42q, Regulator→tps62740, Driver→mcp73831, Battery→bm02b_srss. The current MCU label is STM32 and must be changed together with its geometry if adopting this mapping. Battery is a connector, not the actual LiPo cell. Track the cell separately; do not relabel the pouch as VARTA CP1254. Patient contacts require their own records.
2. Normalize known quantities from mechanical.*.value with strict unit/type checks. Preserve full catalog records for the inspector, including all source pages and conditions. Never pick the first theta_ja value without matching package and copper condition. Do not eval dissipation expressions; use explicitly implemented supported models and validated operating-point inputs.
3. Keep physical facts, CAD mesh bounds, footprint/courtyard dimensions, and clearance policies separate. Body length is not necessarily full lead span. A maximum datasheet height is not necessarily nominal mesh height. Missing values remain unresolved, never zero or 1 mm defaults. Meshes must not be stretched to conceal differences.
4. Feed the engine a strict adapted parts array and a layout extracted from the existing Blender geometry. Preserve declared demo policies as labelled assumptions until a validated physical model replaces them. Map emitter/receiver behavior explicitly and by operating mode; the presence of a thermal property alone is not evidence that a part needs a hot-source flag.
5. Use current 72x38 board and 90x50 enclosure. The upstream fixture uses 92x30 and 100x40. Do not silently replace dimensions or copy its solved coordinates. Our root-local PCB center is (0,0), so engine board XY = Blender root-local XY + (36,19). Board minimum in enclosure coordinates is (9,6,2); PCB top is 3.6. Engine enclosure positions/overlays become Blender root-local by subtracting (45,25,0), then applying the layout root transform. This scene uses 1 Blender unit = 1 mm via scale_length=.001: do NOT also multiply coordinates by .001.
6. Engine accepts only upright board-top parts and 90-degree rotations. Reject unsupported tilted/elevated/free-angle placements at the bridge; do not silently round. The under-board battery needs explicit handling because the current engine assumes every placement sits on the PCB top.
7. Validate → publish one revision atomically → update existing objects by ID and rebuild only engine-owned overlays. Never recreate the whole scene. The engine owns displayed verdicts; the old Blender checker should not publish contradictory results in parallel. Preserve PASS/FAIL/WARN/SKIP distinctly.
8. Solving is an explicit action, not part of dragging. Apply only a candidate that fits the current board and validated part definitions, then read scene geometry back and revalidate. Cache actual before/after results with input hashes and revision. Reject stale/partial results, retaining the last good revision with a visible stale status.

## Acceptance checks before connecting the visible demo

- Unknown IDs, missing dimensions, non-finite numbers and unsupported rotations block publication.
- 0/90/180/270-degree placement and coordinate round trips preserve mm bounds and antenna direction.
- Move a real component in Blender; exactly the relevant engine measurements and overlays change.
- Duplicate part instances stay distinct and mesh/package mismatches remain visible.
- Apply solved placement and re-extract; validation agrees with the solver output.
- Repeated refresh does not accumulate objects. Offline reload preserves revision and sources.
- Keep existing scene intact if an adapter check fails; no fabricated green state.

## Scope decision

Aayush proposes charger→TMP117 heat and antenna→battery keepout for a short demo. Those are not the current six-part subset: TMP117 and a separate chip antenna would add/change components. Preserve the selected ECG subset unless the user chooses that change. The available catalog is excellent input for sourced labels and physical facts now, but it is not component CAD, a complete circuit, or a physical field solver.
