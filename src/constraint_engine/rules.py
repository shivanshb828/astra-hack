"""Constraint checks.

This module does arithmetic, not judgment. It never decides what a threshold
should be and it never invents a justification: every number it compares
against arrives from the parts library or the layout's mission block, and every
product-specific explanation arrives from ``layout.rationales``. Deciding that
a biosignal front end needs 15 mm from a switching regulator is a modelling
call made upstream; measuring 6.0 mm and subtracting is this module's job.

That split is deliberate. A distance computed by a language model is right most
of the time and wrong unpredictably, which is exactly the failure you cannot
debug afterwards. A distance computed here is reproducible forever, and it
costs the upstream model nothing -- it still sets every threshold that matters.

The fallback rationales below are intentionally generic physics, true of any
board. Anything specific to a product belongs in that product's data.

Rules fall into three groups:

* physical    -- does it fit, does it collide, is it too tall, can it be built
* electrical  -- separation between noisy, hot, and sensitive parts
* mission     -- facts true of this product that no generic PCB rule implies
"""

from __future__ import annotations

from .geometry import (
    Rect,
    center_distance,
    circle_rect_overlap,
    containment_overflow,
    edge_gap,
    keepout_rect,
    overlap_area,
    polyline_rect_intersect,
    rects_overlap,
    rotate_direction,
)
from .models import (
    BLOCKER,
    FAIL,
    INFO,
    MAJOR,
    PASS,
    SKIP,
    WARN,
    Board,
    Check,
    Layout,
    Part,
    Placement,
)
from .overlays import AMBER, ORANGE, PURPLE, RED, OverlayBuilder


# Neutral, product-agnostic statements of why each rule family exists. A
# layout supplies better, mission-specific text via its "rationales" block;
# these only stand in when it does not.
FALLBACK_RATIONALE = {
    "fit.board": "Components must stay inside the board outline with margin "
                 "for fabrication tolerance.",
    "fit.enclosure_xy": "Components in the wall keep-out prevent the shell "
                        "from closing and break any perimeter seal.",
    "fit.height": "Component height must fit the space between the board "
                  "surface and the enclosure roof.",
    "fit.overlap": "Two parts cannot occupy the same footprint.",
    "fit.courtyard": "IPC-7351 courtyard excess. Parts closer than the "
                     "courtyard gap cannot be reliably placed or reworked, "
                     "and adjacent solder joints can bridge.",
    "sep.thermal": "Component self-heating shifts the offsets, bias currents "
                   "and reference voltages of nearby sensitive parts.",
    "sep.noise": "Switching edges couple capacitively and inductively into "
                 "nearby high-impedance nodes.",
    "sep.rf": "Broadband switching noise raises the receiver noise floor and "
              "desensitises the radio, costing link margin.",
    "zone.heat_overlap": "Simplified thermal model: a fixed radius standing in "
                         "for the elevated-temperature region around a "
                         "dissipating part. Not a solved thermal field.",
    "zone.rf_keepout": "An antenna needs a clear volume with no copper or bulk "
                       "material in front of it; anything inside detunes it.",
    "safety.skin_contact_temp": "Heat sources near a surface held against skin "
                                "raise that surface's temperature.",
    "safety.battery_thermal": "Sustained heat accelerates cell ageing and "
                              "lowers the thermal runaway threshold.",
    "access.connector": "A connector that does not register with its enclosure "
                        "opening cannot be reached once the product is "
                        "assembled.",
}


class Scene:
    """A resolved layout: placements paired with their parts and footprints.

    Built once and shared by every rule so nothing recomputes geometry, and so
    the solver can rebuild cheaply on each candidate move.
    """

    def __init__(self, layout: Layout, parts: dict[str, Part]):
        self.layout = layout
        self.parts = parts
        self.board = layout.board
        self.enclosure = layout.enclosure
        self.overlays = OverlayBuilder(layout.board)

        self.refs: list[str] = []
        self.part_of: dict[str, Part] = {}
        self.rect_of: dict[str, Rect] = {}
        self.placement_of: dict[str, Placement] = {}
        self.missing: list[Placement] = []

        for pl in layout.placements:
            part = parts.get(pl.part_id)
            if part is None:
                self.missing.append(pl)
                continue
            x_extent, y_extent = pl.footprint(part)
            self.refs.append(pl.ref)
            self.part_of[pl.ref] = part
            self.placement_of[pl.ref] = pl
            self.rect_of[pl.ref] = Rect.from_center(pl.x_mm, pl.y_mm, x_extent, y_extent)

    # -- helpers ---------------------------------------------------------

    @property
    def board_rect(self) -> Rect:
        return Rect.from_origin(0.0, 0.0, self.board.length_mm, self.board.width_mm)

    @property
    def usable_rect(self) -> Rect:
        """Board area minus the edge margin."""
        return self.board_rect.inset(self.board.edge_margin_mm)

    @property
    def enclosure_rect_boardlocal(self) -> Rect:
        """Enclosure interior minus wall keep-out, expressed in board coords."""
        ox, oy, _ = self.board.origin_mm
        allowed = Rect.from_origin(
            0.0, 0.0, self.enclosure.interior_length_mm, self.enclosure.interior_width_mm
        ).inset(self.enclosure.wall_keepout_mm)
        return allowed.translate(-ox, -oy)

    def measure(self, a: str, b: str) -> tuple[float, float, float]:
        """Return (evaluated, edge_gap, center_distance) for a pair of refs."""
        ra, rb = self.rect_of[a], self.rect_of[b]
        gap = edge_gap(ra, rb)
        centers = center_distance(ra, rb)
        evaluated = centers if self.layout.distance_metric == "center" else gap
        return evaluated, gap, centers

    def required_between(self, a: str, b: str) -> float:
        """Largest clearance either part demands of the other.

        Both directions are considered because clearance is a property of the
        pair, not of one part: if the AFE wants 15 mm from noisy sources and the
        regulator wants 5 mm from anything, the answer is 15.
        """
        best = 0.0
        for src, dst in ((a, b), (b, a)):
            part, other = self.part_of[src], self.part_of[dst]
            cl = part.clearances
            if other.heat_source:
                best = max(best, cl.from_property.get("hot", 0.0))
            if other.noise_source:
                best = max(best, cl.from_property.get("noisy", 0.0))
            best = max(best, cl.from_category.get(other.category, 0.0))
        return best

    def refs_where(self, predicate) -> list[str]:
        return [r for r in self.refs if predicate(self.part_of[r])]

    def why(self, family: str) -> str:
        """Mission-authored justification for a rule family, else the generic one."""
        return self.layout.rationale_for(family, FALLBACK_RATIONALE.get(family, ""))


def _inflate(rect: Rect, margin: float) -> Rect:
    """Grow a rectangle on all sides. Used to give a trace its real width."""
    if margin <= 0:
        return rect
    return Rect(rect.min_x - margin, rect.min_y - margin,
                rect.max_x + margin, rect.max_y + margin)


def _pair_label(measured: float, required: float, ok: bool) -> str:
    mark = "✓" if ok else "✗"
    return f"{measured:.1f} mm {mark} (needs {required:.1f})"


# ---------------------------------------------------------------------------
# Physical rules
# ---------------------------------------------------------------------------


def check_board_fit(scene: Scene) -> list[Check]:
    """Every component sits on the board, inside the edge margin."""
    checks: list[Check] = []
    usable = scene.usable_rect
    for ref in scene.refs:
        rect = scene.rect_of[ref]
        overflow = containment_overflow(usable, rect)
        ok = overflow <= 1e-9
        checks.append(
            Check(
                id=f"fit.board::{ref}",
                title=f"{ref} fits on the PCB",
                status=PASS if ok else FAIL,
                severity=BLOCKER,
                subjects=[ref],
                measured_mm=overflow,
                required_mm=0.0,
                margin_mm=-overflow,
                metric="bbox_overflow",
                message=(
                    f"{ref} is inside the board outline with "
                    f"{scene.board.edge_margin_mm:g} mm edge margin."
                    if ok
                    else f"{ref} overhangs the usable board area by "
                    f"{overflow:.2f} mm."
                ),
                rationale=scene.why("fit.board"),
                suggestion="" if ok else f"Move {ref} inward by at least {overflow:.2f} mm.",
                overlay=None if ok else scene.overlays.marker(rect, f"{ref} off board", False),
            )
        )
    return checks


def check_enclosure_fit(scene: Scene) -> list[Check]:
    """Components clear the enclosure walls in plan view."""
    checks: list[Check] = []
    allowed = scene.enclosure_rect_boardlocal
    for ref in scene.refs:
        rect = scene.rect_of[ref]
        overflow = containment_overflow(allowed, rect)
        ok = overflow <= 1e-9
        checks.append(
            Check(
                id=f"fit.enclosure_xy::{ref}",
                title=f"{ref} clears the enclosure wall",
                status=PASS if ok else FAIL,
                severity=BLOCKER,
                subjects=[ref],
                measured_mm=overflow,
                required_mm=0.0,
                margin_mm=-overflow,
                metric="bbox_overflow",
                message=(
                    f"{ref} respects the "
                    f"{scene.enclosure.wall_keepout_mm:g} mm wall keep-out."
                    if ok
                    else f"{ref} intrudes {overflow:.2f} mm into the "
                    f"{scene.enclosure.wall_keepout_mm:g} mm wall keep-out."
                ),
                rationale=scene.why("fit.enclosure_xy"),
                suggestion="" if ok else f"Pull {ref} {overflow:.2f} mm away from the wall.",
                overlay=None if ok else scene.overlays.marker(rect, f"{ref} hits wall", False),
            )
        )
    return checks


def check_height(scene: Scene) -> list[Check]:
    """Components fit under the lid.

    Two ceilings apply: the board's own component-height budget, and the
    physical space left between the board surface and the enclosure roof.
    """
    board: Board = scene.board
    _, _, oz = board.origin_mm
    headroom = scene.enclosure.interior_height_mm - (oz + board.thickness_mm)
    ceiling = min(board.max_component_height_mm, headroom)

    checks: list[Check] = []
    for ref in scene.refs:
        part = scene.part_of[ref]
        ok = part.height_mm <= ceiling + 1e-9
        margin = ceiling - part.height_mm
        checks.append(
            Check(
                id=f"fit.height::{ref}",
                title=f"{ref} fits under the lid",
                status=PASS if ok else FAIL,
                severity=BLOCKER,
                subjects=[ref],
                measured_mm=part.height_mm,
                required_mm=ceiling,
                margin_mm=margin,
                metric="height",
                message=(
                    f"{ref} stands {part.height_mm:g} mm tall against a "
                    f"{ceiling:g} mm ceiling ({margin:.2f} mm spare)."
                    if ok
                    else f"{ref} stands {part.height_mm:g} mm tall but only "
                    f"{ceiling:g} mm is available; over by {-margin:.2f} mm."
                ),
                rationale=(
                    f"Interior height {scene.enclosure.interior_height_mm:g} mm "
                    f"minus the {oz:g} mm standoff and {board.thickness_mm:g} mm "
                    f"board leaves {headroom:g} mm above the surface. "
                    + scene.why("fit.height")
                ),
                suggestion=(
                    "" if ok else f"Source a lower-profile {part.name} or raise the lid."
                ),
                overlay=None if ok else scene.overlays.marker(
                    scene.rect_of[ref], f"{ref} too tall", False
                ),
            )
        )
    return checks


def check_overlap(scene: Scene) -> list[Check]:
    """No two footprints occupy the same board area."""
    checks: list[Check] = []
    refs = scene.refs
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            a, b = refs[i], refs[j]
            ra, rb = scene.rect_of[a], scene.rect_of[b]
            area = overlap_area(ra, rb)
            ok = not rects_overlap(ra, rb)
            if ok:
                continue  # Only report actual collisions; N^2 passes are noise.
            checks.append(
                Check(
                    id=f"fit.overlap::{a}|{b}",
                    title=f"{a} and {b} do not collide",
                    status=FAIL,
                    severity=BLOCKER,
                    subjects=[a, b],
                    measured_mm=area,
                    required_mm=0.0,
                    margin_mm=-area,
                    metric="overlap_area_mm2",
                    message=f"{a} and {b} overlap by {area:.2f} mm² of board area.",
                    rationale=scene.why("fit.overlap"),
                    suggestion=f"Separate {a} and {b}.",
                    overlay=scene.overlays.measure_line(ra, rb, "collision", False),
                )
            )
    return checks


def check_courtyard(scene: Scene) -> list[Check]:
    """Adjacent parts leave enough room to actually be assembled.

    Non-overlapping is not the same as buildable. Two packages butted edge to
    edge give the placement head nowhere to land and the solder joints nowhere
    to fillet, so a minimum courtyard gap is enforced on top of the collision
    check.
    """
    required = scene.board.min_component_gap_mm
    if required <= 0:
        return []

    checks: list[Check] = []
    refs = scene.refs
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            a, b = refs[i], refs[j]
            ra, rb = scene.rect_of[a], scene.rect_of[b]
            if rects_overlap(ra, rb):
                continue  # Already reported as a collision; do not double-count.
            gap = edge_gap(ra, rb)
            if gap >= required - 1e-9:
                continue  # Passing courtyards are N^2 noise in the report.
            checks.append(
                Check(
                    id=f"fit.courtyard::{a}|{b}",
                    title=f"{a} and {b} have assembly clearance",
                    status=FAIL,
                    severity=MAJOR,
                    subjects=[a, b],
                    measured_mm=gap,
                    required_mm=required,
                    margin_mm=gap - required,
                    metric="edge_gap",
                    message=(
                        f"{a} and {b} are only {gap:.2f} mm apart; "
                        f"{required:g} mm of courtyard is required."
                    ),
                    rationale=scene.why("fit.courtyard"),
                    suggestion=f"Open the gap between {a} and {b} by "
                               f"{required - gap:.2f} mm.",
                    overlay=scene.overlays.measure_line(
                        ra, rb, _pair_label(gap, required, False), False
                    ),
                )
            )
    return checks


# ---------------------------------------------------------------------------
# Electrical separation rules
# ---------------------------------------------------------------------------


def _separation_check(
    scene: Scene,
    check_id: str,
    title: str,
    a: str,
    b: str,
    required: float,
    severity: str,
    rationale: str,
    suggestion_verb: str = "Move",
) -> Check:
    evaluated, gap, centers = scene.measure(a, b)
    ok = evaluated >= required - 1e-9
    margin = evaluated - required
    metric = "center_distance" if scene.layout.distance_metric == "center" else "edge_gap"
    return Check(
        id=check_id,
        title=title,
        status=PASS if ok else FAIL,
        severity=severity,
        subjects=[a, b],
        measured_mm=evaluated,
        required_mm=required,
        margin_mm=margin,
        metric=metric,
        edge_gap_mm=gap,
        center_distance_mm=centers,
        message=(
            f"{a} sits {evaluated:.2f} mm from {b} "
            f"({metric.replace('_', ' ')}); {required:g} mm required, "
            f"{margin:.2f} mm to spare."
            if ok
            else f"{a} sits {evaluated:.2f} mm from {b} "
            f"({metric.replace('_', ' ')}) but needs {required:g} mm. "
            f"Short by {-margin:.2f} mm."
        ),
        rationale=rationale,
        suggestion="" if ok else f"{suggestion_verb} {a} at least {-margin:.2f} mm further from {b}.",
        overlay=scene.overlays.measure_line(
            scene.rect_of[a], scene.rect_of[b], _pair_label(evaluated, required, ok), ok
        ),
    )


def check_thermal_separation(scene: Scene) -> list[Check]:
    """Sensitive parts keep their distance from heat sources."""
    checks: list[Check] = []
    sensitive = scene.refs_where(lambda p: p.is_sensitive)
    hot = scene.refs_where(lambda p: p.heat_source)
    for s in sensitive:
        for h in hot:
            if s == h:
                continue
            required = scene.part_of[s].clearances.from_property.get("hot", 0.0)
            if required <= 0:
                continue
            checks.append(
                _separation_check(
                    scene,
                    f"sep.thermal::{s}|{h}",
                    f"{s} is clear of heat source {h}",
                    s,
                    h,
                    required,
                    MAJOR,
                    scene.why("sep.thermal"),
                )
            )
    return checks


def check_noise_separation(scene: Scene) -> list[Check]:
    """Sensitive parts keep their distance from noise sources."""
    checks: list[Check] = []
    sensitive = scene.refs_where(lambda p: p.is_sensitive)
    noisy = scene.refs_where(lambda p: p.noise_source)
    for s in sensitive:
        for n in noisy:
            if s == n:
                continue
            required = scene.part_of[s].clearances.from_property.get("noisy", 0.0)
            required = max(required, scene.required_between(s, n))
            if required <= 0:
                continue
            checks.append(
                _separation_check(
                    scene,
                    f"sep.noise::{s}|{n}",
                    f"{s} is clear of noise source {n}",
                    s,
                    n,
                    required,
                    MAJOR,
                    scene.why("sep.noise"),
                )
            )
    return checks


def check_rf_separation(scene: Scene) -> list[Check]:
    """Radio parts keep their distance from noise sources."""
    checks: list[Check] = []
    radios = scene.refs_where(lambda p: p.category == "wireless")
    noisy = scene.refs_where(lambda p: p.noise_source)
    for r in radios:
        for n in noisy:
            if r == n:
                continue
            required = scene.required_between(r, n)
            required = max(required, scene.part_of[r].clearances.from_property.get("noisy", 0.0))
            if required <= 0:
                continue
            checks.append(
                _separation_check(
                    scene,
                    f"sep.rf::{r}|{n}",
                    f"{r} is clear of noise source {n}",
                    r,
                    n,
                    required,
                    MAJOR,
                    scene.why("sep.rf"),
                )
            )
    return checks


# ---------------------------------------------------------------------------
# Zone rules
# ---------------------------------------------------------------------------


def check_heat_zones(scene: Scene) -> list[Check]:
    """No sensitive part sits inside a hot part's thermal radius.

    The radius is a declared approximation, not a solved temperature field.
    """
    checks: list[Check] = []
    hot = [r for r in scene.refs if scene.part_of[r].heat_zone_radius_mm]
    sensitive = scene.refs_where(lambda p: p.is_sensitive)

    for h in hot:
        radius = scene.part_of[h].heat_zone_radius_mm or 0.0
        hx, hy = scene.rect_of[h].center
        for s in sensitive:
            if s == h:
                continue
            penetration = circle_rect_overlap((hx, hy), radius, scene.rect_of[s])
            ok = penetration <= 1e-9
            checks.append(
                Check(
                    id=f"zone.heat_overlap::{h}|{s}",
                    title=f"{s} is outside the {h} heat zone",
                    status=PASS if ok else FAIL,
                    severity=MAJOR,
                    subjects=[h, s],
                    measured_mm=penetration,
                    required_mm=0.0,
                    margin_mm=-penetration,
                    metric="zone_penetration",
                    message=(
                        f"{s} sits outside the {radius:g} mm thermal zone around {h}."
                        if ok
                        else f"{s} reaches {penetration:.2f} mm inside the "
                        f"{radius:g} mm thermal zone around {h}."
                    ),
                    rationale=scene.why("zone.heat_overlap"),
                    suggestion=(
                        "" if ok else f"Move {s} {penetration:.2f} mm further from {h}, "
                        f"or cut {h} dissipation."
                    ),
                    overlay=(
                        None if ok else scene.overlays.measure_line(
                            scene.rect_of[h], scene.rect_of[s], f"heat zone ✗", False
                        )
                    ),
                )
            )
    return checks


def check_rf_keepout(scene: Scene) -> list[Check]:
    """Nothing occupies the antenna's radiating volume.

    Both components and copper are checked: a trace crossing the keep-out
    detunes the antenna just as effectively as a part sitting in it.
    """
    checks: list[Check] = []
    radios = [r for r in scene.refs if scene.part_of[r].keepout]

    for r in radios:
        part = scene.part_of[r]
        ko = part.keepout
        assert ko is not None
        # The declared direction is relative to the part body, so it turns with
        # the placement.
        facing = rotate_direction(ko.direction, scene.placement_of[r].rotation_deg)
        zone = keepout_rect(scene.rect_of[r], facing, ko.extends_mm, ko.width_mm)

        # Touching counts as intruding. A keep-out is an exclusion region, not
        # a body, so sitting exactly on its boundary means zero clearance.
        intruders: list[str] = []
        for other in scene.refs:
            if other == r:
                continue
            if edge_gap(zone, scene.rect_of[other]) <= 0.0:
                intruders.append(other)

        # A trace is copper with width; testing the bare centerline lets half a
        # track sit inside the zone while the line itself stays outside.
        crossing_traces = [
            t.id
            for t in scene.layout.traces
            if polyline_rect_intersect(t.path_mm, _inflate(zone, t.width_mm / 2.0))
        ]

        ok = not intruders and not crossing_traces
        offenders = intruders + [f"trace {t}" for t in crossing_traces]
        checks.append(
            Check(
                id=f"zone.rf_keepout::{r}",
                title=f"{r} antenna keep-out is clear",
                status=PASS if ok else FAIL,
                severity=MAJOR,
                subjects=[r] + intruders,
                measured_mm=float(len(offenders)),
                required_mm=0.0,
                margin_mm=-float(len(offenders)),
                metric="intruder_count",
                message=(
                    f"The {ko.extends_mm:g} mm keep-out ahead of {r} is clear."
                    if ok
                    else f"The {ko.extends_mm:g} mm keep-out ahead of {r} is "
                    f"obstructed by: {', '.join(offenders)}."
                ),
                rationale=scene.why("zone.rf_keepout"),
                suggestion=(
                    "" if ok else f"Clear {', '.join(offenders)} out of the {r} keep-out, "
                    f"or point the antenna at open space."
                ),
                overlay=scene.overlays.zone_rect(
                    zone,
                    f"{r} keep-out {'✓' if ok else '✗'}",
                    PURPLE if ok else RED,
                ),
            )
        )
    return checks


# ---------------------------------------------------------------------------
# Mission rules
# ---------------------------------------------------------------------------


def check_skin_contact_temperature(scene: Scene) -> list[Check]:
    """Heat sources stay away from parts pressed against the patient.

    IEC 60601-1 caps prolonged skin contact at 43 C. This is a geometric proxy
    for that limit, not a thermal solve, and the report says so.
    """
    required = scene.layout.mission.skin_contact_clearance_mm
    if required <= 0:
        return []

    skin = scene.refs_where(lambda p: p.skin_contact)
    hot = scene.refs_where(lambda p: p.heat_source)
    if not skin:
        return []
    if not hot:
        return [
            Check(
                id="safety.skin_contact_temp",
                title="Skin-contact temperature",
                status=SKIP,
                severity=INFO,
                metric="edge_gap",
                message="No part is flagged as a heat source, so no skin-contact "
                        "temperature risk could be evaluated.",
                rationale="Requires at least one part with heat_source set.",
            )
        ]

    checks: list[Check] = []
    for s in skin:
        for h in hot:
            if s == h:
                continue
            checks.append(
                _separation_check(
                    scene,
                    f"safety.skin_contact_temp::{s}|{h}",
                    f"{s} stays cool enough for skin contact ({h})",
                    s,
                    h,
                    required,
                    BLOCKER,
                    scene.why("safety.skin_contact_temp"),
                )
            )
    return checks


def check_battery_thermal(scene: Scene) -> list[Check]:
    """The lithium cell stays away from sustained heat."""
    required = scene.layout.mission.battery_thermal_clearance_mm
    if required <= 0:
        return []

    cells = scene.refs_where(lambda p: p.thermal_runaway_risk)
    hot = scene.refs_where(lambda p: p.heat_source)
    if not cells or not hot:
        return []

    checks: list[Check] = []
    for c in cells:
        for h in hot:
            if c == h:
                continue
            checks.append(
                _separation_check(
                    scene,
                    f"safety.battery_thermal::{c}|{h}",
                    f"{c} is clear of heat source {h}",
                    c,
                    h,
                    required,
                    BLOCKER,
                    scene.why("safety.battery_thermal"),
                )
            )
    return checks


def check_mission_rules(scene: Scene) -> list[Check]:
    """Product-specific constraints declared in the layout data."""
    checks: list[Check] = []
    for rule in scene.layout.mission_rules:
        a, b = rule.between
        if a not in scene.rect_of or b not in scene.rect_of:
            missing = [r for r in (a, b) if r not in scene.rect_of]
            checks.append(
                Check(
                    id=f"mission.{rule.id}",
                    title=rule.title or rule.id,
                    status=SKIP,
                    severity=INFO,
                    subjects=list(rule.between),
                    message=f"Cannot evaluate: no placement for {', '.join(missing)}.",
                    rationale=rule.rationale,
                )
            )
            continue

        ra, rb = scene.rect_of[a], scene.rect_of[b]
        gap = edge_gap(ra, rb)
        centers = center_distance(ra, rb)
        measured = centers if rule.metric == "center" else gap

        if rule.type == "min_separation":
            ok = measured >= rule.distance_mm - 1e-9
            margin = measured - rule.distance_mm
            detail = (
                f"{measured:.2f} mm apart, {rule.distance_mm:g} mm required"
                if ok
                else f"only {measured:.2f} mm apart, {rule.distance_mm:g} mm required"
            )
        else:
            ok = measured <= rule.distance_mm + 1e-9
            margin = rule.distance_mm - measured
            detail = (
                f"{measured:.2f} mm apart, {rule.distance_mm:g} mm maximum"
                if ok
                else f"{measured:.2f} mm apart, exceeds the {rule.distance_mm:g} mm maximum"
            )

        checks.append(
            Check(
                id=f"mission.{rule.id}",
                title=rule.title or rule.id,
                status=PASS if ok else FAIL,
                severity=rule.severity,
                subjects=[a, b],
                measured_mm=measured,
                required_mm=rule.distance_mm,
                margin_mm=margin,
                metric="center_distance" if rule.metric == "center" else "edge_gap",
                edge_gap_mm=gap,
                center_distance_mm=centers,
                message=f"{a} and {b} are {detail}.",
                rationale=rule.rationale,
                suggestion=(
                    "" if ok else f"Adjust {a}/{b} spacing by {abs(margin):.2f} mm."
                ),
                overlay=scene.overlays.measure_line(
                    ra, rb, _pair_label(measured, rule.distance_mm, ok), ok
                ),
            )
        )
    return checks


def check_connector_access(scene: Scene) -> list[Check]:
    """Connectors line up with an enclosure opening and stay within reach.

    Two independent ways to fail: the connector can be too deep inside the
    shell to reach through the hole, or it can be at the right depth but offset
    so the hole does not line up with it.
    """
    openings = scene.enclosure.openings
    connectors = scene.refs_where(lambda p: p.category == "connector")
    if not connectors:
        return []
    if not openings:
        return [
            Check(
                id="access.connector",
                title="Connector accessibility",
                status=SKIP,
                severity=INFO,
                subjects=connectors,
                message="The enclosure declares no openings, so accessibility "
                        "could not be evaluated.",
                rationale="Requires at least one entry in enclosure.openings.",
            )
        ]

    ox, oy, _ = scene.board.origin_mm
    enc = scene.enclosure
    checks: list[Check] = []

    for ref in connectors:
        rect = scene.rect_of[ref]
        # Work in enclosure coordinates: the openings are defined on the shell.
        enc_rect = rect.translate(ox, oy)

        best: tuple[float, str, float, float] | None = None
        for op in openings:
            if op.face == "-x":
                depth = enc_rect.min_x - 0.0
                span_lo, span_hi = enc_rect.min_y, enc_rect.max_y
            elif op.face == "+x":
                depth = enc.interior_length_mm - enc_rect.max_x
                span_lo, span_hi = enc_rect.min_y, enc_rect.max_y
            elif op.face == "-y":
                depth = enc_rect.min_y - 0.0
                span_lo, span_hi = enc_rect.min_x, enc_rect.max_x
            else:  # "+y"
                depth = enc.interior_width_mm - enc_rect.max_y
                span_lo, span_hi = enc_rect.min_x, enc_rect.max_x

            win_lo = op.center_mm - op.width_mm / 2.0
            win_hi = op.center_mm + op.width_mm / 2.0
            # How far the connector sits outside the window's span, 0 if aligned.
            misalign = max(0.0, win_lo - span_lo, span_hi - win_hi)
            excess_depth = max(0.0, depth - op.max_reach_mm)
            score = misalign + excess_depth
            if best is None or score < best[0]:
                best = (score, op.id, misalign, depth)

        assert best is not None
        score, op_id, misalign, depth = best
        ok = score <= 1e-9

        if ok:
            message = (
                f"{ref} lines up with opening '{op_id}' and sits {depth:.2f} mm "
                f"inside the wall."
            )
        else:
            parts_of_problem = []
            if misalign > 1e-9:
                parts_of_problem.append(f"offset {misalign:.2f} mm outside its span")
            if depth > 1e-9 and score > misalign + 1e-9:
                parts_of_problem.append(f"{depth:.2f} mm deep, beyond reach")
            message = (
                f"{ref} does not line up with opening '{op_id}': "
                f"{', and '.join(parts_of_problem)}."
            )

        checks.append(
            Check(
                id=f"access.connector::{ref}",
                title=f"{ref} is reachable through the enclosure",
                status=PASS if ok else FAIL,
                severity=MAJOR,
                subjects=[ref],
                measured_mm=score,
                required_mm=0.0,
                margin_mm=-score,
                metric="access_offset",
                message=message,
                rationale=scene.why("access.connector"),
                suggestion=(
                    "" if ok else f"Shift {ref} to register with opening '{op_id}'."
                ),
                overlay=scene.overlays.marker(
                    rect, f"{ref} {'✓' if ok else '✗'} {op_id}", ok
                ),
            )
        )
    return checks


# ---------------------------------------------------------------------------
# Data-quality reporting
# ---------------------------------------------------------------------------


def check_unresolved_parts(scene: Scene) -> list[Check]:
    """Surface placements whose part_id is not in the library.

    A silently dropped component is the worst possible failure: the report
    would show all-clear for a board that was never fully evaluated.
    """
    if not scene.missing:
        return []
    return [
        Check(
            id=f"data.unresolved_part::{pl.ref}",
            title=f"{pl.ref} has no matching part",
            status=WARN,
            severity=MAJOR,
            subjects=[pl.ref],
            message=(
                f"Placement '{pl.ref}' references part_id '{pl.part_id}', which "
                f"is not in the parts library. It was excluded from every check."
            ),
            rationale="Every placed component must resolve to a part definition.",
            suggestion=f"Add '{pl.part_id}' to the parts library, or fix the ref.",
        )
        for pl in scene.missing
    ]


def zone_overlays(scene: Scene):
    """Standing scene decoration: heat radii and antenna keep-outs.

    Emitted separately from checks so the Blender scene can always show the
    physical zones, whether or not anything is currently violating them, and so
    no radius is ever hardcoded on the rendering side.
    """
    out = []
    for ref in scene.refs:
        part = scene.part_of[ref]
        cx, cy = scene.rect_of[ref].center
        if part.heat_zone_radius_mm:
            out.append(
                scene.overlays.zone_circle(
                    cx,
                    cy,
                    part.heat_zone_radius_mm,
                    f"{ref} thermal {part.heat_zone_radius_mm:g} mm",
                    ORANGE if part.noise_source else AMBER,
                )
            )
        if part.keepout:
            ko = part.keepout
            facing = rotate_direction(ko.direction, scene.placement_of[ref].rotation_deg)
            out.append(
                scene.overlays.zone_rect(
                    keepout_rect(scene.rect_of[ref], facing, ko.extends_mm, ko.width_mm),
                    f"{ref} antenna keep-out",
                    PURPLE,
                )
            )
        if part.skin_contact:
            out.append(
                scene.overlays.marker(scene.rect_of[ref], f"{ref} skin contact", True)
            )
    return out


ALL_RULES = (
    check_unresolved_parts,
    check_board_fit,
    check_enclosure_fit,
    check_height,
    check_overlap,
    check_courtyard,
    check_thermal_separation,
    check_noise_separation,
    check_rf_separation,
    check_heat_zones,
    check_rf_keepout,
    check_skin_contact_temperature,
    check_battery_thermal,
    check_mission_rules,
    check_connector_access,
)


def run_all(scene: Scene) -> list[Check]:
    checks: list[Check] = []
    for rule in ALL_RULES:
        checks.extend(rule(scene))
    return checks
