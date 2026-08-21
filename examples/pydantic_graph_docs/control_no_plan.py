"""CONTROL ARM — stage 3's three arms with NO Plan layer. Just GraphBuilder.

⚠️ **This is the FAIR version, and the first one was not.** It originally had three copy-pasted
builders, which made the Plan layer look good by comparison and would not have survived ten seconds
of scrutiny: the obvious move is to parameterise, and a parameterised builder handles all three arms
in a dozen lines. Measuring against code nobody would write is not a measurement.

So there is no line-count claim here any more. What is left is the difference that survives a fair
control, and it is not about volume:

    build(square_impl)          you cannot get a graph, a diagram, or a type check
                                until an implementation EXISTS

    Plan(...)                   validates and renders with nothing implemented at all

    uv run python3 -m examples.pydantic_graph_docs.control_no_plan
"""
from __future__ import annotations

import asyncio
from typing import Callable

from pydantic_graph import GraphBuilder, StepContext, reduce_list_append


def build(square_impl: Callable[[int], int]):
    """Their `parallel_processing.py`, with the varying step passed in."""
    g = GraphBuilder(name="arm", input_type=list, output_type=int)

    @g.step
    async def square(ctx: StepContext[None, None, int]) -> int:
        return square_impl(ctx.inputs)

    collect = g.join(reduce_list_append, initial_factory=list)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).map().to(square), g.edge_from(square).to(collect),
          g.edge_from(collect).to(total), g.edge_from(total).to(g.end_node))
    return g.build()


ARMS = {
    "exact": lambda n: n * n,
    "by_addition": lambda n: sum(abs(n) for _ in range(abs(n))),
    "cheap": lambda n: n * n if abs(n) <= 10 else abs(n) * 10,
}
CORPUS = [[1, 2, 3, 4, 5], [12], [3, 20]]


async def main() -> None:
    print(f"  {'input':<16} {'expected':>9} " + " ".join(f"{a:>14}" for a in ARMS))
    for case in CORPUS:
        expected = sum(n * n for n in case)
        cells = []
        for impl in ARMS.values():
            got = await build(impl).run(inputs=case)
            cells.append(f"{got:>8} {'ok' if got == expected else 'WRONG':>5}")
        print(f"  {str(case):<16} {expected:>9} " + " ".join(cells))

    print("\n  Same numbers as stage 3, in twelve lines. This is a GOOD control.")
    print("  The differences that survive it:")
    print("    - `build()` needs an implementation before it can produce anything at all.")
    print("      No graph, no diagram, no type check, until someone has written square_impl.")
    print("    - its diagram has no types on the edges, because an edge carries whatever the")
    print("      function returned and there is no name for it.")
    print("    - its diagram shows map/join as NODES: it draws the machinery, not the process.")


if __name__ == "__main__":
    asyncio.run(main())
