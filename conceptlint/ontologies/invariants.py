"""`ONTOLOGY_IRI` is a citation, and a citation nobody follows is decoration.

The failure this exists to prevent happened here, in this package, on 2026-08-15. `dataflow/step.py`
declared `ONTOLOGY_IRI = "http://purl.org/net/p-plan#Step"` and then implemented a linear pipeline
that P-Plan does not describe: P-Plan puts no cardinality on `hasInputVar` or `hasOutputVar`, so a
Step may consume and produce many Variables, and `MultiStep` — a Plan that is also a Step — has no
representation here at all.

Nobody lied. The IRI was written from memory, it looked authoritative, and **no mechanism could
disagree with it**. That is the whole problem: an external claim with no path back to the source is
indistinguishable from a checked one, right up until someone reads the ontology.

## Why this is the FIRST law, not a third one

It reads like a new category — "grounding" — and it is not. `ONTOLOGY_IRI` asserts *this concept's
meaning is the one defined over there*. If the cited term does not exist, or exists and means
something else, then the word `Step` means one thing in P-Plan and another here **while claiming to
be the same concept**. That is one concept with two meanings, across a repository boundary.

Adding a third law to hold one rule would be the synonym list this project warns about.

## What it can and cannot check

    can     the cited term EXISTS in an ontology we have vendored
    cannot  the cited term means what our implementation does

The second is a reading, not a decision procedure, and an invariant that pretended otherwise would
be the judgement-dressed-as-a-rule that `case-ir.md` forbids. So the semantic half lives in
`tests/test_pplan_grounding.py`, where each divergence is a named `xfail(strict=True)` that fails
when it starts passing.

⚠️ A citation to an ontology we have NOT vendored is reported, not ignored. "We cannot check this"
and "this is fine" must never render the same, which is the same rule as `supports=None` never
rendering as verified.
"""
from __future__ import annotations

import pathlib
import re
from typing import ClassVar, Iterable, Sequence

from conceptlint.core.concept import Concept
from conceptlint.core.invariant import ConceptIssue, Invariant

ONTOLOGIES_DIR = pathlib.Path(__file__).resolve().parent

#: prefix -> the vendored file that defines its terms, relative to this package.
#:
#: A prefix ABSENT here is UNCHECKABLE, and that is reported rather than passed. "We cannot check
#: this" and "this is fine" must never render the same — the same rule that keeps `supports=None`
#: from rendering as verified. Vendoring PROV-O was prompted by exactly that: `Activity` and
#: `Entity` cited prov# and this invariant said so on its first run.
ONTOLOGIES: dict[str, str] = {
    "http://purl.org/net/p-plan#": "pplan/vendored/p-plan.ttl",
    "http://www.w3.org/ns/prov#": "provo/vendored/prov-o.ttl",
}

_SUBJECT = re.compile(r"^:(\w+)", re.MULTILINE)


def terms_in(filename: str) -> set[str]:
    """Every term the vendored ontology defines.

    Reads subjects out of Turtle rather than importing an RDF library: a linter that drags in a
    parser to check five names has bought weight nobody asked for, and P-Plan's serialisation is
    regular enough that the regex is honest about what it does.
    """
    path = ONTOLOGIES_DIR / filename
    if not path.exists():
        return set()
    return set(_SUBJECT.findall(path.read_text(encoding="utf-8")))


class GroundedCitation(Invariant):
    """An `ONTOLOGY_IRI` must name a term that exists in an ontology we have on disk."""

    ID: ClassVar[str] = "grounded-citation"
    LAW: ClassVar[str] = "one-concept-one-meaning"
    WHY: ClassVar[str] = (
        "An ONTOLOGY_IRI asserts that this concept's meaning is the one defined elsewhere. Written "
        "from memory it is indistinguishable from a checked claim — which is how `Step` came to "
        "cite p-plan#Step while implementing a linear pipeline P-Plan does not describe. A "
        "citation nobody can follow is decoration with the authority of a fact.")

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        for c in concepts:
            iri = getattr(c, "ONTOLOGY_IRI", "") or ""
            if not iri:
                continue                      # grounding is optional; most concepts are ours

            prefix = next((p for p in ONTOLOGIES if iri.startswith(p)), None)
            if prefix is None:
                yield ConceptIssue(
                    self.ID,
                    f"{c.__name__} cites {iri}, from an ontology this repo has not vendored",
                    [c.__name__],
                    "vendor the ontology under ontologies/*/vendored/ with its source URL and a "
                    "hash, or drop the IRI — an unverifiable citation reads exactly like a "
                    "verified one")
                continue

            known = terms_in(ONTOLOGIES[prefix])
            if not known:
                yield ConceptIssue(
                    self.ID,
                    f"{c.__name__} cites {prefix} but its vendored file is missing or unreadable",
                    [c.__name__],
                    f"restore {ONTOLOGIES_DIR / ONTOLOGIES[prefix]} — an empty ontology makes every "
                    f"citation vacuously pass, which is worse than not checking")
                continue

            term = iri[len(prefix):]
            if term not in known:
                yield ConceptIssue(
                    self.ID,
                    f"{c.__name__} cites {iri}, and {term!r} is not a term in that ontology",
                    [c.__name__],
                    "fix the IRI to a term that exists, or remove it — the name was probably "
                    "recalled rather than read")
