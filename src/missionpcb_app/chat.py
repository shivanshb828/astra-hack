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

import math
import os
import re
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
