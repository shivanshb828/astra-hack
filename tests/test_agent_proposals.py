"""Agent proposal submission: POST /api/proposals.

The contract these tests defend is that an external agent can ask "what would
happen if" without committing anything, and that the answer it gets back is
the same answer it will get after applying. A prediction that does not match
the eventual result is worse than no prediction, because an agent will act on
it.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

CLEAN_AFE = [45.5, 21.5]      # passing position on the reference board
ON_TOP_OF_BUCK = [47.0, 7.5]  # collides + violates noise/thermal clearances


@pytest.fixture()
def client(monkeypatch):
    """A fresh app against a throwaway database, so tests never share state."""
    db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("MISSIONPCB_DB", db)

    import importlib

    from missionpcb_app import api as api_mod

    api_mod = importlib.reload(api_mod)
    try:
        yield TestClient(api_mod.app)
    finally:
        api_mod.store.close() if hasattr(api_mod.store, "close") else None
        if os.path.exists(db):
            os.unlink(db)


def _revision(client) -> int:
    return client.get("/api/design").json()["design"]["revision"]


def _analyse_now(client) -> dict:
    """Force an analysis of the current revision and return its summary."""
    job = client.post("/api/design/analyze").json()["job_id"]
    return client.get(f"/api/jobs/{job}").json()["result"]


def _submit(client, after, *, ref="AFE", base=None, **extra):
    body = {
        "base_revision": _revision(client) if base is None else base,
        "changes": [{"ref": ref, "field": "pos_mm", "after": after}],
        **extra,
    }
    return client.post("/api/proposals", json=body)


# --------------------------------------------------------------------------
# the core promise: evaluate without mutating
# --------------------------------------------------------------------------


def test_submission_does_not_touch_the_design(client):
    _analyse_now(client)
    before_rev = _revision(client)
    before_afe = [
        c["pos_mm"]
        for c in client.get("/api/design").json()["design"]["components"]
        if c["ref"] == "AFE"
    ][0]

    resp = _submit(client, ON_TOP_OF_BUCK)
    assert resp.status_code == 200

    assert _revision(client) == before_rev, "a proposal must not create a revision"
    after_afe = [
        c["pos_mm"]
        for c in client.get("/api/design").json()["design"]["components"]
        if c["ref"] == "AFE"
    ][0]
    assert after_afe == before_afe, "a proposal must not move a component"


def test_prediction_matches_what_applying_actually_produces(client):
    """The whole feature is worthless if these two disagree."""
    _analyse_now(client)
    proposal = _submit(client, ON_TOP_OF_BUCK).json()
    predicted = proposal["prediction"]["predicted_summary"]

    client.post(f"/api/proposals/{proposal['proposal_id']}/apply")
    actual = _analyse_now(client)["summary"]

    assert predicted == actual


def test_predicted_failure_ids_match_actual_failure_ids(client):
    """Not just the counts -- the specific checks have to line up."""
    _analyse_now(client)
    proposal = _submit(client, ON_TOP_OF_BUCK).json()
    introduced = set(proposal["prediction"]["introduced"])

    client.post(f"/api/proposals/{proposal['proposal_id']}/apply")
    actual_fails = {
        c["check_id"] for c in _analyse_now(client)["checks"] if c["status"] == "fail"
    }

    assert introduced == actual_fails


# --------------------------------------------------------------------------
# the verdict field
# --------------------------------------------------------------------------


def test_regression_is_labelled_and_names_what_it_breaks(client):
    _analyse_now(client)
    pred = _submit(client, ON_TOP_OF_BUCK).json()["prediction"]

    assert pred["verdict"] == "regresses"
    assert pred["net_fail_delta"] > 0
    assert pred["introduced"], "a regression must say which checks it breaks"
    assert pred["fixed"] == []


def test_improvement_is_labelled_and_names_what_it_fixes(client):
    """Break the board first, then propose the repair."""
    client.post(
        "/api/design/edit",
        json={
            "base_revision": _revision(client),
            "changes": [{"ref": "AFE", "field": "pos_mm", "after": ON_TOP_OF_BUCK}],
        },
    )
    _analyse_now(client)

    pred = _submit(client, CLEAN_AFE).json()["prediction"]

    assert pred["verdict"] == "improves"
    assert pred["net_fail_delta"] < 0
    assert pred["fixed"], "an improvement must say which checks it fixes"
    assert pred["introduced"] == []


def test_no_op_change_is_neutral(client):
    _analyse_now(client)
    pred = _submit(client, CLEAN_AFE).json()["prediction"]

    assert pred["verdict"] == "neutral"
    assert pred["net_fail_delta"] == 0
    assert pred["fixed"] == [] and pred["introduced"] == []


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------


def test_before_values_are_filled_in_from_the_live_board(client):
    """The agent sends only `after`; the engine records what it displaced."""
    change = _submit(client, ON_TOP_OF_BUCK).json()["changes"][0]
    assert change["before"] == CLEAN_AFE
    assert change["after"] == ON_TOP_OF_BUCK


def test_stale_base_revision_is_refused_at_submit(client):
    resp = _submit(client, CLEAN_AFE, base=999)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "revision_conflict"


def test_proposal_goes_stale_when_the_design_moves_underneath_it(client):
    """A proposal's `before` values describe a board that no longer exists."""
    _analyse_now(client)
    proposal = _submit(client, CLEAN_AFE).json()

    client.post(
        "/api/design/edit",
        json={
            "base_revision": _revision(client),
            "changes": [{"ref": "BLE", "field": "rotation_deg", "after": 0}],
        },
    )

    resp = client.post(f"/api/proposals/{proposal['proposal_id']}/apply")
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "proposal_stale"


def test_unknown_ref_is_refused_rather_than_skipped(client):
    resp = client.post(
        "/api/proposals",
        json={
            "base_revision": _revision(client),
            "changes": [{"ref": "NOSUCHPART", "field": "pos_mm", "after": [10, 10]}],
        },
    )
    assert resp.status_code == 400
    assert "NOSUCHPART" in str(resp.json()["detail"])


def test_empty_change_list_is_refused(client):
    resp = client.post(
        "/api/proposals", json={"base_revision": _revision(client), "changes": []}
    )
    assert resp.status_code == 400


def test_rejected_proposal_leaves_no_design_history(client):
    before_rev = _revision(client)
    proposal = _submit(client, ON_TOP_OF_BUCK).json()

    assert client.post(f"/api/proposals/{proposal['proposal_id']}/reject").status_code == 200
    assert _revision(client) == before_rev

    # and it cannot be resurrected
    assert client.post(f"/api/proposals/{proposal['proposal_id']}/apply").status_code == 409


def test_dimensions_are_not_reachable_through_a_proposal(client):
    """Catalogue facts are not editable, whoever is asking."""
    resp = client.post(
        "/api/proposals",
        json={
            "base_revision": _revision(client),
            "changes": [{"ref": "AFE", "field": "size_mm", "after": [99, 99]}],
        },
    )
    assert resp.status_code == 400
