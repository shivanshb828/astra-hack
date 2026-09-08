# Desktop Widget Demo

This is the KiCad-first demo surface. The browser UI is not the product; the
desktop widget floats over KiCad and talks to the local backend. It is a tiny
chat surface: type, press Enter, and let Astra update KiCad behind the scenes.
Dhruva's Blender workbench is available as an auxiliary view through typed
commands.

## Run

Start the backend:

```bash
cd /Users/aayushg/Desktop/Projects/astra-hack
set -a; source .env; set +a
MISSIONPCB_KICAD_AUTO_RELOAD=1 PYTHONPATH=src python3 -m uvicorn missionpcb_app.api:app --host 127.0.0.1 --port 8000
```

Open KiCad:

```bash
open -a KiCad kicad/ecg-patch/ecg-patch.kicad_pro
```

Open Dhruva's Blender workbench from the widget by typing:

```text
open Blender
```

Launch the floating desktop widget:

```bash
python3 scripts/astra_desktop_widget.py
```

## Demo Prompts

```text
Build a wearable medical device PCB.
```

```text
7 days, rechargeable, optimize for patient safety first.
```

```text
Move BUCK to x=52 y=7.5.
```

The desktop widget auto-applies placement proposals for the recording flow and
then asks KiCad to reload. There are intentionally no buttons in the widget;
everything is typed and sent with Enter.

## Highlight And Annotate

Use chat commands:

```text
mark AFE
```

```text
highlight BUCK
```

```text
explain CELL
```

These write visible silkscreen annotations directly into the KiCad board file.
If KiCad prompts that the file changed on disk, choose reload. `reload KiCad`
also sends a manual reload/foreground signal.

## Active Loop

```text
desktop widget -> backend/Astra -> KiCad board edit/annotation -> KiCad reload
```

The widget can open KiCad, ask for a reload, apply proposals, and write visible
KiCad annotations. It can also open Dhruva's Blender workbench. It does not
read the KiCad mouse cursor or selected object yet; that requires a KiCad-side
plugin.
