"""Compile a Plan onto [Pydantic Graph](https://pydantic.dev/docs/ai/graph/graph/).

    Plan + Strategy  -->  pydantic_graph.Graph  -->  await graph.run(inputs=...)

**This is the direction the whole package points.** PlanTypes is not another workflow engine and
does not want to be one: LangGraph, Temporal and Pydantic Graph execute workflows, and they are good
at it. What is missing is the layer where you decide whether the process is RIGHT — before retries,
workers, state and serialization are in the room — and then hand it to one of them unchanged.

So the same `Plan` and the same `Strategy` run under `LocalRunner` while you are still arguing about
the shape, and under Pydantic Graph when you want its runtime. Neither the Plan nor any
implementation is edited in between. `examples/pydantic_graph_demo/` runs both and asserts the
results are identical, because a claim like that one has to be executable.

## What this compile does, exactly

Steps in `execution_order`, chained, threading a dict of Variable-name -> value:

    start --> step_0 --> step_1 --> ... --> end

Each compiled node calls the SAME `Strategy` implementation `LocalRunner` would call, through the
same `_outputs_by_name`, so a Step cannot behave differently on the two runtimes.

## What it deliberately does NOT do yet

**No `Fork` / `Join`.** Pydantic Graph 2.x has both, and a Plan's bindings already say which Steps
are independent — so parallelising is DERIVABLE rather than declarable, which is the interesting
version. It is not built, and this docstring is not going to imply it is.

**Acyclic only.** `execution_order` raises on a cycle rather than inventing an order. That is not a
gap in the compile, it is where the split earns its keep: Pydantic Graph's own examples — the fives
graph, the vending machine, the email-feedback loop — are cyclic state machines, and a cyclic Plan
is exactly the case where you SHOULD reach for that engine. PlanTypes says so instead of pretending
to run it.

**No state or deps.** `state_type` and `deps_type` stay `None`. A Step implementation's
dependencies live in its closure — see `strategy.py`.

## On the two `Step` classes

`pydantic_graph.Step` and `plan_types.Step` are different things and both are correctly named:
theirs is an executable node, ours is a declaration — `p-plan:Step` against, in effect,
`prov:Activity`. This module is the one place both are in scope, and it never imports theirs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from plan_types.execution.local import ExecutionError, _outputs_by_name
from plan_types.execution.strategy import Strategy, check_strategy
from plan_types.plan.bindings import execution_order
from plan_types.plan.plan import Plan

if TYPE_CHECKING:  # pragma: no cover
    from pydantic_graph import Graph


def to_pydantic_graph(plan: Plan, strategy: Strategy, *, name: str | None = None) -> "Graph":
    """Build a `pydantic_graph.Graph` that runs `plan` under `strategy`.

    Raises BEFORE building rather than mid-run: an unbound Step or an uncallable signature is a fact
    about the Strategy, and discovering it inside a graph run would attribute it to the runtime.
    """
    try:
        from pydantic_graph import GraphBuilder
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise ExecutionError(
            "pydantic-graph is not installed. It is an OPTIONAL extra, on purpose: plan_types.plan "
            "imports no execution framework, and this adapter is the only module in the package "
            "that imports one. Install with: uv add 'plan-types[pydantic-graph]'") from exc

    problems = check_strategy(plan, strategy)
    if problems:
        raise ExecutionError(
            f"Plan {plan.name!r} cannot be compiled — the Strategy is incomplete:\n  "
            + "\n  ".join(problems))

    order = execution_order(plan)  # raises on a cycle; see the module docstring
    builder = GraphBuilder(name=name or plan.name, input_type=dict, output_type=dict)

    steps = [_compile_step(builder, step, strategy, i) for i, step in enumerate(order)]

    edges = [builder.edge_from(builder.start_node).to(steps[0])]
    edges += [builder.edge_from(a).to(b) for a, b in zip(steps, steps[1:])]
    edges.append(builder.edge_from(steps[-1]).to(builder.end_node))
    builder.add(*edges)
    return builder.build()


def _compile_step(builder: Any, step: Any, strategy: Strategy, i: int) -> Any:
    """One PlanTypes Step -> one pydantic-graph step threading the environment through.

    The closure is what makes the two runtimes agree: it calls the Strategy's implementation and
    `_outputs_by_name` — exactly what `LocalRunner.run` does — rather than a second copy of that
    logic which could drift.
    """
    cls = type(step)
    impl = strategy[cls]

    async def run_step(ctx: Any) -> dict[str, Any]:
        env: dict[str, Any] = dict(ctx.inputs)
        missing = [v.name for v in cls.inputs if v.name not in env]
        if missing:
            raise ExecutionError(
                f"{cls.__name__} needs {missing}, which nothing upstream produced. On a compiled "
                f"graph that is a WIRING fault, not a runtime one — "
                f"validate(plan, topology.ALL) reports it before you compile.")
        result = impl(**{v.name: env[v.name] for v in cls.inputs})
        if hasattr(result, "__await__"):
            result = await result  # async IS fine here — a graph run awaits. LocalRunner cannot.
        env.update(_outputs_by_name(cls, result))
        return env

    run_step.__name__ = f"{cls.__name__}_{i}"
    return builder.step(run_step, label=cls.__name__)
