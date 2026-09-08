# MissionPCB

MissionPCB is an AI hardware engineer that generates PCB designs from real-world mission constraints and validates them with simulation before you build.

This repo is the working space for our Astra hack project. The current goal is to build a lean but convincing prototype that shows how MissionPCB thinks differently from generic AI PCB tools: it starts from the mission, extracts constraints, creates a board/enclosure simulation, checks failure modes, and explains why a design passes or fails.

## Core Idea

Existing AI PCB tools help with parts, schematics, routing, and general PCB workflows. MissionPCB is aimed at higher-constraint hardware work where the important design questions are not only "can this circuit be drawn?" but:

- Will the board fit inside the actual product?
- Will hot components damage people, sensors, batteries, or nearby modules?
- Do noisy parts interfere with sensitive sensors or RF modules?
- Does the design still work under real operating conditions?
- What risks remain before manufacturing?

Our first demo should stay lean. It should not try to solve all PCB design in one shot. It should prove the product thesis visually and technically: MissionPCB can turn messy real-world requirements into a structured constraint model and an inspectable 3D simulation.

## Recommended First Demo

Build a Blender-based 3D simulation of a constrained PCB inside a transparent electronics enclosure.

The demo should show two side-by-side layouts:

- **Naive Layout:** a plausible but bad first-pass board with visible failures.
- **MissionPCB Layout:** a corrected board that satisfies or explains the key constraints.

Only include three constraint types at first:

- Mechanical fit inside the enclosure
- Approximate heat zones around hot components
- Separation between sensitive and noisy components

This is enough to communicate the wedge without overbuilding.

## Why Blender First

Use Blender for the first prototype because it is fast, scriptable, visual, and interactive. Astra can generate Blender Python, run it, inspect renders, and revise the scene. Blender also lets teammates orbit, zoom, select individual parts, and inspect the design from any angle.

Fusion or other CAD tools may become useful later for CAD-grade enclosure import, manufacturing workflows, or enterprise integrations. For the hack/demo, Blender is the fastest path to an impressive simulation.

## Main Docs

Start here:

- [MissionPCB product and build brief](docs/missionpcb-product-build-brief.md)

