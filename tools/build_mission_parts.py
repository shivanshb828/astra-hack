#!/usr/bin/env python3
"""Build the engine's parts library from the catalog plus a mission's constraints.

Two inputs, cleanly split:

    parts/catalog/*.json          physical facts, extracted from datasheets with
                                  page-level provenance. No clearances, by design.
    missions/*-constraints.json   which parts are in this build, and how far apart
                                  they have to be. Judgment, argued for in prose.

Output is the parts library the constraint engine loads. It is *generated* --
never hand-edit it. Before this existed the demo carried hand-typed dimensions
that drifted from the catalog until an invented 3.2 mm cell was standing in for
a real 5.6 mm one, and nothing caught it because the two files had no
relationship. Now a datasheet correction propagates on the next build.

Stdlib only, so it runs anywhere the engine does.

    python3 tools/build_mission_parts.py \
        --constraints missions/ecg-patch-constraints.json \
        --out parts/ecg-patch-parts.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def measurement(block: Any) -> float | None:
    """Pull the number out of a catalog measurement object."""
    if isinstance(block, dict) and "value" in block:
        try:
            return float(block["value"])
        except (TypeError, ValueError):
            return None
    return None


def cite(block: Any) -> str:
    """Render a measurement's provenance so the generated file stays checkable."""
    if not isinstance(block, dict):
        return ""
    src = block.get("source") or {}
    doc, page = src.get("doc", ""), src.get("page")
    qual = block.get("qualifier", "")
    bits = [b for b in (doc, f"p.{page}" if page else "", qual) if b]
    return ", ".join(bits)


def build_part(entry: dict[str, Any], record: dict[str, Any],
               warnings: list[str]) -> dict[str, Any]:
    """Merge one catalog record with one mission BOM entry."""
    ref = entry["ref"]
    mech = record.get("mechanical", {}) or {}

    dims: dict[str, float] = {}
    cites: dict[str, str] = {}
    for axis, key in (("length", "length_mm"), ("width", "width_mm"),
                      ("height", "height_mm")):
        block = mech.get(key)
        value = measurement(block)
        if value is None:
            warnings.append(
                f"{ref} ({record.get('id')}): {key} is not in the catalog record. "
                f"The engine cannot build a footprint without it."
            )
        else:
            dims[axis] = value
            cites[axis] = cite(block)

    part: dict[str, Any] = {
        "id": ref,
        "name": f"{record.get('mpn', ref)} ({record.get('manufacturer', '?')})",
        "category": entry.get("engine_category", record.get("role", "unknown")),
        "dimensions_mm": dims,
        "_dimension_source": cites,
        "_catalog_id": record.get("id"),
    }

    # Behaviour flags are the mission's call, with one override: a record that
    # states how much power the part actually dissipates is asserting a fact the
    # mission cannot wish away.
    #
    # The test is dissipation, not theta_ja. Every IC has a junction-to-ambient
    # resistance -- it describes how well a part sheds heat, not how much it
    # makes. Treating its presence as "this part is hot" marks an ESD diode and
    # a 24-bit front end as heat sources, which is wrong and would push real
    # parts apart for no reason.
    heat = bool(entry.get("heat_source", False))
    thermal = (record.get("emissions", {}) or {}).get("thermal") or {}
    dissipates = bool(thermal.get("dissipation") or thermal.get("dissipation_model"))
    if dissipates and not heat:
        heat = True
        warnings.append(
            f"{ref}: the catalog record states a dissipation figure, so it is "
            f"treated as a heat source even though the mission entry did not "
            f"mark it as one."
        )
    if heat:
        part["heat_source"] = True
    if entry.get("noise_source"):
        part["noise_source"] = True
    if entry.get("sensitivity"):
        part["sensitive"] = entry["sensitivity"]
    if entry.get("skin_contact"):
        part["skin_contact"] = True
    if entry.get("thermal_runaway_risk"):
        part["thermal_runaway_risk"] = True
    if mech.get("access_required"):
        part["_access_required"] = True

    if entry.get("clearances_mm"):
        part["required_clearance_mm"] = entry["clearances_mm"]
    if entry.get("heat_zone_radius_mm"):
        part["heat_zone_radius_mm"] = entry["heat_zone_radius_mm"]
    if entry.get("keepout_zone_mm"):
        part["keepout_zone_mm"] = entry["keepout_zone_mm"]
    if entry.get("why"):
        part["placement_notes"] = entry["why"]

    prov = record.get("provenance", {}) or {}
    if prov.get("datasheet_url"):
        part["source_url"] = prov["datasheet_url"]
    if prov.get("review_status") and prov["review_status"] != "extracted":
        warnings.append(
            f"{ref}: catalog provenance is '{prov['review_status']}', not "
            f"'extracted' -- the numbers behind this part are not fully verified."
        )

    return part


def build(constraints_path: Path, catalog_dir: Path) -> tuple[dict[str, Any], list[str]]:
    spec = json.loads(constraints_path.read_text(encoding="utf-8"))
    warnings: list[str] = []

    records: dict[str, dict[str, Any]] = {}
    for file in sorted(catalog_dir.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        records[str(data.get("id", file.stem))] = data
    if not records:
        raise SystemExit(f"no catalog records found in {catalog_dir}")

    parts = []
    for entry in spec.get("bom", []):
        cid = entry.get("catalog_id")
        record = records.get(cid)
        if record is None:
            raise SystemExit(
                f"{entry.get('ref')}: catalog_id '{cid}' is not in {catalog_dir}. "
                f"Add the record, or fix the id."
            )
        parts.append(build_part(entry, record, warnings))

    library = {
        "library": spec.get("mission", "mission BOM"),
        "_generated_by": "tools/build_mission_parts.py -- do not hand-edit",
        "_inputs": [str(constraints_path), f"{catalog_dir}/*.json"],
        "notes": [
            "Generated. Dimensions come from the catalog records and carry their "
            "citation in _dimension_source; clearances come from the mission's "
            "constraints file, where each one is argued for.",
            "To change a dimension, fix the catalog record. To change a "
            "clearance, edit the constraints file. Then rebuild.",
        ],
        "parts": parts,
    }
    return library, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--constraints", required=True, type=Path)
    ap.add_argument("--catalog", default=Path("parts/catalog"), type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    library, warnings = build(args.constraints, args.catalog)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(library, indent=2) + "\n", encoding="utf-8")

    tallest = max(
        ((p["dimensions_mm"].get("height", 0), p["id"]) for p in library["parts"]),
        default=(0, "-"),
    )
    print(f"{len(library['parts'])} parts -> {args.out}")
    print(f"  tallest: {tallest[1]} at {tallest[0]} mm (this sets the enclosure)")
    for w in warnings:
        print(f"  warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
