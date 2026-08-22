"""Typing invariants — a binding whose types do not line up.

The reason a `Variable` carries a real Python type rather than a string. An earlier design wired
Steps by artifact-kind strings, so a typo silently rewired the graph: it still built, nothing
type-checked, and the mistake surfaced much later as a shape error somewhere else entirely.

⚠️ Sharing a `Variable` already guarantees type agreement — `Variable` is frozen on `(name, type)`,
so two Steps holding the same Variable hold the same type by construction. What this catches is the
case that shape cannot: **two Variables with the SAME NAME and DIFFERENT types**, which reads as a
connection and is not one.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from workflow_plan.invariants.invariant import InvariantCategory, SemanticInvariant
from workflow_plan.plan.plan import Plan
from workflow_plan.plan.variable import Variable


def _compatible(plan: Plan) -> None:
    by_name: dict[str, set[Variable[Any]]] = defaultdict(set)
    for v in plan.variables:
        by_name[v.name].add(v)

    clashes = {n: vs for n, vs in by_name.items() if len(vs) > 1}
    if not clashes:
        return

    detail = "; ".join(
        f"{n!r} appears as " + " and ".join(
            sorted(getattr(v.type, "__name__", str(v.type)) for v in vs))
        for n, vs in sorted(clashes.items()))
    raise COMPATIBLE_BINDINGS.violated(
        f"{detail}. Two Variables sharing a name but not a type look connected and are not — "
        f"nothing flows between them, and the PlanStep that expected a value gets none.")


COMPATIBLE_BINDINGS: SemanticInvariant[Plan] = SemanticInvariant(
    id="typing.compatible_bindings",
    category=InvariantCategory.TYPING,
    statement="No two Variables in a Plan share a name while carrying different types.",
    why=("The failure this replaces: wiring Steps by string keys, where a typo silently rewired "
         "the graph and surfaced much later as a shape error somewhere else. A name collision "
         "across types is the same bug wearing the type system as a disguise — it LOOKS like a "
         "binding in the diagram and in the reading, and moves nothing."),
    check=_compatible,
)


def _declared_shapes_line_up(plan: Plan) -> None:
    """Every PlanStep's declared inputs/outputs are Variables, with no duplicate names per side."""
    bad: list[str] = []
    for s in plan.steps:
        for side in ("inputs", "outputs"):
            vs = getattr(s, side)
            names = [v.name for v in vs]
            if len(names) != len(set(names)):
                bad.append(f"{type(s).__name__}.{side} names a Variable twice: {names}")
    if bad:
        raise DECLARED_SHAPES.violated("; ".join(bad))


DECLARED_SHAPES: SemanticInvariant[Plan] = SemanticInvariant(
    id="typing.declared_shapes",
    category=InvariantCategory.TYPING,
    statement="No PlanStep declares the same Variable name twice on one side.",
    why=("A duplicate name on one side makes the binding ambiguous, and the ambiguity surfaces as "
         "the wrong value arriving rather than as an error — the hardest shape of bug to trace "
         "back to its declaration."),
    check=_declared_shapes_line_up,
)

ALL: tuple[SemanticInvariant[Plan], ...] = (COMPATIBLE_BINDINGS, DECLARED_SHAPES)
