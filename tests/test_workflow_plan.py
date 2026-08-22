"""The core the handoff asks for: a typed, inspectable, validated process spec.

    plan = Plan(...)
    validate(plan)
    print(render_mermaid(plan))

with no execution framework anywhere in reach.
"""
from __future__ import annotations

import pytest

from workflow_plan import Plan, PlanStep, Variable, render_mermaid, validate
from workflow_plan.invariants import topology, typing as typing_inv
from workflow_plan.plan import bindings
from workflow_plan.plan.plan import MultiStep, PlanError


class Paper: ...
class Findings: ...
class Summary: ...


PAPER = Variable("paper", Paper)
FINDINGS = Variable("findings", Findings)
SUMMARY = Variable("summary", Summary)


class Extract(PlanStep):
    inputs, outputs = (PAPER,), (FINDINGS,)


class SummarizePaper(PlanStep):
    """Fans in: needs the paper AND the findings."""

    inputs, outputs = (PAPER, FINDINGS), (SUMMARY,)


def a_plan() -> Plan:
    return Plan(name="extract_and_summarize", steps=(Extract(), SummarizePaper()))


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
    assert len(SummarizePaper.inputs) == 2


def test_declaration_order_carries_no_meaning() -> None:
    """Order is derived from the bindings; declaring backwards must not change it."""
    forward = bindings.execution_order(a_plan())
    backward = bindings.execution_order(Plan(name="x", steps=(SummarizePaper(), Extract())))
    assert [type(s).__name__ for s in forward] == [type(s).__name__ for s in backward]


# ── construction refuses only what is INCOHERENT ─────────────────────────────────────────────────

def test_a_class_instead_of_an_instance_says_so() -> None:
    with pytest.raises(PlanError, match="holds the CLASS"):
        Plan(name="oops", steps=(Extract,))  # type: ignore[arg-type]


def test_a_runtime_object_among_plan_time_declarations_is_refused() -> None:
    class FakeActivity:
        started_at = "10:04"

    with pytest.raises(PlanError, match="not a PlanStep"):
        Plan(name="leaky", steps=(Extract(), FakeActivity()))  # type: ignore[arg-type]


# ── ⚠️ a Plan is NOT a DAG ───────────────────────────────────────────────────────────────────────

def test_a_cyclic_plan_can_be_CONSTRUCTED() -> None:
    """The heart of the correction.

    An earlier design ran a toposort in `__post_init__`, so "acyclic" was part of what a Plan
    MEANT. That closes the door on iterative processes before anyone has asked for one — and
    P-Plan has no acyclicity axiom, only a transitive `isPrecededBy`.
    """
    A, B = Variable("a", int), Variable("b", int)

    class Ping(PlanStep):
        inputs, outputs = (B,), (A,)

    class Pong(PlanStep):
        inputs, outputs = (A,), (B,)

    plan = Plan(name="loop", steps=(Ping(), Pong()))   # must NOT raise
    assert len(plan.steps) == 2


def test_the_acyclic_invariant_reports_that_same_cycle() -> None:
    """Legal to build, checkable when you want it — which is the whole distinction."""
    A, B = Variable("a", int), Variable("b", int)

    class Ping(PlanStep):
        inputs, outputs = (B,), (A,)

    class Pong(PlanStep):
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

    class Needs(PlanStep):
        inputs, outputs = (PAPER, MISSING), (SUMMARY,)

    plan = Plan(name="gap", steps=(Extract(), Needs()), declared_inputs=(PAPER,))
    found = validate(plan, [topology.BOUND_INPUTS])
    assert found and "nobody_makes_this" in found[0].message


def test_a_DECLARED_plan_input_is_NOT_unbound() -> None:
    """The PASS twin. A Plan's own signature must not read as an error."""
    plan = Plan(name="ok", steps=(Extract(), SummarizePaper()), declared_inputs=(PAPER,))
    assert validate(plan, [topology.BOUND_INPUTS]) == []


def test_two_producers_for_one_variable_is_reported() -> None:
    """Not our rule — p-plan:isOutputVarOf is an owl:FunctionalProperty."""
    class AlsoExtract(PlanStep):
        inputs, outputs = (PAPER,), (FINDINGS,)

    found = validate(Plan(name="dup", steps=(Extract(), AlsoExtract(), SummarizePaper())),
                     [topology.SINGLE_PRODUCER])
    assert found and "findings" in found[0].message


# ── typing invariants ────────────────────────────────────────────────────────────────────────────

def test_same_name_different_type_is_reported() -> None:
    """Looks like a binding in the diagram and in the reading; moves nothing."""
    WRONG = Variable("findings", str)

    class Mismatched(PlanStep):
        inputs, outputs = (WRONG,), (SUMMARY,)

    found = validate(Plan(name="clash", steps=(Extract(), Mismatched())),
                     [typing_inv.COMPATIBLE_BINDINGS])
    assert found and "findings" in found[0].message


# ── validate collects, it does not stop at the first ─────────────────────────────────────────────

def test_validate_returns_every_violation() -> None:
    """One cycle can cause several findings, and seeing them all is how you spot one root cause."""
    A, B = Variable("a", int), Variable("b", int)

    class Ping(PlanStep):
        inputs, outputs = (B,), (A,)

    class Pong(PlanStep):
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

    class SummarizeWithExtra(PlanStep):
        inputs, outputs = (PAPER, FINDINGS, Variable("style", str)), (SUMMARY,)

    after = render_mermaid(Plan(name="extract_and_summarize",
                                steps=(Extract(), SummarizeWithExtra()))).count("-->")
    assert after > before


def test_the_label_splitter_handles_runs_of_capitals() -> None:
    class PICOSetBuilder(PlanStep):
        inputs, outputs = (PAPER,), (SUMMARY,)

    assert "PICO Set Builder" in render_mermaid(Plan(name="p", steps=(PICOSetBuilder(),)))


# ── p-plan:MultiStep — a Plan that is also a PlanStep ────────────────────────────────────────────────

def test_multistep_is_both_a_plan_and_decomposable() -> None:
    ms = MultiStep(name="inner", steps=(Extract(), SummarizePaper()))
    assert isinstance(ms, Plan)
    assert ms.decomposed_as_plan().shape() == ms.shape()


# --- the README must not lie ---------------------------------------------------------------------

def test_the_readme_example_runs_and_returns_what_it_claims() -> None:
    """The README asserts `validate(...) → []`. It said that while returning a finding.

    Caught by running it: without `declared_inputs`, `topology.bound_inputs` reports NOT CHECKED,
    so the claimed empty list was wrong. A README whose code does not run is the exact failure this
    package is about — a confident claim with nothing checking it.
    """
    import pathlib

    from examples.hello.flow import fast, plan, precise

    readme = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert "declared_inputs=(document,)" in readme, (
        "the 60-second example must declare its inputs, or the validate() it claims is wrong")

    assert validate(plan, [*topology.ALL, *typing_inv.ALL]) == [], (
        "the README claims this returns []")

    # ⚠️ The diagram must be BYTE-IDENTICAL to what the renderer produces. The previous version of
    # this test rebuilt an equivalent Plan from local fixtures and grepped for three edges, so a
    # hand-edited README block passed as long as it contained them — and it was hand-edited: the
    # committed block used node ids `s0`/`s1`, which this renderer has never emitted.
    assert render_mermaid(plan) in readme, (
        "the README's mermaid block is not what render_mermaid(plan) returns — regenerate it "
        "rather than editing it, since a hand-drawn diagram stops being true silently")

    # And the claim that matters: one Plan, two strategies, without touching the Plan.
    assert fast is not precise
    assert set(fast) == set(precise), "both arms must implement the same Steps"


def test_the_readme_does_not_claim_unbuilt_integrations() -> None:
    """`voice.md`: copy may only claim what the artifact delivers EVERY time.

    Execution adapters and agent hooks are non-goals for now, so the Status section has to say so
    rather than letting the 'why this exists' narrative imply they exist.
    """
    import pathlib

    readme = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert "Not built:" in readme
    for unbuilt in ("Temporal", "persistence", "agent-hook"):
        assert unbuilt in readme.split("Not built:")[1][:400], (
            f"{unbuilt} is not implemented; Status must say so")


# --- MultiStep: a Plan that is also a PlanStep -------------------------------------------------------

def test_a_multistep_can_actually_be_a_step() -> None:
    """It could not until 2026-08-20 — the one thing the class exists for.

    It subclassed Plan alone, so `Plan.__post_init__`'s isinstance(s, PlanStep) check rejected it. The
    ontology citation said rdfs:subClassOf BOTH; the code implemented one. Nothing caught it
    because nothing had ever nested a Plan.
    """
    from workflow_plan.plan.plan import MultiStep

    a, b, c = Variable("a", str), Variable("b", str), Variable("c", str)

    class In1(PlanStep):
        inputs, outputs = (a,), (b,)

    class In2(PlanStep):
        inputs, outputs = (b,), (c,)

    class After(PlanStep):
        inputs, outputs = (c,), (Variable("d", str),)

    nested = MultiStep(name="inner", steps=(In1(), In2()))
    assert isinstance(nested, PlanStep)

    outer = Plan(name="outer", steps=(nested, After()))
    assert len(outer.steps) == 2

    # Ports are DERIVED from the inner Plan, never declared twice.
    assert [v.name for v in nested.inputs] == ["a"]
    assert [v.name for v in nested.outputs] == ["c"]


def test_a_multistep_knows_whether_its_inner_plan_iterates() -> None:
    """`until` names the Variable that ends the loop. Read the cycle, do not declare it."""
    from workflow_plan.plan.plan import MultiStep

    draft, critique = Variable("draft", str), Variable("critique", str)

    class Write(PlanStep):
        inputs, outputs = (critique,), (draft,)

    class Review(PlanStep):
        inputs, outputs = (draft,), (critique,)

    loop = MultiStep(name="revise", steps=(Write(), Review()), until=critique)
    assert loop.iterative is True
    assert loop.until is critique
    assert "until='critique'" in repr(loop)

    straight = MultiStep(name="chain", steps=(Write(),))
    assert straight.iterative is False


def test_the_readme_does_not_promise_rdf_it_does_not_have() -> None:
    """The grounding is a CHECKED VOCABULARY, not a serialization format.

    The README says a Plan is legible to anything else that speaks P-Plan, and immediately says
    there is no import or export. That second sentence is the one that stops the first from being
    an overclaim, so both halves are asserted here: the disclaimer must be present, and no RDF
    machinery may quietly appear that would make it stale in the other direction.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    assert "no RDF import or export" in readme

    sources = " ".join(f.read_text() for f in (root / "workflow_plan").rglob("*.py"))
    for term in ("rdflib", "to_turtle", "to_jsonld"):
        assert term not in sources, (
            f"{term} exists now — the README's 'a door, not a feature' paragraph is stale and "
            f"understates what ships")


# --- Activity.duration_secs: a measurement, not a derived value ----------------------------------

def test_a_negative_duration_is_refused_not_clamped() -> None:
    """A monotonic clock does not run backwards, so a negative duration proves the value was
    derived from wall-clock timestamps across a correction. Clamping it downstream is how a
    40-second step reports as instant."""
    from datetime import datetime

    from workflow_plan.ontology import Activity
    from workflow_plan.ontology.prov import GraphError

    t = datetime(2026, 8, 22, 12, 0, 0)
    with pytest.raises(GraphError, match="does not run backwards"):
        Activity(id="a", step_name="S", started_at=t, ended_at=t, duration_secs=-0.5)


def test_zero_and_unmeasured_are_different_states() -> None:
    """0.0 is a real measurement of a sub-millisecond step. None is NOT MEASURED. A renderer that
    shows them the same puts back the failure the field exists to prevent."""
    from datetime import datetime

    from workflow_plan.ontology import Activity

    t = datetime(2026, 8, 22, 12, 0, 0)
    assert Activity(id="a", step_name="S", started_at=t, ended_at=t, duration_secs=0.0).duration_secs == 0.0
    assert Activity(id="b", step_name="S", started_at=t, ended_at=t).duration_secs is None


def test_a_duration_without_an_end_is_refused() -> None:
    """Otherwise 'still running' and 'finished, unmeasured' are the same state."""
    from datetime import datetime

    from workflow_plan.ontology import Activity
    from workflow_plan.ontology.prov import GraphError

    with pytest.raises(GraphError, match="has not ended"):
        Activity(id="a", step_name="S", started_at=datetime(2026, 8, 22), duration_secs=1.0)


def test_a_reconstructed_duration_is_reported() -> None:
    """The invariant Boris asked for: if duration_secs was computed as ended_at - started_at, say
    so. Two clocks started at different instants do not agree to full float precision."""
    from datetime import datetime, timedelta

    from workflow_plan.invariants import validate
    from workflow_plan.invariants.provenance import DURATION_ALL
    from workflow_plan.ontology import Activity

    t = datetime(2026, 8, 22, 12, 0, 0)
    derived = Activity(id="a", step_name="S", started_at=t, ended_at=t + timedelta(seconds=3),
                       duration_secs=3.0)
    assert "reconstructed" in str(validate([derived], DURATION_ALL)[0])

    measured = Activity(id="b", step_name="S", started_at=t, ended_at=t + timedelta(seconds=3),
                        duration_secs=3.0001227)
    assert validate([measured], DURATION_ALL) == []


def test_clock_divergence_is_reported_as_the_finding() -> None:
    """The other direction: the measurement is fine and the wall clock moved under it. Reported,
    not resolved — which clock to believe depends on deploy history this rule cannot see."""
    from datetime import datetime, timedelta

    from workflow_plan.invariants import validate
    from workflow_plan.invariants.provenance import DURATION_ALL
    from workflow_plan.ontology import Activity

    t = datetime(2026, 8, 22, 12, 0, 0)
    ntp_stepped = Activity(id="a", step_name="S", started_at=t, ended_at=t + timedelta(seconds=40),
                           duration_secs=2.5)
    assert "disagree" in str(validate([ntp_stepped], DURATION_ALL)[0])
