"""Command line interface.

The CLI is the surface the rest of the team actually types, and its exit codes
are what a CI step would branch on, so both are worth pinning down.
"""

import json
from pathlib import Path

import pytest

from constraint_engine.cli import EXIT_BAD_INPUT, EXIT_FAILURES, EXIT_OK, main
from constraint_engine.overlays import OverlayBuilder
from constraint_engine.models import Board

PARTS = "parts/ecg-patch-parts.json"
NAIVE = "layouts/ecg-patch-naive.json"
TARGET = "layouts/ecg-patch-missionpcb.json"


@pytest.fixture(autouse=True)
def _in_repo(repo, monkeypatch):
    """Every CLI invocation runs with the repo root as the working directory."""
    monkeypatch.chdir(repo)


class TestValidate:
    def test_failing_layout_exits_one(self, tmp_path):
        code = main(["validate", "--parts", PARTS, "--layout", NAIVE,
                     "--out", str(tmp_path)])
        assert code == EXIT_FAILURES

    def test_passing_layout_exits_zero(self, tmp_path):
        code = main(["validate", "--parts", PARTS, "--layout", TARGET,
                     "--out", str(tmp_path)])
        assert code == EXIT_OK

    def test_writes_both_artifacts(self, tmp_path):
        main(["validate", "--parts", PARTS, "--layout", NAIVE, "--out", str(tmp_path)])
        results = tmp_path / "validation_results.json"
        report = tmp_path / "validation_report.md"
        assert results.exists() and report.exists()
        data = json.loads(results.read_text())
        assert data["passed"] is False
        assert "# Validation Report" in report.read_text()

    def test_creates_missing_output_directory(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        main(["validate", "--parts", PARTS, "--layout", NAIVE, "--out", str(nested)])
        assert (nested / "validation_results.json").exists()

    def test_now_flag_is_recorded(self, tmp_path):
        main(["validate", "--parts", PARTS, "--layout", NAIVE,
              "--out", str(tmp_path), "--now", "2026-09-08T12:00:00Z"])
        data = json.loads((tmp_path / "validation_results.json").read_text())
        assert data["generated_at"] == "2026-09-08T12:00:00Z"

    def test_omitting_now_keeps_output_reproducible(self, tmp_path):
        # Two runs with no timestamp must produce identical bytes, so the
        # artifacts can be committed and diffed.
        a, b = tmp_path / "a", tmp_path / "b"
        main(["validate", "--parts", PARTS, "--layout", NAIVE, "--out", str(a)])
        main(["validate", "--parts", PARTS, "--layout", NAIVE, "--out", str(b)])
        assert (a / "validation_results.json").read_bytes() == (
            b / "validation_results.json"
        ).read_bytes()
        assert (a / "validation_report.md").read_bytes() == (
            b / "validation_report.md"
        ).read_bytes()


class TestSolve:
    def test_solves_naive_and_exits_zero(self, tmp_path):
        out = tmp_path / "solved.json"
        code = main(["solve", "--parts", PARTS, "--layout", NAIVE, "--out", str(out)])
        assert code == EXIT_OK
        assert out.exists()

    def test_output_is_a_loadable_layout(self, tmp_path):
        from constraint_engine import load_layout

        out = tmp_path / "solved.json"
        main(["solve", "--parts", PARTS, "--layout", NAIVE, "--out", str(out)])
        layout, warnings = load_layout(out)
        assert not warnings
        assert len(layout.placements) == 8

    def test_name_flag_renames_the_layout(self, tmp_path):
        out = tmp_path / "solved.json"
        main(["solve", "--parts", PARTS, "--layout", NAIVE, "--out", str(out),
              "--name", "Custom Name"])
        assert json.loads(out.read_text())["name"] == "Custom Name"

    def test_report_dir_writes_a_report(self, tmp_path):
        out = tmp_path / "solved.json"
        reports = tmp_path / "reports"
        main(["solve", "--parts", PARTS, "--layout", NAIVE, "--out", str(out),
              "--report-dir", str(reports)])
        assert (reports / "validation_report.md").exists()

    def test_seeds_flag_is_accepted(self, tmp_path):
        out = tmp_path / "solved.json"
        code = main(["solve", "--parts", PARTS, "--layout", NAIVE,
                     "--out", str(out), "--seeds", "0"])
        assert code in (EXIT_OK, EXIT_FAILURES)


class TestCompare:
    def test_exit_code_reflects_the_worst_layout(self, tmp_path):
        # One failing layout in the set means a non-zero exit, even though the
        # other passes.
        code = main(["compare", "--parts", PARTS, "--layouts", NAIVE, TARGET])
        assert code == EXIT_FAILURES

    def test_all_passing_exits_zero(self):
        assert main(["compare", "--parts", PARTS, "--layouts", TARGET]) == EXIT_OK

    def test_out_writes_one_file_per_layout(self, tmp_path):
        main(["compare", "--parts", PARTS, "--layouts", NAIVE, TARGET,
              "--out", str(tmp_path)])
        assert (tmp_path / "ecg-patch-naive_results.json").exists()
        assert (tmp_path / "ecg-patch-missionpcb_results.json").exists()

    def test_reports_which_checks_changed(self, capsys, tmp_path):
        main(["compare", "--parts", PARTS, "--layouts", NAIVE, TARGET])
        out = capsys.readouterr().out
        assert "Resolved going from" in out
        assert "mission.lead_vector" in out


class TestExplain:
    def test_writes_both_brief_formats(self, tmp_path):
        code = main(["explain", "--parts", PARTS, "--layout", NAIVE,
                     "--out", str(tmp_path)])
        assert code == EXIT_FAILURES  # the layout still fails
        assert (tmp_path / "explain_brief.json").exists()
        assert (tmp_path / "explain_brief.txt").exists()

    def test_brief_lists_every_failure(self, tmp_path):
        main(["explain", "--parts", PARTS, "--layout", NAIVE, "--out", str(tmp_path)])
        brief = json.loads((tmp_path / "explain_brief.json").read_text())
        assert len(brief["findings"]) == 10

    def test_include_passes_widens_the_brief(self, tmp_path):
        main(["explain", "--parts", PARTS, "--layout", NAIVE,
              "--out", str(tmp_path), "--include-passes"])
        brief = json.loads((tmp_path / "explain_brief.json").read_text())
        assert len(brief["findings"]) == 45

    def test_stdout_prints_the_brief(self, capsys, tmp_path):
        main(["explain", "--parts", PARTS, "--layout", NAIVE,
              "--out", str(tmp_path), "--stdout"])
        out = capsys.readouterr().out
        assert "FINDINGS" in out
        assert "Never recompute" in out


class TestBadInput:
    def test_missing_parts_file_exits_two(self, tmp_path, capsys):
        code = main(["validate", "--parts", str(tmp_path / "nope.json"),
                     "--layout", NAIVE, "--out", str(tmp_path)])
        assert code == EXIT_BAD_INPUT
        assert "file not found" in capsys.readouterr().err

    def test_malformed_json_exits_two(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code = main(["validate", "--parts", str(bad), "--layout", NAIVE,
                     "--out", str(tmp_path)])
        assert code == EXIT_BAD_INPUT

    def test_unknown_subcommand_is_rejected(self):
        with pytest.raises(SystemExit):
            main(["frobnicate"])

    def test_missing_required_flag_is_rejected(self):
        with pytest.raises(SystemExit):
            main(["validate", "--parts", PARTS])


class TestWarningsSurface:
    def test_loader_warnings_reach_stderr_and_the_report(self, tmp_path, capsys):
        main(["validate", "--parts", PARTS, "--layout", NAIVE, "--out", str(tmp_path)])
        captured = capsys.readouterr()
        assert "avoid_near" in captured.err
        report = (tmp_path / "validation_report.md").read_text()
        assert "Data warnings" in report


class TestTextOverlay:
    """`text` is advertised in the contract doc, so it needs to work."""

    def test_text_overlay_serializes_with_a_position(self):
        builder = OverlayBuilder(Board("b", 90, 40, thickness_mm=1.0,
                                       origin_mm=(4, 5, 2)))
        overlay = builder.text(10, 20, "Orbit and select components")
        data = overlay.to_dict()
        assert data["type"] == "text"
        assert data["label"] == "Orbit and select components"
        # Board origin plus local offset, on top of the board surface.
        assert data["center"][0] == pytest.approx(14.0)
        assert data["center"][1] == pytest.approx(25.0)
        assert data["label_at"] == data["center"]
        assert data["collection"] == "03_Constraint_Overlays"
