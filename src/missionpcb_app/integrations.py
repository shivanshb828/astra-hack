"""Adapters for the two optional external tools: KiCad and Blender.

Both report their real availability. When a tool or its project files are
absent the status is "not_connected" and no checks are produced -- a missing
KiCad run must never surface as a green check, and fabrication claims are never
derived from Blender geometry.

Subprocess use is constrained to a fixed argument vector built here, with paths
resolved inside the repository. Nothing from a request or a model reaches a
shell.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from typing import Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BLENDER_CANDIDATES = [
    "/Applications/Blender.app/Contents/MacOS/Blender",
    shutil.which("blender") or "",
]
KICAD_CLI_CANDIDATES = [
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    shutil.which("kicad-cli") or "",
]


def _first_existing(candidates: list[str]) -> str | None:
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _in_repo(path: str) -> str:
    """Resolve a path and refuse anything outside the project."""
    resolved = os.path.realpath(os.path.join(REPO_ROOT, path))
    if not resolved.startswith(os.path.realpath(REPO_ROOT) + os.sep):
        raise ValueError(f"path escapes the project directory: {path}")
    return resolved


# -- KiCad -------------------------------------------------------------------


def kicad_status() -> dict[str, Any]:
    """Report whether KiCad and native project files are both present."""
    cli = _first_existing(KICAD_CLI_CANDIDATES)
    projects = sorted(
        glob.glob(os.path.join(REPO_ROOT, "**", "*.kicad_pro"), recursive=True)
    )
    boards = sorted(
        glob.glob(os.path.join(REPO_ROOT, "**", "*.kicad_pcb"), recursive=True)
    )
    connected = bool(cli and (projects or boards))
    return {
        "name": "KiCad",
        "status": "connected" if connected else "not_connected",
        "cli_path": cli,
        "cli_present": bool(cli),
        "project_files": [os.path.relpath(p, REPO_ROOT) for p in projects],
        "board_files": [os.path.relpath(p, REPO_ROOT) for p in boards],
        "detail": (
            "kicad-cli and native project files found; DRC/ERC can be run."
            if connected
            else "Not connected. No native KiCad project files and/or kicad-cli "
                 "were found, so no electrical or DRC results are available. "
                 "Placement edits made in this app are application proposals "
                 "only and do not update routing or schematic connectivity."
        ),
        # Read-only for this version, per the brief.
        "capabilities": ["drc", "erc"] if connected else [],
    }


def run_kicad_drc(board_file: str) -> dict[str, Any]:
    """Run DRC through kicad-cli, if it is genuinely available."""
    status = kicad_status()
    if status["status"] != "connected":
        return {"ok": False, "reason": status["detail"], "checks": []}

    board = _in_repo(board_file)
    out = _in_repo("out/kicad_drc.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        proc = subprocess.run(
            [status["cli_path"], "pcb", "drc", "--format", "json",
             "--output", out, board],
            capture_output=True, text=True, timeout=180, cwd=REPO_ROOT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "reason": f"kicad-cli failed: {exc}", "checks": []}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stderr": proc.stderr[-2000:],
        "report_path": os.path.relpath(out, REPO_ROOT) if os.path.exists(out) else None,
    }


# -- Blender -----------------------------------------------------------------


def blender_status() -> dict[str, Any]:
    binary = _first_existing(BLENDER_CANDIDATES)
    glb = os.path.join(REPO_ROOT, "web", "public", "assets", "ecg_patch.glb")
    version = None
    if binary:
        try:
            proc = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=60
            )
            version = proc.stdout.splitlines()[0].strip() if proc.stdout else None
        except (subprocess.TimeoutExpired, OSError):
            version = None
    return {
        "name": "Blender",
        "status": "connected" if binary else "not_connected",
        "binary": binary,
        "version": version,
        "asset_present": os.path.exists(glb),
        "asset_path": "/assets/ecg_patch.glb" if os.path.exists(glb) else None,
        "detail": (
            f"{version} available for background GLB export and high-quality renders."
            if binary
            else "Not connected. The viewport falls back to placeholder geometry "
                 "generated from nominal part dimensions."
        ),
    }


def run_blender_export(
    results_path: str, layout_path: str, *, render: bool = True
) -> dict[str, Any]:
    """Re-export the GLB (and optionally render) as a background job.

    Deliberately not called on drag: transforms are applied in the viewport
    from design state, and Blender re-runs only when geometry changes in a way
    a transform cannot express.
    """
    status = blender_status()
    if status["status"] != "connected":
        return {"ok": False, "reason": status["detail"]}

    script = _in_repo("blender/build_scene.py")
    argv = [
        status["binary"], "-b", "--factory-startup", "--python", script, "--",
        "--results", _in_repo(results_path),
        "--layout", _in_repo(layout_path),
        "--blend", _in_repo("blender/out/ecg_patch.blend"),
        "--glb", _in_repo("web/public/assets/ecg_patch.glb"),
    ]
    if render:
        argv += ["--render", _in_repo("blender/out/render_iso.png"), "--samples", "96"]

    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=900, cwd=REPO_ROOT
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "reason": f"blender failed: {exc}"}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "log": "\n".join(
            line for line in proc.stdout.splitlines() if line.startswith("[")
        ),
        "stderr": proc.stderr[-2000:],
        "glb": "/assets/ecg_patch.glb",
        "render": "/api/blender/render.png" if render else None,
    }
