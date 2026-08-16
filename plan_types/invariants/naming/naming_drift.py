"""**Many names → one code concept.** The same thing, called several things.

    class EvidenceCaseGraphBuilder: ...

and the conversation drifts:

    EvidenceCaseGraphBuilder
    evidence assembler
    case graph generator

All three mean the one class. The danger is not untidy wording — **a coding agent eventually reads
an alias as a new architectural concept and writes a second implementation of it.** That is how a
codebase grows a duplicate nobody decided to add.

## Why two signals, both required

A shared head noun alone is noise: `UserRequest` and `SearchRequest` share one and are properly
distinct. So a pair is reported only when the name overlaps AND either

    the FIELDS overlap          the shape is the same
    the DEFINITION overlaps     the stated meaning is the same

⚠️ Fields alone were the original rule, and it was fragile in the one direction it could not
report: rename the fields and the finding vanishes while the duplicated meaning is untouched.
Two corroborators, so shape is not the only evidence.
"""
from __future__ import annotations

from typing import Sequence

from plan_types.invariants.invariant import InvariantCategory, SemanticInvariant
from plan_types.naming.records import ModelRecord, near_duplicates


def _no_drift(models: Sequence[ModelRecord]) -> None:
    hits = list(near_duplicates(models))
    if not hits:
        return
    detail = "; ".join(
        f"{a.name}/{b.name} ({score:.0%} of their {signal})" for a, b, score, signal in hits[:6])
    more = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
    raise NAMING_DRIFT.violated(
        f"{len(hits)} concept(s) reachable by more than one name: {detail}{more}. "
        f"Reuse one, declare the refinement by inheritance, or state the distinction.")


NAMING_DRIFT: SemanticInvariant[Sequence[ModelRecord]] = SemanticInvariant(
    id="naming.naming_drift",
    category=InvariantCategory.NAMING,
    statement="The same code concept must not be referred to by multiple names.",
    why=("An alias is not a wording problem. A coding agent reads `evidence assembler` beside "
         "`EvidenceCaseGraphBuilder` as a SECOND concept and writes a second implementation — so "
         "the drift becomes duplicate code, and the duplicate then needs its own maintenance, "
         "tests and eventual reconciliation."),
    check=_no_drift,
)
