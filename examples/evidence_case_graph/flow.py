"""The first real Plan: a study becomes findings, findings become an evidence graph.

    Study -> ParseStudyStep -> Findings -> BuildEvidenceGraphStep -> EvidenceGraph

⚠️ The EvidenceGraph produced here is the PRODUCT — the canonical IR for one case. The Plan above is
how it gets built. §10: do not collapse those two graphs. Mermaid, PDF and JSON are projections of
the EvidenceGraph, never of the Plan.

Domain types are deliberately thin. This is an example inside a generic package, and a realistic
Finding model would drag medical vocabulary into code that must stay domain-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from conceptlint.dataflow import Plan, Step, Variable


@dataclass(frozen=True)
class Study:
    pmid: str
    text: str


@dataclass(frozen=True)
class Findings:
    pmid: str
    claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceGraph:
    """The canonical case IR. Projections read this; nothing reads the Plan."""

    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = field(default_factory=tuple)


class ParseStudyStep(Step[Study, Findings]):
    consumes = Variable("study", Study)
    produces = Variable("findings", Findings)

    def run(self, value: Study) -> Findings:
        claims = tuple(s.strip() for s in value.text.split(".") if s.strip())
        return Findings(pmid=value.pmid, claims=claims)


class BuildEvidenceGraphStep(Step[Findings, EvidenceGraph]):
    consumes = Variable("findings", Findings)
    produces = Variable("graph", EvidenceGraph)

    def run(self, value: Findings) -> EvidenceGraph:
        nodes = (value.pmid, *value.claims)
        return EvidenceGraph(nodes=nodes, edges=tuple((value.pmid, c) for c in value.claims))


EVIDENCE_CASE_GRAPH = Plan(
    name="evidence_case_graph",
    steps=(ParseStudyStep(), BuildEvidenceGraphStep()),
)
