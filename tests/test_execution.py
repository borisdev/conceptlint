"""A Step declares; a Strategy implements; a Runner performs.

Each test names the failure it would catch. The ones worth reading twice are `test_async_refused`
and `test_examples_import` — both exist because the thing they check was silently broken and no
test could see it.
"""
from __future__ import annotations

import pytest

from workflow_plan import Plan, Step, Variable
from workflow_plan.execution import (ExecutionError, LocalRunner, StepRunner, check_strategy,
                                  run)

document = Variable("document", str)
outline = Variable("outline", tuple)
summary = Variable("summary", str)


class BuildIndex(Step):
    inputs, outputs = (document,), (outline,)


class Condense(Step):
    inputs, outputs = (document, outline), (summary,)


plan = Plan(name="t", steps=(BuildIndex(), Condense()),
            declared_inputs=(document,))


def index_impl(document: str) -> tuple:
    return tuple(document.split())


def condense_short(document: str, outline: tuple) -> str:
    return outline[0] if outline else document


def condense_long(document: str, outline: tuple) -> str:
    return " ".join(outline)


short = {BuildIndex: index_impl, Condense: condense_short}
long_ = {BuildIndex: index_impl, Condense: condense_long}


# ── the declaration carries no implementation ────────────────────────────────────────────────────

def test_step_has_no_run() -> None:
    """The removal itself. A `run` reachable on Step is one implementation privileged over peers."""
    assert not hasattr(Step, "run")
    assert not hasattr(BuildIndex(), "run")


def test_declaring_run_fails_at_import() -> None:
    """Retired, not merely deleted — otherwise the privileged implementation comes back silently."""
    with pytest.raises(TypeError, match="retired"):
        class Rebel(Step):
            inputs, outputs = (document,), (summary,)

            def run(self, **values):  # noqa: ANN001, ANN201
                return "x"


def test_retired_message_names_its_own_replacement() -> None:
    """The old error built its text with `'Input' if old == 'consumes' else 'Output'`, so a THIRD
    retired name would have been explained as being about hasOutputVar."""
    with pytest.raises(TypeError, match="Strategy"):
        class Rebel2(Step):
            inputs, outputs = (document,), (summary,)

            def run(self, **values):  # noqa: ANN001, ANN201
                return "x"

    with pytest.raises(TypeError, match="hasInputVar"):
        class Old(Step):
            consumes = document


# ── one Plan, several strategies ─────────────────────────────────────────────────────────────────

def test_same_plan_two_strategies_differ() -> None:
    """The capability the whole change exists for: the Plan object is not touched between arms."""
    a = run(plan, {"document": "one two three"}, LocalRunner(short))
    b = run(plan, {"document": "one two three"}, LocalRunner(long_))
    assert a["summary"] == "one"
    assert b["summary"] == "one two three"


def test_execute_returns_intermediates_too() -> None:
    env = run(plan, {"document": "a b"}, LocalRunner(short))
    assert env["outline"] == ("a", "b")


def test_local_runner_satisfies_the_protocol_structurally() -> None:
    """No inheritance. An adapter in another package conforms without importing workflow_plan."""
    assert isinstance(LocalRunner({}), StepRunner)


# ── what the runner refuses, loudly ──────────────────────────────────────────────────────────────

def test_missing_binding_names_the_step() -> None:
    with pytest.raises(ExecutionError, match="Condense"):
        run(plan, {"document": "a"}, LocalRunner({BuildIndex: index_impl}))


def test_async_refused() -> None:
    """A coroutine is truthy, has a repr, and flows onward as though it were data."""
    async def condense_async(document: str, outline: tuple) -> str:
        return "x"

    strategy = {BuildIndex: index_impl, Condense: condense_async}
    with pytest.raises(ExecutionError, match="coroutine"):
        run(plan, {"document": "a"}, LocalRunner(strategy))


def test_wrong_output_type_refused() -> None:
    strategy = {BuildIndex: index_impl, Condense: lambda document, outline: 42}
    with pytest.raises(ExecutionError, match="declares 'summary' as str"):
        run(plan, {"document": "a"}, LocalRunner(strategy))


def test_multi_output_arity_refused() -> None:
    left, right = Variable("left", str), Variable("right", str)

    class Split(Step):
        inputs, outputs = (document,), (left, right)

    two = Plan(name="two", steps=(Split(),), declared_inputs=(document,))
    with pytest.raises(ExecutionError, match="must return a tuple of 2"):
        run(two, {"document": "a"}, LocalRunner({Split: lambda document: "only one"}))

    env = run(two, {"document": "a"}, LocalRunner({Split: lambda document: ("l", "r")}))
    assert (env["left"], env["right"]) == ("l", "r")


def test_output_from_a_step_declaring_none_refused() -> None:
    class Audit(Step):
        inputs, outputs = (document,), ()

    p = Plan(name="a", steps=(Audit(),), declared_inputs=(document,))
    with pytest.raises(ExecutionError, match="declares no outputs"):
        run(p, {"document": "a"}, LocalRunner({Audit: lambda document: "leaked"}))

    assert run(p, {"document": "a"}, LocalRunner({Audit: lambda document: None})) == {
        "document": "a"}


def test_missing_plan_input_named() -> None:
    with pytest.raises(ExecutionError, match=r"expects \['document'\]"):
        run(plan, {}, LocalRunner(short))


def test_two_variables_one_name_refused() -> None:
    """A Variable is (name, type), so two can differ in type and collide in a name-keyed env."""
    same_name_other_type = Variable("outline", list)

    class Other(Step):
        inputs, outputs = (document,), (same_name_other_type,)

    p = Plan(name="clash", steps=(BuildIndex(), Other()), declared_inputs=(document,))
    with pytest.raises(ExecutionError, match="sharing the name"):
        run(p, {"document": "a"}, LocalRunner({}))


# ── check_strategy: static, and honest about what it cannot see ──────────────────────────────────

def test_check_strategy_clean() -> None:
    assert check_strategy(plan, short) == ()


def test_check_strategy_reports_every_problem_not_the_first() -> None:
    findings = check_strategy(plan, {})
    assert len(findings) == 2
    assert any("BuildIndex" in f for f in findings)
    assert any("Condense" in f for f in findings)


def test_check_strategy_catches_a_parameter_name_mismatch() -> None:
    """`Variable.name` is part of the contract, because the runner calls by keyword."""
    findings = check_strategy(plan, {BuildIndex: index_impl,
                                     Condense: lambda doc, outline: "x"})
    assert any("will not accept by keyword" in f for f in findings)


def test_check_strategy_catches_an_undeclared_required_parameter() -> None:
    findings = check_strategy(plan, {BuildIndex: index_impl,
                                     Condense: lambda document, outline, model: "x"})
    assert any("'model'" in f and "does not declare" in f for f in findings)


def test_check_strategy_catches_async_before_execution() -> None:
    async def condense_async(document: str, outline: tuple) -> str:
        return "x"

    findings = check_strategy(plan, {BuildIndex: index_impl, Condense: condense_async})
    assert any("async" in f for f in findings)


def test_check_strategy_says_not_checked_when_it_cannot_read_a_signature() -> None:
    """NOT CHECKED and "checked, fine" must never render the same.

    `min` is the stand-in because C builtins are the real case: `inspect.signature(min)` raises
    ValueError, and the tempting `return []` there would report a clean Strategy for a callable
    nobody had looked at.
    """
    findings = check_strategy(plan, {BuildIndex: index_impl, Condense: min})
    assert any("NOT CHECKED" in f for f in findings)


# ── the examples are code, so they have to run ───────────────────────────────────────────────────

def test_examples_import_and_run() -> None:
    """`examples/evidence_case_graph/flow.py` raised TypeError on import for two months — it still
    declared `consumes`, retired 2026-08-16 — and nothing noticed, because no test touched it. An
    example nobody imports is not an example, it is a claim."""
    from examples.evidence_case_graph import flow as evidence
    from examples.hello import flow as hello

    hello.main()
    evidence.main()
