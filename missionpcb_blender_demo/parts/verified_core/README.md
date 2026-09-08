# Critical core CAD verification

**MSP430FR2433IRGER** is a supported demo choice with the **RGE0024H** package. The cached STEP and normalized GLB here match that package drawing:4×4mm body,24terminals,0.5mm pitch,2.7×2.7mm exposed pad. The CAD height is0.8mm; the datasheet maximum is1mm. Use the maximum for conservative enclosure clearance. The2.1mm-EP RGE0024C candidate is rejected. [TI datasheet,PDFpage89](https://www.ti.com/lit/ds/symlink/msp430fr2433.pdf)

**ADS1292RIRSMR** requires **RSM0032B**,4×4mm,32terminals,0.4mm pitch and2.8×2.8mm exposed pad. Existing generic2.65mm-EP CAD is not an exact package match. A correct finished STEP has not been downloaded. [TI datasheet,PDFpage80](https://www.ti.com/lit/ds/symlink/ads1292r.pdf)

**TPS62740DSSR** requires **DSS0012A**,2×3mm,12terminals,0.5mm pitch and0.9×2mm exposed pad,0.8mm maximum height. The local WSON12 candidate was intended for LM27762 and has a different exposed pad; do not use it as an exact TPS62740 model. A correct finished STEP has not been downloaded. [TI datasheet,PDFpage30](https://www.ti.com/lit/ds/symlink/tps62740.pdf)

TI links to exact-part STEP export pages for [ADS1292RIRSMR](https://vendor.ultralibrarian.com/TI/embedded/?gpn=ADS1292R&package=RSM&pin=32) and [TPS62740DSSR](https://vendor.ultralibrarian.com/TI/embedded/?gpn=TPS62740&package=DSS&pin=12). Normal download flow was inspected but not submitted; registration/authorization and cookies are mentioned. No access control was bypassed, no signup was performed and SnapMagic was not accessed.

`core_verification.json` contains full provenance, hashes and source links. STEP/GLB copies retain the KiCad license in`KICAD_LICENSE.md`. This verification does not modify the existing candidate library or board.
