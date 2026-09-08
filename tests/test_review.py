"""The JSON-in / JSON-out review contract.

This is an interface with another team's system, so the tests here are mostly
about the promises that interface makes rather than about geometry: identity is
echoed and never inferred, every component is named in all three vocabularies,
approximations are labelled as such, and unusable input fails loudly instead of
being quietly worked around.
"""

import copy
import hashlib
import json

import pytest

from constraint_engine.review import (
    LIMITATION_BY_FAMILY,
    METHOD_BY_FAMILY,
    SCHEMA_VERSION,
    UNSUPPORTED,
    SubmissionError,
    review,
)

KICAD = {"ELEC_A": "J1", "ELEC_B": "J2", "ESD": "D1", "AFE": "U1", "BLE": "U2",
         "BUCK": "U3", "CHG": "U4", "CELL": "BT1", "BATCON": "J3"}


@pytest.fixture(scope="module")
def submission(repo):
    lib = json.loads((repo / "parts" / "ecg-patch-parts.json").read_text())
    lay = json.loads((repo / "layouts" / "ecg-patch-naive.json").read_text())
    by_ref = {p["id"]: p for p in lib["parts"]}
    return {
        "design_id": "ecg-patch",
        "revision": 7,
        "source_board_hash": "sha256:" + hashlib.sha256(b"board").hexdigest()[:16],
        "brief": "Single-lead ECG chest patch, 14-day wear, sealed.",
        "distance_metric": "edge",
        "catalog": {p["_catalog_id"]: p for p in lib["parts"]},
        "components": [
            {"ref": pl["ref"], "catalog_id": by_ref[pl["ref"]]["_catalog_id"],
             "kicad_ref": KICAD[pl["ref"]], "position_mm": pl["pos_mm"],
             "rotation_deg": pl.get("rotation_deg", 0)}
            for pl in lay["placements"]
        ],
        "geometry": {"enclosure": lay["enclosure"], "board": lay["board"],
                     "traces": []},
        "constraints": {
            "mission_profile": lay["mission"],
            "mission_rules": lay["mission_rules"],
            "rationales": lay["rationales"],
        },
    }


@pytest.fixture(scope="module")
def result(submission):
    return review(submission)


class TestIdentityIsEchoed:
    """The round-trip guard: the caller must be able to prove which board these
    findings describe before annotating anything."""

    def test_design_id_revision_and_hash_come_back_verbatim(self, submission, result):
        assert result["design_id"] == submission["design_id"]
        assert result["revision"] == submission["revision"]
        assert result["source_board_hash"] == submission["source_board_hash"]

    def test_revision_type_is_preserved_not_coerced(self, submission):
        # A caller using string revisions must get strings back, or their
        # equality check against the board on disk silently fails.
        sub = copy.deepcopy(submission)
        sub["revision"] = "v7.2-rc1"
        assert review(sub)["revision"] == "v7.2-rc1"

    def test_absent_hash_is_null_not_invented(self, submission):
        sub = copy.deepcopy(submission)
        del sub["source_board_hash"]
        assert review(sub)["source_board_hash"] is None

    def test_versions_are_declared(self, result):
        assert result["schema_version"] == SCHEMA_VERSION
        assert result["engine_version"]


class TestThreeVocabularies:
    """A finding must be annotatable without a lookup table."""

    def test_every_finding_component_carries_all_three_names(self, result):
        for f in result["findings"]:
            for c in f["components"]:
                assert set(c) == {"ref", "catalog_id", "kicad_ref"}
                assert c["ref"]

    def test_kicad_refs_are_resolved_on_a_real_finding(self, result):
        lead = next(f for f in result["findings"]
                    if f["rule_id"] == "mission.lead_vector")
        assert lead["kicad_refs"] == ["J1", "J2"]
        assert {c["catalog_id"] for c in lead["components"]} == {"jst_zh_electrode"}

    def test_component_index_covers_every_submitted_part(self, submission, result):
        assert len(result["components"]) == len(submission["components"])
        assert {c["kicad_ref"] for c in result["components"]} == set(KICAD.values())


class TestFindingPayload:
    def test_a_failing_check_carries_measurement_and_threshold(self, result):
        lead = next(f for f in result["findings"]
                    if f["rule_id"] == "mission.lead_vector")
        assert lead["status"] == "fail"
        assert lead["severity"] == "blocker"
        assert lead["measured"] == {"value": 6.0, "unit": "mm"}
        assert lead["threshold"]["value"] == 35.0
        assert lead["threshold"]["unit"] == "mm"
        assert lead["explanation"]

    def test_separation_findings_report_both_metrics(self, result):
        sep = next(f for f in result["findings"]
                   if f["rule_id"].startswith("sep.noise"))
        assert "edge_gap_mm" in sep["both_metrics"]
        assert "center_distance_mm" in sep["both_metrics"]

    def test_failing_findings_carry_overlay_geometry(self, result):
        drawable = [f for f in result["findings"]
                    if f["status"] == "fail" and not f["rule_id"].startswith("data.")]
        assert drawable
        assert all("overlay" in f for f in drawable)

    def test_overlay_frame_is_declared_not_assumed(self, result):
        assert result["coordinate_frame"]["frame"] == "enclosure"
        assert result["coordinate_frame"]["units"] == "mm"


class TestThresholdDirection:
    """Half the rule families test "at least" and half test "at most". Getting
    the operator from the metric name gets the second group backwards."""

    def _find(self, result, rule_id):
        return next(f for f in result["findings"] if f["rule_id"] == rule_id)

    def test_min_separation_reads_as_at_least(self, result):
        t = self._find(result, "mission.lead_vector")["threshold"]
        assert t["comparison"] == ">="
        assert t["reads_as"] == "measured >= 35.0 mm"

    def test_max_separation_reads_as_at_most(self, result):
        # The ESD clamp must be WITHIN 10 mm of the connector. Reporting ">="
        # here would tell an engineer to move it further away -- the exact
        # opposite of the fix.
        t = self._find(result, "mission.esd_at_the_boundary")["threshold"]
        assert t["comparison"] == "<="
        assert t["reads_as"] == "measured <= 10.0 mm"

    def test_zone_penetration_reads_as_at_most(self, result):
        t = self._find(result, "zone.heat_overlap::BUCK|AFE")["threshold"]
        assert t["comparison"] == "<="

    def test_clearance_reads_as_at_least(self, result):
        t = self._find(result, "sep.noise::AFE|BUCK")["threshold"]
        assert t["comparison"] == ">="

    def test_every_family_with_a_threshold_declares_a_direction(self, result):
        for f in result["findings"]:
            if "threshold" in f:
                assert "comparison" in f["threshold"], f["rule_id"]


class TestPerComponentIndex:
    """A board UI annotates parts, not checks."""

    def test_every_submitted_component_appears_even_when_clean(self, result):
        clean = [c for c in result["components"] if c["counts"]["fail"] == 0]
        assert clean, "expected at least one component with no failures"
        # Absent would be ambiguous; present-and-passing is not.
        assert all(c["checked"] for c in clean)

    def test_worst_status_and_severity_roll_up(self, result):
        cell = next(c for c in result["components"] if c["ref"] == "CELL")
        assert cell["worst_status"] == "fail"
        assert cell["worst_severity"] == "blocker"

    def test_a_skipped_component_is_unknown_not_pass(self, result):
        # BATCON's only applicable check is connector access, which is skipped
        # for a top-entry header. That must not read as clean.
        batcon = next(c for c in result["components"] if c["ref"] == "BATCON")
        assert batcon["worst_status"] == "unknown"

    def test_rule_ids_let_the_ui_link_back(self, result):
        afe = next(c for c in result["components"] if c["ref"] == "AFE")
        assert afe["rule_ids"]
        known = {f["rule_id"] for f in result["findings"]}
        assert set(afe["rule_ids"]) <= known


class TestCoverageBlock:
    def test_coverage_lists_what_ran_and_what_did_not(self, result):
        cov = result["coverage"]
        assert "sep.noise" in cov["families_evaluated"]
        assert set(cov["not_evaluated"]) == set(UNSUPPORTED)

    def test_brief_is_echoed(self, submission, result):
        assert result["brief"] == submission["brief"]


class TestMethodAndLimitation:
    """An approximation must never read as a measurement."""

    def test_geometric_checks_are_labelled_exact(self, result):
        fit = [f for f in result["findings"] if f["family"].startswith("fit.")]
        assert fit
        assert all(f["method"] == "exact" for f in fit)

    def test_heuristics_are_labelled_and_carry_their_limitation(self, result):
        heur = [f for f in result["findings"] if f["method"] == "heuristic"]
        assert heur
        for f in heur:
            assert f["limitation"], f["rule_id"]

    def test_every_heuristic_family_has_a_stated_limitation(self):
        for family, method in METHOD_BY_FAMILY.items():
            if method == "heuristic":
                assert family in LIMITATION_BY_FAMILY, family

    def test_unsupported_categories_are_returned_not_omitted(self, result):
        # Silence would read as a pass.
        ids = {f["rule_id"] for f in result["findings"]}
        for category in UNSUPPORTED:
            assert f"coverage.not_evaluated::{category}" in ids

    def test_unsupported_findings_are_unknown_never_pass(self, result):
        cov = [f for f in result["findings"] if f["family"] == "coverage"]
        assert cov
        assert all(f["status"] == "unknown" for f in cov)
        assert all(f["method"] == "unsupported" for f in cov)

    def test_an_unresolved_part_is_unknown_not_pass(self, submission):
        # A component the engine could not evaluate must not report clean.
        sub = copy.deepcopy(submission)
        sub["components"][0]["catalog_id"] = "afe-ecg-24bit"
        sub["catalog"]["afe-ecg-24bit"] = {"category": "sensor"}  # no dimensions
        out = review(sub)
        assert out["summary"].get("pass", 0) < len(out["findings"])


class TestSubmissionErrors:
    """Unusable input fails loudly. A design that merely fails its checks does
    not -- that is a successful review."""

    @pytest.mark.parametrize("missing", ["design_id", "revision", "components"])
    def test_missing_top_level_field(self, submission, missing):
        sub = copy.deepcopy(submission)
        del sub[missing]
        with pytest.raises(SubmissionError, match=missing):
            review(sub)

    def test_unknown_catalog_id_is_an_error_not_a_guess(self, submission):
        sub = copy.deepcopy(submission)
        sub["components"][0]["catalog_id"] = "does-not-exist"
        with pytest.raises(SubmissionError, match="does-not-exist"):
            review(sub)

    def test_missing_position_is_an_error(self, submission):
        sub = copy.deepcopy(submission)
        del sub["components"][0]["position_mm"]
        with pytest.raises(SubmissionError, match="position_mm"):
            review(sub)

    def test_component_with_no_properties_at_all(self, submission):
        sub = copy.deepcopy(submission)
        del sub["components"][0]["catalog_id"]
        with pytest.raises(SubmissionError, match="properties"):
            review(sub)

    def test_empty_component_list(self, submission):
        sub = copy.deepcopy(submission)
        sub["components"] = []
        with pytest.raises(SubmissionError, match="no components"):
            review(sub)

    def test_non_object_submission(self):
        with pytest.raises(SubmissionError):
            review(["not", "an", "object"])

    def test_a_failing_design_is_not_an_error(self, result):
        assert result["summary"]["fail"] > 0  # the naive board fails
        assert result["summary"]["blocking"] > 0


class TestInlineProperties:
    def test_inline_properties_work_without_a_catalog(self, submission):
        sub = copy.deepcopy(submission)
        cat = sub.pop("catalog")
        for comp in sub["components"]:
            comp["properties"] = cat[comp["catalog_id"]]
        assert review(sub)["summary"]["total"] == review(submission)["summary"]["total"]

    def test_overriding_the_catalog_is_recorded(self, submission):
        # An override is the caller asserting a physical fact; it should not
        # happen silently.
        sub = copy.deepcopy(submission)
        sub["components"][0]["properties"] = dict(
            sub["catalog"][sub["components"][0]["catalog_id"]]
        )
        out = review(sub)
        assert any("override" in w for w in out["warnings"])


class TestPurity:
    def test_same_submission_same_findings(self, submission):
        a, b = review(copy.deepcopy(submission)), review(copy.deepcopy(submission))
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_review_does_not_mutate_its_input(self, submission):
        before = json.dumps(submission, sort_keys=True)
        review(submission)
        assert json.dumps(submission, sort_keys=True) == before

    def test_result_is_json_serializable(self, result):
        json.dumps(result)


def test_shipped_example_matches_the_implementation(repo):
    """docs/examples/ is the contract other teams code against; it has to be
    what the code actually produces."""
    request = json.loads((repo / "docs" / "examples" / "review-request.json").read_text())
    expected = json.loads((repo / "docs" / "examples" / "review-response.json").read_text())
    assert review(request) == expected
