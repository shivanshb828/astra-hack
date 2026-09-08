# Three-component mechanical CAD audit

The source STEP vertices, raw KiCad GLB world bounds, and normalized GLB bounds agree. No rotation, coordinate baking, or unit conversion error explains the differences below. Measurements are saved in `model_bounds.json` and `material_bounds.json`; diagnostic Blender scripts are alongside them.

## MCP73831 OT: corrected drawing-adapted package

Microchip package drawing C04-091-OT Rev F, sheet 2, datasheet page 23 specifies overall height A <= 1.45 mm, molded thickness A2 <= 1.30 mm, and standoff A1 <= 0.15 mm. The generic KiCad SOT-23-5 source incorrectly matches this part at 1.55 mm overall: its molded body is 1.45 mm thick and starts at Z=0.10 mm.

`MCP73831_OT_drawing_adapted.normalized.glb` retains all pin coordinates, every XY coordinate, and the 0.10 mm body standoff. Only molded-body Z thickness is reduced to 1.30 mm and the pin-one top marking is moved to Z=1.40 mm. Overall dimensions are 2.8 x 2.9 x 1.4 mm. This is a drawing-adapted generic package, not manufacturer CAD or verified production geometry. Source hashes and assertions are in `MCP73831_OT_adaptation.json`.

Source: https://ww1.microchip.com/downloads/en/DeviceDoc/MCP73831-Family-Data-Sheet-DS20001984H.pdf

## JST BM02B-SRSS-TB: retain nominal candidate, disclose 0.02 mm discrepancy

The primary drawing identifies the top-entry body's height as 4.25 mm, body depth as 2.9 mm, and body standoff as 0.05 mm. The side-entry variant is 2.9 mm high. The cached top-entry mesh has correct 4.0 x 2.9 x 4.25 mm body dimensions, but 0.07 mm body standoff. Overall cached dimensions, including contacts, are 4.0 x 3.6 x 4.32 mm. It is a nominal KiCad model with a 0.02 mm standoff discrepancy, not a grossly wrong orientation. No geometry was changed.

Source: https://www.jst-mfg.com/product/pdf/eng/eSH.pdf (page 3; native render `jst_native.png`). The manufacturer offers STEP through an email-delivery form requiring contact information and license acceptance; no form was submitted and no manufacturer CAD was obtained.

## ADS1292R RSM: outer package fits, exposed pad candidate is undersized

TI RSM0032B drawing specifies 4 x 4 mm nominal body, 0.4 mm pin pitch, maximum height 1.0 mm, and exposed thermal pad 2.8 +/- 0.05 mm. The cached generic QFN32 candidate has 4 x 4 x 0.92 mm outer bounds but a 2.65 x 2.65 mm exposed-pad designation, so it should not be presented as an exact package match. Use a 2.8 mm EP model or separately adapt and verify the exposed pad; no geometry changed in this audit.

Source: https://www.ti.com/lit/ds/symlink/ads1292r.pdf (PDF page 80, RSM0032B; `ads1292r_outline.png`). Installed KiCad footprint `VQFN-32-1EP_4x4mm_P0.4mm_EP2.8x2.8mm.kicad_mod` references a correspondingly named STEP, which is not present in the installed model subset.
