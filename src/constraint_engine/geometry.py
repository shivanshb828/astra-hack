"""2D geometry primitives for constraint checking.

All distances are millimetres. Rectangles are axis-aligned, which holds because
placement rotation is restricted to 90-degree steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle defined by its minimum and maximum corners."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @classmethod
    def from_center(cls, cx: float, cy: float, x_extent: float, y_extent: float) -> "Rect":
        hx, hy = x_extent / 2.0, y_extent / 2.0
        return cls(cx - hx, cy - hy, cx + hx, cy + hy)

    @classmethod
    def from_origin(cls, ox: float, oy: float, x_extent: float, y_extent: float) -> "Rect":
        return cls(ox, oy, ox + x_extent, oy + y_extent)

    @property
    def center(self) -> Point:
        return ((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def inset(self, margin: float) -> "Rect":
        """Shrink on all sides. Used to apply edge margins and wall keep-outs."""
        return Rect(
            self.min_x + margin,
            self.min_y + margin,
            self.max_x - margin,
            self.max_y - margin,
        )

    def translate(self, dx: float, dy: float) -> "Rect":
        return Rect(self.min_x + dx, self.min_y + dy, self.max_x + dx, self.max_y + dy)


def center_distance(a: Rect, b: Rect) -> float:
    """Straight-line distance between rectangle centers."""
    ax, ay = a.center
    bx, by = b.center
    return math.hypot(bx - ax, by - ay)


def edge_gap(a: Rect, b: Rect) -> float:
    """Shortest distance between rectangle edges.

    Returns 0.0 when the rectangles touch or overlap. This is the metric that
    matches how clearance is specified in practice: a 15 mm keep-out means 15 mm
    of empty space, not 15 mm between part origins.
    """
    dx = max(a.min_x - b.max_x, b.min_x - a.max_x, 0.0)
    dy = max(a.min_y - b.max_y, b.min_y - a.max_y, 0.0)
    return math.hypot(dx, dy)


def overlap_area(a: Rect, b: Rect) -> float:
    """Area of intersection, 0.0 if disjoint or merely touching."""
    w = min(a.max_x, b.max_x) - max(a.min_x, b.min_x)
    h = min(a.max_y, b.max_y) - max(a.min_y, b.min_y)
    if w <= 0 or h <= 0:
        return 0.0
    return w * h


def rects_overlap(a: Rect, b: Rect) -> bool:
    """True when interiors intersect. Touching edges do not count."""
    return overlap_area(a, b) > 0.0


def contains(outer: Rect, inner: Rect) -> bool:
    """True when `inner` lies entirely within `outer`, edges inclusive."""
    return (
        inner.min_x >= outer.min_x
        and inner.min_y >= outer.min_y
        and inner.max_x <= outer.max_x
        and inner.max_y <= outer.max_y
    )


def containment_overflow(outer: Rect, inner: Rect) -> float:
    """How far `inner` pokes outside `outer`, as a single worst-side distance.

    0.0 means fully contained. Used both as a pass/fail signal and as a solver
    cost gradient, so it must degrade smoothly rather than being boolean.
    """
    return max(
        0.0,
        outer.min_x - inner.min_x,
        outer.min_y - inner.min_y,
        inner.max_x - outer.max_x,
        inner.max_y - outer.max_y,
    )


def closest_point_on_rect(rect: Rect, px: float, py: float) -> Point:
    """Point on (or inside) `rect` nearest to the given point."""
    return (
        min(max(px, rect.min_x), rect.max_x),
        min(max(py, rect.min_y), rect.max_y),
    )


def point_to_rect_distance(rect: Rect, px: float, py: float) -> float:
    """Distance from a point to a rectangle. 0.0 if the point is inside."""
    cx, cy = closest_point_on_rect(rect, px, py)
    return math.hypot(px - cx, py - cy)


def circle_rect_overlap(center: Point, radius: float, rect: Rect) -> float:
    """Penetration depth of a circle into a rectangle.

    Returns 0.0 when they do not intersect, otherwise how far past the
    rectangle's nearest point the circle reaches. Used for heat-zone checks:
    a hot part's thermal radius must not reach a sensitive part.
    """
    dist = point_to_rect_distance(rect, center[0], center[1])
    return max(0.0, radius - dist)


def _orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    """Cross product of AB x AC. Sign gives turn direction, 0 means collinear."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> bool:
    """Whether collinear point P lies within segment AB's bounding box."""
    return (
        min(ax, bx) <= px <= max(ax, bx)
        and min(ay, by) <= py <= max(ay, by)
    )


def segments_intersect(p0: Point, p1: Point, q0: Point, q1: Point) -> bool:
    """Standard orientation-based segment intersection, collinear cases included."""
    d1 = _orientation(*p0, *p1, *q0)
    d2 = _orientation(*p0, *p1, *q1)
    d3 = _orientation(*q0, *q1, *p0)
    d4 = _orientation(*q0, *q1, *p1)

    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        if d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0:
            return True

    if d1 == 0 and _on_segment(*p0, *p1, *q0):
        return True
    if d2 == 0 and _on_segment(*p0, *p1, *q1):
        return True
    if d3 == 0 and _on_segment(*q0, *q1, *p0):
        return True
    if d4 == 0 and _on_segment(*q0, *q1, *p1):
        return True
    return False


def point_in_rect(rect: Rect, px: float, py: float) -> bool:
    return rect.min_x <= px <= rect.max_x and rect.min_y <= py <= rect.max_y


def segment_rect_intersect(p0: Point, p1: Point, rect: Rect) -> bool:
    """True when a segment touches or passes through a rectangle.

    Catches the fully-contained case too, which the edge tests alone would miss.
    """
    if point_in_rect(rect, *p0) or point_in_rect(rect, *p1):
        return True

    corners = [
        (rect.min_x, rect.min_y),
        (rect.max_x, rect.min_y),
        (rect.max_x, rect.max_y),
        (rect.min_x, rect.max_y),
    ]
    for i in range(4):
        if segments_intersect(p0, p1, corners[i], corners[(i + 1) % 4]):
            return True
    return False


def polyline_rect_intersect(path: list[Point], rect: Rect) -> bool:
    """True when any leg of a polyline touches the rectangle."""
    if len(path) == 1:
        return point_in_rect(rect, *path[0])
    for i in range(len(path) - 1):
        if segment_rect_intersect(path[i], path[i + 1], rect):
            return True
    return False


# Counter-clockwise order, so advancing one entry is a 90 degree rotation.
DIRECTIONS = ("+x", "+y", "-x", "-y")


def rotate_direction(direction: str, degrees: int) -> str:
    """Rotate a face direction by a multiple of 90 degrees.

    A keep-out is declared against the part's own body ("the antenna radiates
    off this edge"). When the part is placed rotated, that edge points
    somewhere else in board space, so the direction has to rotate with it --
    otherwise the solver can turn the antenna 90 degrees and the engine keeps
    checking the volume in front of where it used to be.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction: {direction!r}")
    steps = (int(degrees) // 90) % 4
    return DIRECTIONS[(DIRECTIONS.index(direction) + steps) % 4]


def keepout_rect(host: Rect, direction: str, extends_mm: float, width_mm: float) -> Rect:
    """Build the exclusion rectangle projecting off one face of a part.

    The zone is centered on the host's face and extends outward by
    ``extends_mm``, spanning ``width_mm`` across.
    """
    cx, cy = host.center
    half_w = width_mm / 2.0

    if direction == "+x":
        return Rect(host.max_x, cy - half_w, host.max_x + extends_mm, cy + half_w)
    if direction == "-x":
        return Rect(host.min_x - extends_mm, cy - half_w, host.min_x, cy + half_w)
    if direction == "+y":
        return Rect(cx - half_w, host.max_y, cx + half_w, host.max_y + extends_mm)
    if direction == "-y":
        return Rect(cx - half_w, host.min_y - extends_mm, cx + half_w, host.min_y)
    raise ValueError(f"unknown keep-out direction: {direction!r}")
