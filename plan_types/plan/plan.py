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
from plan_types.plan.service import Service
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

    #: Every Service any Step may reference. Top-level declaration is MANDATORY, exactly as
    #: docker-compose requires for a named volume: a Step using something absent from this tuple is
    #: a violation, so one word cannot come to mean three things.
    services: tuple[Service, ...] = ()

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

    @property
    def used_services(self) -> tuple[Service, ...]:
        """Every Service the Steps actually reference, first-seen order.

        Compare against `services` to find both failure directions: a Step reaching for something
        undeclared, and a declaration nothing uses.
        """
        seen: dict[Service, None] = {}
        for s in self.steps:
            for svc in getattr(s, "uses", ()):
                seen.setdefault(svc, None)
        return tuple(seen)

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
class MultiStep(Plan, Step):
    """[p-plan:MultiStep](http://purl.org/net/p-plan#MultiStep) — a Plan that appears as a Step.

    `rdfs:subClassOf` **both** `p-plan:Plan` and `p-plan:Step`, bound to its definition by
    `isDecomposedAsPlan`. This is how a Plan nests: one node in an outer Plan, a whole Plan inside.

    ## ⚠️ It did not inherit from `Step` until 2026-08-20, so it could not BE one

    It subclassed `Plan` alone, and `Plan.__post_init__` requires every entry in `steps` to be a
    `Step` — so putting a MultiStep inside a Plan raised. The one thing the class exists for did not
    work, for as long as the class existed, because nothing ever nested a Plan. The ontology
    citation was right and the code did not implement it: the failure
    `provenance.grounded_citation` exists to catch, in the class that carries the IRI.

    Ports are DERIVED — `Plan.inputs` and `Plan.outputs` already mean free and terminal Variables,
    which is exactly what this node consumes and produces. Declaring them again would be a second
    source of truth that goes stale the moment a nested Step moves.

    ## `until` — the termination predicate, declared but not implemented here

    An iterative region cannot be linearised, and the reason is not the toposort: a Plan that says
    `WriteEmail -> Feedback -> WriteEmail` never says when to STOP, so no scheduler could run it
    either. `until` names the Variable whose value decides.

        class ReviseUntilApproved(MultiStep): ...
        ReviseUntilApproved(name="revise", steps=(...), until=approved)

    Plan-time: it declares WHICH Variable governs termination. The test itself is a function and
    therefore an implementation, so it lives in the `Strategy` alongside every other one — the same
    split as `Step`, for the same reason. This keeps `Decision`, branching and `End` out of the Plan
    layer, where pydantic-graph and LangGraph already own them and do them well.

    ⚠️ `until` is OURS, deliberately uncited. P-Plan's 18 terms are Plan/Step/Variable structure and
    PROV-O describes executions; neither has a word for "this planned region repeats until". Citing
    one that does not say it is the failure this package was built to report.
    """

    #: The Variable whose value ends the iteration. `None` means this MultiStep is not iterative —
    #: it is plain nesting, and `topology.terminating_iteration` refuses a cyclic inner Plan without
    #: one, because a non-terminating declaration is not a specification.
    until: Variable[Any] | None = None

    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#MultiStep"

    def decomposed_as_plan(self) -> Plan:
        """p-plan:isDecomposedAsPlan — the Plan this step expands into."""
        return Plan(name=self.name, steps=self.steps)

    @property
    def iterative(self) -> bool:
        """Does the inner Plan contain a cycle? Read from the bindings, never declared."""
        from plan_types.plan.bindings import execution_order  # noqa: PLC0415 — import cycle

        try:
            execution_order(self.decomposed_as_plan())
        except PlanError:
            return True
        return False

    def __repr__(self) -> str:
        tail = f", until={self.until.name!r}" if self.until else ""
        return f"MultiStep({self.name!r}, {len(self.steps)} steps{tail})"
