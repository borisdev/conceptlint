"""`Plan` — Steps wired through shared typed Variables. A dependency graph, not a sequence.

Grounded in [p-plan:Plan](http://purl.org/net/p-plan#Plan): *"composed of smaller steps (p-plan:Step)
that use and produce Variables"*. The wiring IS the shared Variables — there is no "next step"
relation in P-Plan, and inventing one is what this file used to do.

    Variable[A] ──┐
    Variable[B] ──┼──> Step ──> Variable[D]
    Variable[C] ──┘

## What changed, and what it cost to find out

Until 2026-08-16 a Plan validated `zip(steps, steps[1:])` — each step's single output feeding the
next step's single input — and took its own inputs and outputs from `steps[0]` and `steps[-1]`.
None of that is in P-Plan. It was written from a remembered reading of the ontology, and it made the
first real pipeline inexpressible: nobsmed's `evidence_first` has a step needing three earlier
values at once.

Order is now DERIVED from the dependency edges rather than declared, which is the actual fix.
Declaration order was never execution semantics; it just looked like it while every example had one
input and one output.

## Which rules are P-Plan's and which are OURS

Stating this matters as much as the code — labelling our constraint as grounding is the same error
one level down.

    P-Plan   a Variable has ONE producer      isOutputVarOf is owl:FunctionalProperty
    P-Plan   a Variable may have MANY consumers   isInputVarOf is not functional
    P-Plan   ordering exists                  isPrecededBy, transitive
    OURS     the graph is ACYCLIC             P-Plan permits cycles; we refuse them, because
                                              `toposort` must terminate and a cyclic build is a
                                              version boundary, not an edge (case-ir.md §Versions)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable, Sequence

from conceptlint.dataflow.step import Step
from conceptlint.dataflow.variable import Variable


class PlanError(ValueError):
    """A Plan that cannot be wired. Raised at declaration, never at run time."""


@dataclass(frozen=True)
class Plan:
    """A set of Steps and the Variables that connect them.

    `steps` is a tuple for reproducible reporting, NOT because order means anything. Execution order
    comes from `order()`, which reads the dependency edges.
    """

    name: str
    steps: tuple[Step, ...]

    #: p-plan:Plan. Checked by `ontologies/invariants.GroundedCitation`.
    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Plan"

    def __post_init__(self) -> None:
        if not self.steps:
            raise PlanError(f"Plan {self.name!r} has no steps")

        for s in self.steps:
            if isinstance(s, type) and issubclass(s, Step):
                # Kept from the pre-DAG version because it is the mistake people actually make, and
                # the generic "not a Step" message sends them looking in the wrong place.
                raise PlanError(
                    f"Plan {self.name!r} holds the CLASS {s.__name__}, not an instance — write "
                    f"{s.__name__}() . A Plan is built from Steps, and a class is a declaration of "
                    f"one.")
            if not isinstance(s, Step):
                raise PlanError(
                    f"Plan {self.name!r} contains {s!r}, which is not a Step. A runtime object "
                    f"among plan-time declarations is the Step/Activity collapse P-Plan separates.")

        # p-plan:isOutputVarOf is FUNCTIONAL — exactly one producer per Variable. Not our rule.
        producer: dict[Variable[Any], Step] = {}
        for s in self.steps:
            for out in s.outputs:
                if out in producer:
                    raise PlanError(
                        f"Plan {self.name!r}: {out.name!r} is produced by both "
                        f"{type(producer[out]).__name__} and {type(s).__name__}. "
                        f"p-plan:isOutputVarOf is an owl:FunctionalProperty — one producer per "
                        f"Variable — and two make lineage ambiguous rather than merely redundant.")
                producer[out] = s

        # Every input is either produced inside the Plan or free (a Plan input). A name that matches
        # but whose TYPE does not is the mis-wire the whole package exists to catch, so it is checked
        # explicitly rather than left to `in`.
        for s in self.steps:
            for inp in s.inputs:
                if inp in producer:
                    continue
                clash = next((p for p in producer if p.name == inp.name), None)
                if clash is not None:
                    raise PlanError(
                        f"Plan {self.name!r}: {type(s).__name__} consumes {inp!r} but the Plan "
                        f"produces {clash!r} under that name — same name, different type.")

        self.order()          # refuses a cycle at declaration, not at run time

    # ── the Plan's own contract ──────────────────────────────────────────────────────────────────

    @property
    def inputs(self) -> tuple[Variable[Any], ...]:
        """Variables consumed but produced by nothing here — the Plan's free variables.

        Derived, not `steps[0]`. A Plan whose first declared step happens to need two things has two
        inputs, and the old first/last rule silently reported one of them.
        """
        produced = {v for s in self.steps for v in s.outputs}
        seen, out = set(), []
        for s in self.steps:
            for v in s.inputs:
                if v not in produced and v not in seen:
                    seen.add(v)
                    out.append(v)
        return tuple(out)

    @property
    def outputs(self) -> tuple[Variable[Any], ...]:
        """Variables produced but consumed by nothing here — what the Plan hands back."""
        consumed = {v for s in self.steps for v in s.inputs}
        seen, out = set(), []
        for s in self.steps:
            for v in s.outputs:
                if v not in consumed and v not in seen:
                    seen.add(v)
                    out.append(v)
        return tuple(out)

    def shape(self) -> tuple[tuple[type, ...], tuple[type, ...]]:
        """The contract. Two Plans with equal shapes are substitutable.

        Sorted by NAME so two Plans that declare the same ports in a different order still compare
        equal — the shape is a set of typed ports, and letting declaration order leak into it would
        reintroduce exactly the sequence-thinking this file removed.
        """
        return (tuple(v.type for v in sorted(self.inputs, key=lambda v: v.name)),
                tuple(v.type for v in sorted(self.outputs, key=lambda v: v.name)))

    # ── ordering, derived ────────────────────────────────────────────────────────────────────────

    def order(self) -> tuple[Step, ...]:
        """Steps in a valid execution order, from the dependency edges. Kahn's algorithm.

        ⚠️ Acyclicity is OUR constraint, not P-Plan's — see the module docstring. The message says so
        rather than blaming the ontology, because a reader who checks will find P-Plan permits it.
        """
        producer = {v: s for s in self.steps for v in s.outputs}
        pending = {s: {producer[v] for v in s.inputs if v in producer} for s in self.steps}

        ordered: list[Step] = []
        while pending:
            ready = [s for s, deps in pending.items() if not deps - set(ordered)]
            if not ready:
                stuck = ", ".join(sorted(type(s).__name__ for s in pending))
                raise PlanError(
                    f"Plan {self.name!r} has a dependency cycle among: {stuck}. P-Plan permits "
                    f"cycles; this package does not, because execution order must terminate and an "
                    f"iteration is a version boundary rather than an edge.")
            # Sorted for determinism: two independent steps must not reorder between runs, or a
            # diff of the order becomes noise and stops being readable.
            ready.sort(key=lambda s: type(s).__name__)
            for s in ready:
                ordered.append(s)
                del pending[s]
        return tuple(ordered)

    def run(self, **values: Any) -> dict[str, Any]:
        """Execute in dependency order. The simplest possible executor, deliberately not a framework.

        No retry, durability, checkpointing, parallelism or interrupts. An execution backend decides
        HOW computation runs; this package only says WHAT computation exists.
        """
        missing = [v.name for v in self.inputs if v.name not in values]
        if missing:
            raise PlanError(f"Plan {self.name!r} needs inputs: {', '.join(missing)}")

        scope = dict(values)
        for s in self.order():
            produced = s.run(**{v.name: scope[v.name] for v in s.inputs})
            if len(s.outputs) == 1:
                scope[s.outputs[0].name] = produced
            else:
                for v, val in zip(s.outputs, produced):
                    scope[v.name] = val
        return {v.name: scope[v.name] for v in self.outputs}


def substitutable(a: Plan, b: Plan) -> bool:
    """Do these two Plans have the same contract?"""
    return a.shape() == b.shape()


def check_arms(arms: Sequence[Plan]) -> None:
    """Refuse a set of arms that do not share one shape."""
    shapes = {a.shape() for a in arms}
    if len(shapes) > 1:
        raise PlanError(f"arms must share one shape; got {sorted(map(str, shapes))}")


@dataclass(frozen=True)
class MultiStep(Plan):
    """[p-plan:MultiStep](http://purl.org/net/p-plan#MultiStep) — a Plan that appears as a Step.

    The ontology's own words: *"representation of a plan that appears as a step of another plan"*,
    and it is `rdfs:subClassOf` **both** `p-plan:Plan` and `p-plan:Step`. `isDecomposedAsPlan` binds
    it to the Plan holding its definition.

    Boris asked for "one big plan node with a sub DAG inside" before either of us had read this.
    That intuition has a name, and having the name is the difference between nesting being a
    property of the model and being something the renderer fakes.
    """

    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#MultiStep"

    def decomposed_as_plan(self) -> Plan:
        """p-plan:isDecomposedAsPlan — the Plan this step expands into."""
        return Plan(name=self.name, steps=self.steps)
