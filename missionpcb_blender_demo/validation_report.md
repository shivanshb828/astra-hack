# MissionPCB ECG chest-patch validation

Generated: 2026-09-08T12:49:48.064411-07:00

Blender: 5.2.1 LTS. Engine: BLENDER_EEVEE.
Environment: macOS-15.6-arm64-arm-64bit-Mach-O; arm64; bundled Python 3.13.13.
Units: one Blender unit = one millimeter. Enclosure: nonconductive polymer.

Authored demonstration placements; this is geometric validation, not an AI placement optimizer.

## Components

| Layout | Component / part | Dimensions mm | Center mm | Heat | Noise | Sensitivity |
|---|---|---|---|---|---|---|
| Naive | STM32L071CB | 12.00, 12.00, 2.00 | 0.00, -10.00, 4.60 | False | False | medium |
| Naive | ADS1292R | 6.00, 6.00, 1.50 | 5.00, 0.00, 4.35 | False | False | high |
| Naive | nRF52-based BLE module (vendor unspecified) | 16.00, 10.00, 2.00 | -20.00, 9.00, 4.60 | False | False | high |
| Naive | TPS62740 | 8.00, 8.00, 3.00 | -5.00, 10.00, 5.10 | True | True | low |
| Naive | MCP73831 | 14.00, 10.00, 3.00 | 18.00, -4.00, 5.10 | True | False | low |
| Naive | JST-SH connector + LiPo (exact variant unspecified) | 10.00, 6.00, 5.00 | -28.00, -11.00, 6.10 | False | False | low |
| Naive | Protection | 4.00, 4.00, 1.50 | -13.00, 1.00, 4.35 | proxy only | n/a | patient-connected / support |
| Naive | ElectrodeA | 3.60, 3.60, 1.30 | -16.00, -3.00, 4.25 | proxy only | n/a | patient-connected / support |
| Naive | ElectrodeB | 3.60, 3.60, 1.30 | -13.00, 16.00, 4.25 | proxy only | n/a | patient-connected / support |
| Naive | LiPo | 24.00, 16.00, 1.60 | -12.00, -5.00, 1.00 | proxy only | n/a | patient-connected / support |
| MissionPCB | STM32L071CB | 12.00, 12.00, 2.00 | 12.00, -11.00, 4.60 | False | False | medium |
| MissionPCB | ADS1292R | 6.00, 6.00, 1.50 | -2.00, 4.00, 4.35 | False | False | high |
| MissionPCB | nRF52-based BLE module (vendor unspecified) | 16.00, 10.00, 2.00 | -27.00, 10.00, 4.60 | False | False | high |
| MissionPCB | TPS62740 | 8.00, 8.00, 3.00 | 29.00, 9.00, 5.10 | True | True | low |
| MissionPCB | MCP73831 | 14.00, 10.00, 3.00 | 27.00, -10.00, 5.10 | True | False | low |
| MissionPCB | JST-SH connector + LiPo (exact variant unspecified) | 10.00, 6.00, 5.00 | 30.00, 0.00, 6.10 | False | False | low |
| MissionPCB | Protection | 4.00, 4.00, 1.50 | -9.00, 6.00, 4.35 | proxy only | n/a | patient-connected / support |
| MissionPCB | ElectrodeA | 3.60, 3.60, 1.30 | -9.00, 0.00, 4.25 | proxy only | n/a | patient-connected / support |
| MissionPCB | ElectrodeB | 3.60, 3.60, 1.30 | -9.00, 12.00, 4.25 | proxy only | n/a | patient-connected / support |
| MissionPCB | LiPo | 24.00, 16.00, 1.60 | 22.00, -5.00, 1.00 | proxy only | n/a | patient-connected / support |

## Naive: FAIL

| Category | Status | Reason |
|---|---|---|
| Patch mechanical fit | PASS | PCB wall clearance |
| Patient-contact heat proxy | FAIL | Source to designated contact region; heat proxy |
| ECG analog noise separation | FAIL | AFE to MCU centers |
| Patient-connected spacing | FAIL | Protection to LiPo XY envelope; spacing proxy |
| RF antenna keep-out | FAIL | Conductors in antenna zone: PowerTrace_1_Naive |
| Regulator / battery heat zone | FAIL | Charger center to sensor footprint |
| Power trace width proxy | FAIL | Measured copper width; example threshold, not ampacity |
| Connector / assembly access | FAIL | Rear opening distance |

| Check | Measured | Rule | Status | Explanation |
|---|---|---|---|---|
| pcb_wall | 6.0000 mm | >= 3 | PASS | PCB wall clearance |
| pcb_floor | 2.0000 mm | >= 0 | PASS | PCB above floor |
| pcb_ceiling | 6.4000 mm | >= 0 | PASS | PCB below ceiling |
| board_MCU | 3.0000 mm | >= 1 | PASS | MCU PCB edge clearance |
| wall_MCU | 9.0000 mm | >= 3 | PASS | MCU wall clearance |
| mount_MCU | 0.0000 mm | <= 0.05 | PASS | MCU mounting gap |
| upright_MCU | 1.0000 boolean | >= 1 | PASS | MCU upright |
| height_MCU | 2.0000 mm | <= 14 | PASS | MCU above PCB |
| ceiling_MCU | 4.4000 mm | >= 0 | PASS | MCU lid clearance |
| board_Sensor | 16.0000 mm | >= 1 | PASS | ECG AFE PCB edge clearance |
| wall_Sensor | 22.0000 mm | >= 3 | PASS | ECG AFE wall clearance |
| mount_Sensor | 0.0000 mm | <= 0.05 | PASS | ECG AFE mounting gap |
| upright_Sensor | 1.0000 boolean | >= 1 | PASS | ECG AFE upright |
| height_Sensor | 1.5000 mm | <= 14 | PASS | ECG AFE above PCB |
| ceiling_Sensor | 4.9000 mm | >= 0 | PASS | ECG AFE lid clearance |
| board_RF | 5.0000 mm | >= 1 | PASS | RF PCB edge clearance |
| wall_RF | 11.0000 mm | >= 3 | PASS | RF wall clearance |
| mount_RF | 0.0000 mm | <= 0.05 | PASS | RF mounting gap |
| upright_RF | 1.0000 boolean | >= 1 | PASS | RF upright |
| height_RF | 2.0000 mm | <= 14 | PASS | RF above PCB |
| ceiling_RF | 4.4000 mm | >= 0 | PASS | RF lid clearance |
| board_Regulator | 5.0000 mm | >= 1 | PASS | Regulator PCB edge clearance |
| wall_Regulator | 11.0000 mm | >= 3 | PASS | Regulator wall clearance |
| mount_Regulator | 0.0000 mm | <= 0.05 | PASS | Regulator mounting gap |
| upright_Regulator | 1.0000 boolean | >= 1 | PASS | Regulator upright |
| height_Regulator | 3.0000 mm | <= 14 | PASS | Regulator above PCB |
| ceiling_Regulator | 3.4000 mm | >= 0 | PASS | Regulator lid clearance |
| board_Driver | 10.0000 mm | >= 1 | PASS | Charger PCB edge clearance |
| wall_Driver | 16.0000 mm | >= 3 | PASS | Charger wall clearance |
| mount_Driver | 0.0000 mm | <= 0.05 | PASS | Charger mounting gap |
| upright_Driver | 1.0000 boolean | >= 1 | PASS | Charger upright |
| height_Driver | 3.0000 mm | <= 14 | PASS | Charger above PCB |
| ceiling_Driver | 3.4000 mm | >= 0 | PASS | Charger lid clearance |
| board_Battery | 3.0000 mm | >= 1 | PASS | Battery PCB edge clearance |
| wall_Battery | 11.0000 mm | >= 3 | PASS | Battery wall clearance |
| mount_Battery | 0.0000 mm | <= 0.05 | PASS | Battery mounting gap |
| upright_Battery | 1.0000 boolean | >= 1 | PASS | Battery upright |
| height_Battery | 5.0000 mm | <= 14 | PASS | Battery above PCB |
| ceiling_Battery | 1.4000 mm | >= 0 | PASS | Battery lid clearance |
| collision_MCU_Sensor | 0.0000 count | <= 0 | PASS | MCU/ECG AFE body overlaps |
| collision_MCU_RF | 0.0000 count | <= 0 | PASS | MCU/RF body overlaps |
| collision_MCU_Regulator | 0.0000 count | <= 0 | PASS | MCU/Regulator body overlaps |
| collision_MCU_Driver | 0.0000 count | <= 0 | PASS | MCU/Charger body overlaps |
| collision_MCU_Battery | 0.0000 count | <= 0 | PASS | MCU/Battery body overlaps |
| collision_Sensor_RF | 0.0000 count | <= 0 | PASS | ECG AFE/RF body overlaps |
| collision_Sensor_Regulator | 0.0000 count | <= 0 | PASS | ECG AFE/Regulator body overlaps |
| collision_Sensor_Driver | 0.0000 count | <= 0 | PASS | ECG AFE/Charger body overlaps |
| collision_Sensor_Battery | 0.0000 count | <= 0 | PASS | ECG AFE/Battery body overlaps |
| collision_RF_Regulator | 0.0000 count | <= 0 | PASS | RF/Regulator body overlaps |
| collision_RF_Driver | 0.0000 count | <= 0 | PASS | RF/Charger body overlaps |
| collision_RF_Battery | 0.0000 count | <= 0 | PASS | RF/Battery body overlaps |
| collision_Regulator_Driver | 0.0000 count | <= 0 | PASS | Regulator/Charger body overlaps |
| collision_Regulator_Battery | 0.0000 count | <= 0 | PASS | Regulator/Battery body overlaps |
| collision_Driver_Battery | 0.0000 count | <= 0 | PASS | Charger/Battery body overlaps |
| center_Sensor | 5.0000 mm | <= 12 | PASS | ECG AFE center offset (demo policy) |
| sensor_heat_Regulator | 14.1421 mm | >= 15 | FAIL | ECG AFE to Regulator centers |
| sensor_disk_Regulator | 9.8995 mm | >= 18 | FAIL | Regulator center to sensor footprint |
| sensor_heat_Driver | 13.6015 mm | >= 15 | FAIL | ECG AFE to Charger centers |
| sensor_disk_Driver | 10.0499 mm | >= 22 | FAIL | Charger center to sensor footprint |
| antenna | 1.0000 count | <= 0 | FAIL | Conductors in antenna zone: PowerTrace_1_Naive |
| battery_gap | 68.0000 mm | <= 12 | FAIL | Rear opening distance |
| battery_inside | 68.0000 mm | >= 0 | PASS | Connector inside enclosure |
| battery_alignment | -10.0000 mm | >= 0 | FAIL | Opening projection clearance |
| battery_facing | 0.0000 degrees | <= 5 | PASS | Connector facing rear |
| battery_corridor | 2.0000 count | <= 0 | FAIL | Insertion corridor obstacles: MCU, Charger |
| center_MCU | 10.0000 mm | <= 18 | PASS | MCU center offset |
| aux_fit_Protection | 16.0000 mm | >= 1 | PASS | Protection board envelope |
| aux_floor_Protection | 3.6000 mm | >= 0 | PASS | Protection floor clearance |
| aux_ceiling_Protection | 4.9000 mm | >= 0 | PASS | Protection lid clearance |
| aux_fit_ElectrodeA | 14.2000 mm | >= 1 | PASS | ElectrodeA board envelope |
| aux_floor_ElectrodeA | 3.6000 mm | >= 0 | PASS | ElectrodeA floor clearance |
| aux_ceiling_ElectrodeA | 5.1000 mm | >= 0 | PASS | ElectrodeA lid clearance |
| aux_fit_ElectrodeB | 1.2000 mm | >= 1 | PASS | ElectrodeB board envelope |
| aux_floor_ElectrodeB | 3.6000 mm | >= 0 | PASS | ElectrodeB floor clearance |
| aux_ceiling_ElectrodeB | 5.1000 mm | >= 0 | PASS | ElectrodeB lid clearance |
| aux_fit_LiPo | 6.0000 mm | >= 1 | PASS | LiPo board envelope |
| aux_floor_LiPo | 0.2000 mm | >= 0 | PASS | LiPo floor clearance |
| aux_ceiling_LiPo | 8.2000 mm | >= 0 | PASS | LiPo lid clearance |
| aux_collision_MCU_Protection | 0.0000 count | <= 0 | PASS | MCU/Protection body overlap |
| aux_collision_MCU_ElectrodeA | 0.0000 count | <= 0 | PASS | MCU/ElectrodeA body overlap |
| aux_collision_MCU_ElectrodeB | 0.0000 count | <= 0 | PASS | MCU/ElectrodeB body overlap |
| aux_collision_MCU_LiPo | 0.0000 count | <= 0 | PASS | MCU/LiPo body overlap |
| aux_collision_Sensor_Protection | 0.0000 count | <= 0 | PASS | Sensor/Protection body overlap |
| aux_collision_Sensor_ElectrodeA | 0.0000 count | <= 0 | PASS | Sensor/ElectrodeA body overlap |
| aux_collision_Sensor_ElectrodeB | 0.0000 count | <= 0 | PASS | Sensor/ElectrodeB body overlap |
| aux_collision_Sensor_LiPo | 0.0000 count | <= 0 | PASS | Sensor/LiPo body overlap |
| aux_collision_RF_Protection | 0.0000 count | <= 0 | PASS | RF/Protection body overlap |
| aux_collision_RF_ElectrodeA | 0.0000 count | <= 0 | PASS | RF/ElectrodeA body overlap |
| aux_collision_RF_ElectrodeB | 0.0000 count | <= 0 | PASS | RF/ElectrodeB body overlap |
| aux_collision_RF_LiPo | 0.0000 count | <= 0 | PASS | RF/LiPo body overlap |
| aux_collision_Regulator_Protection | 0.0000 count | <= 0 | PASS | Regulator/Protection body overlap |
| aux_collision_Regulator_ElectrodeA | 0.0000 count | <= 0 | PASS | Regulator/ElectrodeA body overlap |
| aux_collision_Regulator_ElectrodeB | 0.0000 count | <= 0 | PASS | Regulator/ElectrodeB body overlap |
| aux_collision_Regulator_LiPo | 0.0000 count | <= 0 | PASS | Regulator/LiPo body overlap |
| aux_collision_Driver_Protection | 0.0000 count | <= 0 | PASS | Driver/Protection body overlap |
| aux_collision_Driver_ElectrodeA | 0.0000 count | <= 0 | PASS | Driver/ElectrodeA body overlap |
| aux_collision_Driver_ElectrodeB | 0.0000 count | <= 0 | PASS | Driver/ElectrodeB body overlap |
| aux_collision_Driver_LiPo | 0.0000 count | <= 0 | PASS | Driver/LiPo body overlap |
| aux_collision_Battery_Protection | 0.0000 count | <= 0 | PASS | Battery/Protection body overlap |
| aux_collision_Battery_ElectrodeA | 0.0000 count | <= 0 | PASS | Battery/ElectrodeA body overlap |
| aux_collision_Battery_ElectrodeB | 0.0000 count | <= 0 | PASS | Battery/ElectrodeB body overlap |
| aux_collision_Battery_LiPo | 0.0000 count | <= 0 | PASS | Battery/LiPo body overlap |
| aux_collision_Protection_ElectrodeA | 0.0000 count | <= 0 | PASS | Protection/ElectrodeA body overlap |
| aux_collision_Protection_ElectrodeB | 0.0000 count | <= 0 | PASS | Protection/ElectrodeB body overlap |
| aux_collision_Protection_LiPo | 0.0000 count | <= 0 | PASS | Protection/LiPo body overlap |
| aux_collision_ElectrodeA_ElectrodeB | 0.0000 count | <= 0 | PASS | ElectrodeA/ElectrodeB body overlap |
| aux_collision_ElectrodeA_LiPo | 0.0000 count | <= 0 | PASS | ElectrodeA/LiPo body overlap |
| aux_collision_ElectrodeB_LiPo | 0.0000 count | <= 0 | PASS | ElectrodeB/LiPo body overlap |
| ecg_noise_Regulator | 14.1421 mm | >= 20 | FAIL | AFE to Regulator centers |
| ecg_noise_RF | 26.5707 mm | >= 20 | PASS | AFE to RF centers |
| ecg_noise_MCU | 11.1803 mm | >= 18 | FAIL | AFE to MCU centers |
| skin_heat_Regulator | 0.0000 mm | >= 18 | FAIL | Source to designated contact region; heat proxy |
| skin_heat_Driver | 14.0357 mm | >= 22 | FAIL | Source to designated contact region; heat proxy |
| skin_heat_LiPo | 2.0000 mm | >= 9 | FAIL | Source to designated contact region; heat proxy |
| battery_afe_heat | 14.1421 mm | >= 9 | PASS | LiPo center to AFE footprint; heat proxy |
| patient_gap_Sensor_MCU | 1.0000 mm | >= 3 | FAIL | Sensor to MCU XY envelope; spacing proxy |
| patient_gap_Sensor_RF | 14.0357 mm | >= 3 | PASS | Sensor to RF XY envelope; spacing proxy |
| patient_gap_Sensor_Regulator | 4.2426 mm | >= 3 | PASS | Sensor to Regulator XY envelope; spacing proxy |
| patient_gap_Sensor_Driver | 3.0000 mm | >= 3 | PASS | Sensor to Driver XY envelope; spacing proxy |
| patient_gap_Sensor_Battery | 25.4951 mm | >= 3 | PASS | Sensor to Battery XY envelope; spacing proxy |
| patient_gap_Sensor_LiPo | 2.0000 mm | >= 3 | FAIL | Sensor to LiPo XY envelope; spacing proxy |
| patient_gap_Protection_MCU | 5.8310 mm | >= 3 | PASS | Protection to MCU XY envelope; spacing proxy |
| patient_gap_Protection_RF | 1.0000 mm | >= 3 | FAIL | Protection to RF XY envelope; spacing proxy |
| patient_gap_Protection_Regulator | 3.6056 mm | >= 3 | PASS | Protection to Regulator XY envelope; spacing proxy |
| patient_gap_Protection_Driver | 22.0000 mm | >= 3 | PASS | Protection to Driver XY envelope; spacing proxy |
| patient_gap_Protection_Battery | 10.6301 mm | >= 3 | PASS | Protection to Battery XY envelope; spacing proxy |
| patient_gap_Protection_LiPo | 0.0000 mm | >= 3 | FAIL | Protection to LiPo XY envelope; spacing proxy |
| patient_gap_ElectrodeA_MCU | 8.2000 mm | >= 3 | PASS | ElectrodeA to MCU XY envelope; spacing proxy |
| patient_gap_ElectrodeA_RF | 5.2000 mm | >= 3 | PASS | ElectrodeA to RF XY envelope; spacing proxy |
| patient_gap_ElectrodeA_Regulator | 8.8814 mm | >= 3 | PASS | ElectrodeA to Regulator XY envelope; spacing proxy |
| patient_gap_ElectrodeA_Driver | 25.2000 mm | >= 3 | PASS | ElectrodeA to Driver XY envelope; spacing proxy |
| patient_gap_ElectrodeA_Battery | 6.1057 mm | >= 3 | PASS | ElectrodeA to Battery XY envelope; spacing proxy |
| patient_gap_ElectrodeA_LiPo | 0.0000 mm | >= 3 | FAIL | ElectrodeA to LiPo XY envelope; spacing proxy |
| patient_gap_ElectrodeB_MCU | 18.9283 mm | >= 3 | PASS | ElectrodeB to MCU XY envelope; spacing proxy |
| patient_gap_ElectrodeB_RF | 0.2000 mm | >= 3 | FAIL | ElectrodeB to RF XY envelope; spacing proxy |
| patient_gap_ElectrodeB_Regulator | 2.2091 mm | >= 3 | FAIL | ElectrodeB to Regulator XY envelope; spacing proxy |
| patient_gap_ElectrodeB_Driver | 25.8279 mm | >= 3 | PASS | ElectrodeB to Driver XY envelope; spacing proxy |
| patient_gap_ElectrodeB_Battery | 23.6660 mm | >= 3 | PASS | ElectrodeB to Battery XY envelope; spacing proxy |
| patient_gap_ElectrodeB_LiPo | 11.2000 mm | >= 3 | PASS | ElectrodeB to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_Naive_MCU | 9.0000 mm | >= 3 | PASS | PatientTrace_0_0_Naive to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_Naive_RF | 2.0000 mm | >= 3 | FAIL | PatientTrace_0_0_Naive to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_Naive_Regulator | 7.2111 mm | >= 3 | PASS | PatientTrace_0_0_Naive to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_Naive_Driver | 26.0000 mm | >= 3 | PASS | PatientTrace_0_0_Naive to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_Naive_Battery | 7.2111 mm | >= 3 | PASS | PatientTrace_0_0_Naive to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_Naive_LiPo | 0.0000 mm | >= 3 | FAIL | PatientTrace_0_0_Naive to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_1_Naive_MCU | 7.2111 mm | >= 3 | PASS | PatientTrace_0_1_Naive to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_1_Naive_RF | 2.0000 mm | >= 3 | FAIL | PatientTrace_0_1_Naive to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_1_Naive_Regulator | 5.0000 mm | >= 3 | PASS | PatientTrace_0_1_Naive to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_1_Naive_Driver | 23.0000 mm | >= 3 | PASS | PatientTrace_0_1_Naive to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_1_Naive_Battery | 10.0000 mm | >= 3 | PASS | PatientTrace_0_1_Naive to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_1_Naive_LiPo | 0.0000 mm | >= 3 | FAIL | PatientTrace_0_1_Naive to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_Naive_MCU | 7.2111 mm | >= 3 | PASS | PatientTrace_1_0_Naive to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_Naive_RF | 0.0000 mm | >= 3 | FAIL | PatientTrace_1_0_Naive to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_Naive_Regulator | 3.0000 mm | >= 3 | PASS | PatientTrace_1_0_Naive to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_Naive_Driver | 23.0000 mm | >= 3 | PASS | PatientTrace_1_0_Naive to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_Naive_Battery | 12.0416 mm | >= 3 | PASS | PatientTrace_1_0_Naive to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_Naive_LiPo | 0.0000 mm | >= 3 | FAIL | PatientTrace_1_0_Naive to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_Naive_MCU | 4.0000 mm | >= 3 | PASS | PatientTrace_2_0_Naive to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_Naive_RF | 2.0000 mm | >= 3 | FAIL | PatientTrace_2_0_Naive to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_Naive_Regulator | 4.0000 mm | >= 3 | PASS | PatientTrace_2_0_Naive to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_Naive_Driver | 5.0000 mm | >= 3 | PASS | PatientTrace_2_0_Naive to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_Naive_Battery | 12.0416 mm | >= 3 | PASS | PatientTrace_2_0_Naive to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_Naive_LiPo | 0.0000 mm | >= 3 | FAIL | PatientTrace_2_0_Naive to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_Naive_MCU | 3.0000 mm | >= 3 | PASS | PatientTrace_2_1_Naive to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_Naive_RF | 16.1245 mm | >= 3 | PASS | PatientTrace_2_1_Naive to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_Naive_Regulator | 6.4031 mm | >= 3 | PASS | PatientTrace_2_1_Naive to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_Naive_Driver | 5.0000 mm | >= 3 | PASS | PatientTrace_2_1_Naive to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_Naive_Battery | 27.8927 mm | >= 3 | PASS | PatientTrace_2_1_Naive to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_Naive_LiPo | 4.0000 mm | >= 3 | PASS | PatientTrace_2_1_Naive to LiPo XY envelope; spacing proxy |
| trace_width_PowerTrace_0_Naive | 0.2500 mm | >= 0.6 | FAIL | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_1_Naive | 0.2500 mm | >= 0.6 | FAIL | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_2_Naive | 0.2500 mm | >= 0.6 | FAIL | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_3_Naive | 0.2500 mm | >= 0.6 | FAIL | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_4_Naive | 0.2500 mm | >= 0.6 | FAIL | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_5_Naive | 0.2500 mm | >= 0.6 | FAIL | Measured copper width; example threshold, not ampacity |

## MissionPCB: PASS

| Category | Status | Reason |
|---|---|---|
| Patch mechanical fit | PASS | PCB wall clearance |
| Patient-contact heat proxy | PASS | Source to designated contact region; heat proxy |
| ECG analog noise separation | PASS | AFE to Regulator centers |
| Patient-connected spacing | PASS | Sensor to MCU XY envelope; spacing proxy |
| RF antenna keep-out | PASS | Conductors in antenna zone |
| Regulator / battery heat zone | PASS | Charger center to sensor footprint |
| Power trace width proxy | PASS | Measured copper width; example threshold, not ampacity |
| Connector / assembly access | PASS | Rear opening distance |

| Check | Measured | Rule | Status | Explanation |
|---|---|---|---|---|
| pcb_wall | 6.0000 mm | >= 3 | PASS | PCB wall clearance |
| pcb_floor | 2.0000 mm | >= 0 | PASS | PCB above floor |
| pcb_ceiling | 6.4000 mm | >= 0 | PASS | PCB below ceiling |
| board_MCU | 2.0000 mm | >= 1 | PASS | MCU PCB edge clearance |
| wall_MCU | 8.0000 mm | >= 3 | PASS | MCU wall clearance |
| mount_MCU | 0.0000 mm | <= 0.05 | PASS | MCU mounting gap |
| upright_MCU | 1.0000 boolean | >= 1 | PASS | MCU upright |
| height_MCU | 2.0000 mm | <= 14 | PASS | MCU above PCB |
| ceiling_MCU | 4.4000 mm | >= 0 | PASS | MCU lid clearance |
| board_Sensor | 12.0000 mm | >= 1 | PASS | ECG AFE PCB edge clearance |
| wall_Sensor | 18.0000 mm | >= 3 | PASS | ECG AFE wall clearance |
| mount_Sensor | 0.0000 mm | <= 0.05 | PASS | ECG AFE mounting gap |
| upright_Sensor | 1.0000 boolean | >= 1 | PASS | ECG AFE upright |
| height_Sensor | 1.5000 mm | <= 14 | PASS | ECG AFE above PCB |
| ceiling_Sensor | 4.9000 mm | >= 0 | PASS | ECG AFE lid clearance |
| board_RF | 1.0000 mm | >= 1 | PASS | RF PCB edge clearance |
| wall_RF | 10.0000 mm | >= 3 | PASS | RF wall clearance |
| mount_RF | 0.0000 mm | <= 0.05 | PASS | RF mounting gap |
| upright_RF | 1.0000 boolean | >= 1 | PASS | RF upright |
| height_RF | 2.0000 mm | <= 14 | PASS | RF above PCB |
| ceiling_RF | 4.4000 mm | >= 0 | PASS | RF lid clearance |
| board_Regulator | 3.0000 mm | >= 1 | PASS | Regulator PCB edge clearance |
| wall_Regulator | 12.0000 mm | >= 3 | PASS | Regulator wall clearance |
| mount_Regulator | 0.0000 mm | <= 0.05 | PASS | Regulator mounting gap |
| upright_Regulator | 1.0000 boolean | >= 1 | PASS | Regulator upright |
| height_Regulator | 3.0000 mm | <= 14 | PASS | Regulator above PCB |
| ceiling_Regulator | 3.4000 mm | >= 0 | PASS | Regulator lid clearance |
| board_Driver | 2.0000 mm | >= 1 | PASS | Charger PCB edge clearance |
| wall_Driver | 10.0000 mm | >= 3 | PASS | Charger wall clearance |
| mount_Driver | 0.0000 mm | <= 0.05 | PASS | Charger mounting gap |
| upright_Driver | 1.0000 boolean | >= 1 | PASS | Charger upright |
| height_Driver | 3.0000 mm | <= 14 | PASS | Charger above PCB |
| ceiling_Driver | 3.4000 mm | >= 0 | PASS | Charger lid clearance |
| board_Battery | 1.0000 mm | >= 1 | PASS | Battery PCB edge clearance |
| wall_Battery | 10.0000 mm | >= 3 | PASS | Battery wall clearance |
| mount_Battery | 0.0000 mm | <= 0.05 | PASS | Battery mounting gap |
| upright_Battery | 1.0000 boolean | >= 1 | PASS | Battery upright |
| height_Battery | 5.0000 mm | <= 14 | PASS | Battery above PCB |
| ceiling_Battery | 1.4000 mm | >= 0 | PASS | Battery lid clearance |
| collision_MCU_Sensor | 0.0000 count | <= 0 | PASS | MCU/ECG AFE body overlaps |
| collision_MCU_RF | 0.0000 count | <= 0 | PASS | MCU/RF body overlaps |
| collision_MCU_Regulator | 0.0000 count | <= 0 | PASS | MCU/Regulator body overlaps |
| collision_MCU_Driver | 0.0000 count | <= 0 | PASS | MCU/Charger body overlaps |
| collision_MCU_Battery | 0.0000 count | <= 0 | PASS | MCU/Battery body overlaps |
| collision_Sensor_RF | 0.0000 count | <= 0 | PASS | ECG AFE/RF body overlaps |
| collision_Sensor_Regulator | 0.0000 count | <= 0 | PASS | ECG AFE/Regulator body overlaps |
| collision_Sensor_Driver | 0.0000 count | <= 0 | PASS | ECG AFE/Charger body overlaps |
| collision_Sensor_Battery | 0.0000 count | <= 0 | PASS | ECG AFE/Battery body overlaps |
| collision_RF_Regulator | 0.0000 count | <= 0 | PASS | RF/Regulator body overlaps |
| collision_RF_Driver | 0.0000 count | <= 0 | PASS | RF/Charger body overlaps |
| collision_RF_Battery | 0.0000 count | <= 0 | PASS | RF/Battery body overlaps |
| collision_Regulator_Driver | 0.0000 count | <= 0 | PASS | Regulator/Charger body overlaps |
| collision_Regulator_Battery | 0.0000 count | <= 0 | PASS | Regulator/Battery body overlaps |
| collision_Driver_Battery | 0.0000 count | <= 0 | PASS | Charger/Battery body overlaps |
| center_Sensor | 4.4721 mm | <= 12 | PASS | ECG AFE center offset (demo policy) |
| sensor_heat_Regulator | 31.4006 mm | >= 15 | PASS | ECG AFE to Regulator centers |
| sensor_disk_Regulator | 28.0713 mm | >= 18 | PASS | Regulator center to sensor footprint |
| sensor_heat_Driver | 32.2025 mm | >= 15 | PASS | ECG AFE to Charger centers |
| sensor_disk_Driver | 28.2312 mm | >= 22 | PASS | Charger center to sensor footprint |
| antenna | 0.0000 count | <= 0 | PASS | Conductors in antenna zone |
| battery_gap | 10.0000 mm | <= 12 | PASS | Rear opening distance |
| battery_inside | 10.0000 mm | >= 0 | PASS | Connector inside enclosure |
| battery_alignment | 0.4000 mm | >= 0 | PASS | Opening projection clearance |
| battery_facing | 0.0000 degrees | <= 5 | PASS | Connector facing rear |
| battery_corridor | 0.0000 count | <= 0 | PASS | Insertion corridor obstacles |
| center_MCU | 16.2788 mm | <= 18 | PASS | MCU center offset |
| aux_fit_Protection | 11.0000 mm | >= 1 | PASS | Protection board envelope |
| aux_floor_Protection | 3.6000 mm | >= 0 | PASS | Protection floor clearance |
| aux_ceiling_Protection | 4.9000 mm | >= 0 | PASS | Protection lid clearance |
| aux_fit_ElectrodeA | 17.2000 mm | >= 1 | PASS | ElectrodeA board envelope |
| aux_floor_ElectrodeA | 3.6000 mm | >= 0 | PASS | ElectrodeA floor clearance |
| aux_ceiling_ElectrodeA | 5.1000 mm | >= 0 | PASS | ElectrodeA lid clearance |
| aux_fit_ElectrodeB | 5.2000 mm | >= 1 | PASS | ElectrodeB board envelope |
| aux_floor_ElectrodeB | 3.6000 mm | >= 0 | PASS | ElectrodeB floor clearance |
| aux_ceiling_ElectrodeB | 5.1000 mm | >= 0 | PASS | ElectrodeB lid clearance |
| aux_fit_LiPo | 2.0000 mm | >= 1 | PASS | LiPo board envelope |
| aux_floor_LiPo | 0.2000 mm | >= 0 | PASS | LiPo floor clearance |
| aux_ceiling_LiPo | 8.2000 mm | >= 0 | PASS | LiPo lid clearance |
| aux_collision_MCU_Protection | 0.0000 count | <= 0 | PASS | MCU/Protection body overlap |
| aux_collision_MCU_ElectrodeA | 0.0000 count | <= 0 | PASS | MCU/ElectrodeA body overlap |
| aux_collision_MCU_ElectrodeB | 0.0000 count | <= 0 | PASS | MCU/ElectrodeB body overlap |
| aux_collision_MCU_LiPo | 0.0000 count | <= 0 | PASS | MCU/LiPo body overlap |
| aux_collision_Sensor_Protection | 0.0000 count | <= 0 | PASS | Sensor/Protection body overlap |
| aux_collision_Sensor_ElectrodeA | 0.0000 count | <= 0 | PASS | Sensor/ElectrodeA body overlap |
| aux_collision_Sensor_ElectrodeB | 0.0000 count | <= 0 | PASS | Sensor/ElectrodeB body overlap |
| aux_collision_Sensor_LiPo | 0.0000 count | <= 0 | PASS | Sensor/LiPo body overlap |
| aux_collision_RF_Protection | 0.0000 count | <= 0 | PASS | RF/Protection body overlap |
| aux_collision_RF_ElectrodeA | 0.0000 count | <= 0 | PASS | RF/ElectrodeA body overlap |
| aux_collision_RF_ElectrodeB | 0.0000 count | <= 0 | PASS | RF/ElectrodeB body overlap |
| aux_collision_RF_LiPo | 0.0000 count | <= 0 | PASS | RF/LiPo body overlap |
| aux_collision_Regulator_Protection | 0.0000 count | <= 0 | PASS | Regulator/Protection body overlap |
| aux_collision_Regulator_ElectrodeA | 0.0000 count | <= 0 | PASS | Regulator/ElectrodeA body overlap |
| aux_collision_Regulator_ElectrodeB | 0.0000 count | <= 0 | PASS | Regulator/ElectrodeB body overlap |
| aux_collision_Regulator_LiPo | 0.0000 count | <= 0 | PASS | Regulator/LiPo body overlap |
| aux_collision_Driver_Protection | 0.0000 count | <= 0 | PASS | Driver/Protection body overlap |
| aux_collision_Driver_ElectrodeA | 0.0000 count | <= 0 | PASS | Driver/ElectrodeA body overlap |
| aux_collision_Driver_ElectrodeB | 0.0000 count | <= 0 | PASS | Driver/ElectrodeB body overlap |
| aux_collision_Driver_LiPo | 0.0000 count | <= 0 | PASS | Driver/LiPo body overlap |
| aux_collision_Battery_Protection | 0.0000 count | <= 0 | PASS | Battery/Protection body overlap |
| aux_collision_Battery_ElectrodeA | 0.0000 count | <= 0 | PASS | Battery/ElectrodeA body overlap |
| aux_collision_Battery_ElectrodeB | 0.0000 count | <= 0 | PASS | Battery/ElectrodeB body overlap |
| aux_collision_Battery_LiPo | 0.0000 count | <= 0 | PASS | Battery/LiPo body overlap |
| aux_collision_Protection_ElectrodeA | 0.0000 count | <= 0 | PASS | Protection/ElectrodeA body overlap |
| aux_collision_Protection_ElectrodeB | 0.0000 count | <= 0 | PASS | Protection/ElectrodeB body overlap |
| aux_collision_Protection_LiPo | 0.0000 count | <= 0 | PASS | Protection/LiPo body overlap |
| aux_collision_ElectrodeA_ElectrodeB | 0.0000 count | <= 0 | PASS | ElectrodeA/ElectrodeB body overlap |
| aux_collision_ElectrodeA_LiPo | 0.0000 count | <= 0 | PASS | ElectrodeA/LiPo body overlap |
| aux_collision_ElectrodeB_LiPo | 0.0000 count | <= 0 | PASS | ElectrodeB/LiPo body overlap |
| ecg_noise_Regulator | 31.4006 mm | >= 20 | PASS | AFE to Regulator centers |
| ecg_noise_RF | 25.7099 mm | >= 20 | PASS | AFE to RF centers |
| ecg_noise_MCU | 20.5183 mm | >= 18 | PASS | AFE to MCU centers |
| skin_heat_Regulator | 25.0000 mm | >= 18 | PASS | Source to designated contact region; heat proxy |
| skin_heat_Driver | 24.0416 mm | >= 22 | PASS | Source to designated contact region; heat proxy |
| skin_heat_LiPo | 18.1108 mm | >= 9 | PASS | Source to designated contact region; heat proxy |
| battery_afe_heat | 21.8403 mm | >= 9 | PASS | LiPo center to AFE footprint; heat proxy |
| patient_gap_Sensor_MCU | 7.8102 mm | >= 3 | PASS | Sensor to MCU XY envelope; spacing proxy |
| patient_gap_Sensor_RF | 14.0000 mm | >= 3 | PASS | Sensor to RF XY envelope; spacing proxy |
| patient_gap_Sensor_Regulator | 24.0000 mm | >= 3 | PASS | Sensor to Regulator XY envelope; spacing proxy |
| patient_gap_Sensor_Driver | 19.9249 mm | >= 3 | PASS | Sensor to Driver XY envelope; spacing proxy |
| patient_gap_Sensor_Battery | 24.0000 mm | >= 3 | PASS | Sensor to Battery XY envelope; spacing proxy |
| patient_gap_Sensor_LiPo | 9.0000 mm | >= 3 | PASS | Sensor to LiPo XY envelope; spacing proxy |
| patient_gap_Protection_MCU | 15.8114 mm | >= 3 | PASS | Protection to MCU XY envelope; spacing proxy |
| patient_gap_Protection_RF | 8.0000 mm | >= 3 | PASS | Protection to RF XY envelope; spacing proxy |
| patient_gap_Protection_Regulator | 32.0000 mm | >= 3 | PASS | Protection to Regulator XY envelope; spacing proxy |
| patient_gap_Protection_Driver | 28.4605 mm | >= 3 | PASS | Protection to Driver XY envelope; spacing proxy |
| patient_gap_Protection_Battery | 32.0156 mm | >= 3 | PASS | Protection to Battery XY envelope; spacing proxy |
| patient_gap_Protection_LiPo | 17.0294 mm | >= 3 | PASS | Protection to LiPo XY envelope; spacing proxy |
| patient_gap_ElectrodeA_MCU | 13.5823 mm | >= 3 | PASS | ElectrodeA to MCU XY envelope; spacing proxy |
| patient_gap_ElectrodeA_RF | 8.8023 mm | >= 3 | PASS | ElectrodeA to RF XY envelope; spacing proxy |
| patient_gap_ElectrodeA_Regulator | 32.3586 mm | >= 3 | PASS | ElectrodeA to Regulator XY envelope; spacing proxy |
| patient_gap_ElectrodeA_Driver | 27.3876 mm | >= 3 | PASS | ElectrodeA to Driver XY envelope; spacing proxy |
| patient_gap_ElectrodeA_Battery | 32.2000 mm | >= 3 | PASS | ElectrodeA to Battery XY envelope; spacing proxy |
| patient_gap_ElectrodeA_LiPo | 17.2000 mm | >= 3 | PASS | ElectrodeA to LiPo XY envelope; spacing proxy |
| patient_gap_ElectrodeB_MCU | 20.1316 mm | >= 3 | PASS | ElectrodeB to MCU XY envelope; spacing proxy |
| patient_gap_ElectrodeB_RF | 8.2000 mm | >= 3 | PASS | ElectrodeB to RF XY envelope; spacing proxy |
| patient_gap_ElectrodeB_Regulator | 32.2000 mm | >= 3 | PASS | ElectrodeB to Regulator XY envelope; spacing proxy |
| patient_gap_ElectrodeB_Driver | 31.1589 mm | >= 3 | PASS | ElectrodeB to Driver XY envelope; spacing proxy |
| patient_gap_ElectrodeB_Battery | 32.9952 mm | >= 3 | PASS | ElectrodeB to Battery XY envelope; spacing proxy |
| patient_gap_ElectrodeB_LiPo | 18.6462 mm | >= 3 | PASS | ElectrodeB to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_MissionPCB_MCU | 14.5602 mm | >= 3 | PASS | PatientTrace_0_0_MissionPCB to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_MissionPCB_RF | 9.0000 mm | >= 3 | PASS | PatientTrace_0_0_MissionPCB to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_MissionPCB_Regulator | 33.0000 mm | >= 3 | PASS | PatientTrace_0_0_MissionPCB to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_MissionPCB_Driver | 28.2843 mm | >= 3 | PASS | PatientTrace_0_0_MissionPCB to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_MissionPCB_Battery | 33.0000 mm | >= 3 | PASS | PatientTrace_0_0_MissionPCB to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_0_0_MissionPCB_LiPo | 18.0000 mm | >= 3 | PASS | PatientTrace_0_0_MissionPCB to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_MissionPCB_MCU | 17.2047 mm | >= 3 | PASS | PatientTrace_1_0_MissionPCB to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_MissionPCB_RF | 9.0000 mm | >= 3 | PASS | PatientTrace_1_0_MissionPCB to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_MissionPCB_Regulator | 33.0000 mm | >= 3 | PASS | PatientTrace_1_0_MissionPCB to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_MissionPCB_Driver | 29.7321 mm | >= 3 | PASS | PatientTrace_1_0_MissionPCB to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_MissionPCB_Battery | 33.0606 mm | >= 3 | PASS | PatientTrace_1_0_MissionPCB to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_1_0_MissionPCB_LiPo | 18.1108 mm | >= 3 | PASS | PatientTrace_1_0_MissionPCB to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_MissionPCB_MCU | 12.2066 mm | >= 3 | PASS | PatientTrace_2_0_MissionPCB to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_MissionPCB_RF | 9.0000 mm | >= 3 | PASS | PatientTrace_2_0_MissionPCB to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_MissionPCB_Regulator | 26.0000 mm | >= 3 | PASS | PatientTrace_2_0_MissionPCB to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_MissionPCB_Driver | 23.2594 mm | >= 3 | PASS | PatientTrace_2_0_MissionPCB to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_MissionPCB_Battery | 26.0768 mm | >= 3 | PASS | PatientTrace_2_0_MissionPCB to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_0_MissionPCB_LiPo | 11.1803 mm | >= 3 | PASS | PatientTrace_2_0_MissionPCB to LiPo XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_MissionPCB_MCU | 10.6301 mm | >= 3 | PASS | PatientTrace_2_1_MissionPCB to MCU XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_MissionPCB_RF | 16.0000 mm | >= 3 | PASS | PatientTrace_2_1_MissionPCB to RF XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_MissionPCB_Regulator | 26.0000 mm | >= 3 | PASS | PatientTrace_2_1_MissionPCB to Regulator XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_MissionPCB_Driver | 22.4722 mm | >= 3 | PASS | PatientTrace_2_1_MissionPCB to Driver XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_MissionPCB_Battery | 26.0000 mm | >= 3 | PASS | PatientTrace_2_1_MissionPCB to Battery XY envelope; spacing proxy |
| patient_gap_PatientTrace_2_1_MissionPCB_LiPo | 11.0000 mm | >= 3 | PASS | PatientTrace_2_1_MissionPCB to LiPo XY envelope; spacing proxy |
| trace_width_PowerTrace_0_MissionPCB | 0.6000 mm | >= 0.6 | PASS | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_1_MissionPCB | 0.6000 mm | >= 0.6 | PASS | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_2_MissionPCB | 0.6000 mm | >= 0.6 | PASS | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_3_MissionPCB | 0.6000 mm | >= 0.6 | PASS | Measured copper width; example threshold, not ampacity |
| trace_width_PowerTrace_4_MissionPCB | 0.6000 mm | >= 0.6 | PASS | Measured copper width; example threshold, not ampacity |

## Simplifications

This demo uses geometric constraints and approximate heat/noise zones. It is not a substitute for thermal FEA, SPICE electrical simulation, electromagnetic simulation, or manufacturing DFM review.

Distances are XY center separations. Heat additionally checks sensor-footprint clearance from the drawn disk. Collision and antenna tests use conservative rectangles/bounding boxes. Package tilt fails mounting. Copper is illustrative and has no electrical netlist. Antenna keep-out excludes its own package/pads and permits nonconductive air, plastic and copper-free FR-4.
Demo policies: AFE/MCU center offsets ≤12/18 mm, PCB edge margin ≥1 mm, mounting gap ≤0.05 mm, rear access gap ≤12 mm, connector facing within 5 degrees. Connector access uses a straight clearance corridor, not cable bend physics.

## Verification evidence

14 Python unit tests passed. Blender integration passed: independent editable components, dimensions, eight ECG categories, dashboard/result agreement, actual movement -> FAIL -> restore PASS, stale detection, layout-root invariance, fixed antenna clearance under RF scaling, runtime registration and deterministic demo controls. Standalone copied .blend passed the same integration test using embedded code without adjacent source files. GUI inspection confirmed opening, orbit, top-down camera control and individual AFE selection/metadata; the complete button flow was verified by automated Blender operations. Both final 1920 x 1080 views rendered successfully and were visually inspected.

## Artifacts

- missionpcb_lean_constraint_demo.blend
- renders/top_down.png
- renders/isometric.png
- validation_results.json

## Next steps

- KiCad import/export
- Part metadata ingestion
- Real thermal solver
- SPICE/electrical checks
- Enclosure CAD/STL import
- Drag-and-drop web UI

## ECG interpretation and limits

All PASS results mean only that these configured geometric demo policies pass. No skin temperature, electrical leakage, isolation, creepage path over real materials, biosignal noise floor, or copper ampacity has been simulated. Charging while worn and clinical ECG performance are not validated.
Patient-contact heat measures XY distance from a heat source to the designated contact region, not the temperature of the entire skin-facing patch. Moving heat outward is a placement heuristic, not proof of patient safety.
Patient-connected spacing is conservative XY envelope spacing. Trace width is measured from curve bevel geometry and compared with an example 0.6 mm rule; the illustrative 0.15 A input is not used as an ampacity calculation.
The six named IC/module roles retain illustrative functional placement envelopes, which include room for surrounding circuitry. They are not manufacturer footprint-accurate package models. BLE module, JST-SH connector and LiPo variants are unspecified.
MCP73831 is a linear charger, so it is treated as a potential heat source rather than as a switching regulator. ADS1292R supports two channels; this demo depicts a single-lead mission and does not implement its electrical circuit.
Standards-informed review categories; all numeric separation/heat-radius policies are authored examples, not values extracted from a medical standard. No IEC compliance or medical certification is claimed.

## Offline part references

- STM32L071CB — https://www.st.com/en/microcontrollers-microprocessors/stm32l071cb.html
- ADS1292R — https://www.ti.com/product/ADS1292R
- nRF52-based BLE module (vendor unspecified) — https://www.nordicsemi.com/Products/nRF52832/Modules
- TPS62740 — https://www.ti.com/product/TPS62740
- MCP73831 — https://www.microchip.com/en-us/product/mcp73831
- JST-SH connector + LiPo (exact variant unspecified) — exact variant unspecified

See cached part_metadata.md for manufacturer context. FDA testing context: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/electromagnetic-compatibility-emc-medical-devices . This is a testing-context reference, not a source for the demo distance thresholds.
