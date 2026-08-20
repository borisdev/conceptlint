"""STAGE 3 — their `parallel_processing.py`: map, join, reducer.

Their example, from https://pydantic.dev/docs/ai/graph/builder/ ("A More Complex Example"):

    g.add(
        g.edge_from(g.start_node).map().to(square),
        g.edge_from(square).to(collect_results),
        g.edge_from(collect_results).to(g.end_node),
    )

`square` is `int -> int`. The `.map()` fans each item out to its own execution; `collect_results` is
a join with `reduce_list_append`. Their words, kept: **map**, **join**, **reducer**.

A Plan says the same thing by declaring the per-item Step and what it maps over:

    class Square(Step):
        inputs, outputs = (number,), (squared,)     # int -> int, exactly theirs
        map_over = (numbers, squares)               # list[int] in, list[int] out

⚠️ Read what that buys and what it does not. The Plan declares that a fan-out EXISTS. It says
nothing about workers, ordering or concurrency — so the same declaration is a sequential loop under
LocalRunner and an actual parallel `.map()` + join on their engine, with no edit. That is the split
doing its job, and it is the whole claim.

    uv run python3 -m examples.pydantic_graph_docs.stage3_map_join
"""
from __future__ import annotations

import asyncio

from plan_types import Plan, Step, Variable, render_mermaid, validate
from plan_types.execution import LocalRunner, check_strategy, execute
from plan_types.execution.pydantic_graph import to_pydantic_graph
from plan_types.invariants import topology, typing

numbers = Variable("numbers", list)
number = Variable("number", int)
squared = Variable("squared", int)
squares = Variable("squares", list)
total = Variable("total", int)


class Square(Step):
    """Theirs, unchanged: one number in, one number out."""

    inputs, outputs = (number,), (squared,)
    map_over = (numbers, squares)


class Total(Step):
    """Their example stops at the joined list; summing gives us something to eval."""

    inputs, outputs = (squares,), (total,)


plan = Plan(name="parallel_processing", steps=(Square(), Total()),
            declared_inputs=(numbers,))


# ── three strategies for the SAME logical Step ───────────────────────────────────────────────────
#
# Stage 2's point again, now on their fan-out. `Square` is one operation; these are peers.

def square_exact(number: int) -> int:
    return number * number


def square_by_addition(number: int) -> int:
    return sum(abs(number) for _ in range(abs(number)))


def square_cheap(number: int) -> int:
    """Wrong above 10 — the arm an eval has to catch."""
    return number * number if abs(number) <= 10 else abs(number) * 10


def total_impl(squares: list) -> int:
    return sum(squares)


ARMS = {
    "exact": {Square: square_exact, Total: total_impl},
    "by_addition": {Square: square_by_addition, Total: total_impl},
    "cheap": {Square: square_cheap, Total: total_impl},
}

CORPUS = [[1, 2, 3, 4, 5], [12], [3, 20]]


async def main() -> None:
    print("invariants:", validate(plan, [*topology.ALL, *typing.ALL]) or "[]")
    print(render_mermaid(plan, ARMS["exact"]))

    print("\nTHEIR DOCS' OWN CASE — inputs=[1, 2, 3, 4, 5]\n")
    strategy = ARMS["exact"]
    local = execute(plan, {"numbers": [1, 2, 3, 4, 5]}, LocalRunner(strategy))
    on_theirs = await to_pydantic_graph(plan, strategy).run(
        state={}, inputs={"numbers": [1, 2, 3, 4, 5]})
    print(f"  their docs say          Results: [1, 4, 9, 16, 25]")
    print(f"  LocalRunner (a loop)    {local['squares']}")
    print(f"  compiled to .map()/join {on_theirs['squares']}")
    assert local["squares"] == on_theirs["squares"] == [1, 4, 9, 16, 25]
    print("  identical               ✓  — one declaration, sequential here, parallel there")

    print("\nTHREE STRATEGIES OVER THE ONE PLAN\n")
    print(f"  {'input':<16} {'expected':>9} " + " ".join(f"{a:>14}" for a in ARMS))
    for case in CORPUS:
        expected = sum(n * n for n in case)
        cells = []
        for s in ARMS.values():
            assert check_strategy(plan, s) == ()
            got = execute(plan, {"numbers": case}, LocalRunner(s))["total"]
            cells.append(f"{got:>8} {'ok' if got == expected else 'WRONG':>5}")
        print(f"  {str(case):<16} {expected:>9} " + " ".join(cells))

    print("\n  The Plan object is never edited between arms. `Square` is ONE logical Step with")
    print("  three implementations — not SquareV1/V2/V3, which would be three names for one thing.")


if __name__ == "__main__":
    asyncio.run(main())
