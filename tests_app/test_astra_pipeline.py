from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from missionpcb_app.astra_pipeline import (  # noqa: E402
    astra_primary_fixture,
    astra_primary_from_render_fixture,
    astra_secondary_kicad_fixture,
    component_catalog_payload,
    render_contract_payload,
)
from missionpcb_app.analysis import DEFAULT_PARTS  # noqa: E402
from missionpcb_app.schema import DesignState  # noqa: E402


LAYOUT = os.path.join(REPO_ROOT, "layouts", "ecg-patch-naive.json")
RENDER = os.path.join(REPO_ROOT, "render", "naive.json")


def load_design() -> DesignState:
    with open(LAYOUT) as fh:
        raw = json.load(fh)
    return DesignState.from_engine_layout(
        raw,
        design_id="astra-fixture",
        revision=3,
        parts_source=DEFAULT_PARTS,
    )


def test_component_payload_contains_parts_and_positions():
    design = load_design()
    payload = component_catalog_payload(design)
    refs = {item["ref"] for item in payload}
    assert {"AFE", "BUCK", "CELL"}.issubset(refs)
    cell = next(item for item in payload if item["ref"] == "CELL")
    assert cell["part_id"] == "CELL"
    assert cell["name"].startswith("CP 1254")
    assert cell["size_mm"][2] == 5.6
    assert isinstance(cell["position_mm"], list)


def test_primary_fixture_finds_worries_from_parts_and_scene():
    design = load_design()
    out = astra_primary_fixture("Build a 7-day ECG patch", design)
    assert out["mode"] == "fixture"
    assert out["design_revision"] == 3
    assert out["components"]
    blocker_ids = {b["id"] for b in out["blockers"]}
    assert "sep.noise::AFE|BUCK" in blocker_ids
    assert any("AFE" in b["component_refs"] for b in out["blockers"])


def test_secondary_fixture_turns_worries_into_native_tool_actions():
    primary = astra_primary_fixture("Build a 7-day ECG patch", load_design())
    out = astra_secondary_kicad_fixture(primary)
    assert out["mode"] == "fixture"
    assert out["upstream_source"] == "astra_primary_fixture"
    assert any(a["tool"] == "blender" and a["action"] == "highlight" for a in out["actions"])
    assert any(a["tool"] == "kicad" and a["requires_user_apply"] for a in out["actions"])
    assert out["limits"]


def test_render_contract_payload_uses_dhruva_baseline():
    out = render_contract_payload(RENDER)
    assert out["source"] == "render_contract"
    assert out["path"] == "render/naive.json"
    assert out["components"]
    assert out["failed_checks"]
    assert any(check["id"] == "sep.noise::AFE|BUCK" for check in out["failed_checks"])
    assert out["overlays"]


def test_primary_fixture_can_start_from_render_contract():
    out = astra_primary_from_render_fixture("Build a 7-day ECG patch", RENDER)
    assert out["source"] == "astra_primary_from_render_fixture"
    assert out["native_view"]["source"] == "render_contract"
    assert any("AFE" in blocker["component_refs"] for blocker in out["blockers"])
