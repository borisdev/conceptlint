"""The core the handoff asks for: a typed, inspectable, validated process spec.

    plan = Plan(...)
    validate(plan)
    print(render_mermaid(plan))

with no execution framework anywhere in reach.
"""
from __future__ import annotations

import pytest

from plan_types import Plan, Step, Variable, render_mermaid, validate
from plan_types.invariants import topology, typing as typing_inv
from plan_types.plan import bindings
from plan_types.plan.plan import MultiStep, PlanError


class Paper: ...
class Findings: ...
class Summary: ...


PAPER = Variable("paper", Paper)
FINDINGS = Variable("findings", Findings)
SUMMARY = Variable("summary", Summary)


class Extract(Step):
    inputs, outputs = (PAPER,), (FINDINGS,)


class Summarize(Step):
    """Fans in: needs the paper AND the findings."""

    inputs, outputs = (PAPER, FINDINGS), (SUMMARY,)


def a_plan() -> Plan:
    return Plan(name="extract_and_summarize", steps=(Extract(), Summarize()))


# ── the Plan answers the eight questions ─────────────────────────────────────────────────────────

def test_concrete_types_survive_into_the_contract() -> None:
    """`object` everywhere would make the type check theatre."""
    assert a_plan().shape() == ((Paper,), (Summary,))


def test_inputs_are_the_free_variables_not_the_first_step() -> None:
    plan = a_plan()
    assert [v.name for v in plan.inputs] == ["paper"]
    assert [v.name for v in plan.outputs] == ["summary"]
    assert len(plan.variables) == 3


def test_a_step_may_consume_many_variables() -> None:
    """p-plan:hasInputVar carries no cardinality restriction — fan-in is the ordinary case."""
    assert len(Summarize.inputs) == 2


def test_declaration_order_carries_no_meaning() -> None:
    """Order is derived from the bindings; declaring backwards must not change it."""
    forward = bindings.execution_order(a_plan())
    backward = bindings.execution_order(Plan(name="x", steps=(Summarize(), Extract())))
    assert [type(s).__name__ for s in forward] == [type(s).__name__ for s in backward]


# ── construction refuses only what is INCOHERENT ─────────────────────────────────────────────────

def test_a_class_instead_of_an_instance_says_so() -> None:
    with pytest.raises(PlanError, match="holds the CLASS"):
        Plan(name="oops", steps=(Extract,))  # type: ignore[arg-type]


def test_a_runtime_object_among_plan_time_declarations_is_refused() -> None:
    class FakeActivity:
        started_at = "10:04"

    with pytest.raises(PlanError, match="not a Step"):
        Plan(name="leaky", steps=(Extract(), FakeActivity()))  # type: ignore[arg-type]


# ── ⚠️ a Plan is NOT a DAG ───────────────────────────────────────────────────────────────────────

def test_a_cyclic_plan_can_be_CONSTRUCTED() -> None:
    """The heart of the correction.

    An earlier design ran a toposort in `__post_init__`, so "acyclic" was part of what a Plan
    MEANT. That closes the door on iterative processes before anyone has asked for one — and
    P-Plan has no acyclicity axiom, only a transitive `isPrecededBy`.
    """
    A, B = Variable("a", int), Variable("b", int)

    class Ping(Step):
        inputs, outputs = (B,), (A,)

    class Pong(Step):
        inputs, outputs = (A,), (B,)

    plan = Plan(name="loop", steps=(Ping(), Pong()))   # must NOT raise
    assert len(plan.steps) == 2


def test_the_acyclic_invariant_reports_that_same_cycle() -> None:
    """Legal to build, checkable when you want it — which is the whole distinction."""
    A, B = Variable("a", int), Variable("b", int)

    class Ping(Step):
        inputs, outputs = (B,), (A,)

    class Pong(Step):
        inputs, outputs = (A,), (B,)

    found = validate(Plan(name="loop", steps=(Ping(), Pong())), [topology.ACYCLIC])
    assert [v.invariant_id for v in found] == ["topology.acyclic"]


# ── topology invariants ──────────────────────────────────────────────────────────────────────────

def test_a_clean_plan_violates_nothing() -> None:
    """⚠️ BOUND_INPUTS excluded — without `declared_inputs` it reports NOT CHECKED, not a pass."""
    checks = [i for i in (*topology.ALL, *typing_inv.ALL) if i is not topology.BOUND_INPUTS]
    assert validate(a_plan(), checks) == []


def test_an_undeclared_plan_reports_NOT_CHECKED_rather_than_passing() -> None:
    """The distinction that makes bound_inputs meaningful at all.

    With inputs DERIVED — "consumed here, produced by nothing here" — an accidental gap and the
    Plan's own signature are the same set, so the check cannot fire. Reporting a pass there would
    make "we did not look" indistinguishable from "we looked and it was fine".
    """
    found = validate(a_plan(), [topology.BOUND_INPUTS])
    assert found and found[0].message.startswith("NOT CHECKED")


def test_an_unbound_input_is_reported_once_inputs_are_declared() -> None:
    MISSING = Variable("nobody_makes_this", Findings)

    class Needs(Step):
        inputs, outputs = (PAPER, MISSING), (SUMMARY,)

    plan = Plan(name="gap", steps=(Extract(), Needs()), declared_inputs=(PAPER,))
    found = validate(plan, [topology.BOUND_INPUTS])
    assert found and "nobody_makes_this" in found[0].message


def test_a_DECLARED_plan_input_is_NOT_unbound() -> None:
    """The PASS twin. A Plan's own signature must not read as an error."""
    plan = Plan(name="ok", steps=(Extract(), Summarize()), declared_inputs=(PAPER,))
    assert validate(plan, [topology.BOUND_INPUTS]) == []


def test_two_producers_for_one_variable_is_reported() -> None:
    """Not our rule — p-plan:isOutputVarOf is an owl:FunctionalProperty."""
    class AlsoExtract(Step):
        inputs, outputs = (PAPER,), (FINDINGS,)

    found = validate(Plan(name="dup", steps=(Extract(), AlsoExtract(), Summarize())),
                     [topology.SINGLE_PRODUCER])
    assert found and "findings" in found[0].message


# ── typing invariants ────────────────────────────────────────────────────────────────────────────

def test_same_name_different_type_is_reported() -> None:
    """Looks like a binding in the diagram and in the reading; moves nothing."""
    WRONG = Variable("findings", str)

    class Mismatched(Step):
        inputs, outputs = (WRONG,), (SUMMARY,)

    found = validate(Plan(name="clash", steps=(Extract(), Mismatched())),
                     [typing_inv.COMPATIBLE_BINDINGS])
    assert found and "findings" in found[0].message


# ── validate collects, it does not stop at the first ─────────────────────────────────────────────

def test_validate_returns_every_violation() -> None:
    """One cycle can cause several findings, and seeing them all is how you spot one root cause."""
    A, B = Variable("a", int), Variable("b", int)

    class Ping(Step):
        inputs, outputs = (B,), (A,)

    class Pong(Step):
        inputs, outputs = (A,), (B,)

    found = validate(Plan(name="loop", steps=(Ping(), Pong())), topology.ALL)
    assert len(found) >= 1
    assert all(v.invariant_id.startswith("topology.") for v in found)


# ── visualization is derived ─────────────────────────────────────────────────────────────────────

def test_the_diagram_shows_the_actual_relationships() -> None:
    out = render_mermaid(a_plan())
    assert "IN_paper -- paper --> extract_and_summarize_0" in out
    assert "extract_and_summarize_0 -- findings --> extract_and_summarize_1" in out
    assert "IN_paper -- paper --> extract_and_summarize_1" in out, "the fan-in must be drawn"
    assert "extract_and_summarize_1 --> OUT_summary" in out


def test_the_diagram_is_deterministic() -> None:
    assert render_mermaid(a_plan()) == render_mermaid(a_plan())


def test_adding_an_input_changes_the_picture_with_no_edit_to_the_renderer() -> None:
    before = render_mermaid(a_plan()).count("-->")

    class SummarizeWithExtra(Step):
        inputs, outputs = (PAPER, FINDINGS, Variable("style", str)), (SUMMARY,)

    after = render_mermaid(Plan(name="extract_and_summarize",
                                steps=(Extract(), SummarizeWithExtra()))).count("-->")
    assert after > before


def test_the_label_splitter_handles_runs_of_capitals() -> None:
    class PICOSetBuilder(Step):
        inputs, outputs = (PAPER,), (SUMMARY,)

    assert "PICO Set Builder" in render_mermaid(Plan(name="p", steps=(PICOSetBuilder(),)))


# ── p-plan:MultiStep — a Plan that is also a Step ────────────────────────────────────────────────

def test_multistep_is_both_a_plan_and_decomposable() -> None:
    ms = MultiStep(name="inner", steps=(Extract(), Summarize()))
    assert isinstance(ms, Plan)
    assert ms.decomposed_as_plan().shape() == ms.shape()
