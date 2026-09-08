"""Demo guarantees.

These lock in the behaviour the demo depends on: the naive board fails in
specific, named ways across every constraint family, and the corrected board is
clean. A refactor that quietly changes either of those breaks the story on
stage, so it should break the build here first.
"""

import ast
import json
from pathlib import Path

import pytest

from constraint_engine import build_brief, render_report, validate
from constraint_engine.brief import render_brief_text

# Every failure the naive layout is designed to exhibit. Written out in full
# rather than counted, so a rule that starts firing on the wrong pair is caught
# even if the total happens to stay the same.
EXPECTED_NAIVE_FAILURES = {
    # Signal integrity: the front end is boxed in by power in schematic order.
    "sep.noise::AFE|BUCK",
    "sep.thermal::AFE|BUCK",
    "sep.thermal::AFE|CHG",
    "zone.heat_overlap::BUCK|AFE",
    # Safety: the coin cell sits inside the charger's thermal radius.
    "safety.battery_thermal::CELL|CHG",
    # Mission: electrodes adjacent, so the lead vector cannot resolve.
    "mission.lead_vector",
    # Mission: the ESD clamp sits downstream of what it protects.
    "mission.esd_at_the_boundary",
}

# One failure from each family the mission exercises, so a family cannot
# silently stop being covered.
REQUIRED_FAMILIES = {
    "sep.": "signal separation",
    "zone.": "thermal zones",
    "safety.": "battery safety",
    "mission.": "product-specific rules",
}


class TestNaiveLayout:
    def test_fails_exactly_the_designed_failures(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        assert {c.id for c in results.failures} == EXPECTED_NAIVE_FAILURES

    def test_every_constraint_family_is_exercised(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        failed = {c.id for c in results.failures}
        for prefix, label in REQUIRED_FAMILIES.items():
            assert any(f.startswith(prefix) for f in failed), (
                f"no failure in the {label} family; the demo no longer covers it"
            )

    def test_failures_carry_measured_numbers_and_reasons(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        for c in results.failures:
            assert c.message, f"{c.id} has no message"
            assert c.rationale, f"{c.id} has no rationale"
            assert c.measured_mm is not None, f"{c.id} has no measurement"
            assert c.required_mm is not None, f"{c.id} has no requirement"

    def test_failures_carry_overlays_for_the_simulation(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        # Every failure the 3D scene should draw attention to needs geometry.
        drawable = [c for c in results.failures if not c.id.startswith("data.")]
        assert all(c.overlay is not None for c in drawable)

    def test_only_the_expected_check_is_skipped(self, naive_layout, parts):
        # A SKIP means the engine could not evaluate something, so each one has
        # to be accounted for. Exactly one is expected here: both headers are
        # top-entry, so the enclosure declares no lateral opening and connector
        # accessibility has nothing to measure against.
        results = validate(naive_layout, parts)
        skipped = {c.id for c in results.by_status("SKIP")}
        assert skipped == {"access.connector"}


class TestCorrectedLayout:
    def test_passes_everything(self, target_layout, parts):
        results = validate(target_layout, parts)
        assert results.passed, [c.id for c in results.failures]

    def test_resolves_every_naive_failure(self, naive_layout, target_layout, parts):
        before = {c.id for c in validate(naive_layout, parts).failures}
        after = {c.id for c in validate(target_layout, parts).failures}
        assert before - after == before  # all resolved
        assert after == set()

    def test_uses_the_same_bom(self, naive_layout, target_layout):
        assert (
            sorted(p.part_id for p in naive_layout.placements)
            == sorted(p.part_id for p in target_layout.placements)
        )

    def test_uses_the_same_enclosure_and_board(self, naive_layout, target_layout):
        a, b = naive_layout, target_layout
        assert a.enclosure.interior_length_mm == b.enclosure.interior_length_mm
        assert a.enclosure.interior_width_mm == b.enclosure.interior_width_mm
        assert a.enclosure.interior_height_mm == b.enclosure.interior_height_mm
        assert a.board.length_mm == b.board.length_mm
        assert a.board.width_mm == b.board.width_mm

    def test_margins_are_reported_even_when_passing(self, target_layout, parts):
        # The tight ones are the interesting ones; a reviewer needs to see
        # that battery-to-regulator passed by well under a millimetre.
        results = validate(target_layout, parts)
        battery = next(c for c in results.checks
                       if c.id == "safety.battery_thermal::CELL|CHG")
        assert battery.margin_mm is not None
        assert battery.margin_mm >= 0
        assert battery.measured_mm > battery.required_mm


class TestOverlays:
    def test_overlay_coordinates_land_inside_the_enclosure(self, naive_layout, parts):
        # A label floating outside the shell is a rendering bug that only
        # shows up visually, so assert it numerically instead.
        results = validate(naive_layout, parts)
        enc = naive_layout.enclosure
        margin = 25.0  # labels sit above the board and zones may overhang it

        def check(point, where):
            x, y, z = point
            assert -margin <= x <= enc.interior_length_mm + margin, where
            assert -margin <= y <= enc.interior_width_mm + margin, where
            assert -margin <= z <= enc.interior_height_mm + margin, where

        overlays = [c.overlay for c in results.checks if c.overlay]
        overlays += results.zone_overlays
        assert overlays
        for ov in overlays:
            d = ov.to_dict()
            for key in ("from", "to", "center", "label_at", "marker_at"):
                if key in d:
                    check(d[key], f"{ov.type}.{key}")

    def test_zone_overlays_carry_declared_radii(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        circles = [o for o in results.zone_overlays if o.type == "zone_circle"]
        assert circles
        # The buck's 6 mm thermal radius comes from the parts data, so the
        # renderer never has to hardcode it.
        assert any(o.radius_mm == 6 for o in circles)  # BUCK thermal radius

    def test_every_overlay_names_a_collection(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        all_overlays = [c.overlay for c in results.checks if c.overlay]
        all_overlays += results.zone_overlays
        assert all(o.collection for o in all_overlays)


class TestSerializedOutput:
    def test_results_json_is_serializable_and_complete(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        blob = json.dumps(results.to_dict())
        data = json.loads(blob)
        assert data["layout"] == naive_layout.name
        assert data["passed"] is False
        assert len(data["checks"]) == len(results.checks)
        assert data["component_positions"]
        # Failures sort first so a consumer reading top-down sees them.
        assert data["checks"][0]["status"] == "FAIL"

    def test_component_positions_give_both_coordinate_frames(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        pos = next(p for p in results.component_positions if p["ref"] == "AFE")
        ox, oy, oz = naive_layout.board.origin_mm
        bx, by = pos["board_xy_mm"]
        ex, ey, ez = pos["enclosure_xyz_mm"]
        assert ex == pytest.approx(ox + bx)
        assert ey == pytest.approx(oy + by)
        assert ez == pytest.approx(oz + naive_layout.board.thickness_mm)

    def test_report_renders_and_states_its_limits(self, naive_layout, parts):
        md = render_report(validate(naive_layout, parts), "parts.json", "layout.json")
        assert "# Validation Report" in md
        assert "## Verdict: FAIL" in md
        assert "Required before manufacturing" in md
        # The honesty section is not optional.
        assert "not a solved thermal field" in md
        assert "Not evaluated at all" in md

    def test_report_is_deterministic(self, naive_layout, parts):
        a = render_report(validate(naive_layout, parts))
        b = render_report(validate(naive_layout, parts))
        assert a == b


class TestExplainBrief:
    def test_brief_carries_facts_not_prose_to_invent(self, naive_layout, parts):
        results = validate(naive_layout, parts)
        brief = build_brief(results, naive_layout, parts)
        assert brief["summary"]["verdict"] == "FAIL"
        assert len(brief["findings"]) == len(results.failures)
        for f in brief["findings"]:
            assert f["measured_mm"] is not None
            assert f["computed_statement"]
            assert f["part_context"]

    def test_brief_forbids_recomputation(self, naive_layout, parts):
        brief = build_brief(validate(naive_layout, parts), naive_layout, parts)
        text = brief["instructions"].lower()
        assert "never recompute" in text
        assert "quote the measured numbers" in text

    def test_brief_includes_part_behaviour_context(self, naive_layout, parts):
        brief = build_brief(validate(naive_layout, parts), naive_layout, parts)
        battery = [
            f for f in brief["findings"]
            if f["id"].startswith("safety.battery_thermal")
        ]
        assert battery
        ctx = battery[0]["part_context"]["CELL"]
        assert "thermal runaway risk" in ctx["behaviour"]

    def test_brief_is_json_serializable(self, naive_layout, parts):
        brief = build_brief(validate(naive_layout, parts), naive_layout, parts)
        json.dumps(brief)

    def test_brief_text_renders(self, naive_layout, parts):
        brief = build_brief(validate(naive_layout, parts), naive_layout, parts)
        text = render_brief_text(brief)
        assert "FINDINGS" in text
        assert "MODEL LIMITATIONS" in text
        assert "THRESHOLDS IN FORCE" in text

    def test_passing_layout_produces_no_findings(self, target_layout, parts):
        brief = build_brief(validate(target_layout, parts), target_layout, parts)
        assert brief["findings"] == []
        assert brief["summary"]["verdict"] == "PASS"


class TestBlenderCompatibility:
    """The package must import inside Blender's bundled Python, which has no pip."""

    ALLOWED = {
        "__future__", "json", "math", "random", "argparse", "sys", "typing",
        "pathlib", "dataclasses", "collections", "itertools", "functools",
        "copy", "os", "re", "textwrap", "enum",
    }

    def test_no_third_party_imports(self, repo):
        package = repo / "src" / "constraint_engine"
        offenders = []
        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:  # relative import within the package
                        continue
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                for name in names:
                    if name and name not in self.ALLOWED:
                        offenders.append(f"{path.name}: {name}")
        assert not offenders, (
            "third-party imports break the Blender import path: " + ", ".join(offenders)
        )

    def test_package_imports_without_the_repo_on_the_path(self, repo):
        # Mirrors what the Blender script does: point sys.path at src/ and
        # import, with no installation step.
        import subprocess
        import sys

        code = (
            "import sys; sys.path.insert(0, %r);"
            "import constraint_engine as ce;"
            "print(ce.__version__)" % str(repo / "src")
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, cwd="/"
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip()
