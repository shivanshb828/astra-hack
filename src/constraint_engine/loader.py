"""Tolerant JSON loading for parts libraries and layouts.

The parts file is authored by hand, in parallel, by someone who is not reading
this module. It therefore has to accept more than one spelling of the same
fact. Two styles are already in circulation:

    Style A, keyed by the *behaviour* of the other part::

        "required_clearance_mm": {"from_hot_components": 15, "from_noisy_components": 18}

    Style B, keyed by the *category* of the other part::

        "avoid_near": ["rf", "sensor"],
        "min_distance_mm": {"rf": 20, "sensor": 15}

Both normalize into the same :class:`~constraint_engine.models.Part`. Anything
unrecognised produces a warning that travels through to the report rather than
an exception -- a missing field should be visible, never silent, and never fatal
in the middle of a demo.
"""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any

from .models import (
    Board,
    Clearances,
    Enclosure,
    Keepout,
    Layout,
    MissionProfile,
    MissionRule,
    Opening,
    Part,
    Placement,
    Trace,
)

# Applied when a part says to avoid something but never says by how much.
DEFAULT_AVOID_DISTANCE_MM = 10.0

# Canonical categories, with the informal names people actually type.
CATEGORY_ALIASES = {
    "rf": "wireless",
    "radio": "wireless",
    "wireless": "wireless",
    "antenna": "wireless",
    "mcu": "processor",
    "cpu": "processor",
    "microcontroller": "processor",
    "processor": "processor",
    "power": "power_regulator",
    "regulator": "power_regulator",
    "psu": "power_regulator",
    "dcdc": "power_regulator",
    "power_regulator": "power_regulator",
    "driver": "driver",
    "motor": "driver",
    "motor_driver": "driver",
    "load": "driver",
    "sensor": "sensor",
    "imu": "sensor",
    "afe": "sensor",
    "analog_frontend": "sensor",
    "biosignal": "sensor",
    "electrode": "electrode",
    "connector": "connector",
    "header": "connector",
    "pogo": "connector",
    "battery": "battery",
    "lipo": "battery",
    "cell": "battery",
}

# Behavioural clearance keys -> canonical property name.
PROPERTY_ALIASES = {
    "from_hot_components": "hot",
    "from_hot_component": "hot",
    "from_hot": "hot",
    "hot": "hot",
    "heat": "hot",
    "thermal": "hot",
    "from_heat_sources": "hot",
    "from_noisy_components": "noisy",
    "from_noisy_component": "noisy",
    "from_noisy": "noisy",
    "noisy": "noisy",
    "noise": "noisy",
    "from_noise_sources": "noisy",
    "emi": "noisy",
}

# Where clearance dictionaries may live.
CLEARANCE_CONTAINERS = (
    "required_clearance_mm",
    "min_distance_mm",
    "clearance_mm",
    "min_separation_mm",
    "keep_away_mm",
)

_HIGH_WORDS = {"high", "yes", "true", "severe", "critical"}
_MED_WORDS = {"medium", "med", "moderate"}
_LOW_WORDS = {"low", "minor", "slight"}


class LoadError(Exception):
    """Raised only when the input is unusable, e.g. malformed JSON."""


def _read_json(path: str | Path) -> Any:
    p = Path(path)
    try:
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise LoadError(f"file not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise LoadError(f"{p} is not valid JSON: {exc}") from exc


def _as_float(value: Any) -> float | None:
    """Coerce a number that might have arrived as a string like '15 mm'.

    Non-finite values are rejected rather than passed through. NaN is the
    dangerous one: every comparison against it is False, so `max(0.0, nan)`
    returns 0.0 and a NaN-sized component reads as *inside* the board. A single
    typo'd dimension would silently switch off containment checking instead of
    failing loudly.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        cleaned = value.strip().lower().removesuffix("mm").strip()
        try:
            parsed = float(cleaned)
        except ValueError:
            return None
    else:
        return None
    return parsed if isfinite(parsed) else None


def _num_or(value: Any, default: float) -> float:
    """Coerce to float, substituting the default only when there is no number.

    Deliberately not ``_as_float(x) or default``: zero is a legitimate value for
    most of these fields. A layout may declare no wall keep-out, no edge margin,
    or no courtyard requirement, and ``or`` would silently overwrite that choice
    with the default -- then report violations the author explicitly opted out of.
    """
    parsed = _as_float(value)
    return default if parsed is None else parsed


def _as_bool(value: Any) -> bool:
    """Accept booleans, yes/no strings, and risk levels like 'high'."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in _HIGH_WORDS | _MED_WORDS
    return False


def _normalize_category(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    return CATEGORY_ALIASES.get(key, key)


def _normalize_sensitivity(raw: dict[str, Any], part_id: str,
                          warnings: list[str]) -> str:
    """Map assorted spellings onto none/low/medium/high.

    An unrecognised word warns rather than quietly resolving to "none".
    Falling back silently would switch off every thermal and noise rule for
    that part, and the report would look clean because the checks never ran.
    """
    value = raw.get("sensitive", raw.get("sensitivity"))
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "high" if value else "none"
    if isinstance(value, str):
        word = value.strip().lower()
        if word in _HIGH_WORDS:
            return "high"
        if word in _MED_WORDS:
            return "medium"
        if word in _LOW_WORDS:
            return "low"
        if word in ("none", "no", "false"):
            return "none"
    warnings.append(
        f"part '{part_id}': unrecognised sensitivity {value!r}; treated as "
        f"'none', which disables its thermal and noise clearance checks. "
        f"Use one of: none, low, medium, high."
    )
    return "none"


def _extract_dimensions(raw: dict[str, Any], part_id: str,
                        warnings: list[str]) -> tuple[float, float, float]:
    """Pull length/width/height from any of the shapes people write."""
    for container in ("dimensions_mm", "size_mm", "dimensions", "size"):
        dims = raw.get(container)
        if isinstance(dims, dict):
            length = _as_float(dims.get("length", dims.get("l", dims.get("x"))))
            width = _as_float(dims.get("width", dims.get("w", dims.get("y"))))
            height = _as_float(dims.get("height", dims.get("h", dims.get("z"))))
            if None not in (length, width, height):
                return length, width, height  # type: ignore[return-value]
        elif isinstance(dims, (list, tuple)) and len(dims) == 3:
            vals = [_as_float(v) for v in dims]
            if None not in vals:
                return vals[0], vals[1], vals[2]  # type: ignore[return-value]

    # Flat keys: length_mm / width_mm / height_mm
    flat = [_as_float(raw.get(k)) for k in ("length_mm", "width_mm", "height_mm")]
    if None not in flat:
        return flat[0], flat[1], flat[2]  # type: ignore[return-value]

    warnings.append(
        f"part '{part_id}': no usable dimensions found; "
        f"defaulting to 1x1x1 mm. Add a \"dimensions_mm\" object with "
        f"length/width/height."
    )
    return 1.0, 1.0, 1.0


def _extract_clearances(raw: dict[str, Any], part_id: str,
                        warnings: list[str]) -> Clearances:
    """Fold every clearance spelling into the two canonical lookups.

    A single container may legitimately mix both styles, so each key is routed
    on its own: recognised behaviour words go to ``from_property``, everything
    else is treated as a category.
    """
    by_property: dict[str, float] = {}
    by_category: dict[str, float] = {}

    for container in CLEARANCE_CONTAINERS:
        block = raw.get(container)
        if not isinstance(block, dict):
            continue
        for key, value in block.items():
            dist = _as_float(value)
            if dist is None:
                warnings.append(
                    f"part '{part_id}': clearance '{container}.{key}' has "
                    f"non-numeric value {value!r}; ignored."
                )
                continue
            norm_key = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if norm_key in PROPERTY_ALIASES:
                prop = PROPERTY_ALIASES[norm_key]
                by_property[prop] = max(by_property.get(prop, 0.0), dist)
            else:
                cat = _normalize_category(norm_key)
                by_category[cat] = max(by_category.get(cat, 0.0), dist)

    # "avoid_near" without a distance still expresses intent; honour it with a
    # documented default and say so loudly.
    avoid = raw.get("avoid_near", raw.get("avoid", []))
    if isinstance(avoid, str):
        avoid = [avoid]
    if isinstance(avoid, (list, tuple)):
        for entry in avoid:
            norm_key = str(entry).strip().lower().replace("-", "_").replace(" ", "_")
            if norm_key in PROPERTY_ALIASES:
                prop = PROPERTY_ALIASES[norm_key]
                if prop not in by_property:
                    by_property[prop] = DEFAULT_AVOID_DISTANCE_MM
                    warnings.append(
                        f"part '{part_id}': avoid_near '{entry}' has no distance; "
                        f"assumed {DEFAULT_AVOID_DISTANCE_MM:g} mm."
                    )
            else:
                cat = _normalize_category(norm_key)
                if cat not in by_category:
                    by_category[cat] = DEFAULT_AVOID_DISTANCE_MM
                    warnings.append(
                        f"part '{part_id}': avoid_near '{entry}' has no distance; "
                        f"assumed {DEFAULT_AVOID_DISTANCE_MM:g} mm."
                    )

    return Clearances(from_property=by_property, from_category=by_category)


def _extract_keepout(raw: dict[str, Any]) -> Keepout | None:
    """Read an antenna-style directional exclusion zone, if declared."""
    block = raw.get("keepout_zone_mm", raw.get("keepout_mm", raw.get("keepout")))
    if not isinstance(block, dict):
        return None
    extends = _as_float(block.get("extends", block.get("length", block.get("depth"))))
    width = _as_float(block.get("width", block.get("span")))
    if extends is None:
        return None
    direction = block.get("direction", "+x")
    if direction not in ("+x", "-x", "+y", "-y"):
        direction = "+x"
    return Keepout(
        extends_mm=extends,
        width_mm=width if width is not None else extends / 2.0,
        direction=direction,
    )


def _heat_zone(raw: dict[str, Any]) -> float | None:
    for key in ("heat_zone_radius_mm", "heat_radius_mm", "thermal_zone_mm"):
        val = _as_float(raw.get(key))
        if val is not None:
            return val
    return None


def parse_part(raw: dict[str, Any], warnings: list[str]) -> Part:
    """Normalize one raw part dictionary."""
    part_id = str(raw.get("id") or raw.get("part_id") or raw.get("name") or "unnamed")
    length, width, height = _extract_dimensions(raw, part_id, warnings)

    heat = _as_bool(raw.get("heat_source", raw.get("thermal_risk", False)))
    noise = _as_bool(raw.get("noise_source", raw.get("noisy", False)))

    # A declared thermal radius implies the part is a heat source even if the
    # boolean was never written.
    heat_radius = _heat_zone(raw)
    if heat_radius is not None and not heat:
        heat = True

    category = _normalize_category(raw.get("category", "unknown"))

    # A lithium cell carries runaway risk whether or not anyone remembered to
    # write the flag, so infer it from the category as a floor.
    runaway = _as_bool(raw.get("thermal_runaway_risk", False)) or category == "battery"

    return Part(
        id=part_id,
        name=str(raw.get("name", part_id)),
        category=category,
        length_mm=length,
        width_mm=width,
        height_mm=height,
        heat_source=heat,
        noise_source=noise,
        sensitivity=_normalize_sensitivity(raw, part_id, warnings),
        heat_zone_radius_mm=heat_radius,
        keepout=_extract_keepout(raw),
        clearances=_extract_clearances(raw, part_id, warnings),
        skin_contact=_as_bool(raw.get("skin_contact", raw.get("patient_contact", False))),
        thermal_runaway_risk=runaway,
        placement_notes=str(raw.get("placement_notes", "")),
        datasheet_url=raw.get("source_url") or raw.get("datasheet_url"),
        raw=raw,
    )


def load_parts(path: str | Path) -> tuple[dict[str, Part], list[str]]:
    """Load a parts library. Returns (parts by id, warnings)."""
    data = _read_json(path)

    # Accept either a bare list or {"parts": [...]}.
    if isinstance(data, dict):
        data = data.get("parts", [])
    if not isinstance(data, list):
        raise LoadError(
            f"{path}: expected a JSON array of parts, or an object with a "
            f"'parts' array; got {type(data).__name__}"
        )

    warnings: list[str] = []
    parts: dict[str, Part] = {}
    for entry in data:
        if not isinstance(entry, dict):
            warnings.append(f"skipped a non-object entry in {path}: {entry!r}")
            continue
        part = parse_part(entry, warnings)
        if part.id in parts:
            warnings.append(f"duplicate part id '{part.id}'; later entry wins.")
        parts[part.id] = part

    if not parts:
        raise LoadError(f"{path}: no usable parts found")
    return parts, warnings


def _parse_enclosure(raw: dict[str, Any], warnings: list[str]) -> Enclosure:
    interior = raw.get("interior_mm", raw)
    length = _num_or(interior.get("length"), 90.0)
    width = _num_or(interior.get("width"), 50.0)
    height = _num_or(interior.get("height"), 18.0)

    openings: list[Opening] = []
    for idx, entry in enumerate(raw.get("openings", []) or []):
        if not isinstance(entry, dict):
            warnings.append(f"enclosure opening #{idx} is not an object; skipped.")
            continue
        face = entry.get("face", "-x")
        if face not in ("+x", "-x", "+y", "-y"):
            warnings.append(
                f"enclosure opening '{entry.get('id', idx)}' has unknown face "
                f"{face!r}; assuming '-x'."
            )
            face = "-x"
        size = entry.get("size_mm", {})
        openings.append(
            Opening(
                id=str(entry.get("id", f"opening_{idx}")),
                face=face,
                center_mm=_num_or(entry.get("center_mm"), 0.0),
                width_mm=_num_or(size.get("width"), 20.0),
                height_mm=_num_or(size.get("height"), 10.0),
                max_reach_mm=_num_or(entry.get("max_reach_mm"), 12.0),
            )
        )

    return Enclosure(
        interior_length_mm=length,
        interior_width_mm=width,
        interior_height_mm=height,
        wall_thickness_mm=_num_or(raw.get("wall_thickness_mm"), 2.0),
        wall_keepout_mm=_num_or(raw.get("wall_keepout_mm"), 3.0),
        openings=openings,
    )


def _parse_board(raw: dict[str, Any]) -> Board:
    size = raw.get("size_mm", {})
    origin = raw.get("origin_mm", [0.0, 0.0, 0.0])
    origin_vals = [_num_or(v, 0.0) for v in origin] + [0.0, 0.0, 0.0]
    return Board(
        id=str(raw.get("id", "PCB")),
        length_mm=_num_or(size.get("length"), 72.0),
        width_mm=_num_or(size.get("width"), 38.0),
        thickness_mm=_num_or(size.get("thickness"), 1.6),
        origin_mm=(origin_vals[0], origin_vals[1], origin_vals[2]),
        edge_margin_mm=_num_or(raw.get("edge_margin_mm"), 2.0),
        max_component_height_mm=_num_or(raw.get("max_component_height_mm"), 14.0),
        min_component_gap_mm=_num_or(raw.get("min_component_gap_mm"), 0.5),
    )


def _parse_placements(entries: list[Any], warnings: list[str]) -> list[Placement]:
    placements: list[Placement] = []
    for idx, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            warnings.append(f"placement #{idx} is not an object; skipped.")
            continue
        pos = entry.get("pos_mm", [0.0, 0.0])
        x = _num_or(pos[0], 0.0) if len(pos) > 0 else 0.0
        y = _num_or(pos[1], 0.0) if len(pos) > 1 else 0.0
        rotation = int(_num_or(entry.get("rotation_deg"), 0.0)) % 360
        if rotation % 90 != 0:
            warnings.append(
                f"placement '{entry.get('ref', idx)}': rotation {rotation} is not a "
                f"multiple of 90; rounded down to keep footprints axis-aligned."
            )
            rotation = (rotation // 90) * 90
        placements.append(
            Placement(
                ref=str(entry.get("ref", f"C{idx}")),
                part_id=str(entry.get("part_id", "")),
                x_mm=x,
                y_mm=y,
                rotation_deg=rotation,
                anchored=bool(entry.get("anchored", False)),
            )
        )
    return placements


def _parse_traces(entries: list[Any], warnings: list[str]) -> list[Trace]:
    traces: list[Trace] = []
    for idx, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            warnings.append(f"trace #{idx} is not an object; skipped.")
            continue
        path_raw = entry.get("path_mm", [])
        path: list[tuple[float, float]] = []
        for pt in path_raw:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                px, py = _as_float(pt[0]), _as_float(pt[1])
                if px is not None and py is not None:
                    path.append((px, py))
        if len(path) < 1:
            warnings.append(
                f"trace '{entry.get('id', idx)}' has no usable path points; skipped."
            )
            continue
        traces.append(
            Trace(
                id=str(entry.get("id", f"trace_{idx}")),
                path_mm=path,
                net=str(entry.get("net", "")),
                width_mm=_num_or(entry.get("width_mm"), 0.5),
                high_current=bool(entry.get("high_current", False)),
            )
        )
    return traces


def _parse_mission(raw: dict[str, Any]) -> MissionProfile:
    defaults = MissionProfile()
    return MissionProfile(
        skin_contact_clearance_mm=_num_or(
            raw.get("skin_contact_clearance_mm"),
            defaults.skin_contact_clearance_mm,
        ),
        battery_thermal_clearance_mm=_num_or(
            raw.get("battery_thermal_clearance_mm"),
            defaults.battery_thermal_clearance_mm,
        ),
    )


def _parse_mission_rules(entries: list[Any], warnings: list[str]) -> list[MissionRule]:
    rules: list[MissionRule] = []
    for idx, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            warnings.append(f"mission rule #{idx} is not an object; skipped.")
            continue
        rule_id = str(entry.get("id", f"mission_{idx}"))
        rule_type = str(entry.get("type", "min_separation"))
        if rule_type not in ("min_separation", "max_separation"):
            warnings.append(
                f"mission rule '{rule_id}': unknown type {rule_type!r}; skipped."
            )
            continue
        between = [str(r) for r in entry.get("between", [])]
        if len(between) != 2:
            warnings.append(
                f"mission rule '{rule_id}': 'between' needs exactly 2 refs; skipped."
            )
            continue
        distance = _as_float(entry.get("distance_mm"))
        if distance is None:
            warnings.append(
                f"mission rule '{rule_id}': missing numeric distance_mm; skipped."
            )
            continue
        metric = str(entry.get("metric", "center")).lower()
        if metric not in ("center", "edge"):
            warnings.append(
                f"mission rule '{rule_id}': unknown metric {metric!r}; using 'center'."
            )
            metric = "center"
        rules.append(
            MissionRule(
                id=rule_id,
                type=rule_type,
                between=between,
                distance_mm=distance,
                metric=metric,
                severity=str(entry.get("severity", "major")),
                title=str(entry.get("title", rule_id)),
                rationale=str(entry.get("rationale", "")),
            )
        )
    return rules


def load_layout(path: str | Path) -> tuple[Layout, list[str]]:
    """Load a layout file. Returns (layout, warnings)."""
    data = _read_json(path)
    if not isinstance(data, dict):
        raise LoadError(f"{path}: expected a JSON object describing a layout")

    warnings: list[str] = []
    metric = str(data.get("distance_metric", "edge")).lower()
    if metric not in ("edge", "center"):
        warnings.append(f"unknown distance_metric {metric!r}; using 'edge'.")
        metric = "edge"

    layout = Layout(
        name=str(data.get("name", Path(path).stem)),
        enclosure=_parse_enclosure(data.get("enclosure", {}), warnings),
        board=_parse_board(data.get("board", {})),
        placements=_parse_placements(data.get("placements", []), warnings),
        traces=_parse_traces(data.get("traces", []), warnings),
        distance_metric=metric,
        mission=_parse_mission(data.get("mission", {}) or {}),
        mission_rules=_parse_mission_rules(data.get("mission_rules", []), warnings),
        description=str(data.get("description", "")),
        rationales={
            str(k): str(v)
            for k, v in (data.get("rationales", {}) or {}).items()
            if isinstance(v, str)
        },
    )
    return layout, warnings


def layout_to_dict(layout: Layout) -> dict[str, Any]:
    """Serialize a layout back to the same schema ``load_layout`` reads.

    Round-tripping matters: the solver's output must be re-loadable and
    re-validatable through the identical code path, with no special casing.
    """
    enc = layout.enclosure
    board = layout.board
    return {
        "name": layout.name,
        "description": layout.description,
        "distance_metric": layout.distance_metric,
        "rationales": dict(layout.rationales),
        "mission": {
            "skin_contact_clearance_mm": layout.mission.skin_contact_clearance_mm,
            "battery_thermal_clearance_mm": layout.mission.battery_thermal_clearance_mm,
        },
        "mission_rules": [
            {
                "id": r.id,
                "type": r.type,
                "between": list(r.between),
                "distance_mm": r.distance_mm,
                "metric": r.metric,
                "severity": r.severity,
                "title": r.title,
                "rationale": r.rationale,
            }
            for r in layout.mission_rules
        ],
        "enclosure": {
            "interior_mm": {
                "length": enc.interior_length_mm,
                "width": enc.interior_width_mm,
                "height": enc.interior_height_mm,
            },
            "wall_thickness_mm": enc.wall_thickness_mm,
            "wall_keepout_mm": enc.wall_keepout_mm,
            "openings": [
                {
                    "id": o.id,
                    "face": o.face,
                    "center_mm": o.center_mm,
                    "size_mm": {"width": o.width_mm, "height": o.height_mm},
                    "max_reach_mm": o.max_reach_mm,
                }
                for o in enc.openings
            ],
        },
        "board": {
            "id": board.id,
            "size_mm": {
                "length": board.length_mm,
                "width": board.width_mm,
                "thickness": board.thickness_mm,
            },
            "origin_mm": list(board.origin_mm),
            "edge_margin_mm": board.edge_margin_mm,
            "max_component_height_mm": board.max_component_height_mm,
            "min_component_gap_mm": board.min_component_gap_mm,
        },
        "placements": [
            {
                "ref": p.ref,
                "part_id": p.part_id,
                "pos_mm": [round(p.x_mm, 3), round(p.y_mm, 3)],
                "rotation_deg": p.rotation_deg,
                **({"anchored": True} if p.anchored else {}),
            }
            for p in layout.placements
        ],
        "traces": [
            {
                "id": t.id,
                "net": t.net,
                "path_mm": [[round(x, 3), round(y, 3)] for x, y in t.path_mm],
                "width_mm": t.width_mm,
                "high_current": t.high_current,
            }
            for t in layout.traces
        ],
    }
