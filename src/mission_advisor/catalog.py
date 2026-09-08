"""Read the part catalog and render it for a language model.

The catalog records are verbose by design -- every measurement carries its
conditions and a page-level citation. That structure is what makes the advice
checkable, so it is preserved rather than flattened: the renderer keeps the
qualifier (typ vs max), the conditions, and the `doc p.N` reference on every
number, so a recommendation can point at the line that motivated it.

This module is the *judgment* layer's input. It does no geometry and asserts no
clearances; those belong to `constraint_engine`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Records deliberately omit facts rather than guessing them, so "absent" is a
# meaningful state the model needs to see.
ABSENT = "not extracted"


@dataclass
class PartRecord:
    """One catalog entry, kept close to its on-disk shape."""

    id: str
    mpn: str
    manufacturer: str
    role: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def review_status(self) -> str:
        return str(self.raw.get("provenance", {}).get("review_status", "unknown"))

    @property
    def datasheet_url(self) -> str:
        return str(self.raw.get("provenance", {}).get("datasheet_url", ""))


def load_catalog(directory: str | Path) -> list[PartRecord]:
    """Load every part record in a catalog directory, sorted by id."""
    path = Path(directory)
    if not path.is_dir():
        raise FileNotFoundError(f"catalog directory not found: {path}")

    records: list[PartRecord] = []
    for file in sorted(path.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        records.append(
            PartRecord(
                id=str(data.get("id", file.stem)),
                mpn=str(data.get("mpn", "")),
                manufacturer=str(data.get("manufacturer", "")),
                role=str(data.get("role", "unknown")),
                raw=data,
            )
        )
    if not records:
        raise FileNotFoundError(f"no part records found in {path}")
    return records


def _cite(source: dict[str, Any] | None) -> str:
    if not isinstance(source, dict):
        return ""
    doc = source.get("doc", "")
    page = source.get("page")
    section = source.get("section")
    bits = [b for b in (doc, f"p.{page}" if page else "", section) if b]
    return f" [{', '.join(bits)}]" if bits else ""


def _measurement(label: str, m: Any) -> str | None:
    """Render one measurement with its qualifier, conditions, and citation."""
    if not isinstance(m, dict) or "value" not in m:
        return None
    value = m.get("value")
    unit = m.get("unit", "")
    qualifier = m.get("qualifier", "")
    line = f"{label}: {value} {unit}".rstrip()
    if qualifier:
        line += f" ({qualifier})"
    conditions = m.get("conditions")
    if conditions:
        line += f" -- {conditions}"
    return line + _cite(m.get("source"))


def _model(label: str, m: Any) -> str | None:
    """Render a formula-valued field, e.g. a dissipation model."""
    if not isinstance(m, dict) or "expression" not in m:
        return None
    lines = [f"{label}: {m['expression']} [{m.get('unit', '')}]{_cite(m.get('source'))}"]
    for name, meaning in (m.get("variables") or {}).items():
        lines.append(f"    {name} = {meaning}")
    return "\n  ".join(lines)


def _band(b: Any) -> str:
    if isinstance(b, (list, tuple)) and len(b) == 2:
        return f"{b[0]:g}-{b[1]:g} Hz"
    return str(b)


def render_part(rec: PartRecord) -> str:
    """Render one record as compact, citation-preserving text."""
    d = rec.raw
    out: list[str] = [
        f"### {rec.id}  ({rec.mpn}, {rec.manufacturer})",
        f"role: {rec.role}   provenance: {rec.review_status}",
    ]

    mech = d.get("mechanical", {}) or {}
    dims = []
    for axis in ("length_mm", "width_mm", "height_mm"):
        m = mech.get(axis)
        dims.append(f"{m['value']}" if isinstance(m, dict) and "value" in m else "?")
    out.append(
        f"package: {mech.get('package', '?')}  "
        f"body: {' x '.join(dims)} mm  "
        f"mount: {mech.get('mounting', '?')}"
        + ("  thermal_pad" if mech.get("thermal_pad") else "")
        + ("  ACCESS REQUIRED after assembly" if mech.get("access_required") else "")
    )

    elec = d.get("electrical", {}) or {}
    elec_lines = [
        line
        for key, label in (
            ("v_in_min", "v_in_min"), ("v_in_max", "v_in_max"),
            ("i_quiescent", "i_q"), ("i_typ", "i_typ"), ("i_max", "i_max"),
        )
        if (line := _measurement(label, elec.get(key)))
    ]
    if elec_lines:
        out.append("electrical:")
        out += [f"  {l}" for l in elec_lines]

    em = d.get("emissions", {}) or {}
    em_lines: list[str] = []
    thermal = em.get("thermal", {}) or {}
    for tj in thermal.get("theta_ja", []) or []:
        if line := _measurement("theta_ja", tj):
            em_lines.append(line)
    if line := _measurement("dissipation", thermal.get("dissipation")):
        em_lines.append(line)
    if line := _model("dissipation_model", thermal.get("dissipation_model")):
        em_lines.append(line)
    for c in em.get("conducted", []) or []:
        parts = [f"conducted: {c.get('mechanism', '?')}"]
        if line := _measurement("f0", c.get("f_fundamental_hz")):
            parts.append(line)
        if c.get("harmonics_modeled"):
            parts.append(f"harmonics={c['harmonics_modeled']}")
        if line := _measurement("ripple", c.get("ripple")):
            parts.append(line)
        em_lines.append("  ".join(parts))
    for r in em.get("radiated", []) or []:
        bits = [f"radiated: {_band(r.get('band_hz'))}"]
        if r.get("intentional"):
            bits.append("intentional")
        if line := _measurement("tx_power", r.get("tx_power_dbm")):
            bits.append(line)
        em_lines.append("  ".join(bits))
    for m in em.get("mechanical_emissions", []) or []:
        em_lines.append(
            f"mechanical: {m.get('mechanism', '?')} {_band(m.get('band_hz'))}"
        )
    if em_lines:
        out.append("EMITS:")
        out += [f"  {l}" for l in em_lines]

    sus = d.get("susceptibility", {}) or {}
    sus_lines: list[str] = []
    st = sus.get("thermal", {}) or {}
    for key, label in (
        ("t_op_min", "t_op_min"), ("t_op_max", "t_op_max"),
        ("t_junction_max", "t_junction_max"),
    ):
        if line := _measurement(label, st.get(key)):
            sus_lines.append(line)
    if st.get("accuracy_note"):
        sus_lines.append(f"thermal accuracy: {st['accuracy_note']}")
    for c in sus.get("conducted", []) or []:
        line = f"conducted-sensitive: {_band(c.get('band_hz'))}"
        if c.get("reason"):
            line += f" -- {c['reason']}"
        sus_lines.append(line)
    for r in sus.get("radiated", []) or []:
        line = f"radiated-sensitive: {_band(r.get('band_hz'))}"
        if r.get("reason"):
            line += f" -- {r['reason']}"
        sus_lines.append(line)
    for m in sus.get("mechanical", []) or []:
        line = f"mechanical-sensitive: {_band(m.get('band_hz'))}"
        if m.get("reason"):
            line += f" -- {m['reason']}"
        sus_lines.append(line)
    if sus_lines:
        out.append("SUSCEPTIBLE TO:")
        out += [f"  {l}" for l in sus_lines]

    for note in d.get("design_notes", []) or []:
        if isinstance(note, dict) and note.get("note"):
            out.append(f"note: {note['note']}{_cite(note.get('source'))}")

    if rec.raw.get("provenance", {}).get("notes"):
        out.append(f"provenance note: {rec.raw['provenance']['notes']}")

    return "\n".join(out)


def render_catalog(records: list[PartRecord]) -> str:
    """Render the whole catalog, grouped by role so alternatives sit together."""
    by_role: dict[str, list[PartRecord]] = {}
    for rec in records:
        by_role.setdefault(rec.role, []).append(rec)

    out = [
        f"PART CATALOG -- {len(records)} parts, {len(by_role)} roles.",
        "",
        "Every number carries its qualifier, the conditions it was measured "
        "under, and a page-level citation. A number without conditions is not "
        "usable as a design input. Fields are absent rather than guessed: "
        f"'{ABSENT}' means nobody has pulled it from the drawing yet, which is "
        "itself a finding worth reporting.",
        "",
        "Roles with more than one part are genuine alternatives -- a "
        "substitution between them is grounded, not speculative:",
    ]
    for role, recs in sorted(by_role.items()):
        if len(recs) > 1:
            out.append(f"  {role}: {', '.join(r.id for r in recs)}")
    out.append("")

    for role in sorted(by_role):
        out.append(f"## role: {role}")
        out.append("")
        for rec in by_role[role]:
            out.append(render_part(rec))
            out.append("")
    return "\n".join(out)
