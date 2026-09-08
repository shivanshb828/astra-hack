"""MissionPCB Blender widget.

Install/run inside Blender for the demo:

    import bpy
    exec(open("blender/missionpcb_widget.py").read())

The widget is intentionally thin. It collects natural-language input and scene
metadata, calls an Astra adapter, then reflects returned findings/proposals in
Blender. The fixture adapter below keeps the UI usable without model keys; swap
``ask_astra`` for the real Astra endpoint when it is ready.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import bpy
except ModuleNotFoundError:  # Allows py_compile outside Blender.
    bpy = None


DEFAULT_MISSION = (
    "Build a rechargeable single-lead ECG patch for continuous 7-day wear. "
    "It should stream over BLE, fit in a thin sealed enclosure, and be safe "
    "against patient skin."
)
SCRIPT_PATH = Path(globals().get("__file__", Path.cwd() / "blender" / "missionpcb_widget.py"))
RENDER_CONTRACT = SCRIPT_PATH.resolve().parents[1] / "render" / "naive.json"

QUESTION_DEFAULTS = {
    "wear_duration": "7 days continuous",
    "power_strategy": "rechargeable LiPo",
    "priority": "patient safety",
}

CATEGORY_COLORS = {
    "safety": (0.1, 0.65, 0.35, 1.0),
    "mechanical": (0.65, 0.68, 0.74, 1.0),
    "thermal": (0.95, 0.25, 0.18, 1.0),
    "conducted": (0.95, 0.58, 0.18, 1.0),
    "noise_separation": (0.95, 0.58, 0.18, 1.0),
    "radiated": (0.20, 0.48, 1.0, 1.0),
}


def scene_components() -> list[dict[str, Any]]:
    """Collect stable component metadata from the active Blender scene."""
    out = []
    for obj in bpy.context.scene.objects:
        ref = obj.get("component_ref") or obj.name
        if ref in {"BOARD", "ENCLOSURE"} or obj.type not in {"MESH", "EMPTY"}:
            continue
        out.append(
            {
                "ref": ref,
                "object_name": obj.name,
                "part_id": obj.get("part_id", ""),
                "category": obj.get("category", ""),
                "geometry_source": obj.get("geometry_source", "unknown"),
                "approximate": bool(obj.get("approximate", False)),
                "location": [round(v, 6) for v in obj.location],
            }
        )
    return sorted(out, key=lambda item: item["ref"])


def render_contract_findings() -> list[dict[str, Any]]:
    """Read the committed simulation findings if Dhruva's contract exists."""
    if not RENDER_CONTRACT.exists():
        return []
    contract = json.loads(RENDER_CONTRACT.read_text(encoding="utf-8"))
    blockers = []
    for check in contract.get("checks", []):
        if check.get("status") != "FAIL":
            continue
        blockers.append(
            {
                "id": check.get("id", ""),
                "title": check.get("title", "Finding"),
                "category": str(check.get("id", "")).split("::", 1)[0],
                "component_refs": check.get("subjects", []),
                "why": check.get("message", ""),
                "suggestion": check.get("suggestion", ""),
            }
        )
    return blockers


def ask_astra(mission: str, answers: dict[str, str], components: list[dict[str, Any]]) -> dict[str, Any]:
    """Fixture adapter for Astra.

    The real implementation should POST the same payload shape to Astra and
    return the same response shape. Do not put model reasoning in this widget.
    """
    blockers = render_contract_findings()
    if not blockers:
        refs = {c["ref"] for c in components}
        for ref, category, title in (
            ("CELL", "mechanical", "Battery/enclosure fit needs review"),
            ("BUCK", "conducted", "Regulator architecture needs review"),
            ("AFE", "thermal", "Analog front end is sensitive to nearby heat"),
            ("ANT", "radiated", "Antenna keep-out needs free space"),
        ):
            if ref in refs:
                blockers.append(
                    {
                        "id": f"fixture.{category}.{ref.lower()}",
                        "title": title,
                        "category": category,
                        "component_refs": [ref],
                        "why": "Fixture response standing in for Astra until the live endpoint is connected.",
                    }
                )
    return {
        "mode": "fixture",
        "native_view_source": (
            "render/naive.json" if RENDER_CONTRACT.exists() else "active_blender_scene"
        ),
        "mission": mission,
        "answers": answers,
        "considerations": [
            "Continuous skin contact makes heat and safety constraints first-class.",
            "Sensitive analog circuitry should be separated from switching power.",
            "Battery, charger, and protection need to be reviewed as one subsystem.",
        ],
        "blockers": blockers,
        "proposal": {
            "id": "fixture.move-buck",
            "title": "Move noisy power away from the analog front end",
            "changes": [{"ref": "BUCK", "translation": [0.018, 0.0, 0.0]}],
        },
    }


def material_for(category: str):
    name = f"MissionPCB_{category}"
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = CATEGORY_COLORS.get(category, (1.0, 1.0, 1.0, 1.0))
    return mat


def object_for_ref(ref: str):
    for obj in bpy.context.scene.objects:
        if obj.name == ref or obj.get("component_ref") == ref:
            return obj
    return None


def clear_highlights() -> None:
    for obj in bpy.context.scene.objects:
        if obj.get("missionpcb_original_materials") is not None:
            names = json.loads(obj["missionpcb_original_materials"])
            obj.data.materials.clear()
            for name in names:
                mat = bpy.data.materials.get(name)
                if mat:
                    obj.data.materials.append(mat)
            del obj["missionpcb_original_materials"]


def highlight_findings(response: dict[str, Any]) -> None:
    clear_highlights()
    bpy.ops.object.select_all(action="DESELECT")
    focused = None
    for blocker in response.get("blockers", []):
        mat = material_for(blocker.get("category", "safety"))
        for ref in blocker.get("component_refs", []):
            obj = object_for_ref(ref)
            if not obj or not hasattr(obj.data, "materials"):
                continue
            obj["missionpcb_original_materials"] = json.dumps(
                [slot.name for slot in obj.data.materials]
            )
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            obj.select_set(True)
            focused = focused or obj
    if focused:
        bpy.context.view_layer.objects.active = focused


def export_widget_artifacts(response: dict[str, Any], directory: str = "out/widget") -> Path:
    root = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path.cwd()
    out = root / directory
    out.mkdir(parents=True, exist_ok=True)
    (out / "scene_components.json").write_text(
        json.dumps(scene_components(), indent=2) + "\n", encoding="utf-8"
    )
    (out / "astra_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )
    report = ["# MissionPCB Widget Report", ""]
    report += ["## Considerations", ""]
    report += [f"- {item}" for item in response.get("considerations", [])]
    report += ["", "## Blockers", ""]
    report += [
        f"- **{b.get('title', b.get('id'))}**: {', '.join(b.get('component_refs', []))}"
        for b in response.get("blockers", [])
    ]
    (out / "advisor_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return out


if bpy is not None:

    class MissionPCBState(bpy.types.PropertyGroup):
        mission: bpy.props.StringProperty(name="Prompt", default=DEFAULT_MISSION)
        command: bpy.props.StringProperty(
            name="Message",
            default="",
            description="Natural-language edit, comment, or highlight request",
        )
        wear_duration: bpy.props.StringProperty(
            name="Wear duration", default=QUESTION_DEFAULTS["wear_duration"]
        )
        power_strategy: bpy.props.StringProperty(
            name="Power strategy", default=QUESTION_DEFAULTS["power_strategy"]
        )
        priority: bpy.props.StringProperty(
            name="Priority", default=QUESTION_DEFAULTS["priority"]
        )
        auto_mode: bpy.props.BoolProperty(name="Auto mode", default=False)
        dashboard_open: bpy.props.BoolProperty(name="Dashboard", default=False)
        selected_finding: bpy.props.IntProperty(name="Finding", default=0, min=0)
        response_json: bpy.props.StringProperty(name="Astra response", default="")
        transcript: bpy.props.StringProperty(
            name="Transcript",
            default="Astra: Tell me what we are building, then I will inspect the board.",
        )
        status: bpy.props.StringProperty(name="Status", default="Ready")


    class MISSIONPCB_OT_ask_astra(bpy.types.Operator):
        bl_idname = "missionpcb.ask_astra"
        bl_label = "Ask Astra"

        def execute(self, context):
            state = context.scene.missionpcb
            user_message = state.command.strip() or state.mission
            response = ask_astra(
                state.mission,
                {
                    "wear_duration": state.wear_duration,
                    "power_strategy": state.power_strategy,
                    "priority": state.priority,
                    "user_message": user_message,
                    "mode": "auto" if state.auto_mode else "manual",
                },
                scene_components(),
            )
            state.response_json = json.dumps(response)
            blockers = response.get("blockers", [])
            state.status = f"{len(blockers)} findings from {response.get('native_view_source', 'Astra')}"
            first = blockers[0]["title"] if blockers else "No blockers found."
            state.transcript = f"You: {user_message}\nAstra: {first}"
            state.command = ""
            highlight_findings(response)
            return {"FINISHED"}


    class MISSIONPCB_OT_focus_finding(bpy.types.Operator):
        bl_idname = "missionpcb.focus_finding"
        bl_label = "Focus Finding"

        def execute(self, context):
            state = context.scene.missionpcb
            if not state.response_json:
                self.report({"WARNING"}, "Ask Astra first")
                return {"CANCELLED"}
            response = json.loads(state.response_json)
            blockers = response.get("blockers", [])
            if not blockers:
                return {"CANCELLED"}
            blocker = blockers[min(state.selected_finding, len(blockers) - 1)]
            bpy.ops.object.select_all(action="DESELECT")
            focused = None
            for ref in blocker.get("component_refs", []):
                obj = object_for_ref(ref)
                if obj:
                    obj.select_set(True)
                    focused = focused or obj
            if focused:
                context.view_layer.objects.active = focused
                state.status = f"Focused {', '.join(blocker.get('component_refs', []))}"
                return {"FINISHED"}
            return {"CANCELLED"}


    class MISSIONPCB_OT_apply_proposal(bpy.types.Operator):
        bl_idname = "missionpcb.apply_proposal"
        bl_label = "Apply Proposal"

        def execute(self, context):
            state = context.scene.missionpcb
            if not state.response_json:
                self.report({"WARNING"}, "Ask Astra first")
                return {"CANCELLED"}
            response = json.loads(state.response_json)
            for change in response.get("proposal", {}).get("changes", []):
                obj = object_for_ref(change.get("ref", ""))
                if obj:
                    dx, dy, dz = change.get("translation", [0.0, 0.0, 0.0])
                    obj.location.x += dx
                    obj.location.y += dy
                    obj.location.z += dz
            state.status = "Applied proposal; ask Astra again to rerun"
            return {"FINISHED"}


    class MISSIONPCB_OT_export(bpy.types.Operator):
        bl_idname = "missionpcb.export_widget"
        bl_label = "Export Widget Artifacts"

        def execute(self, context):
            state = context.scene.missionpcb
            response = json.loads(state.response_json) if state.response_json else {}
            out = export_widget_artifacts(response)
            state.status = f"Exported {out}"
            return {"FINISHED"}


    class MISSIONPCB_PT_widget(bpy.types.Panel):
        bl_label = "Astra"
        bl_idname = "MISSIONPCB_PT_widget"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Astra"

        def draw(self, context):
            state = context.scene.missionpcb
            layout = self.layout
            chat = layout.box()
            chat.label(text="What are we building?")
            chat.prop(state, "mission", text="")
            chat.separator()
            chat.label(text="Message Astra")
            chat.prop(state, "command", text="")
            row = chat.row(align=True)
            row.operator("missionpcb.ask_astra", text="Send")
            row.prop(state, "auto_mode", text="Auto")
            actions = chat.row(align=True)
            actions.operator("missionpcb.apply_proposal", text="Apply")
            actions.operator("missionpcb.export_widget", text="Export")

            dashboard_toggle = layout.row()
            dashboard_toggle.prop(state, "dashboard_open", text="Expand dashboard")
            layout.label(text=state.status)
            transcript = layout.box()
            for line in state.transcript.splitlines()[-4:]:
                transcript.label(text=line[:56])

            if state.dashboard_open:
                dashboard = layout.box()
                dashboard.label(text="Astra dashboard")

                interview = dashboard.box()
                interview.label(text="Fast interview")
                interview.prop(state, "wear_duration", text="Wear")
                interview.prop(state, "power_strategy", text="Power")
                interview.prop(state, "priority", text="Priority")

                loop = dashboard.box()
                loop.label(text="Loop")
                loop.label(text="1 Prompt + parts")
                loop.label(text="2 Considerations")
                loop.label(text="3 Review or auto")
                loop.label(text="4 Native actions")
                loop.label(text="5 Re-run")

                export = dashboard.box()
                export.label(text="Export readiness")
                export.label(text="Render contract: ready")
                export.label(text="BOM package: ready")
                export.label(text="KiCad/Gerbers: pending")

                if state.response_json:
                    response = json.loads(state.response_json)
                    blockers = response.get("blockers", [])
                    if blockers:
                        findings = dashboard.box()
                        findings.label(text="Findings")
                        findings.prop(state, "selected_finding", text="Index")
                        findings.operator("missionpcb.focus_finding", text="Focus")
                        for i, blocker in enumerate(blockers[:8]):
                            row = findings.row()
                            row.label(text=f"{i}: {blocker.get('title', blocker.get('id', 'Finding'))[:46]}")


    CLASSES = (
        MissionPCBState,
        MISSIONPCB_OT_ask_astra,
        MISSIONPCB_OT_focus_finding,
        MISSIONPCB_OT_apply_proposal,
        MISSIONPCB_OT_export,
        MISSIONPCB_PT_widget,
    )


    def register():
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.Scene.missionpcb = bpy.props.PointerProperty(type=MissionPCBState)


    def unregister():
        del bpy.types.Scene.missionpcb
        for cls in reversed(CLASSES):
            bpy.utils.unregister_class(cls)


    if __name__ == "__main__":
        register()
