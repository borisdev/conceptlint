"""You write the graph. The Plan owns the declaration and the binding.

    uv run python3 -m examples.pydantic_graph_docs.hand_written_wrapper

This is the integration the README leads with, and it is deliberately NOT `to_pydantic_graph`.

## Why the hand-written one goes first

`to_pydantic_graph` generates the graph for you, and generating somebody's graph invites one
question — *"why would I let you generate my graph?"* — which has no good answer. Their
`GraphBuilder` is theirs, they like it, and the edges are the part they want to see.

So the honest integration is the boring one: you write the nodes exactly as their docs show, and
each node body calls the implementation the Plan has bound. Six lines of glue, no compiler, and
every runtime feature of theirs stays reachable because you never left their API.

What the Plan is still doing while you hold the pen:

    the DECLARATION      Increment produces `count`; DoubleIt consumes it — checkable with no
                         function bodies, before anything is implemented
    the BINDING          `strategy[DoubleIt]` — one Step, several peer implementations, chosen per
                         run rather than one being privileged as an override
    the DIAGRAM          render_mermaid(plan), derived from the same declaration your nodes call

None of which their graph gives you, and none of which requires them to give up their graph.

## The one thing this file must prove

That the node bodies and the Plan cannot drift: both call `strategy[cls]`, so there is one
implementation and two callers. The assertion at the bottom is the whole point — hand-written and
`SequentialRunner` return the same value because they are running the same function.
"""
from __future__ import annotations

import asyncio

from workflow_plan import render_mermaid
from workflow_plan.execution import SequentialRunner, run

from examples.pydantic_graph_docs.stage1_counter import DoubleIt, Increment, plan, strategy


async def hand_written() -> int:
    """Their `simple_counter.py`, node for node — with the bodies delegating to the Plan."""
    from pydantic_graph import GraphBuilder, StepContext

    g = GraphBuilder(state_type=None, output_type=int)

    @g.step
    async def increment(ctx: StepContext[None, None, None]) -> int:
        return strategy[Increment]()                    # <- the Plan's binding, not a body

    @g.step
    async def double_it(ctx: StepContext[None, None, int]) -> int:
        return strategy[DoubleIt](count=ctx.inputs)     # <- keyword IS the Variable name

    g.add(
        g.edge_from(g.start_node).to(increment),
        g.edge_from(increment).to(double_it),
        g.edge_from(double_it).to(g.end_node),
    )
    return await g.build().run()


async def main() -> None:
    print(render_mermaid(plan))

    theirs = await hand_written()
    ours = run(plan, {}, SequentialRunner(strategy))["doubled"]

    print(f"  hand-written GraphBuilder, bodies from the Strategy   {theirs}")
    print(f"  the same Plan on SequentialRunner                     {ours}")
    assert theirs == ours == 2, (theirs, ours)
    print("\n  Same value because it is the same function. The graph is yours; the declaration,")
    print("  the binding and the diagram come from the Plan.")


if __name__ == "__main__":
    asyncio.run(main())
