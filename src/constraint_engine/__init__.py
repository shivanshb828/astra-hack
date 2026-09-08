"""MissionPCB constraint engine.

Turns a parts library plus a component layout into engineering verdicts: what
fits, what interferes, what is unsafe, and by how many millimetres. Outputs a
machine-readable result set for the 3D simulation and a Markdown report for
humans.

Stdlib only, by design -- Blender's bundled Python has no pip, and the
simulation layer needs to import this package directly::

    import sys; sys.path.insert(0, "<repo>/src")
    from constraint_engine import load_parts, load_layout, validate

    parts, _ = load_parts("parts/ecg-patch-parts.json")
    layout, _ = load_layout("layouts/ecg-patch-naive.json")
    results = validate(layout, parts)
"""

from .brief import build_brief, render_brief_text
from .engine import ENGINE_VERSION, build_scene, validate
from .loader import LoadError, layout_to_dict, load_layout, load_parts
from .models import (
    BLOCKER,
    FAIL,
    INFO,
    MAJOR,
    MINOR,
    PASS,
    SKIP,
    WARN,
    Board,
    Check,
    Clearances,
    Enclosure,
    Keepout,
    Layout,
    MissionProfile,
    MissionRule,
    Opening,
    Overlay,
    Part,
    Placement,
    Results,
    Trace,
)
from .report import render_report
from .review import SCHEMA_VERSION, SubmissionError, review
from .solver import solve

__version__ = ENGINE_VERSION

__all__ = [
    "ENGINE_VERSION",
    "__version__",
    "BLOCKER",
    "Board",
    "Check",
    "Clearances",
    "Enclosure",
    "FAIL",
    "INFO",
    "Keepout",
    "Layout",
    "LoadError",
    "MAJOR",
    "MINOR",
    "MissionProfile",
    "MissionRule",
    "Opening",
    "Overlay",
    "PASS",
    "Part",
    "Placement",
    "Results",
    "SKIP",
    "Trace",
    "WARN",
    "build_brief",
    "build_scene",
    "layout_to_dict",
    "load_layout",
    "load_parts",
    "render_brief_text",
    "SCHEMA_VERSION",
    "SubmissionError",
    "render_report",
    "review",
    "solve",
    "validate",
]
