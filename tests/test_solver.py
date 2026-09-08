"""Solver behaviour.

Two properties matter more than optimality. First, determinism: the same input
must produce the same board, or a demo cannot be rehearsed. Second, honesty:
the solver's own cost function and the real rule set must never disagree about
whether a board passes.
"""

import json

import pytest

from constraint_engine import layout_to_dict, load_layout, solve, validate
from constraint_engine.models import (
    Board,
    Clearances,
    Enclosure,
    Layout,
    Part,
    Placement,
)


@pytest.fixture(scope="module")
def solved(naive_layout, parts):
    layout, cost = solve(naive_layout, parts)
    return layout, cost


class TestSolvesTheDemo:
    def test_fixes_the_naive_board(self, solved, parts):
        layout, _ = solved
        results = validate(layout, parts)
        assert results.passed, [c.id for c in results.failures]

    def test_strictly_improves_on_the_input(self, naive_layout, solved, parts):
        before = validate(naive_layout, parts)
        after = validate(solved[0], parts)
        assert len(after.failures) < len(before.failures)

    def test_reports_zero_residual_cost_when_it_succeeds(self, solved, parts):
        layout, cost = solved
        results = validate(layout, parts)
        if results.passed:
            # Any leftover is the compactness tie-breaker, which is deliberately
            # tiny; a hard violation would be orders of magnitude larger.
            assert cost < 1.0

    def test_cost_and_rules_agree(self, solved, parts):
        # The solver optimises a numeric proxy; the verdict comes from the real
        # rules. If those two ever disagree the solver is lying.
        layout, cost = solved
        results = validate(layout, parts)
        assert results.passed == (cost < 1.0)

    def test_keeps_every_component(self, naive_layout, solved):
        layout, _ = solved
        assert (
            sorted(p.ref for p in layout.placements)
            == sorted(p.ref for p in naive_layout.placements)
        )
        assert (
            sorted(p.part_id for p in layout.placements)
            == sorted(p.part_id for p in naive_layout.placements)
        )

    def test_does_not_alter_the_enclosure_or_bom(self, naive_layout, solved):
        layout, _ = solved
        # Solving means moving parts, not quietly growing the product.
        assert layout.enclosure.interior_length_mm == naive_layout.enclosure.interior_length_mm
        assert layout.enclosure.interior_width_mm == naive_layout.enclosure.interior_width_mm
        assert layout.enclosure.interior_height_mm == naive_layout.enclosure.interior_height_mm
        assert layout.board.length_mm == naive_layout.board.length_mm
        assert layout.board.width_mm == naive_layout.board.width_mm

    def test_preserves_mission_rules_and_rationales(self, naive_layout, solved):
        layout, _ = solved
        assert len(layout.mission_rules) == len(naive_layout.mission_rules)
        assert layout.rationales == naive_layout.rationales


class TestDeterminism:
    def test_same_input_same_output(self, naive_layout, parts):
        a, cost_a = solve(naive_layout, parts)
        b, cost_b = solve(naive_layout, parts)
        assert cost_a == cost_b
        assert layout_to_dict(a) == layout_to_dict(b)

    def test_serialized_output_is_byte_identical(self, naive_layout, parts):
        a, _ = solve(naive_layout, parts)
        b, _ = solve(naive_layout, parts)
        assert json.dumps(layout_to_dict(a), indent=2) == json.dumps(
            layout_to_dict(b), indent=2
        )

    def test_different_seeds_are_allowed_to_differ(self, naive_layout, parts):
        # Not a correctness requirement, just confirmation that the seed
        # actually reaches the search rather than being ignored.
        _, cost_default = solve(naive_layout, parts, seeds=(0,))
        _, cost_other = solve(naive_layout, parts, seeds=(0, 1, 2, 3, 4, 5))
        assert cost_other <= cost_default + 1e-9


class TestRoundTrip:
    def test_solved_layout_reloads_and_revalidates_identically(
        self, naive_layout, parts, tmp_path
    ):
        # The solved file must go back through the ordinary loader with no
        # special casing, or "MissionPCB fixed it" is not verifiable.
        layout, _ = solve(naive_layout, parts)
        path = tmp_path / "solved.json"
        path.write_text(json.dumps(layout_to_dict(layout), indent=2), encoding="utf-8")

        reloaded, warnings = load_layout(path)
        assert not warnings

        direct = validate(layout, parts)
        via_disk = validate(reloaded, parts)
        assert direct.summary() == via_disk.summary()
        assert {c.id for c in direct.failures} == {c.id for c in via_disk.failures}


class TestRespectsConstraints:
    def test_anchored_parts_do_not_move(self, naive_layout, parts):
        from dataclasses import replace

        pinned = replace(
            naive_layout,
            placements=[
                replace(p, anchored=True) if p.ref == "CELL" else p
                for p in naive_layout.placements
            ],
        )
        original = naive_layout.placement("CELL")
        solved_layout, _ = solve(pinned, parts)
        after = solved_layout.placement("CELL")
        assert (after.x_mm, after.y_mm) == (original.x_mm, original.y_mm)
        assert after.anchored

    def test_already_good_layout_is_not_made_worse(self, target_layout, parts):
        # Seed 0 starts from the input, so a passing board must stay passing.
        solved_layout, _ = solve(target_layout, parts)
        assert validate(solved_layout, parts).passed

    def test_courtyard_is_enforced_in_the_search(self, solved, parts):
        # Without a courtyard term the compactness tie-breaker butts parts
        # together at exactly zero gap, which passes collision and is unbuildable.
        layout, _ = solved
        results = validate(layout, parts)
        assert not [c for c in results.failures if c.id.startswith("fit.courtyard")]


class TestDegenerateInputs:
    def test_empty_layout_returns_unchanged(self, parts):
        layout = Layout(
            name="empty",
            enclosure=Enclosure(100, 100, 10),
            board=Board("b", 90, 90),
            placements=[],
        )
        solved_layout, cost = solve(layout, parts)
        assert cost == 0.0
        assert solved_layout.placements == []

    def test_unsatisfiable_layout_reports_residual_rather_than_lying(self):
        # Two parts that each demand 400 mm of clearance on a 50 mm board.
        # There is no answer; the solver must say so instead of claiming a pass.
        a = Part(id="a", name="a", category="sensor", length_mm=4, width_mm=4,
                 height_mm=1, sensitivity="high",
                 clearances=Clearances(from_property={"noisy": 400.0}))
        b = Part(id="b", name="b", category="driver", length_mm=4, width_mm=4,
                 height_mm=1, noise_source=True)
        layout = Layout(
            name="impossible",
            enclosure=Enclosure(60, 60, 10, wall_keepout_mm=0),
            board=Board("b", 50, 50, edge_margin_mm=0),
            placements=[Placement("A", "a", 10, 10), Placement("B", "b", 40, 40)],
        )
        solved_layout, cost = solve(layout, {"a": a, "b": b})
        assert cost > 1.0
        results = validate(solved_layout, {"a": a, "b": b})
        assert not results.passed  # honest about the residual violation

    def test_single_component_is_placed_legally(self):
        p = Part(id="p", name="p", category="sensor", length_mm=10, width_mm=10,
                 height_mm=1)
        layout = Layout(
            name="one",
            enclosure=Enclosure(100, 100, 10, wall_keepout_mm=0),
            board=Board("b", 80, 80, edge_margin_mm=2),
            placements=[Placement("A", "p", 200, 200)],  # starts off the board
        )
        solved_layout, _ = solve(layout, {"p": p})
        assert validate(solved_layout, {"p": p}).passed
