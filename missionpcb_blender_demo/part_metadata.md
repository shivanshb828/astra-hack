# Cached ECG BOM context

Cached September 8, 2026. The live demo requires no network calls. These are candidate part identities mapped to the existing functional blocks, not a complete electrical BOM or a validated medical design.

| Demo role | Candidate | Manufacturer-supported context | Geometry / model status |
|---|---|---|---|
| MCU | STM32L071CB | Ultra-low-power Cortex-M0+ MCU, up to 32 MHz; the LQFP48 variant has a 7 × 7 × 1.4 mm package | Scene preserves a 12 × 12 × 2 mm functional placement envelope, not its exact package |
| ECG AFE | ADS1292R | Two-channel, 24-bit delta-sigma ADC front-end with programmable gain; this scene illustrates a single-lead mission | 6 × 6 × 1.5 mm functional envelope; no schematic, ECG acquisition or noise simulation |
| Wireless | nRF52-based BLE module | Nordic lists multiple third-party nRF52832 module implementations | Vendor/module variant unspecified; 16 × 10 × 2 mm placeholder envelope; 22 mm antenna zone is a demo rule |
| Buck regulator | TPS62740 | 2.2–5.5 V input, up to 300 mA step-down converter | 8 × 8 × 3 mm power-block envelope; heat radius is an authored example |
| LiPo charger | MCP73831 | Single-cell Li-ion/Li-polymer linear charge management controller; programmable charging up to 500 mA | 14 × 10 × 3 mm charger-block envelope; treated as heat source, not a switching regulator |
| Battery connection | JST-SH + LiPo | User-supplied family-level selection | Exact connector, cell capacity, protection and battery chemistry variant not selected; no claim of battery safety |

The independent thin LiPo envelope is 24 × 16 × 1.6 mm under the PCB. Electrode snaps and input-protection blocks are schematic geometry; patient circuit insulation and protection are not implemented electrically.

Manufacturer references:

- [ST STM32L071CB](https://www.st.com/en/microcontrollers-microprocessors/stm32l071cb.html)
- [TI ADS1292R](https://www.ti.com/product/ADS1292R)
- [Nordic nRF52832 module list](https://www.nordicsemi.com/Products/nRF52832/Modules)
- [TI TPS62740](https://www.ti.com/product/TPS62740)
- [Microchip MCP73831](https://www.microchip.com/en-us/product/mcp73831)

Thermal resistance, power dissipation, switching frequency and input-referred noise are not translated into safety distances here. Such a translation would require an explicit validated model, operating point, stackup, copper, materials, contact conditions and uncertainty treatment. No missing thermal values have been invented.

The checklist is standards-informed in subject matter only. FDA's [EMC guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/electromagnetic-compatibility-emc-medical-devices) discusses testing electromagnetic compatibility; these geometric checks do not replace such testing. Numeric heat, spacing and trace-width thresholds are configurable demo examples.
