"""`ONTOLOGY_IRI` is a citation. This is the rule that reads the source.

The failure it exists for happened in this package. `Step` declared

    ONTOLOGY_IRI = "http://purl.org/net/p-plan#Step"      # "P-Plan grounding"

written **from memory**, and was then given one input and one output while P-Plan puts no
cardinality on `hasInputVar` or `hasOutputVar`. Nobody lied — the IRI looked authoritative and **no
mechanism could disagree with it**. An external claim with no path back to the source is
indistinguishable from a checked one, right up until someone reads the ontology.

## What it can and cannot decide

    can     the cited term EXISTS in an ontology we have vendored
    cannot  the cited term MEANS what our implementation does

The second is a reading, not a decision procedure, and a rule pretending otherwise would be
judgement dressed as a check. That half lives in `tests/test_pplan_grounding.py`, which asserts the
specific axioms the design depends on.

⚠️ A citation to an ontology we have NOT vendored is REPORTED, not ignored. "We cannot check this"
and "this is fine" must never render the same.
"""
from __future__ import annotations

import pathlib
import re
from typing import Sequence

from workflow_plan.invariants.invariant import InvariantCategory, SemanticInvariant
from workflow_plan.naming.records import ModelRecord

VENDORED = pathlib.Path(__file__).resolve().parents[2] / "ontology" / "vendored"

#: prefix -> the vendored file defining its terms. A prefix absent here is UNCHECKABLE, which is a
#: finding of its own rather than a pass.
ONTOLOGIES: dict[str, str] = {
    "http://purl.org/net/p-plan#": "p-plan.ttl",
    "http://www.w3.org/ns/prov#": "prov-o.ttl",
}

_SUBJECT = re.compile(r"^:(\w+)", re.MULTILINE)


def terms_in(filename: str) -> set[str]:
    """Every term a vendored ontology defines.

    Reads Turtle subjects rather than importing an RDF library: a parser dependency to check a
    handful of names is weight nobody asked for, and these serialisations are regular enough that
    the regex is honest about what it does.
    """
    path = VENDORED / filename
    if not path.exists():
        return set()
    return set(_SUBJECT.findall(path.read_text(encoding="utf-8")))


def _grounded(models: Sequence[ModelRecord]) -> None:
    problems: list[str] = []
    for m in models:
        iri = m.ontology_iri
        if not iri:
            continue                       # grounding is optional; most concepts are ours

        prefix = next((p for p in ONTOLOGIES if iri.startswith(p)), None)
        if prefix is None:
            problems.append(
                f"{m.name} cites {iri}, from an ontology this repo has not vendored — an "
                f"unverifiable citation reads exactly like a verified one")
            continue

        known = terms_in(ONTOLOGIES[prefix])
        if not known:
            problems.append(
                f"{m.name} cites {prefix} but its vendored file is missing or unreadable — an "
                f"empty ontology makes every citation vacuously pass, which is worse than not "
                f"checking")
            continue

        term = iri[len(prefix):]
        if term not in known:
            problems.append(f"{m.name} cites {iri}, and {term!r} is not a term in that ontology")

    if problems:
        raise GROUNDED_CITATION.violated("; ".join(problems))


GROUNDED_CITATION: SemanticInvariant[Sequence[ModelRecord]] = SemanticInvariant(
    id="provenance.grounded_citation",
    category=InvariantCategory.PROVENANCE,
    statement="Every ONTOLOGY_IRI names a term that exists in an ontology vendored in this repo.",
    why=("An ONTOLOGY_IRI asserts that a concept's meaning is the one defined elsewhere. Written "
         "from memory it is indistinguishable from a checked claim — which is how `Step` came to "
         "cite p-plan#Step while implementing a linear pipeline P-Plan does not describe. A "
         "citation nobody can follow is decoration with the authority of a fact."),
    check=_grounded,
)

ALL: tuple[SemanticInvariant[Sequence[ModelRecord]], ...] = (GROUNDED_CITATION,)
