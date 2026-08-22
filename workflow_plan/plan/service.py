"""What a Step needs to EXIST, as opposed to what flows through it.

    Variable   a typed value moving between Steps      an edge in the graph
    Service    something that must be reachable         not a value; not an edge

`RetrievePapers` consumes queries and produces pmids, and both are Variables. It also needs PubMed
to be up, which is neither an input nor an output — it does not flow, nothing produces it, and no
other Step consumes it. Modelling it as a Variable would put a fake node in every diagram and make
`topology.single_producer` demand a producer for something nobody produces.

## Why this exists at all — the naming failure that motivated it

A conversation about a builder used *"retriever"* for three different things across an hour, because
no declared object owned the word. The dataflow vocabulary was declared and precise; the
infrastructure vocabulary was not declared at all, so it drifted freely.

The fix is stolen from `docker-compose`, where the load-bearing property is not the syntax:

    services:
      database:
        volumes: [db_data:/var/lib/postgresql/data]   # reference by NAME

    volumes:
      db_data:                                        # top-level declaration is MANDATORY

**You cannot reference an undeclared volume.** That single rule is what stops the name meaning three
things — there is exactly one declared object and every use must point at it.

## ⚠️ Plan-time, not runtime — the distinction this package exists to keep

`uses = (PUBMED,)` is a REQUIREMENT, in the same family as `inputs`. It is not a record that a call
happened, and it must never grow into one: no `last_called`, no `status`, no `latency`. Those belong
to `prov:Activity`, the execution, and `typing.plan_time_only` will refuse them here.

## On grounding, stated plainly

[PROV-O][prov] has `prov:SoftwareAgent` for the THING, and this class carries that IRI.

It does NOT have a term for *"a planned Step requires this software"*. `prov:wasAssociatedWith`
links an **Activity** — an execution that already happened — to an agent, which is the runtime half.
[P-Plan][pplan] has no term for it either; its 18 terms are entirely Plan/Step/Variable structure.

So `Step.uses` is **ours**, deliberately uncited. The alternative was to cite `wasAssociatedWith`
and quietly mean something it does not say, which is exactly the failure
`provenance.grounded_citation` was written to catch after this package once cited `p-plan#Step` from
memory.

[prov]: https://www.w3.org/TR/prov-o/
[pplan]: http://purl.org/net/p-plan#
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from workflow_plan.naming.declared_term import DeclaredTerm


@dataclass(frozen=True)
class Service(DeclaredTerm):
    """Something a Step needs reachable: an API, a database, a file on disk.

    Frozen and compared by identity-of-value like `Variable`, so two Steps referencing the same
    declared object genuinely share it rather than agreeing by string.
    """

    #: The name a human uses. Unique within a Plan — `topology.declared_services` enforces it.
    name: str

    #: What it is, for a reader deciding whether an arm can be deployed somewhere. Free text on
    #: purpose: an enum here would need extending before anyone could declare a new kind of thing,
    #: which is the "annotate everything first" tax this package refuses elsewhere.
    kind: str = "api"

    #: Why the Plan cannot run without it. Not decoration — this is what a deploy decision reads.
    #: "needs a 9.5 GB file on local disk, so it cannot run on a container app" is the sentence that
    #: currently lives in a docstring where nothing checks it.
    why: str = ""

    ID: ClassVar[str] = "service"
    DEFINITION: ClassVar[str] = (
        "Something a Step needs REACHABLE — an API, a database, a file on disk. Not a value, and "
        "not an edge."
    )
    RATIONALE: ClassVar[str] = (
        "One conversation used 'retriever' for three different things in an hour, because no "
        "declared object owned the word. The dataflow vocabulary was declared and precise; the "
        "infrastructure vocabulary was not declared at all, so it drifted freely."
    )

    #: ⚠️ Was a dataclass FIELD — `field(default=..., compare=False)` — until 2026-08-22. It was
    #: the only one of the six declared as data, and `compare=False` was it already trying not to
    #: be: a citation is a property of the class, not of an instance. As a ClassVar it is excluded
    #: from `__eq__`/`__hash__` for the same reason and by construction rather than by a flag.
    ONTOLOGY_IRI: ClassVar[str] = "http://www.w3.org/ns/prov#SoftwareAgent"
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("Resource", "Dependency", "Backend")

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"Service({self.name})"
