"""STAGE 3 — three variants that ADD nodes while sharing most, and the question that matters.

Stage 2 varied the implementation and the topology was identical. Here the topology changes:

    baseline    Square ─────────────────────> Total
    filtered    Square ──> DropOutliers ─────> Total
    weighted    Square ──> DropOutliers ──> Weight ──> Total

Same contract in every case: `list -> int`. So the question a table of numbers cannot answer is
**are these three arms of one experiment, or three different processes?**

`check_arms` answers it by shape, and the structural diff below says exactly which Steps are shared
and which are new — which is the thing that goes missing when variants are separate hand-wired
graphs, because then the only diff available is a diff of the wiring code.

    uv run python3 -m examples.pydantic_graph_docs.stage3_variants
"""
from __future__ import annotations

import asyncio

from plan_types import Plan, Step, Variable, check_arms, render_mermaid
from plan_types.execution import LocalRunner, execute
from plan_types.execution.pydantic_graph import to_pydantic_graph

numbers = Variable("numbers", list)
squares = Variable("squares", list)
kept = Variable("kept", list)
weighted_vals = Variable("weighted", list)
total = Variable("total", int)


class Square(Step):
    inputs, outputs = (numbers,), (squares,)


class DropOutliers(Step):
    """New in `filtered`. Shared with `weighted`."""

    inputs, outputs = (squares,), (kept,)


class Weight(Step):
    """New in `weighted` only."""

    inputs, outputs = (kept,), (weighted_vals,)


class Total(Step):
    inputs, outputs = (squares,), (total,)


class TotalKept(Step):
    """⚠️ Same job as `Total`, different input. This is the honest cost of explicit dataflow."""

    inputs, outputs = (kept,), (total,)


class TotalWeighted(Step):
    inputs, outputs = (weighted_vals,), (total,)


baseline = Plan(name="baseline", steps=(Square(), Total()), declared_inputs=(numbers,))
filtered = Plan(name="filtered", steps=(Square(), DropOutliers(), TotalKept()),
                declared_inputs=(numbers,))
weighted = Plan(name="weighted", steps=(Square(), DropOutliers(), Weight(), TotalWeighted()),
                declared_inputs=(numbers,))

VARIANTS = {"baseline": baseline, "filtered": filtered, "weighted": weighted}


def square(numbers: list) -> list:
    return [n * n for n in numbers]


def drop_outliers(squares: list) -> list:
    """Drop anything more than 4x the median."""
    if not squares:
        return []
    mid = sorted(squares)[len(squares) // 2]
    return [s for s in squares if s <= 4 * mid]


def weight(kept: list) -> list:
    return [s * 2 if s < 10 else s for s in kept]


def add(**vals: object) -> int:
    return sum(next(iter(vals.values())))  # one input, whatever it is called


STRATEGY = {
    Square: square, DropOutliers: drop_outliers, Weight: weight,
    Total: lambda squares: sum(squares),
    TotalKept: lambda kept: sum(kept),
    TotalWeighted: lambda weighted: sum(weighted),
}

CORPUS = [[1, 2, 3], [1, 2, 50], [2, 2, 2, 40]]


def structural_diff(a: Plan, b: Plan) -> dict[str, list[str]]:
    """Which Steps are shared, which are only in one. Read off the declarations.

    This is the diff you cannot get from two hand-wired graphs: there, "what changed" is a diff of
    wiring code, and a renamed local variable looks like a changed process.
    """
    names = lambda p: {type(s).__name__ for s in p.steps}  # noqa: E731
    return {
        "shared": sorted(names(a) & names(b)),
        f"only in {a.name}": sorted(names(a) - names(b)),
        f"only in {b.name}": sorted(names(b) - names(a)),
    }


async def main() -> None:
    print("SAME CONTRACT?")
    check_arms(list(VARIANTS.values()))
    print(f"  check_arms passed — all three are {baseline.shape()[0]} -> {baseline.shape()[1]}")
    print("  so their numbers may legally be compared. That is a TYPE fact, not a judgement.\n")

    print("STRUCTURAL DIFF — what actually changed between variants\n")
    for a, b in (("baseline", "filtered"), ("filtered", "weighted")):
        print(f"  {a} -> {b}")
        for k, v in structural_diff(VARIANTS[a], VARIANTS[b]).items():
            print(f"    {k:<22} {v}")
        print()

    for name, plan in VARIANTS.items():
        print(f"### {name}")
        print(render_mermaid(plan, STRATEGY))
        print()

    print("EVAL\n")
    print(f"  {'input':<16} " + " ".join(f"{n:>10}" for n in VARIANTS))
    for case in CORPUS:
        cells = [execute(plan, {"numbers": case}, LocalRunner(STRATEGY))["total"]
                 for plan in VARIANTS.values()]
        print(f"  {str(case):<16} " + " ".join(f"{c:>10}" for c in cells))

    print("\n  the outlier case [1, 2, 50] is what separates them: 2505 vs 5 vs 10")
    print("\nall three compiled onto pydantic-graph:")
    for name, plan in VARIANTS.items():
        got = (await to_pydantic_graph(plan, STRATEGY).run(inputs={"numbers": [1, 2, 50]}))["total"]
        print(f"  {name:<10} {got}")


if __name__ == "__main__":
    asyncio.run(main())
