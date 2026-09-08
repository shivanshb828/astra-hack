"""Hand-off from the arithmetic layer to the judgment layer.

MissionPCB splits into two halves that must not be confused:

    A language model decides *what the rules are*. Plain English about the
    product becomes structured constraints; part physics and context become
    thresholds; failures become explanations a hardware engineer would accept.
    None of that has a closed form, and nothing but a model can do it.

    This package decides *whether the rules are met*. Once something upstream
    has asserted "the front end needs 15 mm from the regulator", measuring
    6.0 mm is subtraction. It is reproducible, it is free, and it is right
    every time -- including live on stage, which a sampled distance is not.

This module is the seam. It takes a completed validation run and emits a brief
containing every fact needed to write a real explanation, and nothing that
needs inventing. The model receiving it is told, explicitly, that all geometry
has already been computed and must be quoted rather than recalculated.

Nothing here calls a model or touches the network. The engine stays stdlib-only
and importable from Blender; the brief is data that a caller passes onward.
"""

from __future__ import annotations

from typing import Any

from .models import FAIL, Layout, Part, Results

# Handed to the model alongside the brief. The prohibition is the load-bearing
# part: a model that recomputes a distance will occasionally get it wrong, and
# the disagreement between prose and table is unrecoverable in front of a room.
EXPLAINER_INSTRUCTIONS = (
    "You are reviewing a PCB layout for the product described below. Every "
    "geometric fact in this brief was computed exactly by a deterministic "
    "engine.\n\n"
    "Rules:\n"
    "1. Quote the measured numbers verbatim. Never recompute, re-derive, "
    "estimate, or round a distance, and never introduce a number that does "
    "not appear in this brief.\n"
    "2. For each failure, write what a hardware engineer would say: what will "
    "physically go wrong in this product, and the concrete options for fixing "
    "it. Name the trade-off each option costs.\n"
    "3. Prefer a fix that respects the mission. Moving a part is one option; "
    "so are reducing dissipation, changing a package, reorienting the board, "
    "or accepting the risk with a documented test.\n"
    "4. Where the underlying model is an approximation, say so. Do not imply "
    "a thermal radius is a solved temperature field.\n"
    "5. If two failures share a root cause, say that once rather than "
    "repeating yourself.\n"
)


def _part_context(part: Part) -> dict[str, Any]:
    """Everything known about a part that bears on explaining its failures."""
    ctx: dict[str, Any] = {
        "id": part.id,
        "name": part.name,
        "category": part.category,
        "size_mm": [part.length_mm, part.width_mm, part.height_mm],
    }
    behaviours = []
    if part.heat_source:
        behaviours.append("dissipates heat")
    if part.noise_source:
        behaviours.append("emits switching noise")
    if part.is_sensitive:
        behaviours.append(f"sensitivity {part.sensitivity}")
    if part.skin_contact:
        behaviours.append("held against patient skin")
    if part.thermal_runaway_risk:
        behaviours.append("thermal runaway risk")
    if part.keepout:
        behaviours.append(
            f"needs a {part.keepout.extends_mm:g} mm keep-out on {part.keepout.direction}"
        )
    if part.heat_zone_radius_mm:
        behaviours.append(f"thermal radius {part.heat_zone_radius_mm:g} mm")
    if behaviours:
        ctx["behaviour"] = behaviours
    if part.placement_notes:
        ctx["placement_notes"] = part.placement_notes
    if part.datasheet_url:
        ctx["source"] = part.datasheet_url
    return ctx


def build_brief(
    results: Results,
    layout: Layout,
    parts: dict[str, Part],
    include_passes: bool = False,
) -> dict[str, Any]:
    """Assemble the facts a model needs to explain this validation run.

    Only measured values and declared metadata go in. No prose is synthesised
    here beyond what the mission data already supplied.
    """
    by_ref: dict[str, Part] = {}
    for pl in layout.placements:
        part = parts.get(pl.part_id)
        if part is not None:
            by_ref[pl.ref] = part

    selected = results.checks if include_passes else results.failures

    findings: list[dict[str, Any]] = []
    for c in sorted(selected, key=lambda x: (x.severity, x.id)):
        finding: dict[str, Any] = {
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "severity": c.severity,
            "parts": c.subjects,
            "metric": c.metric,
            "measured_mm": c.measured_mm,
            "required_mm": c.required_mm,
            "margin_mm": c.margin_mm,
            "computed_statement": c.message,
        }
        if c.edge_gap_mm is not None:
            finding["edge_gap_mm"] = c.edge_gap_mm
        if c.center_distance_mm is not None:
            finding["center_distance_mm"] = c.center_distance_mm
        if c.rationale:
            finding["why_the_rule_exists"] = c.rationale
        if c.suggestion:
            # Deliberately labelled: this is the arithmetic consequence of the
            # shortfall, not an engineering recommendation. The model supplies
            # the latter.
            finding["mechanical_delta"] = c.suggestion
        finding["part_context"] = {
            ref: _part_context(by_ref[ref]) for ref in c.subjects if ref in by_ref
        }
        findings.append(finding)

    counts = results.summary()
    return {
        "instructions": EXPLAINER_INSTRUCTIONS,
        "product": {
            "layout": layout.name,
            "description": layout.description,
            "enclosure_interior_mm": [
                layout.enclosure.interior_length_mm,
                layout.enclosure.interior_width_mm,
                layout.enclosure.interior_height_mm,
            ],
            "board_mm": [
                layout.board.length_mm,
                layout.board.width_mm,
                layout.board.thickness_mm,
            ],
            "distance_metric": layout.distance_metric,
            "thresholds": {
                "skin_contact_clearance_mm": layout.mission.skin_contact_clearance_mm,
                "battery_thermal_clearance_mm": layout.mission.battery_thermal_clearance_mm,
                "max_component_height_mm": layout.board.max_component_height_mm,
                "min_component_gap_mm": layout.board.min_component_gap_mm,
                "wall_keepout_mm": layout.enclosure.wall_keepout_mm,
            },
        },
        "summary": {
            "verdict": "FAIL" if counts[FAIL] else "PASS",
            **counts,
        },
        "component_positions": results.component_positions,
        "findings": findings,
        "data_warnings": results.warnings,
        "approximations": [
            "Thermal zones are a declared fixed radius, not a solved thermal "
            "field.",
            "Noise separation is a distance threshold, not a computed coupling "
            "coefficient.",
            "RF keep-out is a rectangular volume, not a radiation pattern.",
            "Skin-contact temperature is inferred from distance to heat "
            "sources, not from a surface-temperature solve.",
        ],
    }


def render_brief_text(brief: dict[str, Any]) -> str:
    """Flatten a brief into prompt-ready plain text."""
    product = brief["product"]
    lines: list[str] = [brief["instructions"], ""]

    lines.append(f"PRODUCT: {product['layout']}")
    if product.get("description"):
        lines.append(product["description"])
    el, ew, eh = product["enclosure_interior_mm"]
    bl, bw, bt = product["board_mm"]
    lines.append(
        f"Enclosure interior {el:g} x {ew:g} x {eh:g} mm; "
        f"board {bl:g} x {bw:g} x {bt:g} mm. "
        f"Distances are measured {product['distance_metric']}-to-{product['distance_metric']}."
    )
    lines.append("")

    lines.append("THRESHOLDS IN FORCE")
    for key, val in product["thresholds"].items():
        lines.append(f"  {key.replace('_', ' ')}: {val:g} mm")
    lines.append("")

    s = brief["summary"]
    lines.append(
        f"VERDICT: {s['verdict']} - {s['PASS']} passed, {s['FAIL']} failed, "
        f"{s['WARN']} warnings, {s['SKIP']} skipped."
    )
    lines.append("")

    if brief["data_warnings"]:
        lines.append("DATA WARNINGS (the engine had to assume something)")
        for w in brief["data_warnings"]:
            lines.append(f"  - {w}")
        lines.append("")

    lines.append("FINDINGS (all geometry already computed - quote, do not recompute)")
    lines.append("")
    for f in brief["findings"]:
        lines.append(f"[{f['severity'].upper()}] {f['title']}  ({f['id']})")
        lines.append(f"  measured: {f['computed_statement']}")
        if f.get("edge_gap_mm") is not None and f.get("center_distance_mm") is not None:
            lines.append(
                f"  both metrics: edge gap {f['edge_gap_mm']:.2f} mm, "
                f"center distance {f['center_distance_mm']:.2f} mm"
            )
        if f.get("why_the_rule_exists"):
            lines.append(f"  rule exists because: {f['why_the_rule_exists']}")
        if f.get("mechanical_delta"):
            lines.append(f"  raw shortfall: {f['mechanical_delta']}")
        for ref, ctx in f.get("part_context", {}).items():
            bits = ", ".join(ctx.get("behaviour", [])) or "no special behaviour"
            size = ctx["size_mm"]
            lines.append(
                f"  {ref} = {ctx['name']} [{ctx['category']}] "
                f"{size[0]:g}x{size[1]:g}x{size[2]:g} mm; {bits}"
            )
            if ctx.get("placement_notes"):
                lines.append(f"      note: {ctx['placement_notes']}")
        lines.append("")

    lines.append("MODEL LIMITATIONS - do not overstate these in your write-up")
    for a in brief["approximations"]:
        lines.append(f"  - {a}")

    return "\n".join(lines).rstrip() + "\n"
