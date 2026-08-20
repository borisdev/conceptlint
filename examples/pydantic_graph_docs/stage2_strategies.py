"""STAGE 2 — three implementations of ONE logical Step, evaluated against each other.

Domain is theirs: `parallel_processing.py` squares numbers. The Plan:

    numbers ──> Square ──> squares ──> Total ──> total

Three strategies vary ONE Step. `Square` stands in for the step you would really want to vary —
a different model, a different prompt, a different agent. Deterministic stand-ins here so the file
runs with no API key and the same numbers come out every time; the STRUCTURE is what is being
shown, and it is identical either way.

What to look at:

    the Plan object is constructed ONCE and never touched
    three diagrams, identical topology, different implementation labels
    an eval table whose rows are comparable BECAUSE the Plan is the same object

    uv run python3 -m examples.pydantic_graph_docs.stage2_strategies
"""
from __future__ import annotations

import asyncio

from plan_types import Plan, Step, Variable, render_mermaid, validate
from plan_types.execution import LocalRunner, check_strategy, execute
from plan_types.execution.pydantic_graph import to_pydantic_graph
from plan_types.invariants import topology, typing

numbers = Variable("numbers", list)
squares = Variable("squares", list)
total = Variable("total", int)


class Square(Step):
    """Square each number. The step whose implementation we are comparing."""

    inputs, outputs = (numbers,), (squares,)


class Total(Step):
    """Add them up. Held fixed across all three arms."""

    inputs, outputs = (squares,), (total,)


plan = Plan(name="square_and_total", steps=(Square(), Total()),
            declared_inputs=(numbers,))


# ── three implementations of Square. Peers, not overrides ────────────────────────────────────────

def square_exact(numbers: list) -> list:
    return [n * n for n in numbers]


def square_by_repeated_addition(numbers: list) -> list:
    """Same contract, different method — the honest 'different model, same task' case."""
    out = []
    for n in numbers:
        acc = 0
        for _ in range(abs(n)):
            acc += abs(n)
        out.append(acc)
    return out


def square_cheap_approximation(numbers: list) -> list:
    """Faster and WRONG above 10 — the arm you want an eval to catch."""
    return [n * n if abs(n) <= 10 else (abs(n) * 10) for n in numbers]


def total_impl(squares: list) -> int:
    return sum(squares)


ARMS = {
    "exact": {Square: square_exact, Total: total_impl},
    "repeated_addition": {Square: square_by_repeated_addition, Total: total_impl},
    "cheap_approximation": {Square: square_cheap_approximation, Total: total_impl},
}

#: The eval corpus. The last case is the one that separates the arms — name the unit, then run it.
CORPUS = [[1, 2, 3], [4, 5], [12], [3, 20]]


async def main() -> None:
    print("invariants:", validate(plan, [*topology.ALL, *typing.ALL]) or "[]")

    print("\nSAME PLAN, THREE STRATEGIES — identical topology, different labels:\n")
    for arm, strategy in ARMS.items():
        print(f"### {arm}")
        print(render_mermaid(plan, strategy))
        print()

    print("EVAL — every row is comparable because the Plan is the same object\n")
    print(f"  {'input':<12} {'expected':>9} " + " ".join(f"{a:>20}" for a in ARMS))
    for case in CORPUS:
        expected = sum(n * n for n in case)
        cells = []
        for strategy in ARMS.values():
            assert check_strategy(plan, strategy) == ()
            got = execute(plan, {"numbers": case}, LocalRunner(strategy))["total"]
            cells.append(f"{got:>13} {'ok' if got == expected else 'WRONG':>6}")
        print(f"  {str(case):<12} {expected:>9} " + " ".join(cells))

    print("\nand the winning arm compiled onto THEIR runtime, unchanged:")
    graph = to_pydantic_graph(plan, ARMS["exact"])
    got = (await graph.run(inputs={"numbers": [3, 20]}))["total"]
    print(f"  pydantic-graph, numbers=[3, 20] -> {got}  (expected 409)")
    assert got == 409


if __name__ == "__main__":
    asyncio.run(main())
