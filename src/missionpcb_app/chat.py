"""Chat adapter: turns engineer requests into structured, reviewable proposals.

Two execution paths, kept explicit rather than blended:

*Demo mode* (no credentials configured) is a deterministic parser over a small
command vocabulary. Its replies are labelled as such and never attributed to
Astra.

*Provider mode* would delegate phrasing to a configured model. The interface is
defined here, but no endpoint is assumed to exist -- ``provider_status`` reports
what is actually configured, and nothing fabricates a connection.

In both paths the model never touches the design. A request becomes a
``Proposal``: a structured, previewable set of component moves the engineer
applies or rejects. Nothing here mutates state, and no free text from a model is
ever executed -- proposals are validated data with resolved component ids and
explicit millimetre deltas.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any

from .schema import DesignState

# Natural-language handles for components. Resolution is by category first
# (which comes from the parts catalogue) and then by these aliases, so a
# renamed part does not break the vocabulary.
CATEGORY_ALIASES = {
    "power_regulator": ["regulator", "reg", "buck", "power regulator", "psu"],
    "sensor": ["front end", "front-end", "frontend", "afe", "analog front end"],
    "battery": ["battery", "cell", "lipo", "pack"],
    "processor": ["mcu", "processor", "cpu", "microcontroller"],
    "wireless": ["antenna", "radio", "rf", "bluetooth", "ble"],
    "electrode": ["electrode", "electrodes", "pad"],
    "connector": ["connector", "charge port", "charging port", "pogo"],
}

SUPPORTED_COMMANDS = [
    "Move <component> <N> mm farther from <component>",
    "Move <component> to x=<N> y=<N>",
    "Why did <check id> fail?",
    "Show me the components involved in <check id>",
    "Undo my last placement change",
]


def provider_status() -> dict[str, Any]:
    """Report what is actually configured. Never assume an endpoint exists."""
    key = os.environ.get("ASTRA_API_KEY") or os.environ.get("MISSIONPCB_MODEL_API_KEY")
    endpoint = os.environ.get("ASTRA_ENDPOINT") or os.environ.get(
        "MISSIONPCB_MODEL_ENDPOINT"
    )
    configured = bool(key and endpoint)
    return {
        "mode": "provider" if configured else "demo",
        "configured": configured,
        "endpoint_configured": bool(endpoint),
        # The key itself is never returned; only whether one is present.
        "credential_present": bool(key),
        "label": (
            "Configured model provider"
            if configured
            else "Deterministic demo mode — responses are generated locally by "
                 "rule, not by Astra or any model."
        ),
        "supported_commands": SUPPORTED_COMMANDS,
    }


def _resolve(design: DesignState, phrase: str, parts_index: dict[str, Any]) -> list[str]:
    """Map a phrase to candidate component refs. Ambiguity is preserved."""
    phrase = phrase.strip().lower()
    if not phrase:
        return []

    exact = [c.ref for c in design.components if c.ref.lower() == phrase]
    if exact:
        return exact

    hits: list[str] = []
    for comp in design.components:
        part = parts_index.get(comp.part_id)
        category = getattr(part, "category", "") if part else ""
        name = (getattr(part, "name", "") if part else "").lower()

        if phrase in comp.ref.lower() or (name and phrase in name):
            hits.append(comp.ref)
            continue
        for alias in CATEGORY_ALIASES.get(category, []):
            if alias in phrase or phrase in alias:
                hits.append(comp.ref)
                break
    return sorted(set(hits))


def _move_away(
    design: DesignState, mover: str, anchor: str, delta_mm: float
) -> dict[str, Any]:
    """Push ``mover`` ``delta_mm`` further from ``anchor`` along their axis.

    Pure geometry on the current state; the engine still has the final say on
    whether the result actually passes.
    """
    m = design.component(mover)
    a = design.component(anchor)
    vx, vy = m.pos_mm[0] - a.pos_mm[0], m.pos_mm[1] - a.pos_mm[1]
    length = math.hypot(vx, vy)
    if length < 1e-6:
        vx, vy, length = 1.0, 0.0, 1.0  # coincident: pick a deterministic axis
    ux, uy = vx / length, vy / length
    return {
        "ref": mover,
        "field": "pos_mm",
        "before": [round(m.pos_mm[0], 3), round(m.pos_mm[1], 3)],
        "after": [
            round(m.pos_mm[0] + ux * delta_mm, 3),
            round(m.pos_mm[1] + uy * delta_mm, 3),
        ],
    }


def _component_payload(design: DesignState, parts_index: dict[str, Any]) -> list[dict[str, Any]]:
    payload = []
    for comp in design.components:
        part = parts_index.get(comp.part_id)
        payload.append(
            {
                "ref": comp.ref,
                "part_id": comp.part_id,
                "kicad_ref": comp.kicad_ref,
                "position_mm": [comp.pos_mm[0], comp.pos_mm[1]],
                "rotation_deg": comp.normalised_rotation(),
                "category": getattr(part, "category", "unknown") if part else "unknown",
                "name": getattr(part, "name", comp.part_id) if part else comp.part_id,
                "size_mm": [
                    getattr(part, "length_mm", None) if part else None,
                    getattr(part, "width_mm", None) if part else None,
                    getattr(part, "height_mm", None) if part else None,
                ],
                "flags": {
                    "heat_source": bool(getattr(part, "heat_source", False)) if part else False,
                    "noise_source": bool(getattr(part, "noise_source", False)) if part else False,
                    "skin_contact": bool(getattr(part, "skin_contact", False)) if part else False,
                    "sensitivity": getattr(part, "sensitivity", "none") if part else "none",
                },
            }
        )
    return payload


def _extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks)


def _json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalise_provider_change(
    change: dict[str, Any],
    design: DesignState,
) -> dict[str, Any]:
    ref = str(change.get("ref", "")).strip()
    comp = design.component(ref) if ref else None
    if comp is None:
        raise ValueError(f"model proposed unknown component ref: {ref!r}")

    field = change.get("field", "pos_mm")
    if field == "pos_mm":
        after = change.get("after")
        if (
            not isinstance(after, list)
            or len(after) != 2
            or not all(isinstance(v, (int, float)) for v in after)
        ):
            raise ValueError(f"model proposed invalid pos_mm for {ref}")
        return {
            "ref": ref,
            "field": "pos_mm",
            "before": [round(comp.pos_mm[0], 3), round(comp.pos_mm[1], 3)],
            "after": [round(float(after[0]), 3), round(float(after[1]), 3)],
        }
    if field == "rotation_deg":
        after = change.get("after")
        if not isinstance(after, (int, float)):
            raise ValueError(f"model proposed invalid rotation_deg for {ref}")
        return {
            "ref": ref,
            "field": "rotation_deg",
            "before": comp.normalised_rotation(),
            "after": int(round(float(after) / 90.0)) * 90 % 360,
        }
    raise ValueError(f"model proposed unsupported field: {field!r}")


def _provider_interpret(
    message: str,
    design: DesignState,
    parts_index: dict[str, Any],
) -> dict[str, Any]:
    key = os.environ.get("ASTRA_API_KEY") or os.environ.get("MISSIONPCB_MODEL_API_KEY")
    endpoint = os.environ.get("ASTRA_ENDPOINT") or os.environ.get("MISSIONPCB_MODEL_ENDPOINT")
    if not key or not endpoint:
        raise RuntimeError("model provider is not configured")

    model = os.environ.get("ASTRA_MODEL") or os.environ.get("MISSIONPCB_MODEL") or "gpt-5-mini"
    context = {
        "design_id": design.design_id,
        "revision": design.revision,
        "board_units": "mm",
        "components": _component_payload(design, parts_index),
        "supported_actions": [
            {"field": "pos_mm", "after": "[x_mm, y_mm]"},
            {"field": "rotation_deg", "after": "0|90|180|270"},
        ],
    }
    system = (
        "You are Astra, an AI electrical engineer controlling KiCad through a safe "
        "proposal interface. Return strict JSON only. Do not invent component refs. "
        "If the user asks for a board manipulation, produce at most two validated "
        "changes. If more information is needed, set needs_clarification true. "
        "Schema: {\"reply\": string, \"needs_clarification\": boolean, "
        "\"considerations\": string[], \"proposal\": null | {\"explanation\": string, "
        "\"changes\": [{\"ref\": string, \"field\": \"pos_mm\"|\"rotation_deg\", "
        "\"after\": number[]|number}]}}."
    )
    req_payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {"user_message": message, "current_design": context},
                    separators=(",", ":"),
                ),
            },
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(req_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"model provider HTTP {exc.code}: {detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"model provider unavailable: {exc}") from exc

    parsed = _json_from_text(_extract_response_text(raw))
    out: dict[str, Any] = {
        "mode": "provider",
        "provider_label": "Configured model provider",
        "needs_clarification": bool(parsed.get("needs_clarification", False)),
        "reply": str(parsed.get("reply") or "Astra returned a proposal."),
        "considerations": parsed.get("considerations", []),
        "raw_response_id": raw.get("id"),
    }
    proposal = parsed.get("proposal")
    if proposal and isinstance(proposal, dict):
        changes = [
            _normalise_provider_change(change, design)
            for change in proposal.get("changes", [])
            if isinstance(change, dict)
        ][:2]
        if changes:
            out["proposal"] = {
                "proposal_id": uuid.uuid4().hex,
                "design_id": design.design_id,
                "base_revision": design.revision,
                "status": "pending",
                "user_request": message,
                "explanation": str(proposal.get("explanation") or out["reply"]),
                "changes": changes,
                "component_refs": sorted({change["ref"] for change in changes}),
                "native_tool": "kicad",
            }
    return out


def interpret(
    message: str, design: DesignState, parts_index: dict[str, Any]
) -> dict[str, Any]:
    """Interpret one message into a reply, and optionally a proposal.

    Returns a dict with ``reply``, ``mode``, optional ``proposal``, and
    ``needs_clarification``. A request this parser cannot resolve produces a
    focused question rather than an arbitrary move.
    """
    status = provider_status()
    text = message.strip()
    lowered = text.lower()
    base = {"mode": status["mode"], "provider_label": status["label"]}

    if status["mode"] == "provider":
        try:
            return _provider_interpret(text, design, parts_index)
        except Exception as exc:
            base = {
                "mode": "provider_error",
                "provider_label": f"Model provider failed; local fallback used: {exc}",
            }

    # "move <a> <n> mm (farther|away) from <b>"
    match = re.search(
        r"move\s+(?:the\s+)?(.+?)\s+(?-i:)?([\d.]+)\s*mm\s+(?:farther|further|away)\s+from\s+(?:the\s+)?(.+?)[.?]?$",
        lowered,
    )
    if match:
        mover_phrase, amount, anchor_phrase = match.groups()
        movers = _resolve(design, mover_phrase, parts_index)
        anchors = _resolve(design, anchor_phrase, parts_index)

        if len(movers) != 1 or len(anchors) != 1:
            options = movers if len(movers) != 1 else anchors
            unclear = mover_phrase if len(movers) != 1 else anchor_phrase
            return {
                **base,
                "needs_clarification": True,
                "reply": (
                    f"'{unclear.strip()}' matches {len(options)} components"
                    f"{': ' + ', '.join(options) if options else ''}. "
                    "Which one did you mean?"
                ),
            }

        change = _move_away(design, movers[0], anchors[0], float(amount))
        return {
            **base,
            "needs_clarification": False,
            "reply": (
                f"Proposed moving {movers[0]} {amount} mm further from "
                f"{anchors[0]}, from ({change['before'][0]}, {change['before'][1]}) "
                f"to ({change['after'][0]}, {change['after'][1]}) mm. "
                "Nothing has changed yet — review and apply."
            ),
            "proposal": {
                "proposal_id": uuid.uuid4().hex,
                "design_id": design.design_id,
                "base_revision": design.revision,
                "status": "pending",
                "user_request": text,
                "explanation": (
                    f"Moves {movers[0]} along the {movers[0]}-{anchors[0]} axis. "
                    "Effects are shown by re-running analysis after it is applied."
                ),
                "changes": [change],
                "component_refs": [movers[0]],
            },
        }

    # "move <a> to x=<n> y=<n>"
    match = re.search(
        r"move\s+(?:the\s+)?(.+?)\s+to\s+x\s*=\s*([\d.-]+)[,\s]+y\s*=\s*([\d.-]+)",
        lowered,
    )
    if match:
        phrase, x_str, y_str = match.groups()
        refs = _resolve(design, phrase, parts_index)
        if len(refs) != 1:
            return {
                **base,
                "needs_clarification": True,
                "reply": (
                    f"'{phrase.strip()}' matches {len(refs)} components"
                    f"{': ' + ', '.join(refs) if refs else ''}. Which one?"
                ),
            }
        comp = design.component(refs[0])
        return {
            **base,
            "needs_clarification": False,
            "reply": (
                f"Proposed placing {refs[0]} at ({x_str}, {y_str}) mm. "
                "Nothing has changed yet — review and apply."
            ),
            "proposal": {
                "proposal_id": uuid.uuid4().hex,
                "design_id": design.design_id,
                "base_revision": design.revision,
                "status": "pending",
                "user_request": text,
                "explanation": f"Sets {refs[0]} to an explicit board-local position.",
                "changes": [
                    {
                        "ref": refs[0],
                        "field": "pos_mm",
                        "before": [round(comp.pos_mm[0], 3), round(comp.pos_mm[1], 3)],
                        "after": [float(x_str), float(y_str)],
                    }
                ],
                "component_refs": [refs[0]],
            },
        }

    if "undo" in lowered:
        return {
            **base,
            "needs_clarification": False,
            "reply": "Use Undo in the toolbar — it reverts the last applied edit "
                     "and records the reversal as its own history event.",
            "action": "undo_hint",
        }

    if lowered.startswith("why") or "explain" in lowered:
        return {
            **base,
            "needs_clarification": False,
            "reply": (
                "Select the check in the issues list — its panel shows the measured "
                "value, the threshold, the method used, and the stated assumptions. "
                "Those numbers come from the constraint engine; this demo mode "
                "quotes them rather than deriving anything."
            ),
        }

    return {
        **base,
        "needs_clarification": True,
        "reply": (
            "Demo mode understands a small command set:\n- "
            + "\n- ".join(SUPPORTED_COMMANDS)
            + "\nNo model credentials are configured, so this reply was produced "
              "locally by rule, not by Astra."
        ),
    }
