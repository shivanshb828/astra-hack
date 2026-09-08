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
        self.geometry("390x510+1040+120")
        self.attributes("-topmost", True)
        self.configure(bg="#fafaf7")
        self.pending_proposal: str | None = None
        self.auto_apply = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Connecting...")
        self.input = tk.StringVar(value="")
        self._build()
        self.after(100, self.refresh_status)

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=(8, 5), relief="flat")
        style.configure("Primary.TButton", background="#111111", foreground="#ffffff")
        style.configure("TCheckbutton", background="#fafaf7")

        header = tk.Frame(self, bg="#ffffff", highlightbackground="#111111", highlightthickness=1)
        header.pack(fill="x")
        mark = tk.Label(header, text="A", fg="#ffffff", bg="#111111", width=3, height=1)
        mark.pack(side="left", padx=(10, 8), pady=10)
        title = tk.Frame(header, bg="#ffffff")
        title.pack(side="left", fill="x", expand=True)
        tk.Label(title, text="Astra KiCad", anchor="w", bg="#ffffff", fg="#111111",
                 font=("Helvetica", 13, "bold")).pack(fill="x")
        tk.Label(title, textvariable=self.status, anchor="w", bg="#ffffff", fg="#555555",
                 font=("Helvetica", 10)).pack(fill="x")
        ttk.Checkbutton(header, text="Auto-apply", variable=self.auto_apply).pack(
            side="right", padx=10
        )

        actions = tk.Frame(self, bg="#f0f0ec")
        actions.pack(fill="x", padx=0, pady=0)
        ttk.Button(actions, text="Open KiCad", command=self.open_kicad).pack(
            side="left", padx=(10, 4), pady=8
        )
        ttk.Button(actions, text="Mark AFE", command=lambda: self.annotate("AFE")).pack(
            side="left", padx=4, pady=8
        )
        ttk.Button(actions, text="Mark BUCK", command=lambda: self.annotate("BUCK")).pack(
            side="left", padx=4, pady=8
        )
        ttk.Button(actions, text="Mark CELL", command=lambda: self.annotate("CELL")).pack(
            side="left", padx=4, pady=8
        )

        self.log = tk.Text(
            self,
            wrap="word",
            bg="#fbfbf8",
            fg="#111111",
            relief="flat",
            padx=10,
            pady=10,
            height=18,
            font=("Helvetica", 12),
        )
        self.log.pack(fill="both", expand=True)
        self.log.insert("end", "Ready. Ask Astra to inspect or change the open KiCad board.\n")
        self.log.configure(state="disabled")

        composer = tk.Frame(self, bg="#ffffff", highlightbackground="#111111", highlightthickness=1)
        composer.pack(fill="x")
        entry = tk.Entry(
            composer,
            textvariable=self.input,
            relief="flat",
            bg="#ffffff",
            fg="#111111",
            font=("Helvetica", 12),
        )
        entry.pack(side="left", fill="x", expand=True, padx=10, pady=12)
        entry.insert(0, "Build a rechargeable 7-day ECG patch...")
        entry.bind("<FocusIn>", self._clear_placeholder)
        entry.bind("<Return>", lambda _event: self.send())
        ttk.Button(composer, text="Send", style="Primary.TButton", command=self.send).pack(
            side="right", padx=(0, 10), pady=8
        )
        ttk.Button(composer, text="Apply", command=self.apply).pack(
            side="right", padx=(0, 6), pady=8
        )

    def _clear_placeholder(self, _event: object) -> None:
        if self.input.get() == "Build a rechargeable 7-day ECG patch...":
            self.input.set("")

    def append(self, who: str, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"\n{who}: {text.strip()}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

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

    def annotate(self, ref: str) -> None:
        notes = {
            "AFE": "sensitive analog front end",
            "BUCK": "switching regulator noise source",
            "CELL": "verify battery height and safety",
        }

        def task() -> None:
            try:
                res = request("/api/kicad/annotate", {"ref": ref, "note": notes[ref]})
                self.append("Astra", f"Marked {res['ref']} in KiCad: {res['note']}")
            except Exception as exc:
                self.append("Astra", f"Mark failed: {exc}")

        self.run_bg(task)

    def send(self) -> None:
        message = self.input.get().strip()
        if not message or message == "Build a rechargeable 7-day ECG patch...":
            return
        self.input.set("")
        self.append("You", message)

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
                    self.append("Astra", "Applied. KiCad board file updated; reload if prompted.")
                else:
                    self.append("Astra", "Applied to design state; no matching KiCad footprint reported.")
            except Exception as exc:
                self.append("Astra", f"Apply failed: {exc}")

        self.run_bg(task)


if __name__ == "__main__":
    AstraWidget().mainloop()
