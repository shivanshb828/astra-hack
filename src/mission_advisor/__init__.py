"""MissionPCB mission advisor — the judgment layer.

Reads a plain-English product brief plus the part catalog's physical facts and
produces considerations: what to change, replace, add, or drop, and why.

Deliberately separate from ``constraint_engine``. That package is stdlib-only
and importable from Blender because it does arithmetic; this one makes network
calls and does judgment. Keeping them apart is what makes the arithmetic
reproducible.
"""

from .catalog import PartRecord, load_catalog, render_catalog, render_part
from .report import render
from .schema import AdvisorOutput, Consideration, Evidence


def __getattr__(name):
    # Local catalog access must work offline without the optional model SDK.
    if name in {"MODEL", "RefusalError", "advise", "build_mission_prompt", "read_mission"}:
        from . import advisor
        return getattr(advisor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MODEL",
    "AdvisorOutput",
    "Consideration",
    "Evidence",
    "PartRecord",
    "RefusalError",
    "advise",
    "build_mission_prompt",
    "load_catalog",
    "read_mission",
    "render",
    "render_catalog",
    "render_part",
]
