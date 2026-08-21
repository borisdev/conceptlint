"""How Variables connect Steps — the topology, derived rather than declared.

A binding is not a separate object to maintain. Two Steps are connected when they share a
`Variable`, and `Variable` is a frozen dataclass, so identity is `(name, type)`. Declaring bindings
a second time would create two sources of truth for one fact, and the second one goes stale.

    Variable[A] ──┐
    Variable[B] ──┼──> Step ──> Variable[D]
    Variable[C] ──┘

Everything the typing and topology invariants need is computed here, once, so no invariant
re-derives it slightly differently.

## Why execution order lives here and not on Plan

`execution_order` is a *consequence* of the bindings, and only meaningful when the Plan happens to
be acyclic. Putting it on `Plan` implied every Plan has one — which is what made "acyclic" read as
part of the type rather than as an invariant a caller opts into.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from plan_types.plan.step import Step, wired_inputs, wired_outputs
from plan_types.plan.variable import Variable

if TYPE_CHECKING:
    from plan_types.plan.plan import Plan


@dataclass(frozen=True)
class Edge:
    """One dependency: `producer` makes `variable`, which `consumer` reads."""

    producer: Step
    variable: Variable[Any]
    consumer: Step

    def __repr__(self) -> str:
        return (f"{type(self.producer).__name__} --{self.variable.name}--> "
                f"{type(self.consumer).__name__}")


def producers(plan: Plan) -> dict[Variable[Any], list[Step]]:
    """Variable -> the Steps that produce it.

    A LIST, deliberately, even though `p-plan:isOutputVarOf` is an `owl:FunctionalProperty` and one
    producer is the rule. Returning a list lets `topology.single_producer` REPORT the violation;
    returning a dict-of-one would make the second producer vanish silently and the invariant
    unwritable.
    """
    out: dict[Variable[Any], list[Step]] = {}
    for s in plan.steps:
        for v in wired_outputs(s):
            out.setdefault(v, []).append(s)
    return out


def consumers(plan: Plan) -> dict[Variable[Any], list[Step]]:
    """Variable -> the Steps that consume it. Many is legal: `isInputVarOf` is not functional."""
    out: dict[Variable[Any], list[Step]] = {}
    for s in plan.steps:
        for v in wired_inputs(s):
            out.setdefault(v, []).append(s)
    return out


def edges(plan: Plan) -> tuple[Edge, ...]:
    """Every producer→consumer dependency implied by a shared Variable."""
    prod = producers(plan)
    return tuple(
        Edge(producer=p, variable=v, consumer=c)
        for v, cs in consumers(plan).items()
        for p in prod.get(v, ())
        for c in cs
    )


def unbound_inputs(plan: Plan) -> tuple[tuple[Step, Variable[Any]], ...]:
    """Step inputs that nothing in the Plan produces and that are not Plan inputs.

    ⚠️ A free variable is NOT unbound. `plan.inputs` are supplied by the caller and are the Plan's
    own signature; treating them as errors would make every Plan with an input invalid.
    """
    prod = producers(plan)
    declared = set(plan.declared_inputs)
    return tuple((s, v) for s in plan.steps for v in wired_inputs(s)
                 if v not in prod and v not in declared)


def orphans(plan: Plan) -> tuple[Variable[Any], ...]:
    """Variables produced but never consumed AND never a Plan output.

    Since `plan.outputs` is defined as produced-and-unconsumed, an orphan can only arise from a
    Variable that is neither — which today means a Step declaring an output nothing reads while the
    Plan does not expose it either. Kept as its own function so the invariant can say WHICH.
    """
    consumed = {v for s in plan.steps for v in wired_inputs(s)}
    terminal = set(plan.outputs)
    return tuple(v for v, _ in producers(plan).items()
                 if v not in consumed and v not in terminal)


def execution_order(plan: Plan) -> tuple[Step, ...]:
    """Steps in a valid execution order — Kahn's algorithm over the bindings.

    ⚠️ RAISES on a cycle, because there is no correct answer to return. That is not the acyclicity
    invariant: `topology.acyclic` REPORTS a cycle as a violation, this function refuses to invent an
    order. A caller who has not run that invariant gets the error here rather than a wrong order.

    Ties are broken by class name so two independent Steps never reorder between runs — otherwise a
    diff of the order is noise and stops being readable.
    """
    from plan_types.plan.plan import PlanError  # noqa: PLC0415 — avoids an import cycle

    prod = producers(plan)
    pending = {s: {p for v in wired_inputs(s) for p in prod.get(v, ()) if p is not s}
               for s in plan.steps}
    ordered: list[Step] = []
    while pending:
        ready = [s for s, deps in pending.items() if not deps - set(ordered)]
        if not ready:
            stuck = ", ".join(sorted(type(s).__name__ for s in pending))
            raise PlanError(
                f"Plan {plan.name!r} has a dependency cycle among: {stuck}. There is no execution "
                f"order to return. A cycle is legal as a PLAN — see topology.acyclic, which reports "
                f"it — but it cannot be linearised.")
        ready.sort(key=lambda s: type(s).__name__)
        for s in ready:
            ordered.append(s)
            del pending[s]
    return tuple(ordered)
