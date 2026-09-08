"""JSON-in / JSON-out review contract.

One function, one call, no state:

    findings = review(submission)

The caller owns KiCad entirely -- parsing, UUID and reference mapping,
coordinate conversion, package export and import, and native annotation. This
module owns the arithmetic and nothing else. It never opens a board file, never
reaches the network, and keeps no memory of previous submissions.

Two properties the round trip depends on:

**Identity is echoed, never inferred.** ``design_id``, ``revision``, and
``source_board_hash`` come back exactly as submitted. The caller compares the
hash against the board on disk before loading anything back, so an engineer's
edits made mid-review are never silently overwritten.

**Every component is named in all three vocabularies.** A finding carries the
engine ``ref``, the ``catalog_id`` it resolved from, and the caller's
``kicad_ref``. Nothing downstream has to maintain a translation table, and a
finding can be annotated onto the board without a lookup.

Stdlib only, like the rest of the engine.
"""

from __future__ import annotations

from typing import Any

from .engine import ENGINE_VERSION, validate
from .loader import _num_or, parse_part
from .models import (
    Board,
    Enclosure,
    Layout,
    MissionProfile,
    MissionRule,
    Opening,
    Part,
    Placement,
    Trace,
)

SCHEMA_VERSION = "review/1"

# The engine's verdict vocabulary, mapped to the contract's. SKIP becomes
# "unknown" and never "pass": a component whose catalog_id did not resolve is
# reported clean precisely because nothing looked at it, and that distinction
# has to survive into the caller's UI.
STATUS_MAP = {"PASS": "pass", "FAIL": "fail", "WARN": "warning", "SKIP": "unknown"}

# How each rule family was actually decided. The caller renders these
# differently: an exact result is a measurement, a heuristic is a threshold
# somebody chose.
METHOD_BY_FAMILY = {
    "fit.board": "exact",
    "fit.enclosure_xy": "exact",
    "fit.height": "exact",
    "fit.overlap": "exact",
    "fit.courtyard": "exact",
    "zone.rf_keepout": "exact",
    "access.connector": "exact",
    "data.unresolved_part": "exact",
    "sep.thermal": "heuristic",
    "sep.noise": "heuristic",
    "sep.rf": "heuristic",
    "zone.heat_overlap": "heuristic",
    "safety.skin_contact_temp": "heuristic",
    "safety.battery_thermal": "heuristic",
    "mission": "declared",
}

# Which direction each rule family tests, so the caller can render "needs at
# least" versus "must not exceed" without guessing.
#
# This is not cosmetic. Roughly half the families measure a quantity that must
# stay *below* a limit -- overflow past a boundary, penetration into a zone,
# component height against a ceiling -- and the other half measure a gap that
# must stay *above* one. Deriving the operator from the metric name gets the
# first group backwards, which is exactly the kind of error that reads as
# correct right up until an engineer acts on it.
COMPARISON_BY_FAMILY = {
    # measured must be at least the threshold
    "fit.courtyard": ">=",
    "sep.thermal": ">=",
    "sep.noise": ">=",
    "sep.rf": ">=",
    "safety.skin_contact_temp": ">=",
    "safety.battery_thermal": ">=",
    # measured must not exceed the threshold (threshold is usually 0)
    "fit.board": "<=",
    "fit.enclosure_xy": "<=",
    "fit.height": "<=",
    "fit.overlap": "<=",
    "zone.heat_overlap": "<=",
    "zone.rf_keepout": "<=",
    "access.connector": "<=",
    # "mission" is resolved per rule from its declared type, not from this table.
}

# What each heuristic is standing in for. Shipped with the finding so a
# declared radius is never read as a solved temperature.
LIMITATION_BY_FAMILY = {
    "sep.thermal": "Distance threshold, not a computed junction temperature.",
    "sep.noise": "Distance threshold, not a computed coupling coefficient.",
    "sep.rf": "Distance threshold, not a computed link budget.",
    "zone.heat_overlap": (
        "Fixed radius standing in for the elevated-temperature region around a "
        "dissipating part. Not a solved thermal field."
    ),
    "safety.skin_contact_temp": (
        "Lateral distance from a heat source, not a surface-temperature solve. "
        "The IEC 60601-1 limit still needs a measurement on hardware."
    ),
    "safety.battery_thermal": (
        "Distance threshold for cell ageing and runaway margin, not a solved "
        "cell temperature."
    ),
    "mission": "Threshold declared in the submitted constraints, not derived.",
}

# Categories the engine cannot evaluate at all. Returned explicitly rather than
# omitted, so their absence from the findings is never read as a pass.
UNSUPPORTED = {
    "trace_current_copper_geometry": (
        "No copper geometry or current data is carried in a submission. Traces "
        "are polylines used only for antenna keep-out crossing, so trace width "
        "against current cannot be evaluated."
    ),
    "patient_connected_spacing": (
        "Creepage needs a path along an insulating surface and clearance needs "
        "separation through air. Neither is derivable from component outlines "
        "and centre distances, so no spacing verdict is issued."
    ),
    "electrical_connectivity": (
        "A submission carries placement, not netlist. Nothing here can tell "
        "whether two pads that should be connected are."
    ),
    "thermal_field": (
        "No thermal solve is performed. Heat is modelled as a declared radius "
        "around a dissipating part, so no surface or junction temperature is "
        "produced and none should be inferred from the zone overlays."
    ),
    "radiated_emissions": (
        "Antenna keep-out is a rectangular exclusion volume, not a radiation "
        "pattern. No emissions level, link budget, or compliance margin is "
        "computed."
    ),
    "manufacturability": (
        "Only IPC-7351 courtyard spacing is checked. Panelisation, stencil "
        "aperture, assembly order, and test-point access are not evaluated."
    ),
}


class SubmissionError(ValueError):
    """The submission is unusable. Distinct from a design that fails checks."""


def _require(obj: dict[str, Any], key: str, where: str) -> Any:
    if key not in obj:
        raise SubmissionError(f"{where}: missing required field '{key}'")
    return obj[key]


def _comparison(family: str, rule_id: str,
                mission_rule_types: dict[str, str]) -> str | None:
    """Which way the threshold is tested, resolved from the rule's own meaning.

    Mission rules are resolved per rule because the caller declares their
    direction: a ``min_separation`` and a ``max_separation`` read identically
    in a finding except for this operator.
    """
    if family == "mission":
        rule = rule_id.split("mission.", 1)[-1]
        return "<=" if mission_rule_types.get(rule) == "max_separation" else ">="
    return COMPARISON_BY_FAMILY.get(family)


def _family(rule_id: str) -> str:
    """'sep.noise::AFE|BUCK' -> 'sep.noise'; 'mission.lead_vector' -> 'mission'."""
    base = rule_id.split("::", 1)[0]
    return "mission" if base.startswith("mission.") else base


def _build_parts(
    components: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]] | None,
    warnings: list[str],
) -> tuple[dict[str, Part], dict[str, dict[str, str]]]:
    """Resolve each component to a Part, and index its three names.

    Properties come from whichever source the submission provides. An inline
    ``properties`` block wins over a catalog lookup, so a caller can override
    one part without maintaining a whole library -- but doing so is recorded,
    because an override is the caller asserting a physical fact.
    """
    parts: dict[str, Part] = {}
    identity: dict[str, dict[str, str]] = {}

    for i, comp in enumerate(components):
        where = f"components[{i}]"
        ref = str(_require(comp, "ref", where))
        catalog_id = comp.get("catalog_id")
        props = comp.get("properties")

        if props is None and catalog_id and catalog:
            props = catalog.get(str(catalog_id))
            if props is None:
                raise SubmissionError(
                    f"{where}: catalog_id '{catalog_id}' is not in the supplied "
                    f"catalog. Send it in `catalog`, or inline the part under "
                    f"`properties`."
                )
        elif props is not None and catalog_id and catalog and catalog_id in catalog:
            warnings.append(
                f"{ref}: inline properties override catalog entry '{catalog_id}'."
            )

        if props is None:
            raise SubmissionError(
                f"{where}: no properties. Supply `catalog_id` with a `catalog`, "
                f"or an inline `properties` object."
            )

        # The engine keys parts by the ref actually placed on the board.
        parts[ref] = parse_part({**props, "id": ref}, warnings)
        identity[ref] = {
            "ref": ref,
            "catalog_id": str(catalog_id) if catalog_id else "",
            "kicad_ref": str(comp.get("kicad_ref", "")),
        }

    if not parts:
        raise SubmissionError("submission contains no components")
    return parts, identity


def _build_layout(sub: dict[str, Any], warnings: list[str]) -> Layout:
    geom = _require(sub, "geometry", "submission")
    enc_raw = _require(geom, "enclosure", "geometry")
    board_raw = _require(geom, "board", "geometry")
    interior = _require(enc_raw, "interior_mm", "geometry.enclosure")

    openings = []
    for j, op in enumerate(enc_raw.get("openings", []) or []):
        size = op.get("size_mm", {}) or {}
        face = op.get("face", "-x")
        if face not in ("+x", "-x", "+y", "-y"):
            warnings.append(
                f"geometry.enclosure.openings[{j}]: unknown face {face!r}; "
                f"assuming '-x'."
            )
            face = "-x"
        openings.append(
            Opening(
                id=str(op.get("id", f"opening_{j}")),
                face=face,
                center_mm=_num_or(op.get("center_mm"), 0.0),
                width_mm=_num_or(size.get("width"), 20.0),
                height_mm=_num_or(size.get("height"), 10.0),
                max_reach_mm=_num_or(op.get("max_reach_mm"), 12.0),
            )
        )

    origin = board_raw.get("origin_mm", [0.0, 0.0, 0.0])
    origin = [_num_or(v, 0.0) for v in origin] + [0.0, 0.0, 0.0]
    size = _require(board_raw, "size_mm", "geometry.board")

    constraints = sub.get("constraints", {}) or {}
    profile_raw = constraints.get("mission_profile", {}) or {}
    defaults = MissionProfile()

    rules = []
    for k, r in enumerate(constraints.get("mission_rules", []) or []):
        between = [str(x) for x in r.get("between", [])]
        if len(between) != 2:
            warnings.append(
                f"constraints.mission_rules[{k}] "
                f"('{r.get('id', k)}'): 'between' needs exactly 2 refs; skipped."
            )
            continue
        if r.get("distance_mm") is None:
            warnings.append(
                f"constraints.mission_rules[{k}] "
                f"('{r.get('id', k)}'): missing distance_mm; skipped."
            )
            continue
        rules.append(
            MissionRule(
                id=str(r.get("id", f"rule_{k}")),
                type=str(r.get("type", "min_separation")),
                between=between,
                distance_mm=float(r["distance_mm"]),
                metric=str(r.get("metric", "center")),
                severity=str(r.get("severity", "major")),
                title=str(r.get("title", r.get("id", f"rule_{k}"))),
                rationale=str(r.get("rationale", "")),
            )
        )

    placements = []
    for i, comp in enumerate(sub.get("components", [])):
        pos = comp.get("position_mm")
        if pos is None or len(pos) < 2:
            raise SubmissionError(
                f"components[{i}] ('{comp.get('ref')}'): missing position_mm [x, y]"
            )
        rot = int(_num_or(comp.get("rotation_deg"), 0.0)) % 360
        if rot % 90:
            warnings.append(
                f"{comp.get('ref')}: rotation {rot} is not a multiple of 90; "
                f"rounded down to keep footprints axis-aligned."
            )
            rot = (rot // 90) * 90
        placements.append(
            Placement(
                ref=str(comp["ref"]),
                part_id=str(comp["ref"]),
                x_mm=_num_or(pos[0], 0.0),
                y_mm=_num_or(pos[1], 0.0),
                rotation_deg=rot,
                anchored=bool(comp.get("anchored", False)),
            )
        )

    traces = []
    for t in geom.get("traces", []) or []:
        path = [
            (_num_or(p[0], 0.0), _num_or(p[1], 0.0))
            for p in t.get("path_mm", [])
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        if path:
            traces.append(
                Trace(
                    id=str(t.get("id", "trace")),
                    path_mm=path,
                    net=str(t.get("net", "")),
                    width_mm=_num_or(t.get("width_mm"), 0.5),
                    high_current=bool(t.get("high_current", False)),
                )
            )

    return Layout(
        name=str(sub.get("design_id", "submission")),
        enclosure=Enclosure(
            interior_length_mm=_num_or(interior.get("length"), 0.0),
            interior_width_mm=_num_or(interior.get("width"), 0.0),
            interior_height_mm=_num_or(interior.get("height"), 0.0),
            wall_thickness_mm=_num_or(enc_raw.get("wall_thickness_mm"), 2.0),
            wall_keepout_mm=_num_or(enc_raw.get("wall_keepout_mm"), 3.0),
            openings=openings,
        ),
        board=Board(
            id=str(board_raw.get("id", "board")),
            length_mm=_num_or(size.get("length"), 0.0),
            width_mm=_num_or(size.get("width"), 0.0),
            thickness_mm=_num_or(size.get("thickness"), 1.6),
            origin_mm=(origin[0], origin[1], origin[2]),
            edge_margin_mm=_num_or(board_raw.get("edge_margin_mm"), 2.0),
            max_component_height_mm=_num_or(
                board_raw.get("max_component_height_mm"), 14.0
            ),
            min_component_gap_mm=_num_or(board_raw.get("min_component_gap_mm"), 0.5),
        ),
        placements=placements,
        traces=traces,
        distance_metric=str(sub.get("distance_metric", "edge")),
        mission=MissionProfile(
            skin_contact_clearance_mm=_num_or(
                profile_raw.get("skin_contact_clearance_mm"),
                defaults.skin_contact_clearance_mm,
            ),
            battery_thermal_clearance_mm=_num_or(
                profile_raw.get("battery_thermal_clearance_mm"),
                defaults.battery_thermal_clearance_mm,
            ),
        ),
        mission_rules=rules,
        description=str(sub.get("brief", "")),
        rationales={
            str(k): str(v)
            for k, v in (constraints.get("rationales", {}) or {}).items()
            if isinstance(v, str)
        },
    )


def review(submission: dict[str, Any]) -> dict[str, Any]:
    """Check one submitted design snapshot. Pure function of its input.

    Raises :class:`SubmissionError` when the submission cannot be read. A
    design that merely *fails* its checks is a successful review with findings.
    """
    if not isinstance(submission, dict):
        raise SubmissionError("submission must be a JSON object")

    design_id = str(_require(submission, "design_id", "submission"))
    revision = _require(submission, "revision", "submission")
    components = _require(submission, "components", "submission")
    if not isinstance(components, list):
        raise SubmissionError("submission.components must be an array")

    warnings: list[str] = []
    catalog = submission.get("catalog")
    parts, identity = _build_parts(components, catalog, warnings)
    layout = _build_layout(submission, warnings)

    results = validate(layout, parts, warnings)

    # Needed to render min- versus max-separation rules correctly.
    mission_rule_types = {r.id: r.type for r in layout.mission_rules}

    findings = []
    for check in results.sorted_checks():
        family = _family(check.id)
        refs = [identity.get(r, {"ref": r, "catalog_id": "", "kicad_ref": ""})
                for r in check.subjects]
        finding: dict[str, Any] = {
            "rule_id": check.id,
            "family": family,
            "title": check.title,
            "status": STATUS_MAP.get(check.status, "unknown"),
            "severity": check.severity,
            "components": refs,
            "kicad_refs": [r["kicad_ref"] for r in refs if r["kicad_ref"]],
            "method": METHOD_BY_FAMILY.get(family, "exact"),
            "explanation": check.message,
            "rationale": check.rationale,
        }
        if check.measured_mm is not None:
            finding["measured"] = {"value": round(check.measured_mm, 4), "unit": "mm"}
        if check.required_mm is not None:
            threshold: dict[str, Any] = {
                "value": round(check.required_mm, 4),
                "unit": "mm",
            }
            comparison = _comparison(family, check.id, mission_rule_types)
            if comparison:
                threshold["comparison"] = comparison
                threshold["reads_as"] = (
                    f"measured {comparison} {round(check.required_mm, 4)} mm"
                )
            finding["threshold"] = threshold
        if check.margin_mm is not None:
            finding["margin"] = {"value": round(check.margin_mm, 4), "unit": "mm"}
        if check.metric:
            finding["metric"] = check.metric
        if check.edge_gap_mm is not None and check.center_distance_mm is not None:
            finding["both_metrics"] = {
                "edge_gap_mm": round(check.edge_gap_mm, 4),
                "center_distance_mm": round(check.center_distance_mm, 4),
            }
        if family in LIMITATION_BY_FAMILY:
            finding["limitation"] = LIMITATION_BY_FAMILY[family]
        if check.suggestion:
            finding["suggested_action"] = check.suggestion
        if check.overlay is not None:
            finding["overlay"] = check.overlay.to_dict()
        findings.append(finding)

    for category, reason in sorted(UNSUPPORTED.items()):
        findings.append({
            "rule_id": f"coverage.not_evaluated::{category}",
            "family": "coverage",
            "title": f"{category.replace('_', ' ').capitalize()} — not evaluated",
            "status": "unknown",
            "severity": "info",
            "components": [],
            "kicad_refs": [],
            "method": "unsupported",
            "explanation": reason,
            "rationale": "",
            "limitation": reason,
        })

    counts: dict[str, int] = {}
    for f in findings:
        counts[f["status"]] = counts.get(f["status"], 0) + 1

    # Per-component index. The engine reasons in checks ("these two are too
    # close"); a board UI annotates components ("this part has two problems").
    # Inverting it here means every consumer gets the same answer instead of
    # each one rolling its own pivot.
    #
    # Every submitted component appears, including the clean ones. A component
    # absent from the findings is ambiguous -- it could be fine, or it could
    # have been skipped -- so `checked` states which of the two it is.
    by_component: list[dict[str, Any]] = []
    for ref in sorted(identity):
        mine = [f for f in findings if any(c["ref"] == ref for c in f["components"])]
        statuses = {f["status"] for f in mine}
        by_component.append({
            **identity[ref],
            "checked": bool(mine),
            "worst_status": (
                "fail" if "fail" in statuses
                else "warning" if "warning" in statuses
                else "unknown" if "unknown" in statuses
                else "pass" if statuses else "not_checked"
            ),
            "worst_severity": min(
                (f["severity"] for f in mine if f["status"] == "fail"),
                key=lambda s: ["blocker", "major", "minor", "info"].index(s),
                default=None,
            ),
            "counts": {
                "fail": sum(1 for f in mine if f["status"] == "fail"),
                "warning": sum(1 for f in mine if f["status"] == "warning"),
                "unknown": sum(1 for f in mine if f["status"] == "unknown"),
                "pass": sum(1 for f in mine if f["status"] == "pass"),
            },
            "rule_ids": [f["rule_id"] for f in mine],
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        # Echoed verbatim so the caller can prove which board these findings
        # describe before annotating anything.
        "design_id": design_id,
        "revision": revision,
        "source_board_hash": submission.get("source_board_hash"),
        "coordinate_frame": {
            "frame": "enclosure",
            "units": "mm",
            "origin": "enclosure interior minimum corner",
            "note": (
                "Overlay geometry is already in this frame. Component positions "
                "were read in board-local mm as submitted."
            ),
        },
        "summary": {
            "total": len(findings),
            "blocking": sum(
                1 for f in findings
                if f["status"] == "fail" and f["severity"] == "blocker"
            ),
            **counts,
        },
        # Echoed so the findings are self-describing: a reviewer reading this
        # file alone can see what the board was meant to do.
        "brief": submission.get("brief", ""),
        "findings": findings,
        # Check-keyed above, component-keyed here. Same facts, two indexes,
        # because a board UI annotates parts and a report lists violations.
        "components": by_component,
        "coverage": {
            "families_evaluated": sorted(
                {f["family"] for f in findings if f["family"] != "coverage"}
            ),
            "not_evaluated": sorted(UNSUPPORTED),
            "note": (
                "A category listed in not_evaluated produced no verdict at all. "
                "Its absence from the findings is not a pass."
            ),
        },
        "warnings": warnings,
    }
