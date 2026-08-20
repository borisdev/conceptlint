"""The layering claim, executed.

`plan_types.plan` must import no execution framework, and the same Plan under the same Strategy must
produce the same answer on `LocalRunner` and on Pydantic Graph. Both are assertions this repo makes
in prose; neither is worth anything unless something runs it.
"""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("pydantic_graph", reason="optional extra: uv sync --extra pydantic-graph")

from plan_types.execution import ExecutionError, LocalRunner, execute  # noqa: E402
from plan_types.execution.pydantic_graph import to_pydantic_graph  # noqa: E402


def test_both_runtimes_agree() -> None:
    from examples.pydantic_graph_demo.flow import User, plan, terse, warm

    reader = User(name="Samuel", interests=("type safety", "graphs"))
    for strategy in (terse, warm):
        local = execute(plan, {"user": reader}, LocalRunner(strategy))["email"]
        graph = to_pydantic_graph(plan, strategy)
        assert asyncio.run(graph.run(inputs={"user": reader}))["email"] == local


def test_the_demo_runs() -> None:
    from examples.pydantic_graph_demo.flow import main

    asyncio.run(main())


def test_an_incomplete_strategy_is_refused_before_the_graph_is_built() -> None:
    """Mid-run would attribute a Strategy fault to the runtime."""
    from examples.pydantic_graph_demo.flow import WriteEmail, plan, terse

    with pytest.raises(ExecutionError, match="Strategy is incomplete"):
        to_pydantic_graph(plan, {WriteEmail: terse[WriteEmail]})


def test_a_cyclic_plan_is_refused_rather_than_linearised() -> None:
    """The case where you SHOULD use their engine, said out loud instead of faked."""
    from plan_types import Plan, Step, Variable
    from plan_types.plan.plan import PlanError

    a, b = Variable("a", int), Variable("b", int)

    class Up(Step):
        inputs, outputs = (a,), (b,)

    class Down(Step):
        inputs, outputs = (b,), (a,)

    cyclic = Plan(name="loop", steps=(Up(), Down()))
    with pytest.raises(PlanError, match="cycle"):
        to_pydantic_graph(cyclic, {Up: lambda a: a, Down: lambda b: b})


def test_the_plan_layer_imports_no_execution_framework() -> None:
    """The layering claim itself. `plan/` must be readable with no engine in the room."""
    import pathlib

    plan_dir = pathlib.Path(__file__).resolve().parents[1] / "plan_types" / "plan"
    for path in plan_dir.glob("*.py"):
        source = path.read_text()
        for engine in ("pydantic_graph", "temporal", "langgraph"):
            assert engine not in source, f"{path.name} references {engine}"
