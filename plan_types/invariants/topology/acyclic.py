"""Topology invariants — cycles, unbound inputs, orphan Variables.

⚠️ Every rule here is OPT-IN. None of them is built into `Plan`, and that is the point: a Plan
whose Steps form a cycle is a legal *specification* of an iterative process. It simply cannot be
linearised, which is `bindings.execution_order`'s problem, not the type's.

An earlier design ran a toposort inside `Plan.__post_init__`, so "acyclic" was part of what a Plan
MEANT. That closes the door on iterative processes before anyone has asked for one — and P-Plan
itself has no acyclicity axiom, only a transitive `isPrecededBy`.
"""
from __future__ import annotations

from plan_types.invariants.invariant import InvariantCategory, SemanticInvariant
from plan_types.plan import bindings
from plan_types.plan.plan import Plan, PlanError


def _acyclic(plan: Plan) -> None:
    try:
        bindings.execution_order(plan)
    except PlanError as exc:
        raise ACYCLIC.violated(str(exc)) from None


ACYCLIC: SemanticInvariant[Plan] = SemanticInvariant(
    id="topology.acyclic",
    category=InvariantCategory.TOPOLOGY,
    statement="The Plan's bindings contain no dependency cycle, so its Steps can be linearised.",
    why=("A cyclic Plan is a legal specification but has no execution order, so anything that "
         "walks it — an executor, a renderer, a diff — either loops forever or silently returns a "
         "partial answer. Opt in when the process is meant to be a straight line; leave it off "
         "when iteration is the design."),
    check=_acyclic,
)


class NotChecked(Exception):
    """The invariant could not run. ⚠️ NOT a pass.

    `.claude/rules/case-ir.md`: a check that was skipped reports NOT CHECKED, never a passing
    value. An audit that implies a check it skipped is the failure the tooling exists to catch.
    """


def _bound_inputs(plan: Plan) -> None:
    if not plan.declared_inputs:
        raise NotChecked(
            f"Plan {plan.name!r} declares no inputs, so 'unbound' cannot be distinguished from "
            f"'the Plan's signature' — with inputs derived, they are the same set. Pass "
            f"`declared_inputs=` to make this checkable.")
    missing = bindings.unbound_inputs(plan)
    if missing:
        detail = ", ".join(f"{type(s).__name__} needs {v.name!r}" for s, v in missing)
        raise BOUND_INPUTS.violated(
            f"{len(missing)} Step input(s) are bound to nothing: {detail}. Either a Step upstream "
            f"should produce them, or they belong in the Plan's own inputs.")


BOUND_INPUTS: SemanticInvariant[Plan] = SemanticInvariant(
    id="topology.bound_inputs",
    category=InvariantCategory.TOPOLOGY,
    statement="Every Step input is either produced inside the Plan or is a Plan input.",
    why=("An input nothing supplies fails at run time, deep inside whichever Step reads it, with a "
         "message about a missing key rather than a missing binding. ⚠️ A Plan INPUT is not "
         "unbound — it is the Plan's signature, and counting it as an error would make every Plan "
         "that takes an argument invalid."),
    check=_bound_inputs,
)


def _no_orphans(plan: Plan) -> None:
    stranded = bindings.orphans(plan)
    if stranded:
        names = ", ".join(v.name for v in stranded)
        raise NO_ORPHAN_VARIABLES.violated(
            f"produced but never read and not a Plan output: {names}. Either something should "
            f"consume it, or the Step should not be producing it.")


NO_ORPHAN_VARIABLES: SemanticInvariant[Plan] = SemanticInvariant(
    id="topology.orphan_variables",
    category=InvariantCategory.TOPOLOGY,
    statement="Every produced Variable is consumed by a Step or exposed as a Plan output.",
    why=("A Variable nobody reads is work being done for nothing, or — worse — a rewiring that "
         "left a Step still computing a value the new topology no longer uses. The second reads "
         "as a working Plan and quietly costs whatever that Step costs."),
    check=_no_orphans,
)


def _single_producer(plan: Plan) -> None:
    doubled = {v: ss for v, ss in bindings.producers(plan).items() if len(ss) > 1}
    if doubled:
        detail = "; ".join(
            f"{v.name!r} by " + " and ".join(sorted(type(s).__name__ for s in ss))
            for v, ss in doubled.items())
        raise SINGLE_PRODUCER.violated(
            f"{detail}. p-plan:isOutputVarOf is an owl:FunctionalProperty — one producer per "
            f"Variable — so two make lineage ambiguous rather than merely redundant.")


SINGLE_PRODUCER: SemanticInvariant[Plan] = SemanticInvariant(
    id="topology.single_producer",
    category=InvariantCategory.TOPOLOGY,
    statement="Each Variable is produced by exactly one Step.",
    why=("This one is NOT ours — `p-plan:isOutputVarOf` is declared `owl:FunctionalProperty` in "
         "the vendored ontology, so it is an axiom we inherit rather than a rule we chose. With "
         "two producers, 'where did this value come from' has two answers and provenance stops "
         "being a chain."),
    check=_single_producer,
)

#: Every topology rule, for callers who want the whole category.
ALL: tuple[SemanticInvariant[Plan], ...] = (
    ACYCLIC, BOUND_INPUTS, NO_ORPHAN_VARIABLES, SINGLE_PRODUCER,
)
