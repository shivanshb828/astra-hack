from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
sys.path.insert(0, REPO_ROOT)

from missionpcb_app.api import app  # noqa: E402


def test_kicad_footprints_endpoint_lists_demo_board():
    client = TestClient(app)
    out = client.get("/api/kicad/footprints")
    assert out.status_code == 200
    refs = {item["ref"] for item in out.json()["footprints"]}
    assert {"AFE", "BUCK", "CELL", "BLE"}.issubset(refs)


def test_chat_explain_ref_uses_local_context(monkeypatch):
    monkeypatch.setenv("MISSIONPCB_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MISSIONPCB_MODEL_ENDPOINT", "https://example.invalid")
    client = TestClient(app)
    out = client.post("/api/chat", json={"message": "explain AFE"})
    assert out.status_code == 200
    body = out.json()
    assert body["selected_ref"] == "AFE"
    assert "sensitivity: high" in body["reply"].lower()
