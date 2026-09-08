from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from missionpcb_app.analysis import DEFAULT_PARTS, analyse  # noqa: E402
from missionpcb_app.manufacturing import build_manufacturing_package  # noqa: E402
from missionpcb_app.schema import DesignState  # noqa: E402


LAYOUT = os.path.join(REPO_ROOT, "layouts", "ecg-patch-missionpcb.json")


def load_design() -> DesignState:
    with open(LAYOUT) as fh:
        raw = json.load(fh)
    return DesignState.from_engine_layout(
        raw,
        design_id="manufacturing-fixture",
        revision=2,
        parts_source=DEFAULT_PARTS,
    )


def test_manufacturing_package_includes_bom_files_and_cost_band():
    design = load_design()
    package = build_manufacturing_package(
        design,
        analysis=analyse(design),
        integrations={
            "kicad": {"status": "not_connected", "project_files": [], "board_files": []},
            "blender": {"asset_present": True, "asset_path": "/assets/ecg_patch.glb"},
        },
        render_contracts=["render/naive.json", "render/solved.json"],
    )

    assert package["schema"] == "missionpcb.manufacturing_export.v1"
    assert len(package["bom"]) == len(design.components)
    assert any(row["ref"] == "CELL" and row["package_size_mm"][2] == 5.6 for row in package["bom"])
    files = {item["kind"]: item for item in package["manufacturing_files"]}
    assert files["render_contract"]["status"] == "ready"
    assert files["kicad_project"]["status"] == "pending"
    assert files["fabrication_outputs"]["status"] == "pending"
    assert package["cost_estimate"]["total"]["high"] > package["cost_estimate"]["total"]["low"]


def test_manufacturing_package_surfaces_validation_failures():
    design = load_design()
    design.component("BUCK").pos_mm = design.component("AFE").pos_mm
    analysis = analyse(design)
    package = build_manufacturing_package(design, analysis=analysis)

    assert package["validation"]["open_failures"]
    assert any("BUCK" in item["component_refs"] for item in package["validation"]["open_failures"])
