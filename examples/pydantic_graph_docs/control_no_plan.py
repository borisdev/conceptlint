"""CONTROL ARM — stage 3's three variants with NO Plan layer. Just GraphBuilder.

Written the way a competent developer would write it with GraphBuilder alone. Not a strawman: this
is short, readable, and uses their idiom. If the Plan layer earns nothing here, that is the result,
and it belongs in the comparison rather than being explained away.

    uv run python3 -m examples.pydantic_graph_docs.control_no_plan
"""
from __future__ import annotations

import asyncio

from pydantic_graph import GraphBuilder, StepContext


def square(xs: list[int]) -> list[int]:
    return [n * n for n in xs]


def drop_outliers(xs: list[int]) -> list[int]:
    if not xs:
        return []
    mid = sorted(xs)[len(xs) // 2]
    return [s for s in xs if s <= 4 * mid]


def weight(xs: list[int]) -> list[int]:
    return [s * 2 if s < 10 else s for s in xs]


def build_baseline():
    g = GraphBuilder(name="baseline", input_type=list, output_type=int)

    @g.step
    async def sq(ctx: StepContext[None, None, list]) -> list:
        return square(ctx.inputs)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).to(sq), g.edge_from(sq).to(total),
          g.edge_from(total).to(g.end_node))
    return g.build()


def build_filtered():
    g = GraphBuilder(name="filtered", input_type=list, output_type=int)

    @g.step
    async def sq(ctx: StepContext[None, None, list]) -> list:
        return square(ctx.inputs)

    @g.step
    async def drop(ctx: StepContext[None, None, list]) -> list:
        return drop_outliers(ctx.inputs)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).to(sq), g.edge_from(sq).to(drop),
          g.edge_from(drop).to(total), g.edge_from(total).to(g.end_node))
    return g.build()


def build_weighted():
    g = GraphBuilder(name="weighted", input_type=list, output_type=int)

    @g.step
    async def sq(ctx: StepContext[None, None, list]) -> list:
        return square(ctx.inputs)

    @g.step
    async def drop(ctx: StepContext[None, None, list]) -> list:
        return drop_outliers(ctx.inputs)

    @g.step
    async def wt(ctx: StepContext[None, None, list]) -> list:
        return weight(ctx.inputs)

    @g.step
    async def total(ctx: StepContext[None, None, list]) -> int:
        return sum(ctx.inputs)

    g.add(g.edge_from(g.start_node).to(sq), g.edge_from(sq).to(drop),
          g.edge_from(drop).to(wt), g.edge_from(wt).to(total),
          g.edge_from(total).to(g.end_node))
    return g.build()


VARIANTS = {"baseline": build_baseline, "filtered": build_filtered, "weighted": build_weighted}
CORPUS = [[1, 2, 3], [1, 2, 50], [2, 2, 2, 40]]


async def main() -> None:
    print(f"  {'input':<16} " + " ".join(f"{n:>10}" for n in VARIANTS))
    for case in CORPUS:
        cells = [await build().run(inputs=case) for build in VARIANTS.values()]
        print(f"  {str(case):<16} " + " ".join(f"{c:>10}" for c in cells))

    print("\n  Same numbers as stage 3. The graphs work, they render, they run.")
    print("  What is NOT available here, and why it is not a strawman:")
    print("    - `sq` is redeclared in all three builders. Three functions, one operation.")
    print("      Nothing says they are the same step; a change to one is silent in the others.")
    print("    - to ask 'do these three share a contract?' you read three functions.")
    print("    - to ask 'what changed between filtered and weighted?' you diff wiring code.")
    print("    - each variant is a build_* FUNCTION, so a fourth variant is a fourth copy.")


if __name__ == "__main__":
    asyncio.run(main())
