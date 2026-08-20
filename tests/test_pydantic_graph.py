"""The layering claim, executed.

`plan_types.plan` must import no execution framework, and the same Plan under the same Strategy must
produce the same answer on `LocalRunner` and on Pydantic Graph. Both are assertions this repo makes
in prose; neither is worth anything unless something runs it.
"""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("pydantic_graph", reason="optional extra: uv sync --extra pydantic-graph")

from plan_types.execution import (ExecutionError, LocalRunner, check_strategy,  # noqa: E402
                                  execute)
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


# ── the staged comparison against their docs (examples/pydantic_graph_docs/) ─────────────────────

def test_stage1_their_docs_example_round_trips() -> None:
    """Their `simple_counter.py` verbatim, our Plan, and our Plan on their runtime all give 2."""
    from examples.pydantic_graph_docs import stage1_counter as s1

    asyncio.run(s1.main())


def test_stage2_three_strategies_over_one_plan() -> None:
    from examples.pydantic_graph_docs import stage2_strategies as s2

    asyncio.run(s2.main())


def test_the_plan_object_is_shared_across_arms_not_copied() -> None:
    """The claim an eval depends on: arms differ ONLY in the Strategy.

    Identity, not equality — a Plan rebuilt per arm could drift a Step and still compare equal
    under a weaker check, which is the failure `AIEvalTrial` exists to prevent.
    """
    from examples.pydantic_graph_docs.stage2_strategies import ARMS, plan

    for strategy in ARMS.values():
        assert check_strategy(plan, strategy) == ()
    assert len({id(plan) for _ in ARMS}) == 1


def test_the_diagrams_differ_only_in_the_implementation_labels() -> None:
    """The visual claim, checked: strip the <i> labels and the three renders are byte-identical."""
    import re

    from plan_types import render_mermaid
    from examples.pydantic_graph_docs.stage2_strategies import ARMS, plan

    strip = lambda t: re.sub(r"<br/><i>[^<]+</i>", "", t)  # noqa: E731
    renders = [render_mermaid(plan, s) for s in ARMS.values()]
    assert len({strip(r) for r in renders}) == 1, "topology differed between arms"
    assert len(set(renders)) == len(ARMS), "the arms rendered identically — labels missing"


def test_stage3_variants_and_control_arm_agree() -> None:
    """The comparison is only worth reading if both arms compute the same thing."""
    from examples.pydantic_graph_docs import control_no_plan as ctrl
    from examples.pydantic_graph_docs import stage3_variants as s3
    from plan_types.execution import LocalRunner, execute

    for case in s3.CORPUS:
        with_plan = [execute(p, {"numbers": case}, LocalRunner(s3.STRATEGY))["total"]
                     for p in s3.VARIANTS.values()]
        control = [asyncio.run(build().run(inputs=case)) for build in ctrl.VARIANTS.values()]
        assert with_plan == control, f"arms disagree on {case}: {with_plan} vs {control}"


def test_the_three_variants_share_one_contract() -> None:
    """`check_arms` is what makes stage 3's eval table legal rather than merely printed."""
    from plan_types import check_arms
    from examples.pydantic_graph_docs.stage3_variants import VARIANTS

    check_arms(list(VARIANTS.values()))
