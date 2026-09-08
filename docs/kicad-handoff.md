# Current direction (user updated)

The user authorized a new, separate MissionPCB KiCad board and a cached ECG demo. Current instructions and run steps: `missionpcb_kicad/README.md`. The older direction below is historical and superseded. Hypnos remains untouched.

# One working Blender scene; KiCad component import support

Working Blender scene: `missionpcb_blender_demo/component_pass/missionpcb_three_cad_components.blend`.
All future edits belong in that file. Older scene files are retained as historical backups. Do not launch another Blender instance; preserve any unsaved live scene edits before reload.

Inspected existing user project: `/Users/dhruvavutukury/Documents/Hypnos/Hypnos.kicad_pcb`. KiCad's 3D Viewer was opened without modifying the project. It displays package CAD for connectors, resistors, diodes, SOT23 devices and two driver packages. Arduino geometry is absent in the visible viewer; its stored model reference names an Arduino Nano rather than specifically an ESP32 Nano. The ADS1292R item is a nine-pin header footprint, not an imported ProtoCentral module assembly. User screenshot also shows 0 track segments and 57 unrouted connections.

This project contains Arduino Nano ESP32, DRV8871 drivers, Peltier connectors, thermistor connectors, vibration connectors and an ADS1292R module connector. It is a different system from the current bare-IC chest-patch BOM. The user clarified that Hypnos was only an example of a view. Do not switch the source board or build a new KiCad board. The requested task is reliable component import into the existing ECG Blender space.

Use KiCad as a local source of component CAD and as a STEP-to-GLB conversion tool for the existing Blender scene. Existing CLI export support was verified locally. Missing 3D models remain missing until sourced and linked; exporting does not synthesize them or complete routing.

Core component audit files are under `missionpcb_blender_demo/parts/verified_core/`. MCU RGE0024H package is verified, charger height adaptation is available, and the official Raytac family outline is cached. Exact AFE RSM0032B and regulator DSS0012A STEP downloads are prepared in TI's Ultra Librarian browser pages, waiting on user terms agreement/CAPTCHA. No terms were accepted and no CAPTCHA was completed by the agent.
