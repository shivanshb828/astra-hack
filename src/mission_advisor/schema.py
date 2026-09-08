"""Structured output schema for the mission advisor.

Every consideration has to be checkable by a human in about thirty seconds,
which is what the `evidence` field is for: a claim about a part must quote the
catalog line and its citation, not paraphrase from memory. A recommendation
with no evidence is an opinion, and the schema makes that visible rather than
letting it blend in with the sourced ones.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Action = Literal[
    "replace",                # swap one part for another
    "add",                    # a part the mission implies but the BOM lacks
    "remove",                 # a part that earns nothing here
    "change_operating_point",  # same BOM, different configuration
    "add_constraint",         # a placement rule the engine should enforce
    "investigate",            # a real question the data cannot settle
]

Severity = Literal["blocker", "major", "minor", "info"]
Confidence = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    """A quoted fact from the catalog, with its citation."""

    part_id: str = Field(description="Catalog id the fact came from.")
    fact: str = Field(
        description="The fact, quoted or closely paraphrased from the record. "
        "Include the number and its units."
    )
    citation: str = Field(
        description="Document and page from the record, e.g. 'DS20001984H p.18'. "
        "Use 'no citation in record' when the record has none -- never invent one."
    )


class Consideration(BaseModel):
    """One recommended change to the design."""

    id: str = Field(description="Short kebab-case slug, e.g. 'charger-thermal-vs-skin'.")
    action: Action
    title: str = Field(description="One line, states the change, not the problem.")
    severity: Severity
    confidence: Confidence = Field(
        description="high = the catalog data settles it. medium = it follows from "
        "the data plus a standard engineering assumption. low = plausible but the "
        "data does not settle it."
    )
    subject_part_ids: list[str] = Field(
        description="Catalog ids this concerns. Empty if it concerns a gap in the BOM."
    )
    proposed_part_ids: list[str] = Field(
        description="Catalog ids proposed as replacements or additions. Empty for "
        "other actions. Only ids that exist in the catalog."
    )
    what_changes: str = Field(description="Concretely, what to do.")
    why: str = Field(
        description="The physical mechanism, in this product's terms. Name what "
        "actually goes wrong for the user or patient, not the rule that was broken."
    )
    tradeoff: str = Field(
        description="What this costs -- money, board area, current, complexity, or "
        "a capability given up. Write 'none material' only when that is true."
    )
    evidence: list[Evidence] = Field(
        description="Catalog facts supporting this. Empty means the recommendation "
        "rests on general engineering knowledge rather than the catalog -- allowed, "
        "but say so in `why`."
    )
    engine_encoding: str | None = Field(
        default=None,
        description="If this can be expressed as a constraint the deterministic "
        "engine could check, state it as a threshold with units, e.g. "
        "'min 8 mm edge gap between bat-lipo and any part with heat_source'. "
        "Null when the change is not geometric.",
    )


class AdvisorOutput(BaseModel):
    """The full advisory pass over one mission and one catalog."""

    mission_summary: str = Field(
        description="What the product is and what actually constrains it, in two "
        "or three sentences, as understood from the brief."
    )
    considerations: list[Consideration]
    open_questions: list[str] = Field(
        description="Questions whose answers would change the recommendations. "
        "Ask the builder, do not guess."
    )
    unmodeled_risks: list[str] = Field(
        description="Real risks this pass cannot assess -- missing catalog fields, "
        "physics outside the data, anything needing measurement rather than review."
    )
