"""`Plan` — a complete typed process specification.

    Plan
     ├── Step
     ├── Step
     ├── Variable
     └── bindings

Grounded in [p-plan:Plan](http://purl.org/net/p-plan#Plan): *"composed of smaller steps that use
and produce Variables"*. The wiring IS the shared Variables — P-Plan has no "next step" relation.

## ⚠️ A Plan is NOT a DAG

Acyclicity is an **invariant**, not the identity of a Plan. `topology.acyclic` checks it, and a
caller decides whether to apply it. Building "must be acyclic" into the type would close the door
on iterative and cyclic processes before anyone has asked for one — and P-Plan itself permits
cycles: `isPrecededBy` is merely transitive, with no acyclicity axiom.

This is a correction of an earlier design where `__post_init__` ran a toposort and raised on a
cycle, which made "acyclic" part of what `Plan` MEANT rather than something one could check.

## ⚠️ `run()` is not the centre of this

The first milestone is an **inspectable, validated specification**, not an executor. A Plan answers:

    what Steps exist            .steps
    what Variables exist        .variables
    what each Step consumes     Step.inputs
    what each Step produces     Step.outputs
    how Variables are bound     bindings.producers / consumers / edges
    what topology results       bindings.edges
    which invariants apply      whichever the caller runs
    does it satisfy them        validate(plan, invariants)

An execution adapter — plain Python, Temporal, LangGraph — wraps Steps from outside. Never the
reverse: `@activity.defn` on a Step subclass couples a process definition to one runtime, which is
the coupling this package exists to avoid.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Sequence

from plan_types.plan.step import Step
from plan_types.plan.variable import Variable


class PlanError(ValueError):
    """A Plan that cannot be constructed at all. Not the same as failing an invariant.

    Construction refuses only what makes the object incoherent — a Step class instead of an
    instance, a runtime object among plan-time declarations. Everything a caller might legitimately
    want to allow (cycles, unbound inputs, orphan Variables) is an INVARIANT, so it can be checked,
    reported, or deliberately permitted.
    """


@dataclass(frozen=True)
class Plan:
    """A set of Steps and the typed Variables that connect them.

    `steps` is a tuple for reproducible reporting, NOT because order carries meaning. Any execution
    order is derived from the bindings — see `plan_types.plan.bindings.execution_order`.
    """

    name: str
    steps: tuple[Step, ...]

    #: What the Plan EXPECTS to be given. Optional, and the reason it exists is subtle:
    #:
    #: with inputs fully derived — "consumed here, produced by nothing here" — an accidentally
    #: unbound input and a deliberate Plan input are THE SAME SET, so `topology.bound_inputs` can
    #: never fire. Declaring them makes the distinction expressible: anything consumed, unproduced
    #: and NOT declared is a gap rather than a signature.
    #:
    #: Left empty, the invariant reports NOT CHECKED rather than passing. A skipped check must
    #: never render as a passing one.
    declared_inputs: tuple[Variable[Any], ...] = ()

    #: p-plan:Plan — checked against the vendored ontology by the provenance invariants.
    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Plan"

    def __post_init__(self) -> None:
        if not self.steps:
            raise PlanError(f"Plan {self.name!r} has no steps")
        for s in self.steps:
            if isinstance(s, type) and issubclass(s, Step):
                raise PlanError(
                    f"Plan {self.name!r} holds the CLASS {s.__name__}, not an instance — write "
                    f"{s.__name__}() . A class is a declaration of a Step, not a Step.")
            if not isinstance(s, Step):
                raise PlanError(
                    f"Plan {self.name!r} contains {s!r}, which is not a Step. A runtime object "
                    f"among plan-time declarations is the Step/Activity collapse P-Plan separates.")

    # ── what exists ──────────────────────────────────────────────────────────────────────────────

    @property
    def variables(self) -> tuple[Variable[Any], ...]:
        """Every Variable any Step consumes or produces, in first-seen order."""
        seen: dict[Variable[Any], None] = {}
        for s in self.steps:
            for v in (*s.inputs, *s.outputs):
                seen.setdefault(v, None)
        return tuple(seen)

    @property
    def inputs(self) -> tuple[Variable[Any], ...]:
        """The Plan's signature — declared if declared, otherwise derived.

        Derived means: consumed here, produced by nothing here.
        """
        if self.declared_inputs:
            return self.declared_inputs
        produced = {v for s in self.steps for v in s.outputs}
        return tuple(v for v in self.variables if v not in produced
                     and any(v in s.inputs for s in self.steps))

    @property
    def outputs(self) -> tuple[Variable[Any], ...]:
        """The Plan's TERMINAL variables — produced here, consumed by nothing here."""
        consumed = {v for s in self.steps for v in s.inputs}
        return tuple(v for v in self.variables if v not in consumed
                     and any(v in s.outputs for s in self.steps))

    def shape(self) -> tuple[tuple[type, ...], tuple[type, ...]]:
        """The Plan's contract: `(input types, output types)`, sorted by Variable name.

        Two Plans with equal shapes are substitutable — the check an eval trial needs before putting
        two implementations' numbers beside each other. Sorted so that declaration order cannot leak
        into the contract.
        """
        return (tuple(v.type for v in sorted(self.inputs, key=lambda v: v.name)),
                tuple(v.type for v in sorted(self.outputs, key=lambda v: v.name)))

    def __repr__(self) -> str:
        return f"Plan({self.name!r}, {len(self.steps)} steps, {len(self.variables)} variables)"


def substitutable(a: Plan, b: Plan) -> bool:
    """Do these two Plans expose the same contract?"""
    return a.shape() == b.shape()


def check_arms(arms: Sequence[Plan]) -> None:
    """Refuse a set of alternative implementations that do not share one shape."""
    shapes = {a.shape() for a in arms}
    if len(shapes) > 1:
        raise PlanError(f"arms must share one shape; got {sorted(map(str, shapes))}")


@dataclass(frozen=True)
class MultiStep(Plan):
    """[p-plan:MultiStep](http://purl.org/net/p-plan#MultiStep) — a Plan that appears as a Step.

    `rdfs:subClassOf` **both** `p-plan:Plan` and `p-plan:Step`, bound to its definition by
    `isDecomposedAsPlan`. This is how a Plan nests: one node in an outer Plan, a whole Plan inside.
    """

    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#MultiStep"

    def decomposed_as_plan(self) -> Plan:
        """p-plan:isDecomposedAsPlan — the Plan this step expands into."""
        return Plan(name=self.name, steps=self.steps)
