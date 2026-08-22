"""The EXECUTION graph: what actually happened, as typed nodes and typed edges.

    Plan / Step / Variable      what SHOULD happen   — reusable across thousands of runs
    Run / Activity / Entity     what DID happen      — instances, with ids

Ported from `nobs.dataflow.model` (nobsmed-v2), renamed onto the P-Plan/PROV-O nouns: `Artifact` ->
`Entity`, `StepRun` -> `Activity`. The rename is the point — the old names were private synonyms for
concepts that already had public ones, which is `no-private-synonym` committed by the authors of the
linter.

## Why this is not an execution framework

There is no retry, durability, checkpointing, fan-out or parallelism here, and there must not be
(§11). This records what happened; it does not decide what happens. A `Run` is a provenance
document, and PROV-O is a vocabulary for exactly that.

## Provenance is a typed graph, never a log

A log is grep-able and unqueryable. Typed edges mean "which Activity produced this Entity" is a
lookup, and "this finding derives from nothing" is distinguishable from "this finding is a root" —
which a dangling id in a log is not.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field, SerializeAsAny, model_validator


class GraphError(Exception):
    """A Run that does not hold together. Raised on construction, never during traversal.

    ⚠️ Subclasses `Exception`, NOT `ValueError`, and that is deliberate. Pydantic catches
    `ValueError` inside a validator and rewraps it as a `ValidationError` — so a caller doing
    `except GraphError` would never fire, while the docstring promised it would. A non-ValueError
    propagates unwrapped and the promise holds.
    """


#: kind tag -> class, populated by `__init_subclass__`.
#:
#: ⚠️ Load-bearing, and it took a real bug to earn. `Run.entities` is `dict[str, Entity]`, and
#: Pydantic serialises against the DECLARED type — so a subclass's extra fields were silently
#: dropped ON WRITE. `SerializeAsAny` on the containers fixes the write; this registry plus the
#: validator below fixes the read. Both halves are needed; either alone looks like it works.
KINDS: dict[str, type[Node]] = {}


class Node(BaseModel):
    """Shared shape of every execution node: a stable id, and a wire tag naming its class.

    ⚠️ NO `metadata` dict. There was one, and removing it is the point: an untyped escape hatch on
    every node is where domain fields go to avoid being modelled.
    """

    KIND: ClassVar[str] = ""

    id: str
    kind: str = ""

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if cls.KIND:
            if cls.KIND in KINDS and KINDS[cls.KIND] is not cls:
                raise GraphError(
                    f"kind {cls.KIND!r} is claimed by {KINDS[cls.KIND].__name__} and {cls.__name__}. "
                    f"Two classes on one tag means deserialisation silently drops one's fields.")
            KINDS[cls.KIND] = cls

    @model_validator(mode="after")
    def _stamp_kind(self) -> Node:
        if not self.kind:
            object.__setattr__(self, "kind", type(self).KIND)
        return self


class Entity(Node):
    """One actual value: prov:Entity. The runtime instantiation of a plan-time `Variable`.

    A Variable says `Findings`. An Entity is the findings from pmid:123, with an id worth joining on.
    """

    KIND: ClassVar[str] = "entity"
    ONTOLOGY_IRI: ClassVar[str] = "http://www.w3.org/ns/prov#Entity"

    #: None means NOT HASHED — never "hashed to nothing". An unhashed Entity cannot take part in a
    #: cache decision, and treating None as a hash would collapse every unhashed one onto one key.
    content_hash: str | None = None


class Activity(Node):
    """One execution of a Step: prov:Activity.

    ⚠️ Temporal's `Activity` is THIS, not a `Step`. Anyone who maps their Activity onto our Step is
    wrong by exactly one level and has no reason to suspect it.
    """

    KIND: ClassVar[str] = "activity"
    ONTOLOGY_IRI: ClassVar[str] = "http://www.w3.org/ns/prov#Activity"

    step_name: str
    started_at: datetime
    ended_at: datetime | None = None
    outcome: str = "ok"          # "ok" | "error"
    error: str = ""

    #: How long the step took, from a MONOTONIC clock. Deliberately NOT derived from
    #: `ended_at - started_at`.
    #:
    #: Those timestamps are PROVENANCE — when it happened, for correlating against logs. This is
    #: MEASUREMENT. The two have no reason to share a failure mode, and deriving one from the other
    #: means a clock correction silently corrupts a performance number. The corruption is asymmetric:
    #: an NTP step backwards gives a NEGATIVE duration, something downstream clamps it, and a
    #: 40-second step reports as instant — which reads as a result rather than an error.
    #:
    #: ⚠️ `None` means NOT MEASURED, never zero. Zero is a legitimate measured value, since a
    #: sub-millisecond step rounds to 0.0. A renderer showing `None` as `0.0s` or a dash puts back
    #: exactly the failure above.
    duration_secs: float | None = None

    @model_validator(mode="after")
    def _duration_is_a_measurement(self) -> Activity:
        """Two shapes a monotonic measurement cannot legally have.

        A monotonic clock does not run backwards, so a negative duration is not a slow step — it is
        proof the value did not come from one, and almost certainly came from subtracting two
        wall-clock timestamps across a correction. Refused here rather than clamped later.

        And a step that has not ended has no duration. Allowing one would make "still running" and
        "finished, unmeasured" the same state.
        """
        if self.duration_secs is not None and self.duration_secs < 0:
            raise GraphError(
                f"Activity {self.id!r} has duration_secs={self.duration_secs}. A monotonic clock "
                f"does not run backwards, so a negative duration means this was derived from "
                f"wall-clock timestamps across a correction, not measured. Use time.monotonic().")
        if self.ended_at is None and self.duration_secs is not None:
            raise GraphError(
                f"Activity {self.id!r} has a duration but no ended_at. A step that has not ended "
                f"has no duration; allowing one makes 'still running' and 'finished, unmeasured' "
                f"the same state.")
        return self


class Agent(Node):
    """Who or what performed an Activity — a service, a model, a person: prov:Agent.

    Distinct from Activity because the same step run by two agents is two different provenance
    facts. "This edge came from the LLM producer" and "this one from the traversal" is exactly the
    claim a reader needs, and a per-graph flag cannot make it.
    """

    KIND: ClassVar[str] = "agent"
    ONTOLOGY_IRI: ClassVar[str] = "http://www.w3.org/ns/prov#Agent"

    name: str


class Used(BaseModel):
    """activity used entity."""
    activity_id: str
    entity_id: str


class WasGeneratedBy(BaseModel):
    """entity wasGeneratedBy activity."""
    entity_id: str
    activity_id: str


class WasDerivedFrom(BaseModel):
    """entity wasDerivedFrom entity."""
    entity_id: str
    source_id: str


class WasAssociatedWith(BaseModel):
    """activity wasAssociatedWith agent."""
    activity_id: str
    agent_id: str


class Run(BaseModel):
    """One execution of a Plan, as a provenance document: prov:Bundle.

    ⚠️ Referential integrity is VALIDATED, not assumed. A dangling id is not cosmetic: lineage
    traversal would return a shorter answer instead of an error, and "this derives from nothing" is
    indistinguishable from "this is a root".
    """

    ONTOLOGY_IRI: ClassVar[str] = "http://www.w3.org/ns/prov#Bundle"

    plan_name: str
    entities: dict[str, SerializeAsAny[Entity]] = Field(default_factory=dict)
    activities: dict[str, SerializeAsAny[Activity]] = Field(default_factory=dict)
    agents: dict[str, SerializeAsAny[Agent]] = Field(default_factory=dict)
    used: tuple[Used, ...] = ()
    generated: tuple[WasGeneratedBy, ...] = ()
    derived: tuple[WasDerivedFrom, ...] = ()
    associated: tuple[WasAssociatedWith, ...] = ()

    @model_validator(mode="after")
    def _edges_resolve(self) -> Run:
        def need(kind: str, ids: dict[str, Any], got: str, edge: str) -> None:
            if got not in ids:
                raise GraphError(f"{edge} references {kind} {got!r}, which this Run does not hold")

        for e in self.used:
            need("activity", self.activities, e.activity_id, "used")
            need("entity", self.entities, e.entity_id, "used")
        for e in self.generated:
            need("entity", self.entities, e.entity_id, "wasGeneratedBy")
            need("activity", self.activities, e.activity_id, "wasGeneratedBy")
        for e in self.derived:
            need("entity", self.entities, e.entity_id, "wasDerivedFrom")
            need("entity", self.entities, e.source_id, "wasDerivedFrom")
        for e in self.associated:
            need("activity", self.activities, e.activity_id, "wasAssociatedWith")
            need("agent", self.agents, e.agent_id, "wasAssociatedWith")
        return self

    def add(self, node: Node) -> Run:
        """Add a node. An empty id is refused HERE, not at construction.

        A node being drafted legitimately has no id yet; being IN a graph is what makes one
        necessary, because that is where edges resolve.
        """
        if not node.id:
            raise GraphError(f"{type(node).__name__} needs an id before it joins a Run")
        if isinstance(node, Entity):
            self.entities[node.id] = node
        elif isinstance(node, Activity):
            self.activities[node.id] = node
        elif isinstance(node, Agent):
            self.agents[node.id] = node
        else:
            raise GraphError(f"{type(node).__name__} is not an Entity, Activity or Agent")
        return self
