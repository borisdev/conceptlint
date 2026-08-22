"""STAGE 1 — their `simple_counter.py`, declared as a Plan and run on their runtime.

Their example, copied verbatim from
https://pydantic.dev/docs/ai/graph/builder/ (Quick Start), is `their_version()` below.

The question this file answers is only: **does the round trip work at all?**

    Plan  ──>  render_mermaid  ──>  to_pydantic_graph  ──>  graph.run()

No claim about value yet. Stage 2 varies the implementation, stage 3 varies the shape.

    uv run python3 -m examples.pydantic_graph_docs.stage1_counter
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from workflow_plan import Plan, PlanStep, Variable, render_mermaid, check
from workflow_plan.execution import SequentialRunner, run
from workflow_plan.execution.pydantic_graph import to_pydantic_graph
from workflow_plan.invariants import topology, typing


# ── theirs, verbatim from the docs ───────────────────────────────────────────────────────────────

@dataclass
class CounterState:
    """State for tracking a counter value."""

    value: int = 0


async def their_version() -> int:
    from pydantic_graph import GraphBuilder, StepContext

    g = GraphBuilder(state_type=CounterState, output_type=int)

    @g.step
    async def increment(ctx: StepContext[CounterState, None, None]) -> int:
        """Increment the counter and return its value."""
        ctx.state.value += 1
        return ctx.state.value

    @g.step
    async def double_it(ctx: StepContext[CounterState, None, int]) -> int:
        """Double the input value."""
        return ctx.inputs * 2

    g.add(
        g.edge_from(g.start_node).to(increment),
        g.edge_from(increment).to(double_it),
        g.edge_from(double_it).to(g.end_node),
    )
    return await g.build().run(state=CounterState())


# ── ours: the same process, said once, with no runtime in it ─────────────────────────────────────

count = Variable("count", int)
doubled = Variable("doubled", int)


class Increment(PlanStep):
    inputs, outputs = (), (count,)


class DoubleIt(PlanStep):
    inputs, outputs = (count,), (doubled,)


plan = Plan(name="counter", steps=(Increment(), DoubleIt()))


def increment() -> int:
    return 1


def double_it(count: int) -> int:
    return count * 2


strategy = {Increment: increment, DoubleIt: double_it}


async def main() -> None:
    print("invariants:", check(plan, [*topology.ALL, *typing.ALL]) or "[]")
    print(render_mermaid(plan))

    theirs = await their_version()
    ours_local = run(plan, {}, SequentialRunner(strategy))["doubled"]
    ours_on_their_runtime = (await to_pydantic_graph(plan, strategy).run(state={}, inputs={}))["doubled"]

    print(f"  their GraphBuilder, hand-wired   {theirs}")
    print(f"  our Plan, SequentialRunner            {ours_local}")
    print(f"  our Plan, compiled onto theirs   {ours_on_their_runtime}")
    assert theirs == ours_local == ours_on_their_runtime == 2
    print("  all three agree                  ✓")

    # ⚠️ The one real difference, and it is not cosmetic. Their `increment` reads and mutates
    # `ctx.state`; it declares its input as None and takes the value from a mutable object that
    # outlives the step. Ours makes the same value an EDGE. Same answer, and the dependency is
    # visible in the diagram rather than in the body of a function.
    print("\n  theirs threads the counter through mutable state (ctx.state.value += 1)")
    print("  ours makes it an edge: Increment -> count -> DoubleIt")


if __name__ == "__main__":
    asyncio.run(main())
