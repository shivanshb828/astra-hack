"""Placement solver.

Searches for a component arrangement that satisfies the constraints, so the
engine can propose a corrected board rather than only grading someone else's.

The method is deliberately plain: seeded multi-start hill climbing over a
discrete grid. With a handful of components on one board the search space is
small enough that a direct sweep beats anything cleverer, and being
deterministic matters more than being optimal -- the same inputs must produce
the same board every time or the demo is not reproducible.

The cost function mirrors :mod:`constraint_engine.rules` but works in raw
numbers instead of building ``Check`` objects, because it runs tens of
thousands of times. :func:`solve` re-validates its own output through the real
rule set afterwards, so the two can never quietly disagree about the verdict.
"""

from __future__ import annotations

import random
from dataclasses import replace
from math import sqrt

from .geometry import (
    Rect,
    center_distance,
    circle_rect_overlap,
    edge_gap,
    keepout_rect,
    overlap_area,
    polyline_rect_intersect,
    rotate_direction,
)
from .models import Layout, Part, Placement
from .rules import Scene

# Hard violations are squared so that being badly wrong is much worse than
# being slightly wrong, which gives the search a gradient to follow.
W_CONTAINMENT = 40.0
W_OVERLAP = 8.0
W_COURTYARD = 20.0
W_SEPARATION = 1.0
W_ZONE = 2.0
W_KEEPOUT = 60.0
W_ACCESS = 3.0
# Small enough that it only ever breaks ties between feasible layouts. Without
# it the search happily flings parts into opposite corners to buy clearance it
# does not need, producing a legal board that no one could route.
W_COMPACT = 0.002

COARSE_STEP_MM = 2.0
FINE_STEP_MM = 0.5
FINE_RADIUS_MM = 4.0
MAX_PASSES = 8
DEFAULT_SEEDS = (0, 1, 2, 3)


class _Model:
    """Precomputed, position-independent facts about one layout.

    Everything that does not change as parts move is worked out once here:
    which pairs actually constrain each other, which parts are movable, and
    what the legal region is. The inner loop then only does arithmetic.
    """

    def __init__(self, scene: Scene):
        self.scene = scene
        self.layout = scene.layout
        self.board = scene.board
        self.refs = list(scene.refs)
        self.part_of = scene.part_of
        self.index = {ref: i for i, ref in enumerate(self.refs)}

        self.movable = [
            ref for ref in self.refs if not scene.placement_of[ref].anchored
        ]

        # Legal region for a component center is the tighter of the board's
        # usable area and the enclosure's wall keep-out.
        usable = scene.usable_rect
        enc = scene.enclosure_rect_boardlocal
        self.region = Rect(
            max(usable.min_x, enc.min_x),
            max(usable.min_y, enc.min_y),
            min(usable.max_x, enc.max_x),
            min(usable.max_y, enc.max_y),
        )

        # Pairs with a real separation requirement, resolved once.
        self.sep_pairs: list[tuple[int, int, float]] = []
        seen: set[tuple[int, int]] = set()
        for a in self.refs:
            for b in self.refs:
                if a == b:
                    continue
                key = (min(self.index[a], self.index[b]), max(self.index[a], self.index[b]))
                if key in seen:
                    continue
                required = self._required(a, b)
                if required > 0:
                    seen.add(key)
                    self.sep_pairs.append((self.index[a], self.index[b], required))

        # Heat zones: (hot index, radius, [sensitive indices]).
        self.heat_zones: list[tuple[int, float, list[int]]] = []
        for ref in self.refs:
            part = self.part_of[ref]
            if not part.heat_zone_radius_mm:
                continue
            targets = [
                self.index[o]
                for o in self.refs
                if o != ref and self.part_of[o].is_sensitive
            ]
            if targets:
                self.heat_zones.append(
                    (self.index[ref], part.heat_zone_radius_mm, targets)
                )

        # Antenna keep-outs: (radio index, keepout spec).
        self.keepouts = [
            (self.index[ref], self.part_of[ref].keepout,
             scene.placement_of[ref].rotation_deg)
            for ref in self.refs
            if self.part_of[ref].keepout
        ]
        # Traces never move, so cache each one's bounding box. The polyline
        # test is the single most expensive thing in the cost function and a
        # box comparison rejects almost every call to it.
        self.trace_paths: list[
            tuple[tuple[float, float, float, float], list, float]
        ] = []
        for t in self.layout.traces:
            xs = [p[0] for p in t.path_mm]
            ys = [p[1] for p in t.path_mm]
            self.trace_paths.append(
                ((min(xs), min(ys), max(xs), max(ys)), t.path_mm, t.width_mm / 2.0)
            )

        # Mission-level safety pairs.
        mission = self.layout.mission
        self.skin_pairs = [
            (self.index[s], self.index[h], mission.skin_contact_clearance_mm)
            for s in self.refs
            if self.part_of[s].skin_contact
            for h in self.refs
            if h != s and self.part_of[h].heat_source
        ] if mission.skin_contact_clearance_mm > 0 else []

        self.battery_pairs = [
            (self.index[c], self.index[h], mission.battery_thermal_clearance_mm)
            for c in self.refs
            if self.part_of[c].thermal_runaway_risk
            for h in self.refs
            if h != c and self.part_of[h].heat_source
        ] if mission.battery_thermal_clearance_mm > 0 else []

        # Declared mission rules, resolved to indices.
        self.mission_rules = [
            (
                self.index[r.between[0]],
                self.index[r.between[1]],
                r.distance_mm,
                r.metric,
                r.type,
            )
            for r in self.layout.mission_rules
            if r.between[0] in self.index and r.between[1] in self.index
        ]

        # Connector access targets.
        ox, oy, _ = self.board.origin_mm
        self.origin = (ox, oy)
        self.connectors = [
            self.index[ref]
            for ref in self.refs
            if self.part_of[ref].category == "connector"
        ]
        self.openings = self.layout.enclosure.openings

        self.center = (self.board.length_mm / 2.0, self.board.width_mm / 2.0)

        # Coarse grids never change, so build each one once instead of on
        # every pass of every restart.
        self._grid_cache: dict[tuple[str, float], list[tuple[float, float]]] = {}

    def candidates(self, ref: str, step: float,
                   around: tuple[float, float] | None = None,
                   radius: float | None = None) -> list[tuple[float, float]]:
        if around is None:
            key = (ref, step)
            grid = self._grid_cache.get(key)
            if grid is None:
                grid = _candidate_positions(self, ref, step)
                self._grid_cache[key] = grid
            return grid
        return _candidate_positions(self, ref, step, around, radius)

    def _required(self, a: str, b: str) -> float:
        """Mirror of Scene.required_between, plus the sensitive-part rules."""
        scene = self.scene
        best = scene.required_between(a, b)
        pa, pb = self.part_of[a], self.part_of[b]
        for src, other in ((pa, pb), (pb, pa)):
            if not src.is_sensitive:
                continue
            if other.heat_source:
                best = max(best, src.clearances.from_property.get("hot", 0.0))
            if other.noise_source:
                best = max(best, src.clearances.from_property.get("noisy", 0.0))
        return best

    # -- geometry ---------------------------------------------------------

    def rect_at(self, idx: int, x: float, y: float, rot: int) -> Rect:
        part = self.part_of[self.refs[idx]]
        if rot % 180 == 90:
            ex, ey = part.width_mm, part.length_mm
        else:
            ex, ey = part.length_mm, part.width_mm
        return Rect.from_center(x, y, ex, ey)

    def rects(self, state: list[tuple[float, float, int]]) -> list[Rect]:
        return [self.rect_at(i, *s) for i, s in enumerate(state)]

    # -- cost -------------------------------------------------------------

    def cost(self, state: list[tuple[float, float, int]]) -> float:
        return self.cost_rects(self.rects(state))

    def cost_rects(self, rects: list[Rect]) -> float:
        """Cost of an already-built footprint list.

        The inner loop moves one part at a time, so the caller keeps the list
        and swaps a single entry rather than rebuilding all of them.

        The pairwise geometry is deliberately written out rather than delegated
        to :mod:`geometry`. This runs on the order of a hundred thousand times
        per solve, and four separate rules all want the same edge gaps, so the
        gaps are computed once into a matrix and then read back. The equivalent
        readable version spends most of its time on repeat work and function
        call overhead.
        """
        total = 0.0
        n = len(rects)

        region = self.region
        rminx, rminy, rmaxx, rmaxy = (
            region.min_x, region.min_y, region.max_x, region.max_y
        )
        for r in rects:
            over = rminx - r.min_x
            o2 = rminy - r.min_y
            if o2 > over:
                over = o2
            o2 = r.max_x - rmaxx
            if o2 > over:
                over = o2
            o2 = r.max_y - rmaxy
            if o2 > over:
                over = o2
            if over > 0.0:
                total += W_CONTAINMENT * over * over

        # One pass over every pair: collision, courtyard, and the edge-gap
        # matrix that the separation rules below all read from.
        min_gap = self.board.min_component_gap_mm
        gaps = [0.0] * (n * n)
        for i in range(n):
            ri = rects[i]
            ax0, ay0, ax1, ay1 = ri.min_x, ri.min_y, ri.max_x, ri.max_y
            base = i * n
            for j in range(i + 1, n):
                rj = rects[j]
                # Signed overlap along each axis. Positive means the boxes
                # share that span; negative is the separation distance.
                ow = (ax1 if ax1 < rj.max_x else rj.max_x) - (
                    ax0 if ax0 > rj.min_x else rj.min_x
                )
                oh = (ay1 if ay1 < rj.max_y else rj.max_y) - (
                    ay0 if ay0 > rj.min_y else rj.min_y
                )
                if ow > 0.0 and oh > 0.0:
                    total += W_OVERLAP * ow * oh
                    gap = 0.0
                else:
                    dx = -ow if ow < 0.0 else 0.0
                    dy = -oh if oh < 0.0 else 0.0
                    gap = sqrt(dx * dx + dy * dy)
                    if min_gap > 0.0 and gap < min_gap:
                        # Courtyard: without this the compactness term happily
                        # butts packages edge to edge, which passes the
                        # collision test and is still unbuildable.
                        short = min_gap - gap
                        total += W_COURTYARD * short * short
                gaps[base + j] = gap
                gaps[j * n + i] = gap

        for i, j, required in self.sep_pairs:
            short = required - gaps[i * n + j]
            if short > 0.0:
                total += W_SEPARATION * short * short

        for i, j, required in self.skin_pairs:
            short = required - gaps[i * n + j]
            if short > 0.0:
                total += W_SEPARATION * short * short

        for i, j, required in self.battery_pairs:
            short = required - gaps[i * n + j]
            if short > 0.0:
                total += W_SEPARATION * short * short

        for hot_i, radius, targets in self.heat_zones:
            cx, cy = rects[hot_i].center
            for t in targets:
                pen = circle_rect_overlap((cx, cy), radius, rects[t])
                if pen > 0.0:
                    total += W_ZONE * pen * pen

        for radio_i, ko, rot in self.keepouts:
            facing = rotate_direction(ko.direction, rot)
            zone = keepout_rect(rects[radio_i], facing, ko.extends_mm, ko.width_mm)
            zx0, zy0, zx1, zy1 = zone.min_x, zone.min_y, zone.max_x, zone.max_y
            for k in range(n):
                if k == radio_i:
                    continue
                area = overlap_area(zone, rects[k])
                if area > 0.0:
                    total += W_KEEPOUT * area
                elif edge_gap(zone, rects[k]) <= 0.0:
                    # Exactly tangent: zero area but zero clearance too, which
                    # the rule counts as an intrusion. Flat nudge to match.
                    total += W_KEEPOUT
            for (tx0, ty0, tx1, ty1), path, half_w in self.trace_paths:
                # Cheap box reject before the polyline test, which is the most
                # expensive call in this function by a wide margin.
                if (tx1 + half_w < zx0 or tx0 - half_w > zx1
                        or ty1 + half_w < zy0 or ty0 - half_w > zy1):
                    continue
                if polyline_rect_intersect(
                    path,
                    Rect(zx0 - half_w, zy0 - half_w, zx1 + half_w, zy1 + half_w),
                ):
                    total += W_KEEPOUT * 10.0

        for i, j, distance, metric, kind in self.mission_rules:
            measured = (
                center_distance(rects[i], rects[j])
                if metric == "center"
                else gaps[i * n + j]
            )
            short = (
                distance - measured if kind == "min_separation" else measured - distance
            )
            if short > 0.0:
                total += W_SEPARATION * short * short

        total += self._access_cost(rects)

        cx, cy = self.center
        for r in rects:
            rx, ry = r.center
            total += W_COMPACT * (abs(rx - cx) + abs(ry - cy))

        return total

    def _access_cost(self, rects: list[Rect]) -> float:
        if not self.connectors or not self.openings:
            return 0.0
        ox, oy = self.origin
        enc = self.layout.enclosure
        total = 0.0
        for ci in self.connectors:
            r = rects[ci].translate(ox, oy)
            best = None
            for op in self.openings:
                if op.face == "-x":
                    depth = r.min_x
                    lo, hi = r.min_y, r.max_y
                elif op.face == "+x":
                    depth = enc.interior_length_mm - r.max_x
                    lo, hi = r.min_y, r.max_y
                elif op.face == "-y":
                    depth = r.min_y
                    lo, hi = r.min_x, r.max_x
                else:
                    depth = enc.interior_width_mm - r.max_y
                    lo, hi = r.min_x, r.max_x
                win_lo = op.center_mm - op.width_mm / 2.0
                win_hi = op.center_mm + op.width_mm / 2.0
                score = (
                    max(0.0, win_lo - lo, hi - win_hi)
                    + max(0.0, depth - op.max_reach_mm)
                )
                if best is None or score < best:
                    best = score
            if best:
                total += W_ACCESS * best * best
        return total


def _candidate_positions(model: _Model, ref: str, step: float,
                         around: tuple[float, float] | None = None,
                         radius: float | None = None) -> list[tuple[float, float]]:
    """Grid of legal center positions for one component."""
    part = model.part_of[ref]
    half_x = max(part.length_mm, part.width_mm) / 2.0
    half_y = half_x

    lo_x = model.region.min_x + half_x
    hi_x = model.region.max_x - half_x
    lo_y = model.region.min_y + half_y
    hi_y = model.region.max_y - half_y

    if around is not None and radius is not None:
        lo_x = max(lo_x, around[0] - radius)
        hi_x = min(hi_x, around[0] + radius)
        lo_y = max(lo_y, around[1] - radius)
        hi_y = min(hi_y, around[1] + radius)

    if hi_x < lo_x:
        lo_x = hi_x = (model.region.min_x + model.region.max_x) / 2.0
    if hi_y < lo_y:
        lo_y = hi_y = (model.region.min_y + model.region.max_y) / 2.0

    xs: list[float] = []
    x = lo_x
    while x <= hi_x + 1e-9:
        xs.append(round(x, 3))
        x += step
    if not xs:
        xs = [lo_x]

    ys: list[float] = []
    y = lo_y
    while y <= hi_y + 1e-9:
        ys.append(round(y, 3))
        y += step
    if not ys:
        ys = [lo_y]

    return [(px, py) for px in xs for py in ys]


def _optimize(model: _Model, state: list[tuple[float, float, int]]) -> tuple[list, float]:
    """Hill climb one starting state to a local minimum."""
    rects = model.rects(state)
    best_cost = model.cost_rects(rects)

    # Most-constrained parts move first: they have the fewest legal homes, so
    # letting the loose parts settle first just boxes them in.
    order = sorted(
        model.movable,
        key=lambda r: -sum(1 for i, j, _ in model.sep_pairs
                           if model.index[r] in (i, j)),
    )

    for step, radius in ((COARSE_STEP_MM, None), (FINE_STEP_MM, FINE_RADIUS_MM)):
        for _ in range(MAX_PASSES):
            improved = False
            for ref in order:
                idx = model.index[ref]
                cur = state[idx]
                cur_x, cur_y, cur_rot = cur
                around = (cur_x, cur_y) if radius is not None else None
                # 0 and 90 cover every distinct axis-aligned footprint; 180 and
                # 270 produce the same bounding box, so trying them is waste.
                part = model.part_of[ref]
                rotations = (0, 90) if part.length_mm != part.width_mm else (0,)

                local_best = cur
                local_rect = rects[idx]
                local_cost = best_cost

                for rot in rotations:
                    for px, py in model.candidates(ref, step, around, radius):
                        if px == cur_x and py == cur_y and rot == cur_rot:
                            continue
                        candidate = model.rect_at(idx, px, py, rot)
                        rects[idx] = candidate
                        c = model.cost_rects(rects)
                        if c < local_cost - 1e-9:
                            local_cost = c
                            local_best = (px, py, rot)
                            local_rect = candidate

                state[idx] = local_best
                rects[idx] = local_rect
                if local_cost < best_cost - 1e-9:
                    best_cost = local_cost
                    improved = True

            if not improved:
                break

    return state, best_cost


def solve(
    layout: Layout,
    parts: dict[str, Part],
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    name: str | None = None,
) -> tuple[Layout, float]:
    """Search for a placement that satisfies the constraints.

    Returns the best layout found and its residual cost. A cost above zero
    means constraints remain violated; the caller is expected to report that
    plainly rather than presenting the result as clean.
    """
    scene = Scene(layout, parts)
    if not scene.refs:
        # An empty board is trivially solved, but a board whose every part_id
        # failed to resolve is not -- returning 0.0 there would report success
        # for a layout the engine never actually looked at.
        if scene.missing:
            return layout, float("inf")
        return layout, 0.0

    model = _Model(scene)

    # Seed 0 starts from the layout as given, so an already-good board is never
    # made worse. The rest start randomised to escape its local minimum.
    starts: list[list[tuple[float, float, int]]] = []
    base = [
        (
            scene.placement_of[ref].x_mm,
            scene.placement_of[ref].y_mm,
            scene.placement_of[ref].rotation_deg,
        )
        for ref in model.refs
    ]
    starts.append(list(base))

    for seed in seeds[1:]:
        rng = random.Random(seed)
        state = list(base)
        for ref in model.movable:
            idx = model.index[ref]
            options = _candidate_positions(model, ref, COARSE_STEP_MM)
            px, py = rng.choice(options)
            rot = rng.choice((0, 90))
            state[idx] = (px, py, rot)
        starts.append(state)

    best_state: list[tuple[float, float, int]] | None = None
    best_cost = float("inf")
    for state in starts:
        candidate, cost = _optimize(model, list(state))
        if cost < best_cost - 1e-9:
            best_cost = cost
            best_state = list(candidate)

    assert best_state is not None

    solved_placements: list[Placement] = []
    for pl in layout.placements:
        if pl.ref not in model.index:
            solved_placements.append(pl)  # unresolved part; leave untouched
            continue
        x, y, rot = best_state[model.index[pl.ref]]
        solved_placements.append(
            replace(pl, x_mm=round(x, 3), y_mm=round(y, 3), rotation_deg=rot)
        )

    solved = replace(
        layout,
        name=name or f"{layout.name} (solved)",
        placements=solved_placements,
    )
    return solved, best_cost
