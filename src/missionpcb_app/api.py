"""FastAPI surface for the MissionPCB workspace.

Every design-mutating endpoint is revision-checked, so a stale client cannot
overwrite a newer edit. Analysis results always carry the revision they were
computed against; the client compares that against the current revision to
decide whether a result is stale, which is what stops a slow job from
presenting itself as a verdict on the current design.

Model credentials never leave the backend: ``/api/integrations`` reports only
whether a credential is present, never its value.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from constraint_engine import load_parts

from . import chat as chat_mod
from . import integrations
from .analysis import DEFAULT_PARTS, analyse
from .manufacturing import build_manufacturing_package
from .schema import SCHEMA_VERSION, DesignState
from .store import RevisionConflict, Store

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_LAYOUT = os.path.join(REPO_ROOT, "layouts", "ecg-patch-missionpcb.json")
DB_PATH = os.environ.get("MISSIONPCB_DB", os.path.join(REPO_ROOT, "data", "missionpcb.db"))
DESIGN_ID = "ecg-patch"

app = FastAPI(title="MissionPCB", version=SCHEMA_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = Store(DB_PATH)


def _seed() -> None:
    """Load the ECG design once; existing state survives a restart untouched."""
    if store.has_design(DESIGN_ID):
        return
    with open(DEFAULT_LAYOUT) as fh:
        raw = json.load(fh)
    state = DesignState.from_engine_layout(
        raw, design_id=DESIGN_ID, revision=0, parts_source=DEFAULT_PARTS
    )
    state.device_type = "ecg_chest_patch"
    store.create_design(state)


_seed()


def _design(revision: int | None = None) -> DesignState:
    try:
        return store.get_design(DESIGN_ID, revision)
    except KeyError:
        raise HTTPException(404, f"design {DESIGN_ID} not found")


def _run_analysis(job_id: str, design_id: str, revision: int) -> None:
    try:
        result = analyse(store.get_design(design_id, revision))
        result.job_id = job_id
        store.finish_job(job_id, result)
    except Exception as exc:  # surfaced to the client as a failed job
        store.fail_job(job_id, str(exc))


class EditRequest(BaseModel):
    base_revision: int
    changes: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "inspector"
    actor: str = "user"
    summary: str = ""
    user_request: str = ""


def _apply_changes(
    state: DesignState, changes: list[dict[str, Any]]
) -> tuple[DesignState, list[dict[str, Any]], list[str]]:
    """Validate and apply component transform changes atomically.

    Only transforms are editable. Nominal dimensions belong to the parts
    catalogue and are not reachable from here, so moving a box in the viewport
    cannot rewrite a manufacturer specification.
    """
    applied: list[dict[str, Any]] = []
    refs: list[str] = []
    new_state = state.model_copy(deep=True)

    for change in changes:
        ref = change.get("ref")
        comp = new_state.component(ref) if ref else None
        if comp is None:
            raise HTTPException(400, f"unknown component ref: {ref!r}")

        field = change.get("field", "pos_mm")
        if field == "pos_mm":
            after = change.get("after")
            if (not isinstance(after, (list, tuple)) or len(after) != 2
                    or not all(isinstance(v, (int, float)) for v in after)):
                raise HTTPException(400, f"pos_mm for {ref} must be [x, y] numbers")
            before = [comp.pos_mm[0], comp.pos_mm[1]]
            comp.pos_mm = (float(after[0]), float(after[1]))
            applied.append({"ref": ref, "field": field, "before": before,
                            "after": [float(after[0]), float(after[1])]})
        elif field == "rotation_deg":
            after = change.get("after")
            if not isinstance(after, (int, float)):
                raise HTTPException(400, f"rotation_deg for {ref} must be a number")
            before = comp.rotation_deg
            comp.rotation_deg = int(round(float(after) / 90.0)) * 90 % 360
            applied.append({"ref": ref, "field": field, "before": before,
                            "after": comp.rotation_deg})
        else:
            raise HTTPException(400, f"field {field!r} is not editable")
        refs.append(ref)

    return new_state, applied, refs


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "schema_version": SCHEMA_VERSION, "design_id": DESIGN_ID}


@app.get("/api/integrations")
def integrations_status() -> dict[str, Any]:
    return {
        "kicad": integrations.kicad_status(),
        "blender": integrations.blender_status(),
        "model": chat_mod.provider_status(),
    }


@app.get("/api/parts")
def parts() -> dict[str, Any]:
    parts_index, warnings = load_parts(DEFAULT_PARTS)
    return {
        "warnings": warnings,
        "parts": {
            pid: {
                "id": p.id, "name": p.name, "category": p.category,
                "length_mm": p.length_mm, "width_mm": p.width_mm,
                "height_mm": p.height_mm, "heat_source": p.heat_source,
                "noise_source": p.noise_source, "sensitivity": p.sensitivity,
                "skin_contact": p.skin_contact,
                "heat_zone_radius_mm": p.heat_zone_radius_mm,
                "placement_notes": p.placement_notes,
                "datasheet_url": p.datasheet_url,
            }
            for pid, p in parts_index.items()
        },
    }


@app.get("/api/design")
def get_design(revision: int | None = None) -> dict[str, Any]:
    state = _design(revision)
    return {
        "design": state.model_dump(),
        "current_revision": store.current_revision(DESIGN_ID),
        "revisions": store.list_revisions(DESIGN_ID),
    }


@app.post("/api/design/edit")
def edit_design(req: EditRequest, background: BackgroundTasks) -> dict[str, Any]:
    state = _design()
    new_state, applied, refs = _apply_changes(state, req.changes)

    try:
        saved, event = store.commit_revision(
            new_state,
            base_revision=req.base_revision,
            actor=req.actor if req.actor in ("user", "assistant", "import", "system") else "user",
            source=req.source if req.source in ("drag", "inspector", "chat", "restore", "import") else "inspector",
            summary=req.summary or f"Moved {', '.join(refs)}",
            user_request=req.user_request,
            changes=applied,
            component_refs=refs,
        )
    except RevisionConflict as conflict:
        raise HTTPException(
            409,
            {
                "error": "revision_conflict",
                "expected": conflict.expected,
                "actual": conflict.actual,
                "message": str(conflict),
            },
        )

    job_id = store.start_job(DESIGN_ID, saved.revision)
    store.attach_analysis(event.event_id, job_id)
    background.add_task(_run_analysis, job_id, DESIGN_ID, saved.revision)

    return {"design": saved.model_dump(), "event": event.model_dump(),
            "analysis_job_id": job_id}


@app.post("/api/design/analyze")
def request_analysis(background: BackgroundTasks) -> dict[str, Any]:
    state = _design()
    job_id = store.start_job(DESIGN_ID, state.revision)
    background.add_task(_run_analysis, job_id, DESIGN_ID, state.revision)
    return {"job_id": job_id, "design_revision": state.revision, "status": "running"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    payload = {
        "job_id": job_id,
        "status": job["status"],
        "design_revision": job["design_revision"],
        "current_revision": store.current_revision(DESIGN_ID),
    }
    if job["result_json"]:
        payload["result"] = json.loads(job["result_json"])
    payload["stale"] = job["design_revision"] != payload["current_revision"]
    return payload


@app.get("/api/design/analysis")
def latest_analysis() -> dict[str, Any]:
    current = store.current_revision(DESIGN_ID)
    exact = store.analysis_for_revision(DESIGN_ID, current)
    result = exact or store.latest_analysis(DESIGN_ID)
    if result is None:
        return {"result": None, "stale": False, "current_revision": current}
    return {
        "result": result.model_dump(),
        # A result for an older revision is reported as stale rather than
        # presented as a verdict on the design as it stands now.
        "stale": result.design_revision != current,
        "current_revision": current,
    }


@app.get("/api/design/history")
def history() -> dict[str, Any]:
    return {
        "events": [e.model_dump() for e in store.history(DESIGN_ID)],
        "current_revision": store.current_revision(DESIGN_ID),
    }


class RestoreRequest(BaseModel):
    revision: int
    base_revision: int


@app.post("/api/design/restore")
def restore(req: RestoreRequest, background: BackgroundTasks) -> dict[str, Any]:
    """Restore an earlier revision as a new revision; history is never erased."""
    try:
        target = store.get_design(DESIGN_ID, req.revision)
    except KeyError:
        raise HTTPException(404, f"revision {req.revision} not found")

    try:
        saved, event = store.commit_revision(
            target,
            base_revision=req.base_revision,
            actor="user",
            source="restore",
            summary=f"Restored revision {req.revision}",
            changes=[{"kind": "restore", "from": req.base_revision,
                      "to": req.revision}],
        )
    except RevisionConflict as conflict:
        raise HTTPException(409, {"error": "revision_conflict",
                                  "expected": conflict.expected,
                                  "actual": conflict.actual})

    job_id = store.start_job(DESIGN_ID, saved.revision)
    store.attach_analysis(event.event_id, job_id)
    background.add_task(_run_analysis, job_id, DESIGN_ID, saved.revision)
    return {"design": saved.model_dump(), "event": event.model_dump(),
            "analysis_job_id": job_id}


@app.post("/api/design/undo")
def undo(background: BackgroundTasks) -> dict[str, Any]:
    current = store.current_revision(DESIGN_ID)
    if current <= 0:
        raise HTTPException(400, "nothing to undo")
    return restore(RestoreRequest(revision=current - 1, base_revision=current),
                   background)


@app.post("/api/design/redo")
def redo(background: BackgroundTasks) -> dict[str, Any]:
    """Redo the revision an undo stepped back from."""
    current = store.current_revision(DESIGN_ID)
    for event in reversed(store.history(DESIGN_ID)):
        for change in event.changes:
            if change.get("kind") == "restore":
                target = change.get("from")
                if isinstance(target, int) and target in store.list_revisions(DESIGN_ID):
                    return restore(
                        RestoreRequest(revision=target, base_revision=current),
                        background,
                    )
        break
    raise HTTPException(400, "nothing to redo")


class ChatRequest(BaseModel):
    message: str


class KiCadMoveRequest(BaseModel):
    ref: str
    x_mm: float
    y_mm: float
    rotation_deg: float | None = None


class WidgetMessageRequest(BaseModel):
    message: str
    auto_mode: bool = False


def _signal_kicad_reload(reason: str, mutation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tell the local demo shell that KiCad's board file changed.

    KiCad does not expose a simple local HTTP control API. The reliable demo
    path is to mutate the board file, write a reload marker, and optionally ask
    macOS to foreground the project. KiCad will prompt/reload when it sees the
    file changed on disk.
    """
    project = os.path.join(REPO_ROOT, "kicad", "ecg-patch", "ecg-patch.kicad_pro")
    board = os.path.join(REPO_ROOT, "kicad", "ecg-patch", "ecg-patch.kicad_pcb")
    marker = os.path.join(REPO_ROOT, "out", "widget", "kicad-reload.json")
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "reason": reason,
        "project": project,
        "board": board,
        "mutation": mutation,
    }
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    auto_open = os.environ.get("MISSIONPCB_KICAD_AUTO_RELOAD") == "1"
    opened = False
    open_error = ""
    if auto_open and os.path.exists(project):
        try:
            subprocess.run(["open", "-a", "KiCad", project], check=True, timeout=5)
            opened = True
        except Exception as exc:
            open_error = str(exc)

    return {
        "strategy": "file_changed",
        "marker": marker,
        "opened_kicad": opened,
        "open_error": open_error,
        "user_action": (
            "If KiCad prompts that the board changed on disk, choose Reload. "
            "Set MISSIONPCB_KICAD_AUTO_RELOAD=1 before starting the backend to foreground KiCad automatically."
        ),
    }


def _sync_kicad_from_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mirror app placement changes into the native KiCad demo board."""
    from scripts.kicad_widget_control import DEFAULT_BOARD, list_refs, move_ref

    synced = []
    if not os.path.exists(DEFAULT_BOARD):
        return synced
    by_ref: dict[str, dict[str, Any]] = {}
    for change in changes:
        ref = change.get("ref")
        if not ref:
            continue
        by_ref.setdefault(ref, {})[change.get("field", "")] = change.get("after")
    for ref, fields in by_ref.items():
        pos = fields.get("pos_mm")
        rot = fields.get("rotation_deg")
        if pos is None and rot is None:
            continue
        if pos is None:
            current = next(
                (
                    item
                    for item in list_refs(DEFAULT_BOARD)["footprints"]
                    if item["ref"] == ref
                ),
                None,
            )
            if current is None:
                continue
            pos = current["position_mm"]
        try:
            synced.append(move_ref(DEFAULT_BOARD, ref, float(pos[0]), float(pos[1]), rot))
        except ValueError:
            # Some app refs may not exist in a partial KiCad demo board yet.
            continue
    return synced


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    state = _design()
    parts_index, _ = load_parts(DEFAULT_PARTS)
    outcome = chat_mod.interpret(req.message, state, parts_index)
    if proposal := outcome.get("proposal"):
        store.save_proposal(proposal)
    return outcome


@app.post("/api/proposals/{proposal_id}/apply")
def apply_proposal(proposal_id: str, background: BackgroundTasks) -> dict[str, Any]:
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(404, "proposal not found")
    if proposal.get("status") != "pending":
        raise HTTPException(409, f"proposal already {proposal.get('status')}")

    result = edit_design(
        EditRequest(
            base_revision=store.current_revision(DESIGN_ID),
            changes=proposal["changes"],
            source="chat",
            actor="assistant",
            summary=proposal.get("explanation", "Applied chat proposal"),
            user_request=proposal.get("user_request", ""),
        ),
        background,
    )
    kicad_sync = _sync_kicad_from_changes(proposal.get("changes", []))
    result["native_tool"] = {
        "kicad": {
            "synced": bool(kicad_sync),
            "changes": kicad_sync,
            "reload": _signal_kicad_reload("proposal_applied", {"proposal_id": proposal_id}),
        }
    }
    store.set_proposal_status(proposal_id, "applied")
    return result


@app.post("/api/widget/send")
def widget_send(req: WidgetMessageRequest, background: BackgroundTasks) -> dict[str, Any]:
    """One-call widget loop: ask Astra/local fallback, optionally apply."""
    outcome = chat(ChatRequest(message=req.message))
    response: dict[str, Any] = {"outcome": outcome, "auto_applied": False}
    proposal = outcome.get("proposal")
    if req.auto_mode and proposal:
        response["apply_result"] = apply_proposal(proposal["proposal_id"], background)
        response["auto_applied"] = True
    return response


@app.get("/api/widget/monitor")
def widget_monitor() -> dict[str, Any]:
    marker = os.path.join(REPO_ROOT, "out", "widget", "kicad-reload.json")
    latest_reload = None
    if os.path.exists(marker):
        with open(marker, encoding="utf-8") as fh:
            latest_reload = json.load(fh)
    return {
        "ok": True,
        "design_revision": store.current_revision(DESIGN_ID),
        "integrations": integrations_status(),
        "latest_analysis": latest_analysis(),
        "latest_kicad_reload": latest_reload,
        "routes": {
            "widget_send": "/api/widget/send",
            "widget_monitor": "/api/widget/monitor",
            "kicad_footprints": "/api/kicad/footprints",
            "kicad_move": "/api/kicad/footprints/move",
            "kicad_reload": "/api/kicad/reload",
        },
    }


@app.post("/api/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str) -> dict[str, Any]:
    """Rejection leaves design state untouched and records no design edit."""
    proposal = store.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(404, "proposal not found")
    store.set_proposal_status(proposal_id, "rejected")
    return {"proposal_id": proposal_id, "status": "rejected",
            "current_revision": store.current_revision(DESIGN_ID)}


@app.get("/api/design/export")
def export_design() -> JSONResponse:
    state = _design()
    analysis = store.analysis_for_revision(DESIGN_ID, state.revision)
    return JSONResponse(
        {
            "schema_version": SCHEMA_VERSION,
            "design": state.model_dump(),
            "engine_layout": state.to_engine_layout(),
            "analysis": analysis.model_dump() if analysis else None,
            "history": [e.model_dump() for e in store.history(DESIGN_ID)],
        },
        headers={"Content-Disposition": "attachment; filename=missionpcb-export.json"},
    )


@app.get("/api/manufacturing/export")
def export_manufacturing_package() -> JSONResponse:
    state = _design()
    analysis = store.analysis_for_revision(DESIGN_ID, state.revision)
    render_contracts = [
        path
        for path in ("render/naive.json", "render/solved.json")
        if os.path.exists(os.path.join(REPO_ROOT, path))
    ]
    payload = build_manufacturing_package(
        state,
        analysis=analysis,
        integrations=integrations_status(),
        render_contracts=render_contracts,
    )
    return JSONResponse(
        payload,
        headers={
            "Content-Disposition": "attachment; filename=missionpcb-manufacturing-export.json"
        },
    )


@app.post("/api/blender/export")
def blender_export() -> dict[str, Any]:
    """Re-export assets from the current revision. Never called per drag event."""
    state = _design()
    result = analyse(state)
    out_dir = os.path.join(REPO_ROOT, "out", "app_scene")
    os.makedirs(out_dir, exist_ok=True)

    # The scene builder consumes the engine's documented results contract, so
    # write that file rather than inventing a second format.
    from constraint_engine import load_layout, validate
    import tempfile

    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(state.to_engine_layout(), tmp)
    tmp.close()
    try:
        layout, warnings = load_layout(tmp.name)
        parts_index, part_warnings = load_parts(DEFAULT_PARTS)
        engine_results = validate(layout, parts_index,
                                  warnings=list(warnings) + list(part_warnings))
        results_path = os.path.join(out_dir, "validation_results.json")
        with open(results_path, "w") as fh:
            json.dump(engine_results.to_dict(), fh, indent=2)
        layout_path = os.path.join(out_dir, "layout.json")
        with open(layout_path, "w") as fh:
            json.dump(state.to_engine_layout(), fh, indent=2)
    finally:
        os.unlink(tmp.name)

    outcome = integrations.run_blender_export(
        os.path.relpath(results_path, REPO_ROOT),
        os.path.relpath(layout_path, REPO_ROOT),
    )
    outcome["design_revision"] = state.revision
    outcome["analysis_summary"] = result.summary
    return outcome


@app.get("/api/blender/render.png")
def blender_render() -> FileResponse:
    path = os.path.join(REPO_ROOT, "blender", "out", "render_iso.png")
    if not os.path.exists(path):
        raise HTTPException(404, "no render available; run a Blender export first")
    return FileResponse(path, media_type="image/png")


@app.post("/api/kicad/drc")
def kicad_drc(board: str = Body(embed=True, default="")) -> dict[str, Any]:
    status = integrations.kicad_status()
    if status["status"] != "connected":
        # Explicitly not a pass: an unavailable integration yields no checks.
        return {"ok": False, "status": "not_connected", "detail": status["detail"],
                "checks": []}
    target = board or (status["board_files"][0] if status["board_files"] else "")
    if not target:
        return {"ok": False, "status": "not_connected",
                "detail": "no .kicad_pcb file found", "checks": []}
    return integrations.run_kicad_drc(target)


@app.get("/api/kicad/footprints")
def kicad_footprints() -> dict[str, Any]:
    from scripts.kicad_widget_control import DEFAULT_BOARD, list_refs

    if not os.path.exists(DEFAULT_BOARD):
        raise HTTPException(404, "no demo KiCad board found")
    return list_refs(DEFAULT_BOARD)


@app.post("/api/kicad/footprints/move")
def kicad_move_footprint(req: KiCadMoveRequest) -> dict[str, Any]:
    from scripts.kicad_widget_control import DEFAULT_BOARD, move_ref

    if not os.path.exists(DEFAULT_BOARD):
        raise HTTPException(404, "no demo KiCad board found")
    try:
        result = move_ref(DEFAULT_BOARD, req.ref, req.x_mm, req.y_mm, req.rotation_deg)
        result["reload"] = _signal_kicad_reload("direct_footprint_move", result)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/kicad/reload")
def kicad_reload() -> dict[str, Any]:
    return _signal_kicad_reload("manual_reload_request")
