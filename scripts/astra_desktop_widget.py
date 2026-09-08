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
from tkinter import ttk
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
        self.geometry("430x220+970+120")
        self.minsize(390, 200)
        self.attributes("-topmost", True)
        self.configure(bg="#141414")
        self.pending_proposal: str | None = None
        self.auto_apply = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Connecting...")
        self.reply = tk.StringVar(value="")
        self.input = tk.StringVar(value="")
        self._build()
        self.after(100, self.refresh_status)

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=(7, 5), relief="flat")
        style.configure("Primary.TButton", background="#f4f4f0", foreground="#111111")
        style.configure("TCheckbutton", background="#141414", foreground="#d8d8d2")

        shell = tk.Frame(self, bg="#141414", padx=18, pady=16)
        shell.pack(fill="both", expand=True)

        prompt = tk.Frame(shell, bg="#202020", padx=8, pady=7)
        prompt.pack(fill="x", pady=(0, 12))
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
        entry.insert(0, "How can I help with this board?")
        entry.bind("<FocusIn>", self._clear_placeholder)
        entry.bind("<Return>", lambda _event: self.send())

        actions = tk.Canvas(shell, height=78, bg="#141414", highlightthickness=0)
        actions.pack(fill="x")
        self._circle_button(actions, 39, "Ki", self.open_kicad)
        self._circle_button(actions, 141, "Bl", self.open_blender)
        self._circle_button(actions, 243, "R", self.reload_kicad)
        self._circle_button(actions, 345, "OK", self.apply)

        tk.Label(
            shell,
            textvariable=self.reply,
            anchor="w",
            justify="left",
            wraplength=380,
            bg="#141414",
            fg="#e7e7e2",
            font=("Helvetica", 10),
        ).pack(fill="x", pady=(0, 6))

        footer = tk.Frame(shell, bg="#141414")
        footer.pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.status,
            anchor="w",
            bg="#141414",
            fg="#969696",
            font=("Helvetica", 9),
        ).pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(
            footer,
            text="Auto-apply",
            variable=self.auto_apply,
        )
        ttk.Button(footer, text="Send", style="Primary.TButton", command=self.send).pack(
            side="right", padx=(8, 0)
        )

    def _circle_button(self, canvas: tk.Canvas, x: int, label: str, command) -> None:
        y = 38
        radius = 31
        oval = canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#242424",
            outline="#242424",
        )
        text = canvas.create_text(
            x,
            y,
            text=label,
            fill="#f4f4f0",
            font=("Helvetica", 13, "bold"),
        )
        for item in (oval, text):
            canvas.tag_bind(item, "<Button-1>", lambda _event, cmd=command: cmd())
            canvas.tag_bind(item, "<Enter>", lambda _event, oid=oval: canvas.itemconfig(oid, fill="#303030", outline="#303030"))
            canvas.tag_bind(item, "<Leave>", lambda _event, oid=oval: canvas.itemconfig(oid, fill="#242424", outline="#242424"))

    def _clear_placeholder(self, _event: object) -> None:
        if self.input.get() == "How can I help with this board?":
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
        if not message or message == "How can I help with this board?":
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
                    {"message": message, "auto_mode": self.auto_apply.get()},
                )
                outcome = res["outcome"]
                proposal = outcome.get("proposal")
                self.pending_proposal = proposal.get("proposal_id") if proposal else None
                suffix = ""
                if proposal and not res.get("auto_applied"):
                    suffix = "\n\nProposal ready. Press Apply to change KiCad."
                elif res.get("auto_applied"):
                    suffix = "\n\nApplied in KiCad."
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
