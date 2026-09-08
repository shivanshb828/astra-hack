# Offline component-model candidates

All29 requested families are represented. These are library candidates, not a selected29-part circuit. No model has been scaled into an exact fit or added to the board. Exact orderable MPN/package selection remains open.

Cached: 2 family-specific candidates, 20 package candidates; 6 unresolved, plus 1 manufacturer-family model. 23 unique STEP files, 3.30MB.

| Family | Status | Candidate packages | Remaining check |
|---|---|---|---|
| ADS1292R | package_candidate_cached | QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm | TI offers RSM VQFN32 4x4 body and PBS TQFP32 5x5 body (7x7 overall). Generic QFN candidate matches pin count/body/pitch class only; EP and height need drawing verification. Do not use installed7x7-body TQFP32 as PBS. |
| AFE4404 | unresolved_no_cached_model | None | TI lists YZP DSBGA15; no compatible installed STEP located. Need exact downloaded model. Body2.6x1.6 per TI, not QFN. |
| OPA333 | package_candidate_cached | SOT-23-5; SOIC-8_3.9x4.9mm_P1.27mm; SOT-353_SC-70-5 | Local family symbol maps candidate package variants; full orderable suffix unresolved. |
| TMP117 | package_candidate_cached | WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm; Texas_DSBGA-6_0.95x1.488mm_Layout2x3_P0.4mm | Local family symbol maps candidate package variants; full orderable suffix unresolved. |
| BMA400 | package_candidate_cached | LGA-12_2x2mm_P0.5mm | Bosch specifies LGA12 2x2x0.95mm. Local generic LGA candidate requires terminal and height comparison; no Bosch-specific model. |
| TMUX1104 | package_candidate_cached | TSSOP-10_3x3mm_P0.5mm; USON-10_2.5x1.0mm_P0.5mm | TI offers DGS VSSOP10 and DQA USON10. Candidate packages only; choose suffix before integration. |
| MSP430FR2433 | package_candidate_cached | Texas_RGE0024C_VQFN-24-1EP_4x4mm_P0.5mm_EP2.1x2.1mm; Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm | TI lists RGE VQFN24 4x4 and YQW DSBGA24. Two local RGE drawings have different EP sizes; neither chosen pending RGE drawing revision check. |
| CC2652R | package_candidate_cached | Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm | TI lists RGZ VQFN48 7x7. Local Texas RGZ drawing candidate; full MPN/suffix and drawing revision remain unresolved. |
| MDBT42Q | manufacturer_family_model_cached | Official Raytac MDBT42Q STEP | Exact suffix unresolved; simplified manufacturer module geometry. Separate manufacturer license/provenance. |
| 2450AT18A100 | family_specific_candidate_cached | Johanson_2450AT18x100 | Family STEP exists. Footprint filename and datasheet URL match2450AT18x100/A100 but description incorrectly says2450AT43F0100. Need outline check before treating as exact. |
| TPS62740 | unresolved_no_cached_model | WSON-12-1EP_3x2mm_P0.5mm_EP1x2.65 | TI specifies DSS WSON12 2x3mm. Local footprint found but referenced STEP missing; no fabricated replacement. |
| TPS63020 | unresolved_no_cached_model | None | TI specifies DSJ VSON14 3x4mm. No matching local STEP found; installed4x4 WSON14 and3x4.45 VSON14 are not substitutes. |
| TPS61099 | package_candidate_cached | WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm | Prefer adjustable TPS61099DRV candidate for base family; TPS610991-7 symbols are different fixed-voltage variants. Same WSON package but do not imply electrical equivalence. |
| MCP73831 | package_candidate_cached | SOT-23-5; DFN-8-1EP_3x2mm_P0.5mm_EP1.7x1.4mm | OT SOT23-5 and MC DFN8 packages both available. Charge voltage variant and package suffix unresolved; MCP73831 is a linear charger. |
| BQ24040 | package_candidate_cached | Texas_DSQ0010A_WSON-10-1EP_2x2mm_P0.4mm_EP0.9x1.5mm | TI lists DSQ WSON10 2x2. Texas DSQ0010A package candidate; full suffix unresolved. |
| TPS7A02 | package_candidate_cached | SOT-23-5; Texas_X2SON-4_1x1mm_P0.65mm | TI lists DBV SOT23-5, DQN X2SON4 and YCH DSBGA4. Output voltage and package suffix unresolved. |
| MCP1700 | package_candidate_cached | SOT-23; SOT-89-3; TO-92_Inline | TT SOT23, MB SOT89 and TO TO92 package candidates available. Output voltage and suffix unresolved; not selected from arbitrary first symbol. |
| TPS22916 | unresolved_no_cached_model | None | TI lists YFP DSBGA4. No compatible local STEP located; do not replace with generic SOT. |
| TPS3839 | package_candidate_cached | SOT-23; Texas_X2SON-4_1x1mm_P0.65mm | DBZ SOT23 and DQN X2SON4 symbol candidates; threshold variant unresolved. |
| BQ27441-G1 | package_candidate_cached | Texas_S-PDSO-N12 | Local family symbol maps Texas_S-PDSO-N12. Need exact G1A/G1B and DRZ suffix selection. |
| DRV2605L | package_candidate_cached | TSSOP-10_3x3mm_P0.5mm | Local DRV2605LDGS maps TSSOP10/VSSOP DGS3x3body. Other package options not researched; no selection inferred. |
| ISO7741 | package_candidate_cached | SOIC-16W_7.5x10.3mm_P1.27mm | TI lists DW SOIC16 wide and DBQ SSOP16; safety properties differ. Wide-body DW package candidate only, no isolation/creepage inference. |
| ISO1541 | package_candidate_cached | SOIC-8_3.9x4.9mm_P1.27mm | Local symbol maps SOIC8. Full orderable suffix unresolved. Model is generic package and cannot validate isolation. |
| TPD4E1B06 | package_candidate_cached | SOT-363_SC-70-6 | TI offers DCK SC70-6 and DRL SOT5X3. SC70-6 generic candidate only; choose suffix. |
| MX25R6435F | package_candidate_cached | WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4.3mm | Macronix datasheet lists ZN WSON8 6x5, ZA USON8 4x4, M2 SOP8 and WLCSP variants. WSON candidate matches body/pin class; exposed pad and height unverified. |
| ABS07 | package_candidate_cached | Crystal_SMD_3215-2Pin_3.2x1.5mm | Abracon datasheet shows3.2x1.5mm crystal; default height0.9mm max or height-option1=0.65mm. Generic3215 two-pad model is candidate, not exact Abracon CAD; load/height suffix unresolved. |
| VARTA CP1254 | unresolved_no_cached_model | None | No local CP1254 model. Cell generation/suffix, contacts/tabs and datasheet must be selected; no coin-cell stand-in. |
| BM02B-SRSS | family_specific_candidate_cached | JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical | Exact family named JST_SH_BM02B-SRSS-TB vertical2-pin1mm-pitch STEP. Full suffix/finish unresolved; no claim that it matches a generic LiPo plug. |
| JST ZH | unresolved_no_cached_model | None | Series only, no pin count, orientation or mounting style. Local footprints exist for2–13pins but no installed ZH STEP located. Need complete MPN; not automatically a flex/FPC connector. |

## Evidence and provenance

Each JSON candidate records the installed symbol, footprint, resolved STEP path, cache path, and SHA-256. Missing referenced models are explicitly recorded. Values parsed from package names are body dimensions, not full lead envelopes, and height is intentionally null.

Package-only online checks used the linked manufacturer product pages in each record; local symbol mappings are library evidence, not manufacturer verification. [ADS1292R](https://www.ti.com/product/ADS1292R), [BMA400](https://www.bosch-sensortec.com/en/products/motion-sensors/accelerometers/bma400), [ABS07](https://abracon.com/Resonators/ABS07.pdf), and [MX25R6435F](https://www.macronix.com/Lists/Datasheet/Attachments/8868/MX25R6435F,%20Wide%20Range,%2064Mb,%20v1.6.pdf) provide the notable package alternatives described above.

The STEP files are unmodified copies from the installed KiCad libraries, including their per-file copyright headers. [KiCad library license](https://www.kicad.org/libraries/license/): CC-BY-SA4.0 with the electronic-design exception. A redistributed library collection must retain its license and attribution. See candidate_models/LICENSE.md and the original STEP headers.

## Next integration step

Compare candidate package drawings, select exact suffixes, convert only selected cached STEP files once to GLB, then measure imported mesh bounds in millimetres. Retain native dimensions; reuse linked meshes for duplicated packages. Missing files stay unresolved and are not replaced by a different part.

Raytac update: the normal manufacturer browser download supplied `manufacturer_models/Raytac/mdbt42q.stp`; see its provenance JSON. This file is not KiCad library data.
