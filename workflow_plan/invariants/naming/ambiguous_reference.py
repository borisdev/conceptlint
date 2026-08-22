"""**One name → many code concepts.** A reference that could mean more than one thing.

    class Plan: ...
    class EvidenceCaseGraph: ...

    "Add provenance validation to the graph."

"The graph" now names two things, and whoever acts on that sentence picks one. If it is a coding
agent, it picks silently and you find out from the diff.

## Two surfaces, one failure

The same ambiguity exists in code and in conversation, and only one of them is checkable today:

    IN CODE     `Protocol` declared in two modules with different shapes. Every import site has
                to know which module it came from to know what it got. Deterministic, checked here.

    IN CHAT     "the graph", "the plan", "the builder". Not checked yet — see `claimed_by`, which
                builds the index that would let something try.

⚠️ Deliberately NOT sophisticated NLP. The interfaces and fixtures come first, and detection can
improve behind them. A clever detector nobody trusts is worth less than a dumb one that fires on
the case everybody agrees about.
"""
from __future__ import annotations

from typing import Sequence

from workflow_plan.invariants.invariant import InvariantCategory, Invariant
from workflow_plan.naming.records import ModelRecord, overloaded


def _unambiguous(models: Sequence[ModelRecord]) -> None:
    hits = list(overloaded(models))
    if not hits:
        return
    detail = "; ".join(
        f"{a.name!r} in {a.file}:{a.line} and {b.file}:{b.line}" for a, b in hits[:6])
    more = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
    raise AMBIGUOUS_REFERENCE.violated(
        f"{len(hits)} name(s) claimed by more than one concept: {detail}{more}. "
        f"Rename one, or merge them.")


AMBIGUOUS_REFERENCE: Invariant[Sequence[ModelRecord]] = Invariant(
    id="naming.ambiguous_reference",
    category=InvariantCategory.NAMING,
    statement="A reference to code must not be ambiguous — one name names one concept.",
    why=("A word that means two things cannot appear in a sentence without the reader picking one, "
         "and a coding agent picks without saying so. `Evidence` as a paper, as support for a "
         "claim, and as a citation is three concepts wearing one word, and every downstream type "
         "inherits the confusion."),
    check=_unambiguous,
)
