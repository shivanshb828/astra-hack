"""Render validation results as Markdown.

The report is both a working artifact and the thing a reviewer reads to decide
whether the board is ready to build, so every failure carries its measured
number, the requirement it missed, why the requirement exists, and what to do
about it. It also states plainly which parts of the model are approximations,
because a validation report that overstates its own rigour is worse than none.
"""

from __future__ import annotations

from .models import FAIL, PASS, SKIP, WARN, Check, Results

_STATUS_MARK = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP"}

# Grouped for readability: a reader scanning for safety problems should not
# have to filter mechanical fit rows out of the way.
_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Safety", "safety.", ("safety.",)),
    ("Mission", "mission.", ("mission.",)),
    ("Signal integrity", "sep.", ("sep.", "zone.")),
    ("Mechanical fit", "fit.", ("fit.",)),
    ("Access", "access.", ("access.",)),
    ("Data quality", "data.", ("data.",)),
)


def _num(value: float | None, suffix: str = " mm") -> str:
    if value is None:
        return "-"
    return f"{value:.2f}{suffix}"


def _group_of(check: Check) -> str:
    for label, _, prefixes in _GROUPS:
        if any(check.id.startswith(p) for p in prefixes):
            return label
    return "Other"


def _table(checks: list[Check]) -> list[str]:
    lines = [
        "| Status | Check | Measured | Required | Margin |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in checks:
        margin = _num(c.margin_mm) if c.margin_mm is not None else "-"
        lines.append(
            f"| {_STATUS_MARK.get(c.status, c.status)} | {c.title} | "
            f"{_num(c.measured_mm)} | {_num(c.required_mm)} | {margin} |"
        )
    return lines


def render_report(results: Results, parts_source: str = "", layout_source: str = "") -> str:
    counts = results.summary()
    total = sum(counts.values())
    lines: list[str] = []

    lines.append(f"# Validation Report: {results.layout_name}")
    lines.append("")
    lines.append(f"- Engine version: `{results.engine_version}`")
    if results.generated_at:
        lines.append(f"- Generated: {results.generated_at}")
    if parts_source:
        lines.append(f"- Parts library: `{parts_source}`")
    if layout_source:
        lines.append(f"- Layout: `{layout_source}`")
    lines.append("")

    verdict = "PASS" if results.passed else "FAIL"
    lines.append(f"## Verdict: {verdict}")
    lines.append("")
    lines.append(
        f"{counts[PASS]} passed, {counts[FAIL]} failed, "
        f"{counts[WARN]} warnings, {counts[SKIP]} skipped "
        f"({total} checks total)."
    )
    lines.append("")

    if results.warnings:
        lines.append("## Data warnings")
        lines.append("")
        lines.append(
            "Raised while reading the input files. These do not fail the board, "
            "but they mean the engine had to assume something."
        )
        lines.append("")
        for w in results.warnings:
            lines.append(f"- {w}")
        lines.append("")

    failures = results.failures
    if failures:
        lines.append("## Failures")
        lines.append("")
        for c in sorted(failures, key=lambda x: (x.severity, x.id)):
            lines.append(f"### {c.title}")
            lines.append("")
            lines.append(f"- **Severity:** {c.severity}")
            if c.subjects:
                lines.append(f"- **Parts:** {', '.join(c.subjects)}")
            if c.measured_mm is not None and c.required_mm is not None:
                lines.append(
                    f"- **Measured:** {_num(c.measured_mm)} "
                    f"against {_num(c.required_mm)} required "
                    f"({c.metric.replace('_', ' ')})"
                )
            if c.edge_gap_mm is not None and c.center_distance_mm is not None:
                lines.append(
                    f"- **Both metrics:** edge gap {_num(c.edge_gap_mm)}, "
                    f"center distance {_num(c.center_distance_mm)}"
                )
            lines.append("")
            lines.append(c.message)
            if c.rationale:
                lines.append("")
                lines.append(f"*Why this matters:* {c.rationale}")
            if c.suggestion:
                lines.append("")
                lines.append(f"*Suggested fix:* {c.suggestion}")
            lines.append("")

    lines.append("## All checks")
    lines.append("")
    seen: set[str] = set()
    for label, _, _prefixes in _GROUPS:
        group = [c for c in results.sorted_checks() if _group_of(c) == label]
        if not group:
            continue
        seen.update(c.id for c in group)
        lines.append(f"### {label}")
        lines.append("")
        lines.extend(_table(group))
        lines.append("")

    other = [c for c in results.sorted_checks() if c.id not in seen]
    if other:
        lines.append("### Other")
        lines.append("")
        lines.extend(_table(other))
        lines.append("")

    if results.component_positions:
        lines.append("## Component positions")
        lines.append("")
        lines.append(
            "| Ref | Part | Board XY (mm) | Size L x W x H (mm) | Rot | Flags |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for pos in results.component_positions:
            flags = []
            if pos.get("heat_source"):
                flags.append("hot")
            if pos.get("noise_source"):
                flags.append("noisy")
            if pos.get("sensitivity") in ("medium", "high"):
                flags.append(f"sensitive:{pos['sensitivity']}")
            if pos.get("skin_contact"):
                flags.append("skin-contact")
            x, y = pos["board_xy_mm"]
            sl, sw, sh = pos["size_mm"]
            lines.append(
                f"| {pos['ref']} | {pos['part_name']} | {x:g}, {y:g} | "
                f"{sl:g} x {sw:g} x {sh:g} | {pos['rotation_deg']}° | "
                f"{', '.join(flags) or '-'} |"
            )
        lines.append("")

    lines.extend(_limits_section())
    return "\n".join(lines).rstrip() + "\n"


def _limits_section() -> list[str]:
    return [
        "## What this report does and does not prove",
        "",
        "**Computed exactly:** component footprints and bounding boxes, "
        "edge-to-edge and center-to-center distances, board and enclosure "
        "containment, height against the available headroom, footprint "
        "collisions, keep-out occupancy, and connector registration against "
        "the enclosure opening. These are geometry, and the numbers are real.",
        "",
        "**Modelled as approximations:** thermal zones are a fixed radius "
        "standing in for the elevated-temperature region around a dissipating "
        "part, not a solved thermal field. Noise separation is a distance "
        "threshold, not a computed coupling coefficient. RF keep-out is a "
        "rectangular volume, not a radiation pattern. Skin-contact temperature "
        "is inferred from distance to heat sources rather than from a "
        "surface-temperature solve.",
        "",
        "**Not evaluated at all:** SPICE or transient electrical behaviour, "
        "thermal FEA, electromagnetic simulation, battery runtime, "
        "manufacturability and DFM, routing correctness, layer stackup, "
        "grounding and shielding strategy, and biocompatibility of any "
        "material in the patient-contact path.",
        "",
        "### Required before manufacturing",
        "",
        "1. Measure the assembled patch's skin-side surface temperature under "
        "worst-case load and confirm it against the IEC 60601-1 43 C limit for "
        "prolonged contact. The distance rule used here is a proxy, not "
        "evidence.",
        "2. Capture a real ECG trace with the radio transmitting at full duty "
        "cycle and confirm the noise floor still resolves the QRS complex.",
        "3. Run a radiated-emissions and link-margin check with the enclosure "
        "closed and the cell installed; both detune the antenna.",
        "4. Cycle the cell at temperature and confirm the thermal margin to the "
        "regulator holds over the intended wear duration.",
        "5. Verify every package dimension against the manufacturer drawing. "
        "The dimensions in the parts library are representative, not sourced "
        "from a specific part number.",
    ]
