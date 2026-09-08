# MissionPCB CAD candidate library

Open `MissionPCB_Package_Candidates.blend` for a gallery of all 29 family records. It contains **23 reusable CAD assets covering 23 families**, with six unresolved families represented by metadata and text only. Gallery objects share mesh data; repeated packages do not duplicate geometry.

These are package/family candidates, not 23 confirmed exact orderable parts. The gallery shows each family's first listed available candidate for review, with alternatives retained in the manifest. No component has been selected for or placed on the ECG board.

## Files and reuse

- `library_manifest.json` maps every family to its candidate asset names and normalized GLBs. It includes native mesh dimensions, source hashes, triangle counts and provenance.
- `verification.json` records the saved-library and normalized-GLB round-trip checks.
- `../converted_models/*.normalized.glb` are centered in XY with their lowest geometry at Z=0. Raw KiCad exports and conversion logs are retained separately.
- Append an asset object from the `.blend` collection `PACKAGE_AND_FAMILY_CAD_ASSETS`. Assets are named `PACKAGE_CANDIDATE__...`, except the manufacturer model `MANUFACTURER_FAMILY__mdbt42q`. The canonical collection is hidden in the gallery to avoid overlap at the origin.

The `.blend` uses **1 Blender unit = 1 mm**, scene scale `0.001`. Normalized GLBs use standard metre units. Blender's glTF importer already converts to the current scene scale: importing into a `0.001` scene needs **no additional scale multiplier**. If importing with scene scale `1`, multiply geometry by 1000 to adopt the MissionPCB millimetre convention. All 23 normalized exports were reimported into a fresh millimetre scene and their bounds checked.

## What the geometry represents

Twenty-two assets are unmodified geometry conversions of installed KiCad package STEP files. These are finished package CAD, often with individual leads and package materials. Dimensions in the manifest are measured mesh envelopes, including leads, not independently validated manufacturer dimensions. Generic package height can differ from a particular orderable part: for example, the generic 3215 crystal measures 0.93 mm high, and generic LGA12 measures 1.025 mm high. Do not silently scale these into an exact fit.

The **Raytac MDBT42Q** is from the manufacturer's normal download. It is a simplified mechanical model: **10 × 16 × 2.2 mm**, 72 vertices, 44 triangles, no supplied materials. It does not contain detailed electronics or individual terminals. The source uses Y as its thickness axis; conversion rotates it +90° around X before recentering and setting the bottom to Z=0. Exact radio/flash suffix remains unresolved.

Unresolved: AFE4404, TPS62740, TPS63020, TPS22916, VARTA CP1254 and JST ZH. No replacement geometry was fabricated for these records.

## Provenance

KiCad source files retain attribution and the library license in `../candidate_models/LICENSE.md`; see [KiCad library licensing](https://www.kicad.org/libraries/license/). A redistributed asset collection retains the applicable library attribution/license.

Raytac is separate manufacturer material, not covered by the KiCad license. See `../manufacturer_models/Raytac/provenance.json`; redistribution rights have not been assessed. The public manufacturer source is [Raytac documents](https://www.raytac.com/document/).

## Rebuild

Run `python3 ../convert_candidates.py`, then run Blender in background with `../build_candidate_library.py`, followed by `../verify_candidate_library.py`. Conversion reuses existing GLBs only after their source and output hashes match. New STEP conversions run one at a time.
