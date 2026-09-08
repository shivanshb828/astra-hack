#!/usr/bin/env python3
"""Native desktop widget for the KiCad demo.

Run after the FastAPI backend is up:

    python3 scripts/astra_desktop_widget.py

This is intentionally tiny and dependency-free. It is a floating control
surface for KiCad, not a replacement editor.
"""

from __future__ import annotations

import json
import subprocess
import threading
import tkinter as tk
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
KICAD_PROJECT = "kicad/ecg-patch/ecg-patch.kicad_pro"
BLENDER_WORKBENCH = "missionpcb_blender_demo/workbench/missionpcb_ecg_workbench.blend"


def request(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{exc.code}: {detail}") from exc


class AstraWidget(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Astra KiCad")
        self.geometry("430x150+970+120")
        self.minsize(390, 135)
        self.attributes("-topmost", True)
        self.configure(bg="#101010")
        self.pending_proposal: str | None = None
        self.status = tk.StringVar(value="Connecting...")
        self.reply = tk.StringVar(value="")
        self.input = tk.StringVar(value="")
        self._build()
        self.after(100, self.refresh_status)

    def _build(self) -> None:
        shell = tk.Frame(self, bg="#101010", padx=18, pady=16)
        shell.pack(fill="both", expand=True)

        prompt_canvas = tk.Canvas(shell, height=62, bg="#101010", highlightthickness=0)
        prompt_canvas.pack(fill="x", pady=(0, 10))
        prompt = tk.Frame(prompt_canvas, bg="#202020", padx=10, pady=8)
        prompt_canvas.create_window(0, 0, anchor="nw", window=prompt, width=394, height=58)
        self._rounded_rect(prompt_canvas, 0, 0, 394, 58, 29, fill="#202020", outline="#202020")
        prompt.lift()

        mark = tk.Label(prompt, text="*", fg="#ff7a3d", bg="#202020", width=2,
                        font=("Helvetica", 20, "bold"))
        mark.pack(side="left", padx=(4, 8))
        entry = tk.Entry(
            prompt,
            textvariable=self.input,
            relief="flat",
            bg="#202020",
            fg="#f4f4f0",
            insertbackground="#f4f4f0",
            font=("Helvetica", 14, "bold"),
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.insert(0, "How can I help today?")
        entry.bind("<FocusIn>", self._clear_placeholder)
        entry.bind("<Return>", lambda _event: self.send())

        tk.Label(
            shell,
            textvariable=self.reply,
            anchor="w",
            justify="left",
            wraplength=380,
            bg="#101010",
            fg="#e7e7e2",
            font=("Helvetica", 9),
        ).pack(fill="x")

    def _rounded_rect(self, canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> None:
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        canvas.create_polygon(points, smooth=True, **kwargs)

    def _clear_placeholder(self, _event: object) -> None:
        if self.input.get() == "How can I help today?":
            self.input.set("")

    def append(self, who: str, text: str) -> None:
        self.reply.set(f"{who}: {text.strip()}")

    def run_bg(self, fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def refresh_status(self) -> None:
        def task() -> None:
            try:
                res = request("/api/widget/monitor")
                kicad = "KiCad ready" if res["integrations"]["kicad"]["status"] == "connected" else "KiCad offline"
                model = "model ready" if res["integrations"]["model"]["configured"] else "local fallback"
                self.status.set(f"{kicad} - {model}")
            except Exception:
                self.status.set("Backend offline")

        self.run_bg(task)

    def open_kicad(self) -> None:
        def task() -> None:
            subprocess.run(["open", "-a", "KiCad", KICAD_PROJECT], check=False)
            self.append("Astra", "Opened the demo KiCad project.")

        self.run_bg(task)

    def open_blender(self) -> None:
        def task() -> None:
            subprocess.run(["open", "-a", "Blender", BLENDER_WORKBENCH], check=False)
            self.append("Astra", "Opened Dhruva's Blender workbench.")

        self.run_bg(task)

    def reload_kicad(self) -> None:
        def task() -> None:
            try:
                self._reload_now()
                self.append("Astra", "Reload signal sent. If KiCad prompts, choose Reload.")
            except Exception as exc:
                self.append("Astra", f"Reload failed: {exc}")

        self.run_bg(task)

    def _reload_now(self) -> None:
        request("/api/kicad/reload", {})

    def annotate(self, ref: str) -> None:
        notes = {
            "AFE": "sensitive analog front end",
            "BUCK": "switching regulator noise source",
            "CELL": "verify battery height and safety",
        }

        def task() -> None:
            try:
                res = request("/api/kicad/annotate", {"ref": ref, "note": notes[ref]})
                self._reload_now()
                self.append("Astra", f"Marked {res['ref']} in KiCad: {res['note']}")
            except Exception as exc:
                self.append("Astra", f"Mark failed: {exc}")

        self.run_bg(task)

    def send(self) -> None:
        message = self.input.get().strip()
        if not message or message == "How can I help today?":
            return
        self.input.set("")
        self.append("You", message)

        lowered = message.lower().strip()
        command_match = None
        for verb in ("mark", "highlight", "annotate"):
            if lowered.startswith(f"{verb} "):
                command_match = message.split(maxsplit=1)[1].strip().upper()
                break
        if command_match:
            ref = command_match.split()[0]
            self.annotate(ref)
            return
        if lowered in {"reload", "reload kicad", "refresh kicad"}:
            self.reload_kicad()
            return
        if lowered in {"open", "open kicad"}:
            self.open_kicad()
            return
        if lowered in {"open blender", "blender"}:
            self.open_blender()
            return

        def task() -> None:
            try:
                res = request(
                    "/api/widget/send",
                    {"message": message, "auto_mode": True},
                )
                outcome = res["outcome"]
                proposal = outcome.get("proposal")
                self.pending_proposal = proposal.get("proposal_id") if proposal else None
                suffix = ""
                if res.get("auto_applied"):
                    suffix = "\n\nUpdated KiCad."
                self.append("Astra", outcome.get("reply", "Done.") + suffix)
            except Exception as exc:
                self.append("Astra", f"Request failed: {exc}")

        self.run_bg(task)

    def apply(self) -> None:
        if not self.pending_proposal:
            self.append("Astra", "No pending proposal to apply.")
            return
        proposal_id = self.pending_proposal
        self.pending_proposal = None

        def task() -> None:
            try:
                res = request(f"/api/proposals/{proposal_id}/apply", {})
                kicad = res.get("native_tool", {}).get("kicad", {})
                if kicad.get("synced"):
                    self._reload_now()
                    self.append("Astra", "Applied. KiCad board file updated; reload if prompted.")
                else:
                    self.append("Astra", "Applied to design state; no matching KiCad footprint reported.")
            except Exception as exc:
                self.append("Astra", f"Apply failed: {exc}")

        self.run_bg(task)


if __name__ == "__main__":
    AstraWidget().mainloop()
