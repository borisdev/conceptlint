"""Compile a Plan onto [Pydantic Graph](https://pydantic.dev/docs/ai/graph/graph/).

    Plan + Strategy  -->  pydantic_graph.Graph  -->  await graph.run(inputs=...)

**This is the direction the whole package points.** workflow-plan is not another workflow engine and
does not want to be one: LangGraph, Temporal and Pydantic Graph execute workflows, and they are good
at it. What is missing is the layer where you decide whether the process is RIGHT — before retries,
workers, state and serialization are in the room — and then hand it to one of them unchanged.

So the same `Plan` and the same `Strategy` run under `SequentialRunner` while you are still arguing about
the shape, and under Pydantic Graph when you want its runtime. Neither the Plan nor any
implementation is edited in between. `examples/pydantic_graph_demo/` runs both and asserts the
results are identical, because a claim like that one has to be executable.

## What this compile does, exactly

Steps in `execution_order`, chained, threading a dict of Variable-name -> value:

    start --> step_0 --> step_1 --> ... --> end

Each compiled node calls the SAME `Strategy` implementation `SequentialRunner` would call, through the
same `_outputs_by_name`, so a PlanStep cannot behave differently on the two runtimes.

## What it deliberately does NOT do yet

**No `Fork` / `Join`.** Pydantic Graph 2.x has both, and a Plan's bindings already say which Steps
are independent — so parallelising is DERIVABLE rather than declarable, which is the interesting
version. It is not built, and this docstring is not going to imply it is.

**Acyclic only.** `execution_order` raises on a cycle rather than inventing an order. That is not a
gap in the compile, it is where the split earns its keep: Pydantic Graph's own examples — the fives
graph, the vending machine, the email-feedback loop — are cyclic state machines, and a cyclic Plan
is exactly the case where you SHOULD reach for that engine. workflow-plan says so instead of pretending
to run it.

**No state or deps.** `state_type` and `deps_type` stay `None`. A PlanStep implementation's
dependencies live in its closure — see `strategy.py`.

## On the two `PlanStep` classes

`pydantic_graph.Step` and `workflow_plan.PlanStep` are different things and both are correctly named:
theirs is an executable node, ours is a declaration — `p-plan:Step` against, in effect,
`prov:Activity`. This module is the one place both are in scope, and it never imports theirs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from workflow_plan.execution.local import ExecutionError, _check_type, _outputs_by_name
from workflow_plan.execution.strategy import Strategy, check_strategy
from workflow_plan.plan.bindings import execution_order
from workflow_plan.plan.plan import Plan

if TYPE_CHECKING:  # pragma: no cover
    from pydantic_graph import Graph


def to_pydantic_graph(plan: Plan, strategy: Strategy, *, name: str | None = None) -> "Graph":
    """Build a `pydantic_graph.Graph` that runs `plan` under `strategy`.

    Raises BEFORE building rather than mid-run: an unbound PlanStep or an uncallable signature is a fact
    about the Strategy, and discovering it inside a graph run would attribute it to the runtime.

    ## Shape of the compiled graph

    The Plan's environment — Variable name -> value — lives in their `state`, which is what state is
    for and is how their own examples carry values that outlive one edge. Edges then carry only what
    a `.map()` needs to fan out.

        seed ──> step ──> step ──> ... ──> finish ──> end

    A MAPPED PlanStep compiles to their four-part fan-out, using their primitives, not a loop wearing
    their name:

        emit ──.map()──> <per-item step> ──> join(reduce_list_append) ──> store

    So a Plan that declares `map_over` becomes an actually-parallel map on their engine, and the
    same declaration is a sequential loop under `SequentialRunner`. That is the split working: the Plan
    says a fan-out exists; how many workers run it is the runtime's business.
    """
    try:
        from pydantic_graph import GraphBuilder, reduce_list_append
    except ImportError as exc:  # pragma: no cover - depends on the extra
        raise ExecutionError(
            "pydantic-graph is not installed. It is an OPTIONAL extra, on purpose: workflow_plan.plan "
            "imports no execution framework, and this adapter is the only module in the package "
            "that imports one. Install with: uv add 'workflow-plan[pydantic-graph]'") from exc

    problems = check_strategy(plan, strategy)
    if problems:
        raise ExecutionError(
            f"Plan {plan.name!r} cannot be compiled — the Strategy is incomplete:\n  "
            + "\n  ".join(problems))

    _refuse_cycles_for_the_right_reason(plan)
    order = execution_order(plan)
    g = GraphBuilder(name=name or plan.name, state_type=dict, input_type=dict, output_type=dict)

    async def seed(ctx: Any) -> None:
        ctx.state.update(ctx.inputs)

    async def finish(ctx: Any) -> dict[str, Any]:
        return dict(ctx.state)

    seed_node = g.step(seed, label="seed")
    finish_node = g.step(finish, label="finish")

    edges = [g.edge_from(g.start_node).to(seed_node)]
    previous: Any = seed_node

    for i, step in enumerate(order):
        cls = type(step)
        if cls.map_over is None:
            node = g.step(_plain(cls, strategy[cls], i), label=cls.__name__)
            edges.append(g.edge_from(previous).to(node))
            previous = node
            continue

        emit, per_item, store = _mapped(g, cls, strategy[cls], i)
        collect = g.join(reduce_list_append, initial_factory=list)
        edges += [
            g.edge_from(previous).to(emit),
            g.edge_from(emit).map().to(per_item),
            g.edge_from(per_item).to(collect),
            g.edge_from(collect).to(store),
        ]
        previous = store

    edges += [g.edge_from(previous).to(finish_node), g.edge_from(finish_node).to(g.end_node)]
    g.add(*edges)
    return g.build()


def _plain(cls: Any, impl: Any, i: int) -> Any:
    """An ordinary PlanStep: read its inputs from state, write its outputs back.

    Calls the same `_outputs_by_name` `SequentialRunner` does, so a PlanStep cannot mean one thing here and
    another there — a second copy of that logic is a second thing to drift.
    """
    async def run_step(ctx: Any) -> None:
        env = ctx.state
        missing = [v.name for v in cls.inputs if v.name not in env]
        if missing:
            raise ExecutionError(
                f"{cls.__name__} needs {missing}, which nothing upstream produced. On a compiled "
                f"graph that is a WIRING fault, not a runtime one — "
                f"validate(plan, topology.ALL) reports it before you compile.")
        result = impl(**{v.name: env[v.name] for v in cls.inputs})
        if hasattr(result, "__await__"):
            result = await result  # async IS fine here — a graph run awaits. SequentialRunner cannot.
        env.update(_outputs_by_name(cls, result))

    run_step.__name__ = f"{cls.__name__}_{i}"
    return run_step


def _mapped(g: Any, cls: Any, impl: Any, i: int) -> tuple[Any, Any, Any]:
    """`emit -> .map() -> per_item -> join -> store`, in their vocabulary.

    `emit` puts the list on the edge, because `.map()` fans out an EDGE's value and our environment
    lives in state. `store` puts the joined list back. Neither is a PlanStep in the Plan — they are the
    seam between our environment and their edges, and they exist because the two models differ, not
    because the Plan has extra nodes in it.
    """
    source, collected = cls.map_over
    item_var, out_var = cls.inputs[0], cls.outputs[0]

    async def emit(ctx: Any) -> list:
        items = ctx.state.get(source.name)
        try:
            return list(items)
        except TypeError:
            raise ExecutionError(
                f"{cls.__name__} maps over {source.name!r}, which arrived as "
                f"{type(items).__name__} and is not iterable.") from None

    async def per_item(ctx: Any) -> Any:
        out = impl(**{item_var.name: ctx.inputs})
        if hasattr(out, "__await__"):
            out = await out
        _check_type(cls, out_var, out)
        return out

    async def store(ctx: Any) -> None:
        ctx.state[collected.name] = list(ctx.inputs)

    emit.__name__ = f"emit_{source.name}_{i}"
    per_item.__name__ = f"{cls.__name__}_{i}"
    store.__name__ = f"store_{collected.name}_{i}"
    return (g.step(emit, label=f"map {source.name}"),
            g.step(per_item, label=cls.__name__),
            g.step(store, label=f"join -> {collected.name}"))


def _refuse_cycles_for_the_right_reason(plan: Plan) -> None:
    """A cyclic Plan cannot compile — and the reason is NOT that toposort fails.

    `execution_order` raises anyway, saying "there is no execution order to return", which reads as
    a limitation of the algorithm. It is not. Given a perfect cyclic scheduler this would still loop
    forever, because **a Plan does not say when to stop**: their `Feedback.run()` returns
    `WriteEmail | End[Email]` and the predicate lives in the node body, where we cannot see it.

    Fixing that in general means adding Decision/branch/End here, which is rebuilding what
    GraphBuilder already owns. The route that does not: collapse each strongly connected component
    into a `MultiStep` and declare `until` — an SCC condensation is ALWAYS a DAG, so the outer Plan
    compiles and the loop inside is theirs. Partly built: `MultiStep.until` exists, the condensation
    does not.
    """
    from workflow_plan.plan.plan import PlanError

    try:
        execution_order(plan)
    except PlanError as exc:
        raise PlanError(
            f"{exc} — and note the reason is NOT that this cannot be ordered. A Plan does not "
            f"carry a termination predicate, so no scheduler could run it either: pydantic-graph "
            f"puts that predicate in the node body (`-> Next | End[T]`), which is the right place "
            f"for it and is theirs. An iterative region belongs in a MultiStep with `until` set, "
            f"whose implementation is one of their graphs; the outer Plan is then a DAG."
        ) from exc
