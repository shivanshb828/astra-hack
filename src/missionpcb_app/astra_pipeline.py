"""Astra boundary fixtures for the native-tool widget.

The live product path is:

    parts + mission + scene -> Astra advisor -> Astra generator -> native tool

This module does not pretend to be that model. It gives the app and Blender
widget a deterministic contract fixture while credentials are absent, so we can
test the request/response shape and native-tool handoff without hiding the fact
that no live Astra call happened.
"""

from __future__ import annotations

from typing import Any
import json
import os

from constraint_engine import load_parts

from .analysis import DEFAULT_PARTS, analyse
from .schema import DesignState

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_RENDER_CONTRACT = os.path.join(REPO_ROOT, "render", "naive.json")


def load_render_contract(path: str = DEFAULT_RENDER_CONTRACT) -> dict[str, Any]:
    """Read Dhruva's committed simulation-lane contract."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render_contract_payload(path: str = DEFAULT_RENDER_CONTRACT) -> dict[str, Any]:
    """Return the native-view context Primary Astra should inspect."""
    contract = load_render_contract(path)
    failed = [check for check in contract.get("checks", []) if check.get("status") == "FAIL"]
    overlays = [check["overlay"] for check in failed if check.get("overlay")]
    overlays.extend(contract.get("zone_overlays", []))
    return {
        "source": "render_contract",
        "path": os.path.relpath(path, REPO_ROOT),
        "layout": contract.get("layout"),
        "passed": contract.get("passed"),
        "summary": contract.get("summary", {}),
        "components": contract.get("component_positions", []),
        "failed_checks": failed,
        "overlays": overlays,
    }


def component_catalog_payload(state: DesignState) -> list[dict[str, Any]]:
    """Return the scene facts Astra needs, keyed by stable component ref."""
    parts_index, _ = load_parts(state.parts_source or DEFAULT_PARTS)
    payload: list[dict[str, Any]] = []
    for comp in state.components:
        part = parts_index.get(comp.part_id)
        payload.append(
            {
                "ref": comp.ref,
                "part_id": comp.part_id,
                "kicad_ref": comp.kicad_ref,
                "position_mm": list(comp.pos_mm),
                "rotation_deg": comp.normalised_rotation(),
                "category": getattr(part, "category", "unknown") if part else "unknown",
                "name": getattr(part, "name", comp.part_id) if part else comp.part_id,
                "size_mm": [
                    getattr(part, "length_mm", None) if part else None,
                    getattr(part, "width_mm", None) if part else None,
                    getattr(part, "height_mm", None) if part else None,
                ],
                "flags": {
                    "heat_source": bool(getattr(part, "heat_source", False)) if part else False,
                    "noise_source": bool(getattr(part, "noise_source", False)) if part else False,
                    "skin_contact": bool(getattr(part, "skin_contact", False)) if part else False,
                    "sensitivity": getattr(part, "sensitivity", "none") if part else "none",
                },
            }
        )
    return payload


def astra_primary_fixture(mission: str, state: DesignState) -> dict[str, Any]:
    """Fixture for the first Astra pass: find worries from parts and scene."""
    analysis = analyse(state)
    components = component_catalog_payload(state)
    failures = [check for check in analysis.checks if check.status == "fail"]
    blockers = [
        {
            "id": check.check_id,
            "title": check.title,
            "category": check.category,
            "severity": check.severity,
            "component_refs": check.component_refs,
            "why": check.explanation,
            "viz": [v.model_dump() for v in check.viz],
        }
        for check in failures
    ]

    cell = next((c for c in components if c["ref"] == "CELL"), None)
    if cell and cell["size_mm"][2] and cell["size_mm"][2] > state.enclosure.interior_height_mm:
        blockers.insert(
            0,
            {
                "id": "astra.mechanical.cell_headroom",
                "title": "Battery exceeds enclosure headroom",
                "category": "mechanical",
                "severity": "blocker",
                "component_refs": ["CELL"],
                "why": (
                    f"{cell['part_id']} is {cell['size_mm'][2]} mm tall, while "
                    f"the enclosure interior is {state.enclosure.interior_height_mm} mm."
                ),
                "viz": [
                    {
                        "type": "height_limit",
                        "frame": "enclosure",
                        "units": "mm",
                        "component_refs": ["CELL"],
                        "measured_mm": cell["size_mm"][2],
                        "limit_mm": state.enclosure.interior_height_mm,
                    }
                ],
            },
        )

    return {
        "mode": "fixture",
        "source": "astra_primary_fixture",
        "mission": mission,
        "design_revision": state.revision,
        "components": components,
        "considerations": [
            "Continuous skin contact makes heat and patient-contact assumptions first-class constraints.",
            "The analog front end is vulnerable to switching noise and heat-source placement.",
            "Battery, charger, and protection choices must be reviewed as a system, not as isolated parts.",
        ],
        "blockers": blockers,
        "open_questions": [
            "Is the enclosure height fixed, or can the industrial design grow to fit the selected cell?",
            "Should Astra swap the buck for a buck-boost before manipulating the board?",
        ],
    }


def astra_primary_from_render_fixture(
    mission: str,
    render_path: str = DEFAULT_RENDER_CONTRACT,
) -> dict[str, Any]:
    """Fixture Primary Astra pass using Dhruva's render contract as context."""
    view = render_contract_payload(render_path)
    blockers = [
        {
            "id": check.get("id"),
            "title": check.get("title"),
            "category": str(check.get("id", "")).split("::", 1)[0],
            "severity": check.get("severity", "major"),
            "component_refs": check.get("subjects", []),
            "why": check.get("message", ""),
            "rationale": check.get("rationale", ""),
            "suggestion": check.get("suggestion", ""),
            "viz": [check["overlay"]] if check.get("overlay") else [],
        }
        for check in view["failed_checks"]
    ]
    return {
        "mode": "fixture",
        "source": "astra_primary_from_render_fixture",
        "mission": mission,
        "native_view": view,
        "components": view["components"],
        "considerations": [
            "Use the committed render contract as the ground truth for what is visible in Blender/KiCad.",
            "Prioritize failed checks with overlays because they can be highlighted directly in the native viewport.",
            "Treat SKIP/not-evaluated rows as demo talking points, not as passes.",
        ],
        "blockers": blockers,
        "open_questions": [
            "Should Astra apply a proposed native-tool move automatically, or wait for user approval?",
            "Which user comments should become durable constraints for the next loop?",
        ],
    }


def astra_secondary_kicad_fixture(primary: dict[str, Any]) -> dict[str, Any]:
    """Fixture for the second Astra pass: convert worries into tool actions."""
    actions: list[dict[str, Any]] = []
    for blocker in primary.get("blockers", []):
        refs = blocker.get("component_refs", [])
        category = blocker.get("category")
        if category in {"noise_separation", "thermal", "mechanical"} or "AFE" in refs:
            actions.append(
                {
                    "tool": "kicad",
                    "action": "propose_component_move",
                    "component_refs": refs,
                    "reason": blocker.get("title", ""),
                    "requires_user_apply": True,
                }
            )
        actions.append(
            {
                "tool": "blender",
                "action": "highlight",
                "component_refs": refs,
                "category": category,
                "requires_user_apply": False,
            }
        )

    return {
        "mode": "fixture",
        "source": "astra_secondary_kicad_fixture",
        "upstream_source": primary.get("source"),
        "actions": actions,
        "limits": [
            "No native KiCad project is connected in this repo, so actions are proposals only.",
            "The fixture does not mutate KiCad or Blender until the widget applies an action.",
        ],
    }
