"""Rule behaviour, exercised on synthetic layouts.

Each rule is tested on both sides of its threshold. A rule that only ever gets
tested in the failing direction will happily fail everything.
"""

import pytest

from constraint_engine import validate
from constraint_engine.models import (
    FAIL,
    PASS,
    SKIP,
    WARN,
    Board,
    Clearances,
    Enclosure,
    Keepout,
    Layout,
    MissionProfile,
    MissionRule,
    Opening,
    Part,
    Placement,
    Trace,
)
from constraint_engine.rules import Scene


def mk_part(pid, l=4.0, w=4.0, h=1.0, **kw):
    return Part(id=pid, name=pid, category=kw.pop("category", "sensor"),
                length_mm=l, width_mm=w, height_mm=h, **kw)


def mk_layout(placements, **kw):
    return Layout(
        name=kw.pop("name", "test"),
        enclosure=kw.pop("enclosure", Enclosure(200, 200, 20, wall_keepout_mm=0)),
        board=kw.pop("board", Board("b", 200, 200, thickness_mm=1.0,
                                    edge_margin_mm=0, min_component_gap_mm=0)),
        placements=placements,
        **kw,
    )


def ids_failing(results, prefix):
    return sorted(c.id for c in results.failures if c.id.startswith(prefix))


def status_of(results, check_id):
    for c in results.checks:
        if c.id == check_id:
            return c.status
    return None


class TestBoardFit:
    def test_inside_passes(self):
        parts = {"p": mk_part("p", 10, 10)}
        r = validate(mk_layout([Placement("A", "p", 100, 100)]), parts)
        assert status_of(r, "fit.board::A") == PASS

    def test_overhang_fails_with_measured_overflow(self):
        parts = {"p": mk_part("p", 10, 10)}
        r = validate(mk_layout([Placement("A", "p", 198, 100)]), parts)
        c = next(c for c in r.checks if c.id == "fit.board::A")
        assert c.status == FAIL
        assert c.measured_mm == pytest.approx(3.0)

    def test_edge_margin_is_enforced(self):
        parts = {"p": mk_part("p", 10, 10)}
        board = Board("b", 200, 200, edge_margin_mm=5, min_component_gap_mm=0)
        # Center at 8 puts the left edge at 3, inside the 5 mm margin.
        r = validate(mk_layout([Placement("A", "p", 8, 100)], board=board), parts)
        assert status_of(r, "fit.board::A") == FAIL


class TestHeight:
    def test_under_ceiling_passes(self):
        parts = {"p": mk_part("p", h=3.0)}
        board = Board("b", 100, 100, thickness_mm=1.0, origin_mm=(0, 0, 2),
                      max_component_height_mm=10, edge_margin_mm=0)
        enc = Enclosure(200, 200, 20, wall_keepout_mm=0)
        r = validate(mk_layout([Placement("A", "p", 50, 50)], board=board,
                               enclosure=enc), parts)
        assert status_of(r, "fit.height::A") == PASS

    def test_enclosure_headroom_can_be_the_binding_limit(self):
        # Board budget allows 10 mm, but the lid only leaves 4 mm.
        parts = {"p": mk_part("p", h=6.0)}
        board = Board("b", 100, 100, thickness_mm=1.0, origin_mm=(0, 0, 2),
                      max_component_height_mm=10, edge_margin_mm=0)
        enc = Enclosure(200, 200, 7, wall_keepout_mm=0)
        r = validate(mk_layout([Placement("A", "p", 50, 50)], board=board,
                               enclosure=enc), parts)
        c = next(c for c in r.checks if c.id == "fit.height::A")
        assert c.status == FAIL
        assert c.required_mm == pytest.approx(4.0)


class TestOverlapAndCourtyard:
    def test_collision_reported(self):
        parts = {"p": mk_part("p", 10, 10)}
        r = validate(mk_layout([Placement("A", "p", 50, 50),
                                Placement("B", "p", 55, 50)]), parts)
        assert ids_failing(r, "fit.overlap") == ["fit.overlap::A|B"]

    def test_clear_parts_produce_no_overlap_rows(self):
        parts = {"p": mk_part("p", 10, 10)}
        r = validate(mk_layout([Placement("A", "p", 50, 50),
                                Placement("B", "p", 90, 50)]), parts)
        assert ids_failing(r, "fit.overlap") == []

    def test_touching_parts_fail_courtyard_not_overlap(self):
        # Zero gap is not a collision, but it is not buildable either.
        parts = {"p": mk_part("p", 10, 10)}
        board = Board("b", 200, 200, edge_margin_mm=0, min_component_gap_mm=0.5)
        r = validate(mk_layout([Placement("A", "p", 50, 50),
                                Placement("B", "p", 60, 50)], board=board), parts)
        assert ids_failing(r, "fit.overlap") == []
        assert ids_failing(r, "fit.courtyard") == ["fit.courtyard::A|B"]

    def test_courtyard_satisfied_just_past_threshold(self):
        parts = {"p": mk_part("p", 10, 10)}
        board = Board("b", 200, 200, edge_margin_mm=0, min_component_gap_mm=0.5)
        r = validate(mk_layout([Placement("A", "p", 50, 50),
                                Placement("B", "p", 60.6, 50)], board=board), parts)
        assert ids_failing(r, "fit.courtyard") == []

    def test_collision_is_not_double_reported_as_courtyard(self):
        parts = {"p": mk_part("p", 10, 10)}
        board = Board("b", 200, 200, edge_margin_mm=0, min_component_gap_mm=0.5)
        r = validate(mk_layout([Placement("A", "p", 50, 50),
                                Placement("B", "p", 52, 50)], board=board), parts)
        assert ids_failing(r, "fit.overlap") == ["fit.overlap::A|B"]
        assert ids_failing(r, "fit.courtyard") == []


class TestSeparation:
    def _pair(self, gap_mm, required=15.0):
        sensor = mk_part("s", 4, 4, sensitivity="high",
                         clearances=Clearances(from_property={"noisy": required}))
        noisy = mk_part("n", 4, 4, category="power_regulator", noise_source=True)
        parts = {"s": sensor, "n": noisy}
        # Centers 4 mm apart edge-to-edge requires 4 mm of body plus the gap.
        layout = mk_layout([Placement("S", "s", 50, 50),
                            Placement("N", "n", 50 + 4 + gap_mm, 50)])
        return validate(layout, parts)

    def test_just_short_fails(self):
        r = self._pair(14.9)
        c = next(c for c in r.checks if c.id == "sep.noise::S|N")
        assert c.status == FAIL
        assert c.measured_mm == pytest.approx(14.9)
        assert c.margin_mm == pytest.approx(-0.1)

    def test_exactly_at_threshold_passes(self):
        assert status_of(self._pair(15.0), "sep.noise::S|N") == PASS

    def test_just_over_passes(self):
        assert status_of(self._pair(15.1), "sep.noise::S|N") == PASS

    def test_both_metrics_are_reported(self):
        r = self._pair(20.0)
        c = next(c for c in r.checks if c.id == "sep.noise::S|N")
        assert c.edge_gap_mm == pytest.approx(20.0)
        assert c.center_distance_mm == pytest.approx(24.0)

    def test_center_metric_changes_the_verdict(self):
        # Same geometry, different declared convention: edge gap 14 fails a
        # 15 mm rule, but center distance 18 passes it.
        sensor = mk_part("s", 4, 4, sensitivity="high",
                         clearances=Clearances(from_property={"noisy": 15.0}))
        noisy = mk_part("n", 4, 4, noise_source=True)
        parts = {"s": sensor, "n": noisy}
        places = [Placement("S", "s", 50, 50), Placement("N", "n", 68, 50)]

        edge = validate(mk_layout(places, distance_metric="edge"), parts)
        center = validate(mk_layout(places, distance_metric="center"), parts)
        assert status_of(edge, "sep.noise::S|N") == FAIL
        assert status_of(center, "sep.noise::S|N") == PASS

    def test_strictest_of_the_pair_wins(self):
        # A demands 10 of hot parts; B demands 20 of sensors. Answer is 20.
        a = mk_part("a", 4, 4, sensitivity="high",
                    clearances=Clearances(from_property={"hot": 10.0}))
        b = mk_part("b", 4, 4, category="power_regulator", heat_source=True,
                    clearances=Clearances(from_category={"sensor": 20.0}))
        scene = Scene(
            mk_layout([Placement("A", "a", 10, 10), Placement("B", "b", 60, 10)]),
            {"a": a, "b": b},
        )
        assert scene.required_between("A", "B") == 20.0

    def test_no_declared_clearance_produces_no_check(self):
        a = mk_part("a", sensitivity="high")
        b = mk_part("b", noise_source=True)
        r = validate(mk_layout([Placement("A", "a", 10, 10),
                                Placement("B", "b", 20, 10)]), {"a": a, "b": b})
        assert not any(c.id.startswith("sep.noise") for c in r.checks)


class TestHeatZone:
    def _scene(self, distance, radius=10.0):
        hot = mk_part("h", 4, 4, heat_source=True, heat_zone_radius_mm=radius)
        sens = mk_part("s", 4, 4, sensitivity="high")
        return validate(
            mk_layout([Placement("H", "h", 50, 50),
                       Placement("S", "s", 50 + distance, 50)]),
            {"h": hot, "s": sens},
        )

    def test_sensitive_part_inside_radius_fails(self):
        # Sensitive body starts 2 mm before its center; 11 - 2 = 9 < 10.
        r = self._scene(11.0)
        c = next(c for c in r.checks if c.id == "zone.heat_overlap::H|S")
        assert c.status == FAIL
        assert c.measured_mm == pytest.approx(1.0)

    def test_sensitive_part_outside_radius_passes(self):
        assert status_of(self._scene(13.0), "zone.heat_overlap::H|S") == PASS

    def test_grazing_exactly_is_a_pass(self):
        assert status_of(self._scene(12.0), "zone.heat_overlap::H|S") == PASS


class TestRfKeepout:
    def _layout(self, intruder_pos=None, trace=None):
        ant = mk_part("a", 4, 2, category="wireless", sensitivity="high",
                      keepout=Keepout(extends_mm=8, width_mm=6, direction="+y"))
        blob = mk_part("b", 4, 4)
        places = [Placement("ANT", "a", 50, 50)]
        if intruder_pos:
            places.append(Placement("BLOB", "b", *intruder_pos))
        traces = [Trace("t", trace)] if trace else []
        return validate(mk_layout(places, traces=traces), {"a": ant, "b": blob})

    def test_clear_keepout_passes(self):
        assert status_of(self._layout(), "zone.rf_keepout::ANT") == PASS

    def test_component_in_keepout_fails(self):
        # Zone spans y 51-59 above the antenna.
        r = self._layout(intruder_pos=(50, 55))
        c = next(c for c in r.checks if c.id == "zone.rf_keepout::ANT")
        assert c.status == FAIL
        assert "BLOB" in c.subjects

    def test_component_beside_keepout_passes(self):
        assert status_of(self._layout(intruder_pos=(70, 55)),
                         "zone.rf_keepout::ANT") == PASS

    def test_trace_crossing_keepout_fails(self):
        r = self._layout(trace=[(40, 55), (60, 55)])
        c = next(c for c in r.checks if c.id == "zone.rf_keepout::ANT")
        assert c.status == FAIL
        assert "trace t" in c.message

    def test_trace_clear_of_keepout_passes(self):
        assert status_of(self._layout(trace=[(40, 20), (60, 20)]),
                         "zone.rf_keepout::ANT") == PASS


class TestMissionSafety:
    def _skin(self, gap, clearance=15.0):
        skin = mk_part("e", 4, 4, category="electrode", skin_contact=True)
        hot = mk_part("h", 4, 4, heat_source=True)
        return validate(
            mk_layout(
                [Placement("E", "e", 50, 50), Placement("H", "h", 54 + gap, 50)],
                mission=MissionProfile(skin_contact_clearance_mm=clearance),
            ),
            {"e": skin, "h": hot},
        )

    def test_heat_near_skin_fails(self):
        assert status_of(self._skin(14.0), "safety.skin_contact_temp::E|H") == FAIL

    def test_heat_far_from_skin_passes(self):
        assert status_of(self._skin(16.0), "safety.skin_contact_temp::E|H") == PASS

    def test_skipped_when_nothing_is_hot(self):
        skin = mk_part("e", 4, 4, skin_contact=True)
        r = validate(mk_layout([Placement("E", "e", 50, 50)]), {"e": skin})
        assert status_of(r, "safety.skin_contact_temp") == SKIP

    def test_battery_near_heat_fails(self):
        cell = mk_part("c", 10, 10, category="battery", thermal_runaway_risk=True)
        hot = mk_part("h", 4, 4, heat_source=True)
        r = validate(
            mk_layout([Placement("C", "c", 50, 50), Placement("H", "h", 62, 50)],
                      mission=MissionProfile(battery_thermal_clearance_mm=8)),
            {"c": cell, "h": hot},
        )
        assert status_of(r, "safety.battery_thermal::C|H") == FAIL

    def test_battery_clear_of_heat_passes(self):
        cell = mk_part("c", 10, 10, category="battery", thermal_runaway_risk=True)
        hot = mk_part("h", 4, 4, heat_source=True)
        r = validate(
            mk_layout([Placement("C", "c", 50, 50), Placement("H", "h", 70, 50)],
                      mission=MissionProfile(battery_thermal_clearance_mm=8)),
            {"c": cell, "h": hot},
        )
        assert status_of(r, "safety.battery_thermal::C|H") == PASS


class TestMissionRules:
    def _rule(self, sep, required=35.0, metric="center"):
        p = mk_part("e", 4, 4)
        rule = MissionRule(id="lead", type="min_separation", between=["A", "B"],
                           distance_mm=required, metric=metric, severity="blocker",
                           title="lead vector", rationale="because")
        return validate(
            mk_layout([Placement("A", "e", 50, 50), Placement("B", "e", 50 + sep, 50)],
                      mission_rules=[rule]),
            {"e": p},
        )

    def test_too_close_fails(self):
        c = next(c for c in self._rule(30).checks if c.id == "mission.lead")
        assert c.status == FAIL
        assert c.measured_mm == pytest.approx(30.0)
        assert c.rationale == "because"

    def test_far_enough_passes(self):
        assert status_of(self._rule(40), "mission.lead") == PASS

    def test_exactly_at_threshold_passes(self):
        assert status_of(self._rule(35), "mission.lead") == PASS

    def test_max_separation_inverts_the_test(self):
        p = mk_part("e", 4, 4)
        rule = MissionRule(id="tight", type="max_separation", between=["A", "B"],
                           distance_mm=20, metric="center")
        near = validate(mk_layout([Placement("A", "e", 0, 0),
                                   Placement("B", "e", 10, 0)],
                                  mission_rules=[rule]), {"e": p})
        far = validate(mk_layout([Placement("A", "e", 0, 0),
                                  Placement("B", "e", 30, 0)],
                                 mission_rules=[rule]), {"e": p})
        assert status_of(near, "mission.tight") == PASS
        assert status_of(far, "mission.tight") == FAIL

    def test_missing_ref_skips_rather_than_crashes(self):
        p = mk_part("e", 4, 4)
        rule = MissionRule(id="lead", type="min_separation",
                           between=["A", "GHOST"], distance_mm=10)
        r = validate(mk_layout([Placement("A", "e", 0, 0)], mission_rules=[rule]),
                     {"e": p})
        assert status_of(r, "mission.lead") == SKIP


class TestConnectorAccess:
    def _layout(self, pos, max_reach=12.0, window_center=20.0):
        con = mk_part("c", 8, 4, category="connector")
        enc = Enclosure(100, 40, 10, wall_keepout_mm=0, openings=[
            Opening("win", "-x", window_center, 20, 5, max_reach_mm=max_reach)
        ])
        board = Board("b", 90, 30, origin_mm=(5, 5, 2), edge_margin_mm=0,
                      min_component_gap_mm=0)
        return validate(mk_layout([Placement("C", "c", *pos)], enclosure=enc,
                                  board=board), {"c": con})

    def test_registered_and_within_reach_passes(self):
        # Board x 5 + local 5 = enclosure x 5, well within a 12 mm reach.
        assert status_of(self._layout((5, 15)), "access.connector::C") == PASS

    def test_too_deep_fails(self):
        assert status_of(self._layout((70, 15)), "access.connector::C") == FAIL

    def test_misaligned_with_window_fails(self):
        # Correct depth, but the window spans a different part of the face.
        r = self._layout((5, 15), window_center=38.0)
        c = next(c for c in r.checks if c.id == "access.connector::C")
        assert c.status == FAIL
        assert "offset" in c.message

    def test_skipped_when_no_openings(self):
        con = mk_part("c", 8, 4, category="connector")
        enc = Enclosure(100, 40, 10, wall_keepout_mm=0, openings=[])
        r = validate(mk_layout([Placement("C", "c", 10, 10)], enclosure=enc),
                     {"c": con})
        assert status_of(r, "access.connector") == SKIP


class TestDataQuality:
    def test_unresolved_part_warns_and_is_excluded(self):
        parts = {"real": mk_part("real")}
        r = validate(mk_layout([Placement("A", "real", 50, 50),
                                Placement("GHOST", "missing", 60, 50)]), parts)
        ghost = next(c for c in r.checks if c.id == "data.unresolved_part::GHOST")
        assert ghost.status == WARN
        # And the phantom must not appear in any geometric check.
        assert not any("GHOST" in c.subjects for c in r.checks
                       if c.id.startswith("fit."))

    def test_rationale_comes_from_layout_data(self):
        p = mk_part("s", 4, 4, sensitivity="high",
                    clearances=Clearances(from_property={"noisy": 15.0}))
        n = mk_part("n", 4, 4, noise_source=True)
        layout = mk_layout([Placement("S", "s", 0, 0), Placement("N", "n", 6, 0)],
                           rationales={"sep.noise": "MISSION SPECIFIC TEXT"})
        r = validate(layout, {"s": p, "n": n})
        c = next(c for c in r.checks if c.id == "sep.noise::S|N")
        assert c.rationale == "MISSION SPECIFIC TEXT"

    def test_fallback_rationale_is_generic(self):
        p = mk_part("s", 4, 4, sensitivity="high",
                    clearances=Clearances(from_property={"noisy": 15.0}))
        n = mk_part("n", 4, 4, noise_source=True)
        r = validate(mk_layout([Placement("S", "s", 0, 0),
                                Placement("N", "n", 6, 0)]), {"s": p, "n": n})
        c = next(c for c in r.checks if c.id == "sep.noise::S|N")
        assert c.rationale
        # Generic physics, nothing product-specific baked into the checker.
        assert "ECG" not in c.rationale and "QRS" not in c.rationale


def test_empty_layout_does_not_crash():
    r = validate(mk_layout([]), {})
    assert r.summary()["FAIL"] == 0
