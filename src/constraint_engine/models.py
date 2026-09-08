"""Core data structures for the MissionPCB constraint engine.

Everything here is a plain dataclass with no third-party dependencies, so the
package stays importable from Blender's bundled Python (which has no pip).

Coordinate conventions
----------------------
Board-local:  XY in mm, origin at the board's minimum corner, +X along board
              length, +Y along board width. Z = 0 is the board's top surface,
              so a component's height is simply its extent above Z = 0.
Enclosure:    XY in mm, origin at the interior's minimum corner. The board sits
              at ``Board.origin_mm``. Overlays are emitted in these coordinates
              so the Blender side needs only a single mm -> m scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Check outcomes.
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

# Severities, ordered most to least serious. Used for report sorting.
BLOCKER = "blocker"
MAJOR = "major"
MINOR = "minor"
INFO = "info"

SEVERITY_ORDER = {BLOCKER: 0, MAJOR: 1, MINOR: 2, INFO: 3}
STATUS_ORDER = {FAIL: 0, WARN: 1, SKIP: 2, PASS: 3}


@dataclass
class Clearances:
    """Minimum separations a part demands from others.

    Kept as two independent lookups rather than collapsing into one, because
    the parts data is authored in two different styles and both are legitimate:

    ``from_property`` is keyed by a behaviour another part exhibits
    (``{"hot": 15.0}`` = "keep me 15 mm from anything hot").

    ``from_category`` is keyed by another part's category
    (``{"wireless": 20.0}`` = "keep me 20 mm from RF modules").
    """

    from_property: dict[str, float] = field(default_factory=dict)
    from_category: dict[str, float] = field(default_factory=dict)


@dataclass
class Keepout:
    """A directional exclusion volume projecting from one face of a part.

    Used for RF antenna clearance: the antenna radiates off one edge and
    nothing may sit in front of it.
    """

    extends_mm: float
    width_mm: float
    direction: str = "+x"  # one of +x, -x, +y, -y


@dataclass
class Part:
    """A normalized part definition, independent of how its JSON was spelled."""

    id: str
    name: str
    category: str
    length_mm: float
    width_mm: float
    height_mm: float
    heat_source: bool = False
    noise_source: bool = False
    sensitivity: str = "none"  # none | low | medium | high
    heat_zone_radius_mm: float | None = None
    keepout: Keepout | None = None
    clearances: Clearances = field(default_factory=Clearances)
    # Mission flags. A chest patch is worn against skin and carries a lithium
    # cell, so two failure modes exist that no purely electrical rule catches.
    skin_contact: bool = False
    thermal_runaway_risk: bool = False
    placement_notes: str = ""
    datasheet_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_sensitive(self) -> bool:
        return self.sensitivity in ("medium", "high")


@dataclass
class Placement:
    """A part instance positioned on a board.

    ``pos_mm`` is the component *center* in board-local coordinates. Rotation is
    restricted to 90-degree steps so every footprint stays axis-aligned; a
    90/270 rotation simply swaps length and width.
    """

    ref: str
    part_id: str
    x_mm: float
    y_mm: float
    rotation_deg: int = 0
    anchored: bool = False

    def footprint(self, part: Part) -> tuple[float, float]:
        """Return (x_extent, y_extent) accounting for rotation."""
        if self.rotation_deg % 180 == 90:
            return part.width_mm, part.length_mm
        return part.length_mm, part.width_mm


@dataclass
class Trace:
    """A routed path, used only for antenna keep-out crossing checks."""

    id: str
    path_mm: list[tuple[float, float]]
    net: str = ""
    width_mm: float = 0.5
    high_current: bool = False


@dataclass
class Opening:
    """An access hole in an enclosure wall."""

    id: str
    face: str  # +x | -x | +y | -y
    center_mm: float  # position along the face's span, in enclosure coords
    width_mm: float
    height_mm: float
    max_reach_mm: float = 12.0  # how far in from the wall a connector may sit


@dataclass
class Enclosure:
    interior_length_mm: float
    interior_width_mm: float
    interior_height_mm: float
    wall_thickness_mm: float = 2.0
    wall_keepout_mm: float = 3.0
    openings: list[Opening] = field(default_factory=list)


@dataclass
class Board:
    id: str
    length_mm: float
    width_mm: float
    thickness_mm: float = 1.6
    origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    edge_margin_mm: float = 2.0
    max_component_height_mm: float = 14.0
    # Courtyard excess in the sense of IPC-7351: parts that merely fail to
    # overlap are still unbuildable if the pick-and-place head cannot reach
    # between them and the solder joints have no room to fillet.
    min_component_gap_mm: float = 0.5


@dataclass
class MissionRule:
    """A constraint specific to this product that no generic PCB rule implies.

    A single-lead ECG patch, for example, needs a minimum physical span between
    its two electrodes: too close together and the measured lead vector is too
    small to resolve the QRS complex, no matter how clean the layout is. That is
    a mission fact, not an electrical one, so it lives in the layout data rather
    than in code.
    """

    id: str
    type: str  # min_separation | max_separation
    between: list[str]
    distance_mm: float
    metric: str = "center"  # center | edge
    severity: str = "major"
    title: str = ""
    rationale: str = ""


@dataclass
class MissionProfile:
    """Thresholds for the mission-level safety rules."""

    # IEC 60601-1 caps prolonged skin contact at 43 C. Rather than model heat
    # flow, keep heat sources a fixed lateral distance from skin-contact parts.
    skin_contact_clearance_mm: float = 15.0
    # Lithium cells degrade and can enter thermal runaway when held near a
    # sustained heat source.
    battery_thermal_clearance_mm: float = 8.0


@dataclass
class Layout:
    name: str
    enclosure: Enclosure
    board: Board
    placements: list[Placement] = field(default_factory=list)
    traces: list[Trace] = field(default_factory=list)
    distance_metric: str = "edge"  # edge | center
    mission: MissionProfile = field(default_factory=MissionProfile)
    mission_rules: list[MissionRule] = field(default_factory=list)
    description: str = ""
    # Why each rule family exists, in this product's terms. Authored upstream
    # by whoever translated the mission into constraints -- that translation is
    # judgment, not arithmetic, so the prose travels with the data instead of
    # being frozen into the checker. Keyed by rule family, e.g. "sep.noise".
    rationales: dict[str, str] = field(default_factory=dict)

    def rationale_for(self, family: str, fallback: str = "") -> str:
        return self.rationales.get(family) or fallback

    def placement(self, ref: str) -> Placement | None:
        for p in self.placements:
            if p.ref == ref:
                return p
        return None


@dataclass
class Overlay:
    """Drawing instructions for the Blender side, in enclosure world mm."""

    type: str  # measure_line | marker | zone_circle | zone_rect | text
    color: tuple[float, float, float]
    collection: str = "03_Constraint_Overlays"
    start: tuple[float, float, float] | None = None
    end: tuple[float, float, float] | None = None
    center: tuple[float, float, float] | None = None
    radius_mm: float | None = None
    size_mm: tuple[float, float] | None = None
    label: str | None = None
    label_at: tuple[float, float, float] | None = None
    marker: str | None = None  # x | check
    marker_at: tuple[float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "color": list(self.color),
                               "collection": self.collection}
        if self.start is not None:
            out["from"] = list(self.start)
        if self.end is not None:
            out["to"] = list(self.end)
        if self.center is not None:
            out["center"] = list(self.center)
        if self.radius_mm is not None:
            out["radius_mm"] = self.radius_mm
        if self.size_mm is not None:
            out["size_mm"] = list(self.size_mm)
        if self.label is not None:
            out["label"] = self.label
        if self.label_at is not None:
            out["label_at"] = list(self.label_at)
        if self.marker is not None:
            out["marker"] = self.marker
        if self.marker_at is not None:
            out["marker_at"] = list(self.marker_at)
        return out


@dataclass
class Check:
    """One constraint evaluation."""

    id: str
    title: str
    status: str
    severity: str
    subjects: list[str] = field(default_factory=list)
    measured_mm: float | None = None
    required_mm: float | None = None
    margin_mm: float | None = None
    metric: str = ""
    message: str = ""
    rationale: str = ""
    suggestion: str = ""
    overlay: Overlay | None = None
    # Reported alongside the evaluated metric so nobody has to guess which
    # convention a number used.
    center_distance_mm: float | None = None
    edge_gap_mm: float | None = None

    @property
    def failed(self) -> bool:
        return self.status == FAIL

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "severity": self.severity,
            "subjects": list(self.subjects),
            "metric": self.metric,
            "message": self.message,
            "rationale": self.rationale,
        }
        for key, val in (
            ("measured_mm", self.measured_mm),
            ("required_mm", self.required_mm),
            ("margin_mm", self.margin_mm),
            ("center_distance_mm", self.center_distance_mm),
            ("edge_gap_mm", self.edge_gap_mm),
        ):
            if val is not None:
                out[key] = round(val, 3)
        if self.suggestion:
            out["suggestion"] = self.suggestion
        if self.overlay is not None:
            out["overlay"] = self.overlay.to_dict()
        return out


@dataclass
class Results:
    """The full output of a validation run."""

    layout_name: str
    checks: list[Check] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    zone_overlays: list[Overlay] = field(default_factory=list)
    component_positions: list[dict[str, Any]] = field(default_factory=list)
    engine_version: str = "0.1.0"
    generated_at: str | None = None

    def by_status(self, status: str) -> list[Check]:
        return [c for c in self.checks if c.status == status]

    @property
    def failures(self) -> list[Check]:
        return self.by_status(FAIL)

    @property
    def unevaluated(self) -> list[Check]:
        """Checks the engine could not run, e.g. a placement with no part.

        Distinct from a failure: nothing was measured at all. These must not be
        allowed to read as a pass, or a board with a typo'd part_id reports
        clean precisely because it was never inspected.
        """
        return [c for c in self.checks if c.id.startswith("data.unresolved_part")]

    @property
    def passed(self) -> bool:
        return not self.failures and not self.unevaluated

    def summary(self) -> dict[str, int]:
        counts = {PASS: 0, FAIL: 0, WARN: 0, SKIP: 0}
        for c in self.checks:
            counts[c.status] = counts.get(c.status, 0) + 1
        return counts

    def sorted_checks(self) -> list[Check]:
        """Most urgent first: failures before passes, blockers before info."""
        return sorted(
            self.checks,
            key=lambda c: (
                STATUS_ORDER.get(c.status, 9),
                SEVERITY_ORDER.get(c.severity, 9),
                c.id,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "generated_at": self.generated_at,
            "layout": self.layout_name,
            "summary": self.summary(),
            "passed": self.passed,
            "warnings": list(self.warnings),
            "component_positions": list(self.component_positions),
            "checks": [c.to_dict() for c in self.sorted_checks()],
            "zone_overlays": [o.to_dict() for o in self.zone_overlays],
        }
