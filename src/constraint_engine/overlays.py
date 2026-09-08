"""Turn constraint results into Blender-ready drawing instructions.

Checks are computed in board-local millimetres, but the Blender scene is built
in enclosure space. Everything emitted here is already transformed into
enclosure world mm, so the consuming script needs only a single mm -> m scale
and never has to redo geometry.
"""

from __future__ import annotations

from .geometry import Rect
from .models import Board, Overlay

# Collection names match those already specified in the Astra demo prompt.
OVERLAY_COLLECTION = "03_Constraint_Overlays"

RED = (0.90, 0.15, 0.15)
GREEN = (0.15, 0.80, 0.30)
AMBER = (0.95, 0.65, 0.10)
GREY = (0.55, 0.55, 0.58)
ORANGE = (0.95, 0.45, 0.10)
PURPLE = (0.60, 0.30, 0.85)

# Vertical offsets above the board surface, in mm, so overlays are legible
# rather than z-fighting with the parts they describe.
LINE_Z = 3.0
LABEL_Z = 9.0
ZONE_Z = 0.4


class OverlayBuilder:
    """Transforms board-local geometry into enclosure-space overlays."""

    def __init__(self, board: Board):
        self.board = board
        ox, oy, oz = board.origin_mm
        self._ox = ox
        self._oy = oy
        # Board top surface: components and overlays sit on top of the PCB.
        self._surface_z = oz + board.thickness_mm

    def point(self, x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
        """Board-local point -> enclosure world mm."""
        return (
            round(self._ox + x, 3),
            round(self._oy + y, 3),
            round(self._surface_z + z, 3),
        )

    def measure_line(
        self,
        a: Rect,
        b: Rect,
        label: str,
        passing: bool,
    ) -> Overlay:
        """A dimension line between two footprints, coloured by verdict."""
        ax, ay = a.center
        bx, by = b.center
        color = GREEN if passing else RED
        mid_x, mid_y = (ax + bx) / 2.0, (ay + by) / 2.0
        return Overlay(
            type="measure_line",
            color=color,
            collection=OVERLAY_COLLECTION,
            start=self.point(ax, ay, LINE_Z),
            end=self.point(bx, by, LINE_Z),
            label=label,
            label_at=self.point(mid_x, mid_y, LABEL_Z),
            marker="check" if passing else "x",
            marker_at=self.point(mid_x, mid_y, LINE_Z),
        )

    def marker(
        self,
        rect: Rect,
        label: str,
        passing: bool,
    ) -> Overlay:
        """A standalone verdict badge over a single component."""
        cx, cy = rect.center
        return Overlay(
            type="marker",
            color=GREEN if passing else RED,
            collection=OVERLAY_COLLECTION,
            center=self.point(cx, cy, LINE_Z),
            label=label,
            label_at=self.point(cx, cy, LABEL_Z),
            marker="check" if passing else "x",
            marker_at=self.point(cx, cy, LINE_Z),
        )

    def zone_circle(
        self,
        center_x: float,
        center_y: float,
        radius_mm: float,
        label: str,
        color: tuple[float, float, float] = ORANGE,
    ) -> Overlay:
        """A thermal/noise radius drawn flat on the board."""
        return Overlay(
            type="zone_circle",
            color=color,
            collection=OVERLAY_COLLECTION,
            center=self.point(center_x, center_y, ZONE_Z),
            radius_mm=radius_mm,
            label=label,
            label_at=self.point(center_x, center_y + radius_mm, LABEL_Z),
        )

    def zone_rect(
        self,
        rect: Rect,
        label: str,
        color: tuple[float, float, float] = PURPLE,
    ) -> Overlay:
        """A rectangular exclusion zone, e.g. an antenna keep-out."""
        cx, cy = rect.center
        return Overlay(
            type="zone_rect",
            color=color,
            collection=OVERLAY_COLLECTION,
            center=self.point(cx, cy, ZONE_Z),
            size_mm=(round(rect.width, 3), round(rect.height, 3)),
            label=label,
            label_at=self.point(cx, cy, LABEL_Z),
        )

    def text(
        self,
        x: float,
        y: float,
        label: str,
        color: tuple[float, float, float] = GREY,
    ) -> Overlay:
        return Overlay(
            type="text",
            color=color,
            collection=OVERLAY_COLLECTION,
            center=self.point(x, y, LABEL_Z),
            label=label,
            label_at=self.point(x, y, LABEL_Z),
        )
