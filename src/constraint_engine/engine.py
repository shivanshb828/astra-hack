"""Top-level validation entry point."""

from __future__ import annotations

from .models import Check, Layout, Part, Results
from .rules import Scene, run_all, zone_overlays

ENGINE_VERSION = "0.1.0"


def build_scene(layout: Layout, parts: dict[str, Part]) -> Scene:
    return Scene(layout, parts)


def validate(
    layout: Layout,
    parts: dict[str, Part],
    warnings: list[str] | None = None,
    generated_at: str | None = None,
) -> Results:
    """Run every rule against a layout and collect the verdicts."""
    scene = Scene(layout, parts)
    checks: list[Check] = run_all(scene)

    positions = []
    for ref in scene.refs:
        pl = scene.placement_of[ref]
        part = scene.part_of[ref]
        rect = scene.rect_of[ref]
        ox, oy, oz = layout.board.origin_mm
        positions.append(
            {
                "ref": ref,
                "part_id": part.id,
                "part_name": part.name,
                "category": part.category,
                "board_xy_mm": [round(pl.x_mm, 3), round(pl.y_mm, 3)],
                "enclosure_xyz_mm": [
                    round(ox + pl.x_mm, 3),
                    round(oy + pl.y_mm, 3),
                    round(oz + layout.board.thickness_mm, 3),
                ],
                "size_mm": [
                    round(rect.width, 3),
                    round(rect.height, 3),
                    round(part.height_mm, 3),
                ],
                "rotation_deg": pl.rotation_deg,
                "heat_source": part.heat_source,
                "noise_source": part.noise_source,
                "sensitivity": part.sensitivity,
                "skin_contact": part.skin_contact,
            }
        )

    return Results(
        layout_name=layout.name,
        checks=checks,
        warnings=list(warnings or []),
        zone_overlays=zone_overlays(scene),
        component_positions=positions,
        engine_version=ENGINE_VERSION,
        generated_at=generated_at,
    )
