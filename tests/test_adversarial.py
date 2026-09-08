"""Regression tests for findings from the adversarial review.

Every case here is a way the engine could return a confidently wrong answer.
They are grouped separately from the feature tests because the failure mode
they guard against is the same one: a check that silently does not run reads
exactly like a check that passed.
"""

import json

import pytest

from constraint_engine import load_layout, load_parts, solve, validate
from constraint_engine.geometry import (
    Rect,
    containment_overflow,
    edge_gap,
    keepout_rect,
    rotate_direction,
)
from constraint_engine.loader import _as_float, parse_part
from constraint_engine.models import (
    Board,
    Enclosure,
    Keepout,
    Layout,
    Part,
    Placement,
    Trace,
)


def _write(tmp_path, name, payload):
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


class TestNonFiniteInput:
    """NaN silently disabled containment: `max(0.0, nan)` returns 0.0."""

    @pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf", "1e400"])
    def test_non_finite_strings_are_rejected(self, value):
        assert _as_float(value) is None

    def test_non_finite_floats_are_rejected(self):
        assert _as_float(float("nan")) is None
        assert _as_float(float("inf")) is None

    def test_finite_values_still_parse(self):
        assert _as_float(15) == 15.0
        assert _as_float("15mm") == 15.0
        assert _as_float(0) == 0.0
        assert _as_float(-3.5) == -3.5

    def test_nan_dimension_falls_back_with_a_warning(self):
        warnings = []
        part = parse_part(
            {"id": "bad", "category": "sensor",
             "dimensions_mm": {"length": "nan", "width": 5, "height": 1}},
            warnings,
        )
        assert (part.length_mm, part.width_mm, part.height_mm) == (1.0, 1.0, 1.0)
        assert any("dimensions" in w for w in warnings)

    def test_nan_geometry_would_have_passed_containment(self):
        # Documents why the loader gate matters: the geometry layer cannot
        # defend itself, because every comparison against NaN is False.
        nan = float("nan")
        assert containment_overflow(Rect(0, 0, 10, 10), Rect(nan, nan, nan, nan)) == 0.0

    def test_nan_threshold_cannot_reach_a_rule(self, tmp_path):
        path = _write(tmp_path, "p.json", [
            {"id": "s", "category": "sensor", "sensitive": "high",
             "dimensions_mm": {"length": 4, "width": 4, "height": 1},
             "required_clearance_mm": {"from_noisy_components": "nan"}},
        ])
        parts, warnings = load_parts(path)
        assert "noisy" not in parts["s"].clearances.from_property
        assert any("non-numeric" in w for w in warnings)


class TestUnknownSensitivity:
    """An unrecognised word turned off every sensor rule without saying so."""

    def test_unrecognised_spelling_warns(self):
        warnings = []
        part = parse_part(
            {"id": "x", "category": "sensor",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "sensitive": "very high"},
            warnings,
        )
        assert part.sensitivity == "none"
        assert any("unrecognised sensitivity" in w for w in warnings)
        assert any("disables" in w for w in warnings)

    def test_recognised_spellings_do_not_warn(self):
        for value in ("high", "medium", "low", "none", True, False):
            warnings = []
            parse_part(
                {"id": "x", "category": "sensor",
                 "dimensions_mm": {"length": 1, "width": 1, "height": 1},
                 "sensitive": value},
                warnings,
            )
            assert not [w for w in warnings if "sensitivity" in w], value

    def test_absent_field_does_not_warn(self):
        warnings = []
        parse_part({"id": "x", "category": "sensor",
                    "dimensions_mm": {"length": 1, "width": 1, "height": 1}}, warnings)
        assert not warnings


class TestUnresolvedPartsAreNotAPass:
    """A board the engine never inspected must not report clean."""

    def test_validate_does_not_pass_with_an_unresolved_part(self):
        layout = Layout(
            name="typo",
            enclosure=Enclosure(100, 100, 10),
            board=Board("b", 90, 90),
            placements=[Placement("GHOST", "no-such-part", 10, 10)],
        )
        results = validate(layout, {})
        assert not results.passed
        assert results.unevaluated

    def test_solver_does_not_claim_success_on_an_unresolved_board(self):
        layout = Layout(
            name="typo",
            enclosure=Enclosure(100, 100, 10),
            board=Board("b", 90, 90),
            placements=[Placement("GHOST", "no-such-part", 10, 10)],
        )
        _, cost = solve(layout, {})
        assert cost == float("inf")

    def test_a_genuinely_empty_board_is_still_a_pass(self):
        layout = Layout(
            name="empty",
            enclosure=Enclosure(100, 100, 10),
            board=Board("b", 90, 90),
            placements=[],
        )
        assert validate(layout, {}).passed
        assert solve(layout, {})[1] == 0.0

    def test_a_resolved_board_is_unaffected(self, naive_layout, target_layout, parts):
        assert validate(target_layout, parts).passed
        assert not validate(naive_layout, parts).passed


class TestKeepoutFollowsRotation:
    """The zone was computed in world axes, so rotating the part aimed it wrong."""

    @pytest.mark.parametrize(
        "start,degrees,expected",
        [("+x", 0, "+x"), ("+x", 90, "+y"), ("+x", 180, "-x"), ("+x", 270, "-y"),
         ("+y", 90, "-x"), ("-x", 90, "-y"), ("-y", 90, "+x"), ("+x", 360, "+x")],
    )
    def test_direction_rotates(self, start, degrees, expected):
        assert rotate_direction(start, degrees) == expected

    def test_unknown_direction_rejected(self):
        with pytest.raises(ValueError):
            rotate_direction("northeast", 90)

    def test_rotated_antenna_moves_its_zone(self):
        ant = Part(id="a", name="a", category="wireless", length_mm=4, width_mm=2,
                   height_mm=1, sensitivity="high",
                   keepout=Keepout(extends_mm=8, width_mm=6, direction="+y"))
        blob = Part(id="b", name="b", category="sensor", length_mm=4, width_mm=4,
                    height_mm=1)
        parts = {"a": ant, "b": blob}

        def check(rotation, blob_pos):
            layout = Layout(
                name="t",
                enclosure=Enclosure(200, 200, 20, wall_keepout_mm=0),
                board=Board("b", 200, 200, edge_margin_mm=0, min_component_gap_mm=0),
                placements=[Placement("ANT", "a", 50, 50, rotation_deg=rotation),
                            Placement("BLOB", "b", *blob_pos)],
            )
            results = validate(layout, parts)
            return next(c for c in results.checks
                        if c.id == "zone.rf_keepout::ANT").status

        # Unrotated: zone projects +y, so an obstruction above is caught and
        # one to the left is not.
        assert check(0, (50, 56)) == "FAIL"
        assert check(0, (42, 50)) == "PASS"
        # Rotated 90 degrees the antenna faces -x, so the verdicts swap.
        assert check(90, (50, 56)) == "PASS"
        assert check(90, (42, 50)) == "FAIL"


class TestTraceWidthCounts:
    """Testing the bare centerline let half a track sit inside the zone."""

    def _status(self, trace_width, trace_y):
        ant = Part(id="a", name="a", category="wireless", length_mm=4, width_mm=2,
                   height_mm=1, sensitivity="high",
                   keepout=Keepout(extends_mm=8, width_mm=6, direction="+y"))
        layout = Layout(
            name="t",
            enclosure=Enclosure(200, 200, 20, wall_keepout_mm=0),
            board=Board("b", 200, 200, edge_margin_mm=0, min_component_gap_mm=0),
            placements=[Placement("ANT", "a", 50, 50)],
            traces=[Trace("t", [(40, trace_y), (60, trace_y)], width_mm=trace_width)],
        )
        results = validate(layout, {"a": ant})
        return next(c for c in results.checks
                    if c.id == "zone.rf_keepout::ANT").status

    def test_wide_trace_just_outside_the_boundary_still_intrudes(self):
        # Zone starts at y=51. A 2 mm track centred at y=50.5 has copper from
        # 49.5 to 51.5, so 0.5 mm of it is inside.
        assert self._status(trace_width=2.0, trace_y=50.5) == "FAIL"

    def test_a_hairline_trace_at_the_same_place_is_clear(self):
        assert self._status(trace_width=0.1, trace_y=50.5) == "PASS"

    def test_a_trace_well_clear_stays_clear(self):
        assert self._status(trace_width=2.0, trace_y=20.0) == "PASS"


class TestBoundarySemantics:
    """Components and traces disagreed about what touching a keep-out meant."""

    def test_component_exactly_tangent_to_the_zone_intrudes(self):
        ant = Part(id="a", name="a", category="wireless", length_mm=4, width_mm=2,
                   height_mm=1, sensitivity="high",
                   keepout=Keepout(extends_mm=8, width_mm=6, direction="+y"))
        blob = Part(id="b", name="b", category="sensor", length_mm=4, width_mm=4,
                    height_mm=1)
        # Antenna body spans y 49-51, so the zone starts at 51. A 4 mm part
        # centred at y=53 spans 51-55 and shares exactly the y=51 edge.
        layout = Layout(
            name="t",
            enclosure=Enclosure(200, 200, 20, wall_keepout_mm=0),
            board=Board("b", 200, 200, edge_margin_mm=0, min_component_gap_mm=0),
            placements=[Placement("ANT", "a", 50, 50),
                        Placement("BLOB", "b", 50, 53)],
        )
        zone = keepout_rect(Rect.from_center(50, 50, 4, 2), "+y", 8, 6)
        assert edge_gap(zone, Rect.from_center(50, 53, 4, 4)) == 0.0
        status = next(
            c for c in validate(layout, {"a": ant, "b": blob}).checks
            if c.id == "zone.rf_keepout::ANT"
        ).status
        assert status == "FAIL"


class TestDemoStillHolds:
    """None of the above changed the demo's behaviour."""

    def test_naive_still_fails_its_designed_set(self, naive_layout, parts):
        # Seven with the real catalog parts; the exact ids are pinned in
        # test_golden.py.
        assert len(validate(naive_layout, parts).failures) == 7

    def test_target_still_passes(self, target_layout, parts):
        assert validate(target_layout, parts).passed

    def test_solver_still_solves(self, naive_layout, parts):
        solved, _ = solve(naive_layout, parts)
        assert validate(solved, parts).passed

    def test_shipped_parts_library_loads_without_warnings(self, repo):
        # The library is generated from the catalog now, so every clearance is
        # stated explicitly and nothing has to be assumed at load time.
        _, warnings = load_parts(repo / "parts" / "ecg-patch-parts.json")
        assert warnings == []

    def test_shipped_layouts_load_without_warnings(self, repo):
        for name in ("ecg-patch-naive", "ecg-patch-missionpcb"):
            _, warnings = load_layout(repo / "layouts" / f"{name}.json")
            assert not warnings, (name, warnings)
