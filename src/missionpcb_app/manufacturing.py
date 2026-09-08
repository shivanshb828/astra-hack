"""Manufacturing/export package for the demo widget.

This is a planning handoff, not a quote engine. It gathers the current design,
catalog facts, validation status, render-contract files, and open manufacturing
risks into one stable payload that a widget can export.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from constraint_engine import load_parts

from .analysis import DEFAULT_PARTS
from .schema import AnalysisResult, DesignState


def _cost_band(quantity: int, assembly: bool) -> dict[str, Any]:
    """Return transparent demo-cost bands for planning conversations."""
    board_low = 25 if quantity <= 5 else 80
    board_high = 90 if quantity <= 5 else 280
    assembly_low = 0 if not assembly else (120 if quantity <= 5 else 300)
    assembly_high = 0 if not assembly else (550 if quantity <= 5 else 1500)
    component_low = quantity * 18
    component_high = quantity * 65
    return {
        "currency": "USD",
        "quantity": quantity,
        "assembly_included": assembly,
        "pcb_fabrication": {"low": board_low, "high": board_high},
        "components": {"low": component_low, "high": component_high},
        "assembly": {"low": assembly_low, "high": assembly_high},
        "total": {
            "low": board_low + component_low + assembly_low,
            "high": board_high + component_high + assembly_high,
        },
        "confidence": "planning_estimate",
        "notes": [
            "Demo estimate only; send Gerbers, BOM, CPL, stackup, and assembly notes for a real quote.",
            "Medical wearable compliance, battery safety qualification, testing, and enclosure tooling are excluded.",
        ],
    }


def build_manufacturing_package(
    state: DesignState,
    *,
    analysis: AnalysisResult | None = None,
    integrations: dict[str, Any] | None = None,
    render_contracts: list[str] | None = None,
    quantity: int = 5,
    assembly: bool = True,
) -> dict[str, Any]:
    """Create the export payload the widget can hand to a human or CM."""
    parts_index, part_warnings = load_parts(state.parts_source or DEFAULT_PARTS)
    rows = []
    for comp in state.components:
        part = parts_index.get(comp.part_id)
        rows.append(
            {
                "ref": comp.ref,
                "part_id": comp.part_id,
                "name": part.name if part else comp.part_id,
                "category": part.category if part else "unknown",
                "quantity": 1,
                "package_size_mm": (
                    [part.length_mm, part.width_mm, part.height_mm] if part else None
                ),
                "datasheet_url": part.datasheet_url if part else None,
                "sourcing_status": "catalog_record" if part else "missing_part_record",
                "notes": part.placement_notes if part else "",
            }
        )

    integration_status = integrations or {}
    kicad = integration_status.get("kicad", {})
    blender = integration_status.get("blender", {})
    manufacturing_files = [
        {
            "kind": "design_json",
            "status": "ready",
            "path": "missionpcb-export.json",
            "use": "Canonical design, layout, analysis, and history for the demo.",
        },
        {
            "kind": "render_contract",
            "status": "ready" if render_contracts else "missing",
            "paths": render_contracts or [],
            "use": "Native simulation lane input: positions, checks, and overlays.",
        },
        {
            "kind": "blender_scene",
            "status": "ready" if blender.get("asset_present") else "pending",
            "path": blender.get("asset_path"),
            "use": "Visual review, comments, and 3D enclosure discussion.",
        },
        {
            "kind": "kicad_project",
            "status": "ready" if kicad.get("status") == "connected" else "pending",
            "paths": kicad.get("project_files", []) + kicad.get("board_files", []),
            "use": "Required before Gerber, drill, netlist, ERC, DRC, BOM, and CPL export.",
        },
        {
            "kind": "fabrication_outputs",
            "status": "pending",
            "paths": [],
            "use": "Gerbers, drill files, pick-and-place/CPL, BOM, paste layers, and assembly drawing.",
        },
    ]

    failures = []
    skips = []
    if analysis:
        failures = [
            {
                "id": check.check_id,
                "title": check.title,
                "severity": check.severity,
                "component_refs": check.component_refs,
                "reason": check.explanation,
            }
            for check in analysis.checks
            if check.status == "fail"
        ]
        skips = [
            {
                "id": check.check_id,
                "title": check.title,
                "missing_inputs": check.missing_inputs,
            }
            for check in analysis.checks
            if check.status == "not_applicable"
        ]

    return {
        "schema": "missionpcb.manufacturing_export.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": {
            "id": state.design_id,
            "revision": state.revision,
            "name": state.name,
            "device_type": state.device_type,
        },
        "bom": rows,
        "validation": {
            "summary": analysis.summary if analysis else None,
            "open_failures": failures,
            "not_evaluated": skips,
            "part_warnings": part_warnings,
        },
        "manufacturing_files": manufacturing_files,
        "manufacturing_path": [
            "Connect or import the KiCad project for the approved layout.",
            "Run ERC/DRC and resolve any native-tool errors.",
            "Export Gerbers, drill files, BOM, CPL, paste layers, and assembly drawings.",
            "Send the package to a PCB assembler for quote and DFM review.",
            "Order a small EVT build, inspect dimensions, then run electrical, thermal, battery, and wearable safety tests.",
        ],
        "cost_estimate": _cost_band(quantity, assembly),
        "blocked_until": [
            "Native KiCad project is connected and checked.",
            "Battery protection module and qualification path are decided.",
            "Unmodelled regulatory, patient-contact, battery, DFM, and enclosure tests are explicitly owned.",
        ],
    }
