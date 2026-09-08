from __future__ import annotations

import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from scripts.kicad_widget_control import list_refs, move_ref  # noqa: E402


BOARD = os.path.join(REPO_ROOT, "kicad", "ecg-patch", "ecg-patch.kicad_pcb")


def test_lists_generated_kicad_footprints():
    out = list_refs(BOARD)
    refs = {item["ref"] for item in out["footprints"]}
    assert {"AFE", "BUCK", "CELL", "BLE"}.issubset(refs)


def test_moves_generated_kicad_footprint(tmp_path):
    board = tmp_path / "copy.kicad_pcb"
    shutil.copyfile(BOARD, board)
    out = move_ref(board, "BUCK", 52.0, 7.5, None)
    assert out["changed"] is True
    assert out["before"]["position_mm"] == [47.0, 3.5]
    assert out["after"]["position_mm"] == [52.0, 7.5]
    refs = {item["ref"]: item for item in list_refs(board)["footprints"]}
    assert refs["BUCK"]["position_mm"] == [52.0, 7.5]
