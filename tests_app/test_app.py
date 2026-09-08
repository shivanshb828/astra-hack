"""Tests for the application layer.

Kept out of ``tests/`` on purpose: the constraint engine is stdlib-only so that
Blender's bundled Python can import it, and these tests need pydantic and
fastapi. Run them with the app virtualenv::

    PYTHONPATH=src .venv/bin/python -m pytest tests_app/ -q

The engine's own suite stays runnable with a bare ``python3 -m pytest tests/``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from missionpcb_app.analysis import analyse  # noqa: E402
from missionpcb_app.schema import DesignState  # noqa: E402
from missionpcb_app.store import RevisionConflict, Store  # noqa: E402

LAYOUT = os.path.join(REPO_ROOT, "layouts", "ecg-patch-missionpcb.json")


@pytest.fixture
def design() -> DesignState:
    with open(LAYOUT) as fh:
        raw = json.load(fh)
    return DesignState.from_engine_layout(raw, design_id="test", revision=0)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.db")
    yield s
    s.close()


@pytest.fixture
def refs(design) -> list[str]:
    """Component refs as the layout actually spells them.

    Deliberately not hardcoded. The parts and layout vocabulary is owned
    upstream and gets renamed there; a test that pins `REG` or `CHARGE` breaks
    on a rename that is not a regression.
    """
    return [c.ref for c in design.components]


def collide(design, moved: str, target: str) -> None:
    """Place one component on top of another to force failures."""
    design.component(moved).pos_mm = design.component(target).pos_mm


class TestLayoutRoundTrip:
    """Design state must survive a trip through the engine's own schema."""

    def test_components_survive_import(self, design):
        with open(LAYOUT) as fh:
            expected = [p["ref"] for p in json.load(fh)["placements"]]
        assert [c.ref for c in design.components] == expected

    def test_known_dimensions_survive(self, design):
        """Calibration: authored extents must import unchanged, not rescaled."""
        with open(LAYOUT) as fh:
            raw = json.load(fh)
        size = raw["board"]["size_mm"]
        interior = raw["enclosure"]["interior_mm"]
        assert design.board.length_mm == size["length"]
        assert design.board.width_mm == size["width"]
        assert design.enclosure.interior_length_mm == interior["length"]
        assert design.enclosure.interior_width_mm == interior["width"]

    def test_round_trip_is_stable(self, design):
        once = design.to_engine_layout()
        twice = DesignState.from_engine_layout(
            once, design_id="test", revision=0
        ).to_engine_layout()
        assert once["placements"] == twice["placements"]
        assert once["board"] == twice["board"]

    def test_rotation_snaps_to_ninety_degrees(self, design, refs):
        comp = design.component(refs[0])
        comp.rotation_deg = 100
        assert comp.normalised_rotation() == 90


class TestAnalysisMapping:
    def test_clean_layout_passes_and_declares_gaps(self, design):
        result = analyse(design)
        assert result.summary.get("fail", 0) == 0
        assert result.summary.get("pass", 0) > 0
        # Unsupported categories are declared, never silently omitted.
        not_evaluated = {c.category for c in result.checks
                         if c.status == "not_applicable"}
        assert "trace_current_copper_geometry" in not_evaluated
        assert "patient_connected_spacing" in not_evaluated

    def test_moving_a_part_turns_a_pass_into_a_fail(self, design, refs):
        before = analyse(design)
        assert before.summary.get("fail", 0) == 0

        collide(design, refs[1], refs[0])
        design.revision = 1

        after = analyse(design)
        assert after.summary.get("fail", 0) > 0
        assert after.design_revision == 1

    def test_restoring_the_position_recovers_the_result(self, design, refs):
        original = design.component(refs[1]).pos_mm
        clean = analyse(design).summary

        collide(design, refs[1], refs[0])
        assert analyse(design).summary.get("fail", 0) > 0

        design.component(refs[1]).pos_mm = original
        assert analyse(design).summary == clean

    def test_heuristics_are_not_labelled_as_exact(self, design, refs):
        collide(design, refs[1], refs[0])
        result = analyse(design)
        by_family = {c.check_id.split("::")[0]: c for c in result.checks}
        # Families resting on a declared threshold, not a solved field.
        for family in ("sep.noise", "sep.thermal", "zone.heat_overlap"):
            if family in by_family:
                assert by_family[family].method == "heuristic"
        # Geometry the engine computes exactly stays exact.
        assert by_family["fit.board"].method == "geometric_check"
        assert by_family["fit.overlap"].method == "geometric_check"

    def test_heuristic_checks_carry_their_caveat(self, design, refs):
        collide(design, refs[1], refs[0])
        result = analyse(design)
        heuristics = [c for c in result.checks if c.method == "heuristic"]
        assert heuristics
        assert all(c.input_assumptions for c in heuristics)

    def test_unresolved_part_never_reads_as_pass(self, design, refs):
        """A typo'd part_id must not produce a clean board."""
        design.component(refs[0]).part_id = "does-not-exist"
        result = analyse(design)
        statuses = {c.check_id: c.status for c in result.checks}
        unresolved = [k for k in statuses if k.startswith("data.unresolved_part")]
        assert unresolved
        assert statuses[unresolved[0]] != "pass"

    def test_viz_instructions_declare_frame_and_units(self, design, refs):
        collide(design, refs[1], refs[0])
        result = analyse(design)
        viz = [v for c in result.checks for v in c.viz] + result.zone_viz
        assert viz
        assert all(v.frame in ("enclosure", "board_local") for v in viz)
        assert all(v.units == "mm" for v in viz)


class TestRevisions:
    def test_edit_increments_revision_and_records_one_event(self, store, design, refs):
        store.create_design(design)
        design.component(refs[0]).pos_mm = (20.0, 20.0)
        saved, event = store.commit_revision(
            design, base_revision=0, actor="user", source="drag",
            summary="moved a component",
        )
        assert saved.revision == 1
        assert event.base_revision == 0 and event.result_revision == 1
        assert len(store.history(design.design_id)) == 1

    def test_stale_base_revision_is_rejected(self, store, design):
        store.create_design(design)
        store.commit_revision(design, base_revision=0, actor="user", source="drag")
        with pytest.raises(RevisionConflict):
            # Second edit from the same stale base must not land.
            store.commit_revision(
                design, base_revision=0, actor="user", source="drag"
            )

    def test_restore_appends_rather_than_erasing(self, store, design, refs):
        store.create_design(design)
        design.component(refs[0]).pos_mm = (30.0, 10.0)
        store.commit_revision(design, base_revision=0, actor="user", source="drag")

        original = store.get_design(design.design_id, 0)
        store.commit_revision(
            original, base_revision=1, actor="user", source="restore"
        )

        assert store.current_revision(design.design_id) == 2
        assert store.list_revisions(design.design_id) == [0, 1, 2]
        # The intermediate revision is still readable; history was not rewritten.
        assert len(store.history(design.design_id)) == 2

    def test_state_survives_a_reopen(self, tmp_path, design, refs):
        path = tmp_path / "persist.db"
        first = Store(path)
        first.create_design(design)
        design.component(refs[0]).pos_mm = (42.0, 12.0)
        first.commit_revision(design, base_revision=0, actor="user", source="drag")
        first.close()

        reopened = Store(path)
        assert reopened.current_revision(design.design_id) == 1
        assert reopened.get_design(design.design_id).component(refs[0]).pos_mm == (
            42.0, 12.0,
        )
        reopened.close()

    def test_analysis_is_stored_against_its_revision(self, store, design):
        store.create_design(design)
        job = store.start_job(design.design_id, 0)
        store.finish_job(job, analyse(design))
        assert store.analysis_for_revision(design.design_id, 0) is not None
        # No result claims to describe a revision that was never analysed.
        assert store.analysis_for_revision(design.design_id, 1) is None
