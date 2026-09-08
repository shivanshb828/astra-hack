"""Geometry primitives, tested on both sides of every boundary.

Threshold rules are only as trustworthy as the arithmetic under them, and the
interesting cases are all degenerate: boxes that touch, circles that graze,
segments that clip a corner.
"""

import math

import pytest

from constraint_engine.geometry import (
    Rect,
    center_distance,
    circle_rect_overlap,
    containment_overflow,
    contains,
    edge_gap,
    keepout_rect,
    overlap_area,
    point_in_rect,
    point_to_rect_distance,
    polyline_rect_intersect,
    rects_overlap,
    segment_rect_intersect,
    segments_intersect,
)


class TestRect:
    def test_from_center(self):
        r = Rect.from_center(10, 20, 4, 6)
        assert (r.min_x, r.min_y, r.max_x, r.max_y) == (8, 17, 12, 23)

    def test_from_origin(self):
        r = Rect.from_origin(1, 2, 10, 20)
        assert (r.min_x, r.min_y, r.max_x, r.max_y) == (1, 2, 11, 22)

    def test_center_and_extent(self):
        r = Rect.from_origin(0, 0, 8, 4)
        assert r.center == (4.0, 2.0)
        assert (r.width, r.height) == (8.0, 4.0)

    def test_inset_shrinks_all_sides(self):
        r = Rect.from_origin(0, 0, 20, 10).inset(2)
        assert (r.min_x, r.min_y, r.max_x, r.max_y) == (2, 2, 18, 8)

    def test_translate(self):
        r = Rect.from_origin(0, 0, 5, 5).translate(3, -2)
        assert (r.min_x, r.min_y) == (3, -2)


class TestEdgeGap:
    def test_touching_boxes_have_zero_gap(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(10, 0, 20, 10)
        assert edge_gap(a, b) == 0.0

    def test_overlapping_boxes_have_zero_gap(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(5, 5, 15, 15)
        assert edge_gap(a, b) == 0.0

    def test_axis_aligned_gap(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(13, 0, 20, 10)
        assert edge_gap(a, b) == pytest.approx(3.0)

    def test_diagonal_gap_is_euclidean(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(13, 14, 20, 20)
        assert edge_gap(a, b) == pytest.approx(5.0)  # 3-4-5

    def test_gap_is_symmetric(self):
        a = Rect(0, 0, 4, 4)
        b = Rect(9, 0, 12, 4)
        assert edge_gap(a, b) == edge_gap(b, a)

    def test_differs_from_center_distance_for_large_parts(self):
        # The reason both metrics are reported: a wide part makes them diverge
        # by more than a typical clearance.
        a = Rect.from_center(0, 0, 30, 16)
        b = Rect.from_center(40, 0, 3, 3)
        assert center_distance(a, b) == pytest.approx(40.0)
        assert edge_gap(a, b) == pytest.approx(23.5)


class TestOverlap:
    def test_touching_is_not_overlapping(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(10, 0, 20, 10)
        assert overlap_area(a, b) == 0.0
        assert not rects_overlap(a, b)

    def test_partial_overlap_area(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(8, 5, 20, 20)
        assert overlap_area(a, b) == pytest.approx(2 * 5)
        assert rects_overlap(a, b)

    def test_contained_box_area_is_its_own(self):
        a = Rect(0, 0, 10, 10)
        b = Rect(2, 2, 4, 4)
        assert overlap_area(a, b) == pytest.approx(4.0)


class TestContainment:
    def test_contains_inclusive_of_edges(self):
        outer = Rect(0, 0, 10, 10)
        assert contains(outer, Rect(0, 0, 10, 10))
        assert contains(outer, Rect(1, 1, 9, 9))

    def test_overflow_zero_when_contained(self):
        outer = Rect(0, 0, 10, 10)
        assert containment_overflow(outer, Rect(2, 2, 8, 8)) == 0.0

    def test_overflow_reports_worst_side(self):
        outer = Rect(0, 0, 10, 10)
        # 3 mm past the right edge, 1 mm past the bottom; worst is 3.
        assert containment_overflow(outer, Rect(-1, 5, 13, 9)) == pytest.approx(3.0)

    def test_overflow_is_a_smooth_gradient(self):
        # The solver follows this value downhill, so it must not be boolean.
        outer = Rect(0, 0, 10, 10)
        far = containment_overflow(outer, Rect(12, 0, 20, 5))
        near = containment_overflow(outer, Rect(9, 0, 17, 5))
        assert far > near > 0


class TestCircleRect:
    def test_point_distance_zero_inside(self):
        r = Rect(0, 0, 10, 10)
        assert point_to_rect_distance(r, 5, 5) == 0.0
        assert point_in_rect(r, 5, 5)

    def test_point_distance_orthogonal(self):
        r = Rect(0, 0, 10, 10)
        assert point_to_rect_distance(r, 14, 5) == pytest.approx(4.0)

    def test_point_distance_diagonal_corner(self):
        r = Rect(0, 0, 10, 10)
        assert point_to_rect_distance(r, 13, 14) == pytest.approx(5.0)

    def test_circle_just_short_does_not_overlap(self):
        r = Rect(10, 0, 20, 10)
        assert circle_rect_overlap((0, 5), 9.9, r) == 0.0

    def test_circle_just_past_overlaps(self):
        r = Rect(10, 0, 20, 10)
        assert circle_rect_overlap((0, 5), 10.1, r) == pytest.approx(0.1)

    def test_circle_exactly_grazing_is_not_an_overlap(self):
        r = Rect(10, 0, 20, 10)
        assert circle_rect_overlap((0, 5), 10.0, r) == 0.0


class TestSegments:
    def test_crossing_segments(self):
        assert segments_intersect((0, 0), (10, 10), (0, 10), (10, 0))

    def test_parallel_segments_do_not_intersect(self):
        assert not segments_intersect((0, 0), (10, 0), (0, 5), (10, 5))

    def test_collinear_touching_segments_intersect(self):
        assert segments_intersect((0, 0), (5, 0), (5, 0), (10, 0))

    def test_segment_through_rect(self):
        r = Rect(0, 0, 10, 10)
        assert segment_rect_intersect((-5, 5), (15, 5), r)

    def test_segment_entirely_inside_rect(self):
        # The corner-edge tests alone would miss this one.
        r = Rect(0, 0, 10, 10)
        assert segment_rect_intersect((2, 2), (8, 8), r)

    def test_segment_clear_of_rect(self):
        r = Rect(0, 0, 10, 10)
        assert not segment_rect_intersect((20, 20), (30, 30), r)

    def test_polyline_intersects_on_any_leg(self):
        r = Rect(0, 0, 10, 10)
        path = [(20, 20), (20, 5), (5, 5)]
        assert polyline_rect_intersect(path, r)

    def test_polyline_clear(self):
        r = Rect(0, 0, 10, 10)
        assert not polyline_rect_intersect([(20, 20), (30, 20), (30, 30)], r)

    def test_single_point_polyline(self):
        r = Rect(0, 0, 10, 10)
        assert polyline_rect_intersect([(5, 5)], r)
        assert not polyline_rect_intersect([(50, 50)], r)


class TestKeepout:
    def test_projects_off_the_named_face(self):
        host = Rect.from_center(10, 10, 4, 2)  # x 8-12, y 9-11
        z = keepout_rect(host, "+y", 8, 6)
        assert (z.min_x, z.max_x) == (7, 13)
        assert (z.min_y, z.max_y) == (11, 19)

    def test_minus_x_direction(self):
        host = Rect.from_center(10, 10, 4, 2)
        z = keepout_rect(host, "-x", 5, 4)
        assert (z.min_x, z.max_x) == (3, 8)
        assert (z.min_y, z.max_y) == (8, 12)

    def test_unknown_direction_rejected(self):
        with pytest.raises(ValueError):
            keepout_rect(Rect(0, 0, 1, 1), "sideways", 5, 5)


def test_center_distance_is_euclidean():
    a = Rect.from_center(0, 0, 2, 2)
    b = Rect.from_center(3, 4, 2, 2)
    assert center_distance(a, b) == pytest.approx(5.0)
    assert center_distance(a, b) == pytest.approx(math.hypot(3, 4))
