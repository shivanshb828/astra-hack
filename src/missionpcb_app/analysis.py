"""Adapter from the constraint engine's results to the application's model.

This module calls the real engine. It does not re-implement a single check, and
it never computes a distance of its own: every measured number in an
``AnalysisResult`` was produced by ``constraint_engine.validate``.

Two mappings carry most of the weight, and both exist to avoid overstating what
the engine proved:

``ENGINE_STATUS_MAP`` sends the engine's ``SKIP`` to ``unknown`` rather than
``pass``. A board with a typo'd ``part_id`` reports clean precisely because it
was never inspected, so that distinction has to survive into the UI.

``METHOD_BY_FAMILY`` labels each rule family with how it was actually decided.
The engine's own contract separates what it computes exactly (bounding boxes,
distances, containment, collisions, keep-out occupancy) from what it
approximates (thermal zones are a declared radius, not a solved field; noise
separation is a distance threshold, not a coupling coefficient). Families in the
second group are reported as ``heuristic`` so a drawn heat volume is never read
as a calculated temperature.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from constraint_engine import (
    ENGINE_VERSION,
    load_layout,
    load_parts,
    validate,
)

from .schema import (
    ENGINE_STATUS_MAP,
    AnalysisCheck,
    AnalysisResult,
    DesignState,
    Method,
    Severity,
    Status,
    VizInstruction,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PARTS = os.path.join(REPO_ROOT, "parts", "ecg-patch-parts.json")

# Rule family -> the brief's check category.
CATEGORY_BY_FAMILY = {
    "fit.board": "board_enclosure_fit",
    "fit.enclosure_xy": "board_enclosure_fit",
    "fit.height": "component_overlap_height",
    "fit.overlap": "component_overlap_height",
    "fit.courtyard": "component_overlap_height",
    "sep.thermal": "thermal_interaction",
    "sep.noise": "afe_interference_risk",
    "sep.rf": "afe_interference_risk",
    "zone.heat_overlap": "thermal_interaction",
    "zone.rf_keepout": "antenna_keepout",
    "safety.skin_contact_temp": "patient_contact_thermal",
    "safety.battery_thermal": "battery_regulator_thermal",
    "access.connector": "connector_assembly_access",
    "data.unresolved_part": "data_integrity",
}

# Exact geometry versus declared-threshold proxy. Sourced from the engine's own
# "What the engine does and does not prove" section, not invented here.
METHOD_BY_FAMILY: dict[str, Method] = {
    "fit.board": "geometric_check",
    "fit.enclosure_xy": "geometric_check",
    "fit.height": "geometric_check",
    "fit.overlap": "geometric_check",
    "fit.courtyard": "geometric_check",
    "zone.rf_keepout": "geometric_check",
    "access.connector": "geometric_check",
    "sep.thermal": "heuristic",
    "sep.noise": "heuristic",
    "sep.rf": "heuristic",
    "zone.heat_overlap": "heuristic",
    "safety.skin_contact_temp": "heuristic",
    "safety.battery_thermal": "heuristic",
    "data.unresolved_part": "geometric_check",
}

# Assumptions attached to approximated families, so the caveat travels with the
# individual result instead of living only in a footnote.
ASSUMPTIONS_BY_FAMILY = {
    "sep.thermal": ["Separation is a declared clearance threshold, not a solved thermal field."],
    "sep.noise": ["Separation is a distance threshold, not a computed coupling coefficient."],
    "sep.rf": ["Separation is a distance threshold, not a computed coupling coefficient."],
    "zone.heat_overlap": ["The heat zone is a declared radius from the parts data, not a simulated field."],
    "safety.skin_contact_temp": [
        "Skin-contact temperature is inferred from lateral distance, not from a surface-temperature solve.",
        "Passing this check does not establish medical-device compliance.",
    ],
    "safety.battery_thermal": ["Cell heating is inferred from distance to a declared heat source."],
}

# Categories the brief asks about that this engine cannot evaluate. Declaring
# them explicitly keeps them visible as gaps rather than silently absent --
# eight green checks must not be manufactured to satisfy a list.
UNSUPPORTED_CATEGORIES = {
    "trace_current_copper_geometry": (
        "No copper geometry or current data in the design state. Traces are "
        "carried only as polylines for antenna keep-out crossing, so trace "
        "width against current cannot be evaluated."
    ),
    "patient_connected_spacing": (
        "Creepage requires a path along an insulating surface and clearance "
        "concerns separation through air. Neither is derivable from component "
        "centre distances, so no spacing verdict is issued."
    ),
}

APPROXIMATIONS = [
    "Thermal zones are a declared radius from the parts data, not a solved thermal field.",
    "Noise and RF separation are distance thresholds, not coupling coefficients.",
    "RF keep-out is a rectangular volume, not a radiation pattern.",
    "Skin-contact temperature is inferred from distance, not a surface-temperature solve.",
    "Not modelled at all: SPICE, thermal FEA, EM simulation, battery runtime, DFM, "
    "routing correctness, layer stackup, grounding and shielding, biocompatibility.",
]


def _family(check_id: str) -> str:
    """'sep.noise::AFE|REG' -> 'sep.noise'; 'mission.lead_vector' -> 'mission'."""
    head = check_id.split("::", 1)[0]
    return "mission" if head.startswith("mission.") else head


@lru_cache(maxsize=4)
def _parts(path: str):
    return load_parts(path)


def _overlay_to_viz(overlay: dict[str, Any], refs: list[str]) -> list[VizInstruction]:
    """Translate one engine overlay into typed instructions.

    Engine overlays are already in enclosure millimetres, so no conversion
    happens here -- only a change of vocabulary. Anything with a type this
    function does not recognise is dropped rather than passed through, which is
    what keeps the instruction set bounded.
    """
    kind = overlay.get("type")
    colour = overlay.get("color")
    colour_t = tuple(colour) if colour and len(colour) == 3 else None
    label = overlay.get("label")
    label_at = overlay.get("label_at")
    out: list[VizInstruction] = []

    if kind == "measure_line" and overlay.get("from") and overlay.get("to"):
        out.append(
            VizInstruction(
                type="distance_measurement",
                component_refs=refs,
                from_mm=tuple(overlay["from"]),
                to_mm=tuple(overlay["to"]),
                label=label,
                label_at_mm=tuple(label_at) if label_at else None,
                color_rgb=colour_t,
                marker=overlay.get("marker"),
            )
        )
    elif kind in ("zone_circle", "zone_rect") and overlay.get("center"):
        out.append(
            VizInstruction(
                type="keepout_volume",
                component_refs=refs,
                center_mm=tuple(overlay["center"]),
                radius_mm=overlay.get("radius_mm"),
                size_mm=tuple(overlay["size_mm"]) if overlay.get("size_mm") else None,
                label=label,
                color_rgb=colour_t,
                # Declared clearance envelope, never a solved field.
                zone_kind="declared_clearance",
            )
        )
    elif kind in ("marker", "text") and overlay.get("center"):
        out.append(
            VizInstruction(
                type="annotation",
                component_refs=refs,
                center_mm=tuple(overlay["center"]),
                label=label,
                color_rgb=colour_t,
                marker=overlay.get("marker"),
            )
        )
    return out


def _to_check(raw: dict[str, Any], revision: int) -> AnalysisCheck:
    check_id = raw["id"]
    family = _family(check_id)
    status: Status = ENGINE_STATUS_MAP.get(raw.get("status", ""), "unknown")
    severity: Severity = raw.get("severity", "info")
    refs = list(raw.get("subjects", []))

    viz = list(_overlay_to_viz(raw["overlay"], refs)) if raw.get("overlay") else []
    if refs:
        # Selecting an issue should be able to light up its components.
        viz.insert(
            0, VizInstruction(type="highlight_components", component_refs=refs)
        )

    suggestion = raw.get("suggestion")
    return AnalysisCheck(
        check_id=check_id,
        design_revision=revision,
        category=CATEGORY_BY_FAMILY.get(family, family),
        title=raw.get("title", check_id),
        status=status,
        severity=severity,
        component_refs=refs,
        measured_value=raw.get("measured_mm"),
        measured_unit="mm" if raw.get("measured_mm") is not None else None,
        threshold_value=raw.get("required_mm"),
        threshold_comparison=">=" if raw.get("required_mm") is not None else None,
        metric=raw.get("metric", ""),
        explanation=raw.get("message", ""),
        method=METHOD_BY_FAMILY.get(family, "geometric_check"),
        input_assumptions=list(ASSUMPTIONS_BY_FAMILY.get(family, [])),
        missing_inputs=["part definition"] if status == "unknown" else [],
        rule_source=raw.get("rationale", ""),
        suggested_actions=[suggestion] if suggestion else [],
        viz=viz,
    )


def _unsupported_checks(revision: int) -> list[AnalysisCheck]:
    """Emit the categories the engine cannot evaluate as explicit unknowns."""
    return [
        AnalysisCheck(
            check_id=f"coverage.not_evaluated::{category}",
            design_revision=revision,
            category=category,
            title=f"{category.replace('_', ' ').capitalize()} — not evaluated",
            status="not_applicable",
            severity="info",
            explanation=reason,
            method="geometric_check",
            missing_inputs=["engine capability"],
        )
        for category, reason in sorted(UNSUPPORTED_CATEGORIES.items())
    ]


def analyse(
    design: DesignState, parts_path: str | None = None
) -> AnalysisResult:
    """Run the real engine against a design state and map the verdicts.

    The design is written to a temporary layout file and read back through the
    engine's public ``load_layout``, so the forgiving loader, its aliases and
    its warnings all apply exactly as they do on the command line.
    """
    parts_file = parts_path or design.parts_source or DEFAULT_PARTS
    parts, part_warnings = _parts(parts_file)

    layout_dict = design.to_engine_layout()
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        json.dump(layout_dict, tmp)
        tmp.close()
        layout, layout_warnings = load_layout(tmp.name)
    finally:
        os.unlink(tmp.name)

    warnings = list(part_warnings) + list(layout_warnings)
    results = validate(layout, parts, warnings=warnings)
    payload = results.to_dict()

    checks = [_to_check(c, design.revision) for c in payload["checks"]]
    checks.extend(_unsupported_checks(design.revision))

    zone_viz: list[VizInstruction] = []
    for overlay in payload.get("zone_overlays", []):
        zone_viz.extend(_overlay_to_viz(overlay, []))

    summary: dict[str, int] = {}
    for check in checks:
        summary[check.status] = summary.get(check.status, 0) + 1

    return AnalysisResult(
        job_id=uuid.uuid4().hex,
        design_id=design.design_id,
        design_revision=design.revision,
        engine_version=ENGINE_VERSION,
        source="missionpcb_engine",
        created_at=datetime.now(timezone.utc).isoformat(),
        summary=summary,
        checks=checks,
        zone_viz=zone_viz,
        warnings=warnings,
        approximations=list(APPROXIMATIONS),
    )
