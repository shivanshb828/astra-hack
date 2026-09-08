"""The judgment half of MissionPCB.

Takes what the builder said about their product, plus the part catalog's
physical facts, and produces considerations: what to change, replace, add, or
drop, and why. This is the half with no closed form -- "worn against skin all
day" becomes a temperature limit, and a datasheet's dissipation formula becomes
a placement consequence, only because a model read both and connected them.

What it deliberately does not do is arithmetic. It never computes a distance,
never decides whether 13.5 mm clears 15 mm, and never reports a pass or fail.
Those are `constraint_engine`'s job, where they are reproducible. When a
consideration *can* be expressed as a checkable threshold, this module emits it
as one (`engine_encoding`) and hands it over rather than evaluating it.

Unlike `constraint_engine`, this package makes network calls and depends on the
Anthropic SDK, so it is not importable from Blender. That separation is the
point.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - exercised in no-SDK dev envs
    anthropic = None

from .catalog import PartRecord, render_catalog
from .schema import AdvisorOutput

MODEL = "claude-opus-5"
# Streamed, so the SDK's non-streaming timeout guard does not apply. A full
# pass over a 29-part catalog reasons for a while before emitting, and a
# truncated structured output is unparseable rather than merely short.
MAX_TOKENS = 64_000

SYSTEM_ROLE = """\
You are a senior hardware engineer reviewing a parts catalog against a product \
brief, before any board has been laid out.

Your output is a set of considerations: concrete changes to the design, each \
one traceable to a fact in the catalog or to named engineering knowledge.

## What you decide, and what you must not

You decide what the rules are. Turning "worn against skin all day" into a \
temperature limit, reading a dissipation formula and recognising what it means \
for placement, judging that a part is wrong for this mission -- that is your \
job, and nothing else can do it.

You do not do arithmetic. A deterministic engine downstream computes every \
distance, gap, and overlap. Do not state a measured separation, do not declare \
a layout pass or fail, and do not claim a specific temperature rise unless the \
catalog gives you the formula and every input it needs. When a consideration \
reduces to a checkable threshold, put it in `engine_encoding` as a threshold \
with units and let the engine measure it.

## Evidence discipline

Every claim about a part must cite the catalog line it came from, with the \
document and page as the record gives it. Quote the number and its units.

Never invent a citation. If the catalog does not contain the fact, either omit \
the claim, or make it and say plainly in `why` that it rests on general \
engineering knowledge rather than this catalog -- then leave `evidence` empty. \
An unsourced recommendation that is honest about being unsourced is useful. One \
wearing a fabricated page number is worse than nothing.

Measurement conditions are part of the value. A theta-JA of 230 C/W on minimum \
copper and 130 C/W on a generous pour are different facts; say which one you \
used. `typ` and `max` are not interchangeable.

## What makes a consideration worth writing

Prefer the specific over the general. "The charger dissipates worst-case during \
the precondition-to-constant-current transition, not at steady state, so a \
thermal check at average charge current understates it" is worth writing. \
"Consider thermal management" is not.

Report absent data as a finding when it blocks a decision. A record that says a \
dimension was deliberately not extracted is telling you something; if a real \
decision waits on that number, say so rather than working around it.

Look for what the brief implies but the BOM does not contain. A part that \
should be there and is not is often the most valuable thing to surface.

Say what each change costs. A recommendation with no tradeoff is usually one \
you have not finished thinking through.

Order considerations by what would hurt most if ignored.
"""


def build_mission_prompt(
    mission: str,
    current_bom: str | None = None,
    engine_findings: str | None = None,
) -> str:
    """Assemble the varying half of the prompt (everything after the cache)."""
    parts = ["# Product brief", "", mission.strip(), ""]

    if current_bom:
        parts += [
            "# Parts currently selected for this build",
            "",
            "These are the parts already chosen. Considerations about them carry "
            "more weight than considerations about parts nobody picked.",
            "",
            current_bom.strip(),
            "",
        ]

    if engine_findings:
        parts += [
            "# What the deterministic engine already measured",
            "",
            "These geometric facts were computed exactly. Quote them; do not "
            "recompute or second-guess them. Use them as input to your judgment "
            "about what to change.",
            "",
            engine_findings.strip(),
            "",
        ]

    parts += [
        "# Your task",
        "",
        "Review the catalog against this brief and produce the considerations.",
        "",
        "Work through it in this order:",
        "1. What does the brief constrain that a schematic would not show? "
        "Environment, duty cycle, who touches it, what happens when it fails.",
        "2. For each part in play, what does it emit and what disturbs it? "
        "Which of those channels actually collide in *this* product?",
        "3. Where the catalog holds alternatives for the same role, is the "
        "better choice clear from the data? If it is, say which and why. If the "
        "data does not settle it, say that instead of picking arbitrarily.",
        "4. What does the brief imply that the catalog has no part for?",
        "5. What decision is blocked on a number nobody has extracted yet?",
    ]
    return "\n".join(parts)


def _client(api_key: str | None = None):
    if anthropic is None:
        raise RuntimeError(
            "anthropic is not installed. Install the provider SDK to run a live "
            "advisor pass, or use --dry-run to inspect the assembled prompt."
        )
    # A bare constructor also resolves ANTHROPIC_AUTH_TOKEN and `ant auth login`
    # profiles, so do not require the env var to be set.
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


class RefusalError(RuntimeError):
    """The request was declined by safety classifiers rather than answered."""


def advise(
    mission: str,
    records: list[PartRecord],
    current_bom: str | None = None,
    engine_findings: str | None = None,
    effort: str = "high",
    api_key: str | None = None,
) -> tuple[AdvisorOutput, dict[str, int]]:
    """Run one advisory pass. Returns the parsed output and token usage.

    The catalog goes in the system prompt behind a cache breakpoint and the
    mission goes in the user turn, because the catalog is stable across runs
    and the brief is not -- caching is a prefix match, so the stable half has to
    come first to be reusable.
    """
    client = _client(api_key)

    # Streamed rather than a plain create: a full catalog pass runs for minutes
    # at high effort, which is long enough to trip the SDK's non-streaming
    # timeout guard.
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": effort},
        system=[
            {"type": "text", "text": SYSTEM_ROLE},
            {
                "type": "text",
                "text": render_catalog(records),
                # Stable across every run against this catalog; the varying
                # brief sits after it in the user turn.
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[
            {
                "role": "user",
                "content": build_mission_prompt(mission, current_bom, engine_findings),
            }
        ],
        output_format=AdvisorOutput,
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        category = getattr(detail, "category", None) if detail else None
        raise RefusalError(
            f"The request was declined by safety classifiers (category: {category}). "
            f"Nothing was generated."
        )

    if response.parsed_output is None:
        raise RuntimeError(
            f"Model returned no parseable output (stop_reason={response.stop_reason}). "
            f"If this is 'max_tokens', raise MAX_TOKENS."
        )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_input_tokens": getattr(
            response.usage, "cache_read_input_tokens", 0
        ) or 0,
        "cache_creation_input_tokens": getattr(
            response.usage, "cache_creation_input_tokens", 0
        ) or 0,
    }
    return response.parsed_output, usage


def read_mission(source: str) -> str:
    """Accept a brief as either an inline string or a path to a file."""
    path = Path(source)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return source
