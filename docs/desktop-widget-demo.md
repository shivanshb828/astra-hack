# Desktop Widget Demo

This is the KiCad-first demo surface. The browser UI is not the product; the
desktop widget floats over KiCad and talks to the local backend.

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

Launch the floating desktop widget:

```bash
python3 scripts/astra_desktop_widget.py
```

## Demo Prompts

```text
Build a rechargeable 7-day ECG patch for continuous patient monitoring.
```

```text
7 days, rechargeable, optimize for patient safety first.
```

```text
Move BUCK to x=52 y=7.5.
```

Keep `Auto-apply` off for recording. With it off, Astra returns a proposal and
the user presses `Apply`; with it on, the proposal is applied immediately.

## Highlight And Annotate

Use `Mark AFE`, `Mark BUCK`, and `Mark CELL` in the desktop widget. These write
visible silkscreen annotations directly into the KiCad board file. If KiCad
prompts that the file changed on disk, choose reload.
