# Datasheet Review Sheet

29 datasheets, 1,381 pages, 44 MB. PDFs in `parts/datasheets/` (gitignored). Manifest: `parts/sources.json`.

Device: single-lead ECG chest patch, BLE, rechargeable.

## BOM

### Sensing

| part | mfr | role | constraint flags | pages |
|---|---|---|---|---|
| `ads1292r` | TI | ecg_afe | sensitive_high | 83 |
| `afe4404` | TI | ppg_afe | sensitive_high | 85 |
| `opa333` | TI | precision_opamp | sensitive_high | 49 |
| `tmp117` | TI | temp_sensor | thermally_sensitive | 50 |
| `bma400` | Bosch | accelerometer | vibration_sensitive | 121 |
| `tmux1104` | TI | analog_mux | sensitive_medium | 38 |

### Compute + Radio

| part | mfr | role | constraint flags | pages |
|---|---|---|---|---|
| `msp430fr2433` | TI | mcu | — | 92 |
| `cc2652r` | TI | ble_soc | rf_source | 61 |
| `mdbt42q` | Raytac | ble_module | rf_source, keepout | 64 |
| `2450at18a100` | Johanson | chip_antenna | keepout_hard | 4 |

### Power

| part | mfr | role | constraint flags | pages |
|---|---|---|---|---|
| `tps62740` | TI | buck | noise_source | 33 |
| `tps63020` | TI | buck_boost | heat_source, noise_source | 34 |
| `tps61099` | TI | boost | noise_source | 34 |
| `mcp73831` | Microchip | lipo_charger | heat_source | 29 |
| `bq24040` | TI | lipo_charger | heat_source | 40 |
| `tps7a02` | TI | ldo | — | 48 |
| `mcp1700` | Microchip | ldo | — | 30 |
| `tps22916` | TI | load_switch | — | 29 |
| `tps3839` | TI | supervisor | — | 35 |
| `bq27441-g1` | TI | fuel_gauge | — | 28 |
| `drv2605l` | TI | haptic_driver | noise_source, vibration_source | 76 |

### Patient Safety

| part | mfr | role | constraint flags | pages |
|---|---|---|---|---|
| `iso7741` | TI | digital_isolator | creepage_barrier | 52 |
| `iso1541` | TI | i2c_isolator | creepage_barrier | 36 |
| `tpd4e1b06` | TI | esd_protection | — | 24 |

### Support

| part | mfr | role | constraint flags | pages |
|---|---|---|---|---|
| `mx25r6435f` | Macronix | spi_flash | — | 87 |
| `abs07` | Abracon | crystal_32k | vibration_sensitive | 6 |

### Mechanical / Energy

| part | mfr | role | constraint flags | pages |
|---|---|---|---|---|
| `varta_cp1254` | VARTA | battery | heat_source, tall, safety_critical | 1 |
| `bm02b_srss` | JST | batt_connector | access_required, tall | 4 |
| `jst_zh_electrode` | JST | electrode_conn | patient_side, access_required | 6 |

## Known gaps

- `nrf52832` — only a 5-page product brief retrievable (Nordic infocenter 403, Mouser bot-blocked). Radio role is covered by `cc2652r` + `mdbt42q`, so this is droppable.
- `analog.com` and `st.com` were unreachable from this machine, so MAX30003 / MAX30102 / ADuM3160 / STM32L071 / STM32WB55 were replaced by TI equivalents in the same roles.
- `varta_cp1254` is a 1-page cell datasheet — dimensions and capacity only. Thermal behaviour will need an explicit assumption, not a citation.
