"""Loader tolerance.

The parts library is authored by hand, in parallel, by someone who is not
reading the loader. The tests that matter most here are the ones proving that
two different spellings of the same fact produce the same engine behaviour, and
that bad input degrades to a visible warning instead of an exception.
"""

import json

import pytest

from constraint_engine import load_layout, load_parts
from constraint_engine.loader import (
    DEFAULT_AVOID_DISTANCE_MM,
    LoadError,
    layout_to_dict,
    parse_part,
)


def _write(tmp_path, name, payload):
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


class TestClearanceStyleEquivalence:
    """The headline guarantee: both spellings must behave identically."""

    def test_property_and_category_styles_agree_on_required_distance(self, tmp_path):
        # Style A: "keep me 15 mm from anything hot".
        # Style B: "keep me 15 mm from parts in the power_regulator category".
        # Against a hot regulator, both must demand 15 mm.
        style_a = {
            "id": "sensor-a",
            "category": "sensor",
            "dimensions_mm": {"length": 5, "width": 5, "height": 1},
            "sensitive": "high",
            "required_clearance_mm": {"from_hot_components": 15},
        }
        style_b = {
            "id": "sensor-b",
            "category": "sensor",
            "dimensions_mm": {"length": 5, "width": 5, "height": 1},
            "sensitive": "high",
            "min_distance_mm": {"power": 15},
        }
        regulator = {
            "id": "reg",
            "category": "power_regulator",
            "dimensions_mm": {"length": 3, "width": 3, "height": 1},
            "heat_source": True,
        }
        path = _write(tmp_path, "p.json", [style_a, style_b, regulator])
        parts, _ = load_parts(path)

        from constraint_engine.models import Board, Enclosure, Layout, Placement
        from constraint_engine.rules import Scene

        layout = Layout(
            name="t",
            enclosure=Enclosure(100, 100, 10),
            board=Board("b", 100, 100),
            placements=[
                Placement("A", "sensor-a", 10, 10),
                Placement("B", "sensor-b", 10, 40),
                Placement("REG", "reg", 60, 25),
            ],
        )
        scene = Scene(layout, parts)
        assert scene.required_between("A", "REG") == 15.0
        assert scene.required_between("B", "REG") == 15.0

    def test_both_styles_may_coexist_in_one_part(self):
        part = parse_part(
            {
                "id": "mix",
                "category": "sensor",
                "dimensions_mm": {"length": 1, "width": 1, "height": 1},
                "required_clearance_mm": {"from_noisy_components": 18, "rf": 20},
            },
            [],
        )
        assert part.clearances.from_property["noisy"] == 18.0
        assert part.clearances.from_category["wireless"] == 20.0

    def test_strictest_rule_wins_when_duplicated(self):
        part = parse_part(
            {
                "id": "dup",
                "category": "sensor",
                "dimensions_mm": {"length": 1, "width": 1, "height": 1},
                "required_clearance_mm": {"from_hot_components": 10},
                "min_distance_mm": {"hot": 22},
            },
            [],
        )
        assert part.clearances.from_property["hot"] == 22.0


class TestAliases:
    @pytest.mark.parametrize(
        "written,canonical",
        [
            ("rf", "wireless"), ("radio", "wireless"), ("antenna", "wireless"),
            ("mcu", "processor"), ("cpu", "processor"),
            ("power", "power_regulator"), ("dcdc", "power_regulator"),
            ("motor", "driver"), ("lipo", "battery"),
        ],
    )
    def test_category_aliases(self, written, canonical):
        part = parse_part(
            {"id": "x", "category": written,
             "dimensions_mm": {"length": 1, "width": 1, "height": 1}},
            [],
        )
        assert part.category == canonical

    @pytest.mark.parametrize(
        "key", ["from_hot_components", "from_hot", "hot", "heat", "thermal"]
    )
    def test_hot_clearance_aliases(self, key):
        part = parse_part(
            {"id": "x", "category": "sensor",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "required_clearance_mm": {key: 12}},
            [],
        )
        assert part.clearances.from_property["hot"] == 12.0

    @pytest.mark.parametrize(
        "container",
        ["dimensions_mm", "size_mm", "dimensions", "size"],
    )
    def test_dimension_container_aliases(self, container):
        part = parse_part(
            {"id": "x", "category": "sensor",
             container: {"length": 4, "width": 3, "height": 2}},
            [],
        )
        assert (part.length_mm, part.width_mm, part.height_mm) == (4, 3, 2)

    def test_dimensions_as_a_list(self):
        part = parse_part({"id": "x", "category": "s", "dimensions_mm": [4, 3, 2]}, [])
        assert (part.length_mm, part.width_mm, part.height_mm) == (4, 3, 2)

    def test_dimensions_as_flat_keys(self):
        part = parse_part(
            {"id": "x", "category": "s",
             "length_mm": 4, "width_mm": 3, "height_mm": 2},
            [],
        )
        assert (part.length_mm, part.width_mm, part.height_mm) == (4, 3, 2)

    def test_xyz_dimension_keys(self):
        part = parse_part({"id": "x", "category": "s",
                           "dimensions_mm": {"x": 4, "y": 3, "z": 2}}, [])
        assert (part.length_mm, part.width_mm, part.height_mm) == (4, 3, 2)

    def test_numeric_string_with_unit_suffix(self):
        part = parse_part(
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": "4mm", "width": "3", "height": 2}},
            [],
        )
        assert (part.length_mm, part.width_mm, part.height_mm) == (4, 3, 2)


class TestFlagCoercion:
    @pytest.mark.parametrize(
        "value,expected",
        [(True, "high"), (False, "none"), ("high", "high"),
         ("medium", "medium"), ("low", "low"), ("none", "none")],
    )
    def test_sensitivity_spellings(self, value, expected):
        part = parse_part(
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "sensitive": value},
            [],
        )
        assert part.sensitivity == expected

    def test_thermal_risk_string_counts_as_heat_source(self):
        part = parse_part(
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "thermal_risk": "high"},
            [],
        )
        assert part.heat_source

    def test_heat_radius_implies_heat_source(self):
        # Someone who bothers to declare a thermal radius clearly means the
        # part is hot, whether or not they also set the boolean.
        part = parse_part(
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "heat_zone_radius_mm": 9},
            [],
        )
        assert part.heat_source
        assert part.heat_zone_radius_mm == 9

    def test_battery_category_implies_runaway_risk(self):
        part = parse_part(
            {"id": "cell", "category": "lipo",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1}},
            [],
        )
        assert part.thermal_runaway_risk

    def test_patient_contact_alias(self):
        part = parse_part(
            {"id": "e", "category": "electrode",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "patient_contact": True},
            [],
        )
        assert part.skin_contact


class TestDegradesVisibly:
    """Bad data must produce a warning, never an exception or a silent guess."""

    def test_missing_dimensions_warns_and_defaults(self):
        warnings = []
        part = parse_part({"id": "nodims", "category": "sensor"}, warnings)
        assert (part.length_mm, part.width_mm, part.height_mm) == (1, 1, 1)
        assert any("nodims" in w and "dimensions" in w for w in warnings)

    def test_avoid_near_without_distance_warns(self):
        warnings = []
        part = parse_part(
            {"id": "vague", "category": "power",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "avoid_near": ["sensor"]},
            warnings,
        )
        assert part.clearances.from_category["sensor"] == DEFAULT_AVOID_DISTANCE_MM
        assert any("assumed" in w for w in warnings)

    def test_non_numeric_clearance_warns_and_is_ignored(self):
        warnings = []
        part = parse_part(
            {"id": "bad", "category": "sensor",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "required_clearance_mm": {"from_hot_components": "far away"}},
            warnings,
        )
        assert "hot" not in part.clearances.from_property
        assert any("non-numeric" in w for w in warnings)

    def test_unknown_keys_are_ignored_not_fatal(self):
        part = parse_part(
            {"id": "x", "category": "sensor",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1},
             "favourite_colour": "green", "moisture_tolerance": "IP67"},
            [],
        )
        assert part.id == "x"
        assert part.raw["favourite_colour"] == "green"

    def test_non_multiple_of_90_rotation_warns(self, tmp_path):
        path = _write(tmp_path, "l.json", {
            "name": "t",
            "board": {"size_mm": {"length": 50, "width": 50}},
            "placements": [{"ref": "A", "part_id": "p", "pos_mm": [1, 1],
                            "rotation_deg": 45}],
        })
        layout, warnings = load_layout(path)
        assert layout.placements[0].rotation_deg == 0
        assert any("multiple of 90" in w for w in warnings)

    def test_bad_json_raises_load_error(self, tmp_path):
        p = tmp_path / "broken.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(LoadError, match="not valid JSON"):
            load_parts(p)

    def test_missing_file_raises_load_error(self, tmp_path):
        with pytest.raises(LoadError, match="file not found"):
            load_parts(tmp_path / "absent.json")

    def test_empty_parts_list_raises(self, tmp_path):
        with pytest.raises(LoadError, match="no usable parts"):
            load_parts(_write(tmp_path, "empty.json", []))


class TestExplicitZero:
    """Regression: an explicit 0 must survive, not fall back to the default.

    `_as_float(x) or default` silently replaced a legitimate zero, so a layout
    declaring no wall keep-out and no edge margin got 3 mm and 2 mm anyway --
    and then failed components against a boundary its author had opted out of.
    """

    def test_zero_wall_keepout_and_edge_margin_survive(self, tmp_path):
        path = _write(tmp_path, "zero.json", {
            "name": "zeroed",
            "enclosure": {
                "interior_mm": {"length": 100, "width": 40, "height": 7},
                "wall_thickness_mm": 0,
                "wall_keepout_mm": 0,
            },
            "board": {
                "size_mm": {"length": 92, "width": 30, "thickness": 1.0},
                "edge_margin_mm": 0,
                "min_component_gap_mm": 0,
            },
        })
        layout, _ = load_layout(path)
        assert layout.enclosure.wall_keepout_mm == 0.0
        assert layout.enclosure.wall_thickness_mm == 0.0
        assert layout.board.edge_margin_mm == 0.0
        assert layout.board.min_component_gap_mm == 0.0

    def test_zero_mission_thresholds_disable_their_rules(self, tmp_path):
        # A non-wearable product sets these to 0 to opt out entirely.
        path = _write(tmp_path, "nomission.json", {
            "name": "industrial",
            "mission": {
                "skin_contact_clearance_mm": 0,
                "battery_thermal_clearance_mm": 0,
            },
            "board": {"size_mm": {"length": 50, "width": 50}},
        })
        layout, _ = load_layout(path)
        assert layout.mission.skin_contact_clearance_mm == 0.0
        assert layout.mission.battery_thermal_clearance_mm == 0.0

    def test_zero_position_is_not_rewritten(self, tmp_path):
        path = _write(tmp_path, "origin.json", {
            "name": "at-origin",
            "board": {"size_mm": {"length": 50, "width": 50}, "origin_mm": [0, 0, 0]},
            "placements": [{"ref": "A", "part_id": "p", "pos_mm": [0, 0]}],
        })
        layout, _ = load_layout(path)
        assert (layout.placements[0].x_mm, layout.placements[0].y_mm) == (0.0, 0.0)

    def test_missing_values_still_get_defaults(self, tmp_path):
        # The fix must not break the absent case it was protecting.
        path = _write(tmp_path, "absent.json", {"name": "bare", "board": {}})
        layout, _ = load_layout(path)
        assert layout.enclosure.wall_keepout_mm == 3.0
        assert layout.board.edge_margin_mm == 2.0
        assert layout.board.min_component_gap_mm == 0.5

    def test_zero_clearance_opts_out_of_the_check(self, tmp_path):
        from constraint_engine import validate
        from constraint_engine.models import Board, Enclosure, Layout, Placement

        parts_path = _write(tmp_path, "p.json", [
            {"id": "s", "category": "sensor", "sensitive": "high",
             "dimensions_mm": {"length": 4, "width": 4, "height": 1},
             "required_clearance_mm": {"from_noisy_components": 0}},
            {"id": "n", "category": "driver", "noise_source": True,
             "dimensions_mm": {"length": 4, "width": 4, "height": 1}},
        ])
        parts, _ = load_parts(parts_path)
        assert parts["s"].clearances.from_property["noisy"] == 0.0

        layout = Layout(
            name="t",
            enclosure=Enclosure(100, 100, 10, wall_keepout_mm=0),
            board=Board("b", 90, 90, edge_margin_mm=0, min_component_gap_mm=0),
            placements=[Placement("S", "s", 10, 10), Placement("N", "n", 20, 10)],
        )
        results = validate(layout, parts)
        # A declared clearance of zero means "no requirement", so no check fires.
        assert not [c for c in results.checks if c.id.startswith("sep.noise")]


class TestContainerShapes:
    def test_bare_array_accepted(self, tmp_path):
        path = _write(tmp_path, "a.json", [
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1}}
        ])
        parts, _ = load_parts(path)
        assert "x" in parts

    def test_wrapped_object_accepted(self, tmp_path):
        path = _write(tmp_path, "b.json", {"parts": [
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1}}
        ]})
        parts, _ = load_parts(path)
        assert "x" in parts

    def test_duplicate_id_warns(self, tmp_path):
        path = _write(tmp_path, "c.json", [
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 1, "width": 1, "height": 1}},
            {"id": "x", "category": "s",
             "dimensions_mm": {"length": 2, "width": 2, "height": 2}},
        ])
        parts, warnings = load_parts(path)
        assert parts["x"].length_mm == 2  # later entry wins
        assert any("duplicate" in w for w in warnings)


class TestRoundTrip:
    def test_layout_survives_serialize_and_reload(self, tmp_path, naive_layout):
        path = tmp_path / "rt.json"
        path.write_text(json.dumps(layout_to_dict(naive_layout)), encoding="utf-8")
        reloaded, _ = load_layout(path)

        assert reloaded.board.length_mm == naive_layout.board.length_mm
        assert reloaded.board.min_component_gap_mm == naive_layout.board.min_component_gap_mm
        assert reloaded.mission.skin_contact_clearance_mm == (
            naive_layout.mission.skin_contact_clearance_mm
        )
        assert len(reloaded.placements) == len(naive_layout.placements)
        assert len(reloaded.mission_rules) == len(naive_layout.mission_rules)
        assert reloaded.rationales == naive_layout.rationales
        for a, b in zip(reloaded.placements, naive_layout.placements):
            assert (a.ref, a.part_id, a.x_mm, a.y_mm) == (b.ref, b.part_id, b.x_mm, b.y_mm)

    def test_mission_rationales_reach_the_layout(self, naive_layout):
        # Product-specific prose must arrive from data, not from the checker.
        assert "QRS" in naive_layout.rationale_for("sep.noise")
        assert "60601" in naive_layout.rationale_for("safety.skin_contact_temp")

    def test_unknown_family_falls_back(self, naive_layout):
        assert naive_layout.rationale_for("nope.nothing", "fallback") == "fallback"


def test_real_parts_library_loads(parts):
    assert len(parts) == 7
    afe = parts["afe-ecg-24bit"]
    assert afe.sensitivity == "high"
    assert afe.clearances.from_property["noisy"] == 15.0
    assert parts["bat-lipo-150mah"].thermal_runaway_risk
    assert parts["elec-snap-agagcl"].skin_contact
    assert parts["ant-chip-2g4"].keepout.extends_mm == 8
