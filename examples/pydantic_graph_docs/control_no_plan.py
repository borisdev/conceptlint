"""CONTROL ARM — stage 3's three strategies with NO Plan layer. Just GraphBuilder.

Their `parallel_processing.py`, written three times with a different `square` each time. This is
what you write if you want to compare three implementations and you have GraphBuilder alone.

Not a strawman: it is short, idiomatic, and uses their `.map()` and join exactly as documented.
If the Plan layer earns nothing here, that is the result and it belongs in the comparison.

    uv run python3 -m examples.pydantic_graph_docs.control_no_plan
"""
from __future__ import annotations

import asyncio

from pydantic_graph import GraphBuilder, StepContext, reduce_list_append


def build_exact():
    g = GraphBuilder(name="exact", input_type=list, output_type=int)

    @g.step
    async def square(ctx: StepContext[None, None, int]) -> int:
        return ctx.inputs * ctx.inputs

    collect = g.join(reduce_list_append, initial_factory=list)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).map().to(square), g.edge_from(square).to(collect),
          g.edge_from(collect).to(total), g.edge_from(total).to(g.end_node))
    return g.build()


def build_by_addition():
    g = GraphBuilder(name="by_addition", input_type=list, output_type=int)

    @g.step
    async def square(ctx: StepContext[None, None, int]) -> int:
        return sum(abs(ctx.inputs) for _ in range(abs(ctx.inputs)))

    collect = g.join(reduce_list_append, initial_factory=list)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).map().to(square), g.edge_from(square).to(collect),
          g.edge_from(collect).to(total), g.edge_from(total).to(g.end_node))
    return g.build()


def build_cheap():
    g = GraphBuilder(name="cheap", input_type=list, output_type=int)

    @g.step
    async def square(ctx: StepContext[None, None, int]) -> int:
        n = ctx.inputs
        return n * n if abs(n) <= 10 else abs(n) * 10

    collect = g.join(reduce_list_append, initial_factory=list)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).map().to(square), g.edge_from(square).to(collect),
          g.edge_from(collect).to(total), g.edge_from(total).to(g.end_node))
    return g.build()


ARMS = {"exact": build_exact, "by_addition": build_by_addition, "cheap": build_cheap}
CORPUS = [[1, 2, 3, 4, 5], [12], [3, 20]]


async def main() -> None:
    print(f"  {'input':<16} {'expected':>9} " + " ".join(f"{a:>14}" for a in ARMS))
    for case in CORPUS:
        expected = sum(n * n for n in case)
        cells = []
        for build in ARMS.values():
            got = await build().run(inputs=case)
            cells.append(f"{got:>8} {'ok' if got == expected else 'WRONG':>5}")
        print(f"  {str(case):<16} {expected:>9} " + " ".join(cells))

    print("\n  Same numbers as stage 3. It works, it renders, it runs in parallel.")
    print("  What is NOT available, and why this is not a strawman:")
    print("    - the map/join wiring is written 3x. Change the reducer and you change it 3 times,")
    print("      or you change 1 and the other two silently disagree.")
    print("    - `total` is written 3x though it never varies. Nothing says the three are one step.")
    print("    - to ask 'is this the same process with a different square?' you diff 3 builders.")
    print("    - a 4th arm is a 4th copy of the whole graph, not one dict entry.")


if __name__ == "__main__":
    asyncio.run(main())
