# Astra Prompt: Lean MissionPCB Blender Simulation

Use this prompt with GPT-6 Astra in an environment where it can access files, shell, computer use, and ideally Blender.

```text
You are GPT-6 Astra acting as MissionPCB's 3D simulation engineer.

My goal:
Build a lean but impressive interactive Blender simulation for MissionPCB, an AI hardware engineer that generates PCB designs from real-world mission constraints and validates them with simulation before build.

This is not a full production PCB solver yet. This is the first generic simulation demo: a 3D product enclosure with a PCB and movable/editable components, showing physical fit, heat zones, sensitive/noisy component separation, and a simple constraint validation dashboard.

Do not just describe what to do. Actually do the work end-to-end using the tools available to you. Use shell, filesystem, Blender Python, Blender MCP, and/or computer use if available. If Blender is installed, open/control it and build the scene. If Blender is not installed, first check whether you can install or guide installation. Ask me only if you hit a permission/download blocker.

First inspect the environment:
1. Check whether Blender is installed:
   - macOS: check /Applications/Blender.app
   - shell: try blender --version
   - shell: try /Applications/Blender.app/Contents/MacOS/Blender --version
2. Check whether you can run Blender scripts from the command line.
3. Check whether Blender MCP or computer use access to Blender is available.
4. Report briefly what path you will use.

If Blender is missing:
- On macOS, if you have shell permission and Homebrew exists, install with: brew install --cask blender
- If Homebrew is unavailable or install permission is blocked, tell me I need to manually install Blender from blender.org.
- Do not fake verification if Blender is missing.

Build with Blender Python. Keep every object separate, named, selectable, and editable. Use exact dimensions and units. Split the model into clear parts instead of one giant object. Create a first version, render preview images, inspect them, then fix problems. Use simple geometric primitives first. Prefer engineering clarity over cinematic complexity. Do not claim real FEA, SPICE, RF, or thermal physics unless actually implemented.

Deliverables:
Create a folder named missionpcb_blender_demo with:
1. missionpcb_lean_constraint_demo.blend
2. build_missionpcb_demo.py
3. validation_report.md
4. renders/top_down.png
5. renders/isometric.png
6. Optional: renders/constraint_walkthrough.mp4

Scene:
Create two versions of the same PCB inside transparent enclosures:
- Left: Naive Layout with visible constraint failures.
- Right: MissionPCB Layout with corrected placement.

Use millimeters.

Enclosure:
- 90 mm x 50 mm x 18 mm interior
- 2 mm walls
- transparent smoky gray
- rear access opening
- red translucent 3 mm wall keep-out margin

PCB:
- 72 mm x 38 mm x 1.6 mm
- green solder mask
- copper-colored pads/traces
- separate objects named PCB_Naive and PCB_MissionPCB

Components on each board:
1. MCU: 12 x 12 x 2 mm, dark blue/black, near center
2. Sensor: 6 x 6 x 1.5 mm, cyan, sensitive, at least 15 mm from hot components and 18 mm from noisy components
3. RF Module: 16 x 10 x 2 mm, purple, at least 20 mm from noisy components, purple antenna keep-out zone extending 22 mm
4. Power Regulator: 8 x 8 x 3 mm, orange, hot and noisy, 18 mm heat/noise zone
5. Driver: 14 x 10 x 3 mm, red, hot and noisy, 22 mm heat/noise zone
6. Battery Connector: 10 x 6 x 5 mm, yellow/gold, must be near rear access opening

Naive Layout:
- Sensor too close to Driver
- RF too close to Regulator
- RF keep-out crossed by trace/wire
- Driver heat zone overlaps Sensor
- Battery connector away from rear opening
- red warning lines and red X markers

MissionPCB Layout:
- Sensor near center but outside heat/noise zones
- RF away from Regulator and Driver
- Battery connector near rear access opening
- Driver and Regulator closer to edges
- high-current trace away from RF antenna zone
- green pass lines and check markers

Constraint logic:
Write Python calculations for bounding boxes, distances, height, wall keep-out, sensor separation, RF separation, battery access, and RF keep-out overlap. Use those calculations to generate scene overlays and validation_report.md.

Interactivity:
- Every component individually selectable
- No merged components
- Clean outliner names
- Collections:
  - 00_Reference
  - 01_Naive_Layout
  - 02_MissionPCB_Layout
  - 03_Constraint_Overlays
  - 04_Cameras_Lights
- Custom component properties:
  - component_type
  - heat_source
  - noise_source
  - sensitive
  - required_clearance_mm
- Add scene text: "Orbit, zoom, and select individual components. Move parts to inspect constraints."
- If feasible, add recalculate_constraints() helper function.

Cameras:
- Camera_TopDown
- Camera_Isometric
- Camera_CloseConstraint

Render top_down.png and isometric.png at 1920x1080.

Self-verification:
After generating the first scene, render a preview, inspect it, fix hidden components, bad labels, wrong scale, missing objects, merged parts, unreadable dashboards, or confusing overlays, then render final images.

Finish only when the .blend, renders, and validation report exist and you have inspected the output.
```

