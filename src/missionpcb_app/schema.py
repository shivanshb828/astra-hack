"""Versioned contracts for the MissionPCB application layer.

The constraint engine already owns the authoritative engineering description of
a board (``constraint_engine.loader``'s layout schema). This module does not
re-describe that geometry in a competing format; it wraps it with the
orchestration metadata the application needs -- schema version, design id,
revision, provenance -- and validates it at the API boundary.

``DesignState.to_engine_layout`` emits exactly the dict ``load_layout`` reads,
so the adapter round-trips through the engine's own parsing code rather than a
parallel implementation of it.

Units and frames
----------------
Lengths are millimetres everywhere in this module, and the engineering frames
are the engine's own: board-local XY with the origin at the board's minimum
corner, and enclosure XY with the origin at the interior's minimum corner. Z is
up. Conversion to the renderer's metres-and-Y-up happens in the web client, at
the rendering boundary, never here.

Nominal part dimensions deliberately do not live on a component. A component
carries only a transform (position, rotation); its size comes from the parts
catalogue. Dragging a box in the viewport therefore cannot silently rewrite a
manufacturer specification.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"

# Status vocabulary. "unknown" and "not_applicable" are first-class: the brief
# requires that a check the engine could not evaluate never reads as a pass.
Status = Literal["pass", "fail", "warning", "unknown", "not_applicable"]
Severity = Literal["blocker", "major", "minor", "info"]

# How a result was arrived at, so a heuristic is never mistaken for a solve.
Method = Literal[
    "geometric_check",
    "analytical_estimate",
    "external_solver",
    "heuristic",
    "fixture",
]

# Engine status string -> application status. SKIP maps to "unknown" rather
# than "pass"; that mapping is the whole point of keeping the vocabularies
# separate.
ENGINE_STATUS_MAP: dict[str, Status] = {
    "PASS": "pass",
    "FAIL": "fail",
    "WARN": "warning",
    "SKIP": "unknown",
}


class Units(BaseModel):
    """Explicit declaration of what the numbers in a payload mean."""

    length: Literal["mm"] = "mm"
    angle: Literal["deg"] = "deg"
    coordinate_frame: Literal["board_local", "enclosure"] = "board_local"
    axis_convention: Literal["z_up"] = "z_up"


class SourceRef(BaseModel):
    """Where a value came from, so provenance survives into the UI."""

    kind: Literal["datasheet", "catalog", "mission_intake", "assumption", "user"]
    detail: str = ""
    url: str | None = None


class ComponentState(BaseModel):
    """A placed component: a stable id plus a transform, and nothing else.

    ``part_id`` points at the parts catalogue, which owns dimensions and
    electrical/thermal properties. ``kicad_ref`` is the stable mapping to a
    native footprint reference when a KiCad project is connected.
    """

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, description="Stable component id, e.g. 'AFE'")
    part_id: str = Field(min_length=1)
    pos_mm: tuple[float, float] = Field(description="Component centre, board-local")
    rotation_deg: int = 0
    anchored: bool = False
    kicad_ref: str | None = None

    def normalised_rotation(self) -> int:
        """Engine footprints stay axis-aligned, so snap to 90-degree steps."""
        return int(round(self.rotation_deg / 90.0)) * 90 % 360


class OpeningState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    face: Literal["+x", "-x", "+y", "-y"]
    center_mm: float
    width_mm: float
    height_mm: float
    max_reach_mm: float = 12.0


class EnclosureState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interior_length_mm: float
    interior_width_mm: float
    interior_height_mm: float
    wall_thickness_mm: float = 2.0
    wall_keepout_mm: float = 3.0
    openings: list[OpeningState] = Field(default_factory=list)
    asset_ref: str | None = None


class BoardState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "PCB"
    length_mm: float
    width_mm: float
    thickness_mm: float = 1.6
    origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    edge_margin_mm: float = 2.0
    max_component_height_mm: float = 14.0
    min_component_gap_mm: float = 0.5


class TraceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    path_mm: list[tuple[float, float]]
    net: str = ""
    width_mm: float = 0.5
    high_current: bool = False


class MissionProfileState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skin_contact_clearance_mm: float = 15.0
    battery_thermal_clearance_mm: float = 8.0


class MissionRuleState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["min_separation", "max_separation"]
    between: list[str]
    distance_mm: float
    metric: Literal["center", "edge"] = "center"
    severity: Severity = "major"
    title: str = ""
    rationale: str = ""


class DesignState(BaseModel):
    """The application's canonical, versioned orchestration state.

    This is not a replacement for complete EDA data: when a KiCad project is
    connected, that project remains authoritative for connectivity, footprints
    and routing. This document orchestrates placement and mission constraints.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    design_id: str
    revision: int = Field(ge=0, description="Increments on every applied edit")
    device_type: str = "ecg_chest_patch"
    name: str = ""
    description: str = ""
    units: Units = Field(default_factory=Units)

    board: BoardState
    enclosure: EnclosureState
    components: list[ComponentState] = Field(default_factory=list)
    traces: list[TraceState] = Field(default_factory=list)

    distance_metric: Literal["edge", "center"] = "edge"
    mission: MissionProfileState = Field(default_factory=MissionProfileState)
    mission_rules: list[MissionRuleState] = Field(default_factory=list)
    rationales: dict[str, str] = Field(default_factory=dict)

    parts_source: str = ""
    provenance: list[SourceRef] = Field(default_factory=list)
    missing_data: list[str] = Field(
        default_factory=list,
        description="Named gaps, so absent inputs stay visible rather than defaulting",
    )

    def component(self, ref: str) -> ComponentState | None:
        for c in self.components:
            if c.ref == ref:
                return c
        return None

    def to_engine_layout(self) -> dict[str, Any]:
        """Emit the exact dict shape ``constraint_engine.load_layout`` reads."""
        return {
            "name": self.name or self.design_id,
            "description": self.description,
            "distance_metric": self.distance_metric,
            "rationales": dict(self.rationales),
            "mission": {
                "skin_contact_clearance_mm": self.mission.skin_contact_clearance_mm,
                "battery_thermal_clearance_mm": self.mission.battery_thermal_clearance_mm,
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
                for r in self.mission_rules
            ],
            "enclosure": {
                "interior_mm": {
                    "length": self.enclosure.interior_length_mm,
                    "width": self.enclosure.interior_width_mm,
                    "height": self.enclosure.interior_height_mm,
                },
                "wall_thickness_mm": self.enclosure.wall_thickness_mm,
                "wall_keepout_mm": self.enclosure.wall_keepout_mm,
                "openings": [
                    {
                        "id": o.id,
                        "face": o.face,
                        "center_mm": o.center_mm,
                        "size_mm": {"width": o.width_mm, "height": o.height_mm},
                        "max_reach_mm": o.max_reach_mm,
                    }
                    for o in self.enclosure.openings
                ],
            },
            "board": {
                "id": self.board.id,
                "size_mm": {
                    "length": self.board.length_mm,
                    "width": self.board.width_mm,
                    "thickness": self.board.thickness_mm,
                },
                "origin_mm": list(self.board.origin_mm),
                "edge_margin_mm": self.board.edge_margin_mm,
                "max_component_height_mm": self.board.max_component_height_mm,
                "min_component_gap_mm": self.board.min_component_gap_mm,
            },
            "placements": [
                {
                    "ref": c.ref,
                    "part_id": c.part_id,
                    "pos_mm": [c.pos_mm[0], c.pos_mm[1]],
                    "rotation_deg": c.normalised_rotation(),
                    "anchored": c.anchored,
                }
                for c in self.components
            ],
            "traces": [
                {
                    "id": t.id,
                    "net": t.net,
                    "path_mm": [[p[0], p[1]] for p in t.path_mm],
                    "width_mm": t.width_mm,
                    "high_current": t.high_current,
                }
                for t in self.traces
            ],
        }

    @classmethod
    def from_engine_layout(
        cls,
        raw: dict[str, Any],
        *,
        design_id: str,
        revision: int = 0,
        parts_source: str = "",
    ) -> DesignState:
        """Build application state from a layout file's raw JSON."""
        enc = raw.get("enclosure", {}) or {}
        interior = enc.get("interior_mm", {}) or {}
        board = raw.get("board", {}) or {}
        size = board.get("size_mm", {}) or {}
        origin = board.get("origin_mm", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0]

        openings = [
            OpeningState(
                id=o.get("id", f"opening_{i}"),
                face=o.get("face", "+x"),
                center_mm=float(o.get("center_mm", 0.0)),
                width_mm=float((o.get("size_mm") or {}).get("width", 0.0)),
                height_mm=float((o.get("size_mm") or {}).get("height", 0.0)),
                max_reach_mm=float(o.get("max_reach_mm", 12.0)),
            )
            for i, o in enumerate(enc.get("openings", []) or [])
        ]

        components = [
            ComponentState(
                ref=p["ref"],
                part_id=p["part_id"],
                pos_mm=(float(p["pos_mm"][0]), float(p["pos_mm"][1])),
                rotation_deg=int(p.get("rotation_deg", 0) or 0),
                anchored=bool(p.get("anchored", False)),
            )
            for p in raw.get("placements", []) or []
        ]

        mission = raw.get("mission", {}) or {}
        return cls(
            design_id=design_id,
            revision=revision,
            name=raw.get("name", design_id),
            description=raw.get("description", ""),
            distance_metric=raw.get("distance_metric", "edge"),
            rationales=dict(raw.get("rationales", {}) or {}),
            mission=MissionProfileState(
                skin_contact_clearance_mm=float(
                    mission.get("skin_contact_clearance_mm", 15.0)
                ),
                battery_thermal_clearance_mm=float(
                    mission.get("battery_thermal_clearance_mm", 8.0)
                ),
            ),
            mission_rules=[
                MissionRuleState(
                    id=r["id"],
                    type=r.get("type", "min_separation"),
                    between=list(r.get("between", [])),
                    distance_mm=float(r.get("distance_mm", 0.0)),
                    metric=r.get("metric", "center"),
                    severity=r.get("severity", "major"),
                    title=r.get("title", ""),
                    rationale=r.get("rationale", ""),
                )
                for r in raw.get("mission_rules", []) or []
            ],
            enclosure=EnclosureState(
                interior_length_mm=float(interior.get("length", 0.0)),
                interior_width_mm=float(interior.get("width", 0.0)),
                interior_height_mm=float(interior.get("height", 0.0)),
                wall_thickness_mm=float(enc.get("wall_thickness_mm", 2.0)),
                wall_keepout_mm=float(enc.get("wall_keepout_mm", 3.0)),
                openings=openings,
            ),
            components=components,
            board=BoardState(
                id=board.get("id", "PCB"),
                length_mm=float(size.get("length", 0.0)),
                width_mm=float(size.get("width", 0.0)),
                thickness_mm=float(size.get("thickness", 1.6)),
                origin_mm=(float(origin[0]), float(origin[1]), float(origin[2])),
                edge_margin_mm=float(board.get("edge_margin_mm", 2.0)),
                max_component_height_mm=float(
                    board.get("max_component_height_mm", 14.0)
                ),
                min_component_gap_mm=float(board.get("min_component_gap_mm", 0.5)),
            ),
            traces=[
                TraceState(
                    id=t.get("id", f"trace_{i}"),
                    net=t.get("net", ""),
                    path_mm=[(float(p[0]), float(p[1])) for p in t.get("path_mm", [])],
                    width_mm=float(t.get("width_mm", 0.5)),
                    high_current=bool(t.get("high_current", False)),
                )
                for i, t in enumerate(raw.get("traces", []) or [])
            ],
            parts_source=parts_source,
        )


# --------------------------------------------------------------------------
# Visualization instructions
# --------------------------------------------------------------------------
# A bounded, typed set. These are data, never code: the client switches on
# ``type`` and refuses anything it does not recognise, so nothing arriving from
# the engine or a model can execute in the browser.

VizType = Literal[
    "highlight_components",
    "distance_measurement",
    "keepout_volume",
    "patient_contact_region",
    "scalar_field",
    "annotation",
    "focus_camera",
]


class VizInstruction(BaseModel):
    """One drawing instruction, in a declared frame with declared units."""

    model_config = ConfigDict(extra="forbid")

    type: VizType
    # Every instruction declares its frame and units rather than assuming.
    frame: Literal["enclosure", "board_local"] = "enclosure"
    units: Literal["mm"] = "mm"
    component_refs: list[str] = Field(default_factory=list)
    zone_id: str | None = None
    from_mm: tuple[float, float, float] | None = None
    to_mm: tuple[float, float, float] | None = None
    center_mm: tuple[float, float, float] | None = None
    radius_mm: float | None = None
    size_mm: tuple[float, float] | None = None
    label: str | None = None
    label_at_mm: tuple[float, float, float] | None = None
    color_rgb: tuple[float, float, float] | None = None
    marker: Literal["x", "check"] | None = None
    # Distinguishes a declared clearance radius from a solved field, so a drawn
    # volume is never read as a computed temperature.
    zone_kind: str | None = None


class AnalysisCheck(BaseModel):
    """One constraint verdict, in the application's vocabulary."""

    model_config = ConfigDict(extra="forbid")

    check_id: str
    design_revision: int
    category: str
    title: str
    status: Status
    severity: Severity
    component_refs: list[str] = Field(default_factory=list)
    zone_refs: list[str] = Field(default_factory=list)
    measured_value: float | None = None
    measured_unit: str | None = None
    threshold_value: float | None = None
    threshold_comparison: str | None = None
    metric: str = ""
    explanation: str = ""
    method: Method = "geometric_check"
    input_assumptions: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    rule_source: str = ""
    suggested_actions: list[str] = Field(default_factory=list)
    viz: list[VizInstruction] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """A complete analysis run, always tagged with the revision it analysed."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    design_id: str
    design_revision: int
    engine_version: str
    source: Literal["missionpcb_engine", "kicad", "fixture"] = "missionpcb_engine"
    created_at: str
    summary: dict[str, int] = Field(default_factory=dict)
    checks: list[AnalysisCheck] = Field(default_factory=list)
    zone_viz: list[VizInstruction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approximations: list[str] = Field(default_factory=list)


class HistoryEvent(BaseModel):
    """One applied change. Rejected proposals never appear here."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    design_id: str
    timestamp: str
    actor: Literal["user", "assistant", "import", "system"]
    source: Literal["drag", "inspector", "chat", "restore", "import"]
    base_revision: int
    result_revision: int
    summary: str = ""
    user_request: str = ""
    explanation: str = ""
    changes: list[dict[str, Any]] = Field(default_factory=list)
    component_refs: list[str] = Field(default_factory=list)
    analysis_job_id: str | None = None
