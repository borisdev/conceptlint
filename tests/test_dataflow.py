"""The typed dataflow contracts, and the plan-time/runtime line they hold.

The interesting tests are the refusals. A Plan that accepts a runtime object, or wires mismatched
types, fails later and somewhere else — which is precisely the debugging session this package exists
to prevent.
"""
from __future__ import annotations

import pathlib
import textwrap
from dataclasses import dataclass

import pytest

from conceptlint.dataflow import Plan, PlanError, Step, Variable, check_arms, substitutable
from conceptlint.dataflow.invariants import NoExecutionFields, NoPrivateSynonym, PlanTimeOnly
from conceptlint.ontologies.pplan.concepts import Activity, Entity, Step as StepConcept


@dataclass(frozen=True)
class Study:
    pmid: str


@dataclass(frozen=True)
class Findings:
    n: int = 0


@dataclass(frozen=True)
class Graph:
    n: int = 0


class Parse(Step[Study, Findings]):
    inputs = (Variable("study", Study),)
    outputs = (Variable("findings", Findings),)

    def run(self, study: Study) -> Findings:      # keyword names ARE the Variable names
        return Findings(n=1)


class Build(Step[Findings, Graph]):
    inputs = (Variable("findings", Findings),)
    outputs = (Variable("graph", Graph),)

    def run(self, findings: Findings) -> Graph:
        return Graph(n=findings.n)


# ── Variable ──────────────────────────────────────────────────────────────────────────────────────

def test_a_variable_needs_a_type_not_a_string() -> None:
    """A string here is the string-keyed wiring this class replaces."""
    with pytest.raises(TypeError, match="needs a TYPE"):
        Variable("findings", "Findings")            # type: ignore[arg-type]


def test_a_variable_accepts_its_own_type_and_subclasses() -> None:
    @dataclass(frozen=True)
    class Detailed(Findings):
        pass

    assert Variable("a", Findings).accepts(Variable("b", Detailed))
    assert not Variable("a", Findings).accepts(Variable("b", Graph))


# ── Step ──────────────────────────────────────────────────────────────────────────────────────────

def test_shape_is_the_contract() -> None:
    assert Parse.shape() == ((Study,), (Findings,))


def test_a_half_declared_step_is_refused() -> None:
    """It would otherwise surface as an AttributeError deep inside Plan validation."""
    # Rewritten 2026-08-16. "Half declared" was meaningful when a Step had exactly one input and
    # one output; with 0..N per P-Plan, an empty side is legal (a source or a sink). The mistake
    # worth catching now is passing a bare Variable where a tuple belongs — the singular form this
    # package was rewritten to remove, which would otherwise iterate as characters or explode later.
    with pytest.raises(TypeError, match="must be a tuple"):
        type("Halfway", (Step,), {"inputs": Variable("x", Study), "outputs": ()})


def test_an_abstract_step_declaring_neither_side_is_fine() -> None:
    type("AbstractBase", (Step,), {})               # must not raise


# ── Plan ──────────────────────────────────────────────────────────────────────────────────────────

def test_a_plan_validates_at_declaration() -> None:
    p = Plan(name="ok", steps=(Parse(), Build()))
    assert p.shape() == ((Study,), (Graph,))
    # Keyword arguments, by Variable name. A Step with three inputs called positionally
    # is one reorder away from a silent mis-wire that the type check cannot see.
    assert p.run(study=Study("pmid:1")) == {"graph": Graph(n=1)}


def test_declaring_steps_out_of_order_is_FINE_now() -> None:
    """This used to raise. It should not.

    Under the old chain model `Plan(steps=(Build(), Parse()))` was "the types do not line up",
    because step N's single output had to feed step N+1's single input. In a P-Plan graph the
    wiring is the shared Variable, so declaration order carries no meaning and the execution order
    is derived. Keeping the old assertion would have preserved the bug as a test.
    """
    plan = Plan(name="backwards", steps=(Build(), Parse()))
    assert [type(s).__name__ for s in plan.order()] == ["Parse", "Build"]


def test_the_same_name_with_a_different_type_is_refused_before_anything_runs() -> None:
    """What "mismatched" means once order stops meaning anything: a name collision that lies."""
    class MakesFindingsAsAStr(Step):
        inputs, outputs = (Variable("study", Study),), (Variable("findings", str),)

    with pytest.raises(PlanError, match="same name, different type"):
        Plan(name="bad", steps=(MakesFindingsAsAStr(), Build()))


def test_a_runtime_object_in_a_plan_is_refused() -> None:
    """§10 and §19: `plan.steps.append(activity_execution)` is the named failure."""
    class FakeActivity:
        started_at = "10:04"

    with pytest.raises(PlanError, match="not a Step"):
        Plan(name="leaky", steps=(Parse(), FakeActivity()))     # type: ignore[arg-type]


def test_passing_the_class_instead_of_an_instance_says_so() -> None:
    with pytest.raises(PlanError, match="holds the CLASS"):
        Plan(name="oops", steps=(Parse,))            # type: ignore[arg-type]


def test_an_empty_plan_is_refused() -> None:
    with pytest.raises(PlanError, match="no steps"):
        Plan(name="empty", steps=())


# ── substitutability: what makes arms comparable ──────────────────────────────────────────────────

def test_two_plans_with_one_shape_are_substitutable() -> None:
    class Direct(Step[Study, Graph]):
        inputs = (Variable("study", Study),)
        outputs = (Variable("graph", Graph),)

        def run(self, value: Study) -> Graph:
            return Graph(n=99)

    two_step = Plan(name="two", steps=(Parse(), Build()))
    one_step = Plan(name="one", steps=(Direct(),))
    assert substitutable(two_step, one_step)
    check_arms([two_step, one_step])                 # must not raise


def test_arms_with_different_shapes_are_refused() -> None:
    """The line that makes 'interchangeable' enforced rather than asserted."""
    with pytest.raises(PlanError, match="must share one shape"):
        check_arms([Plan(name="a", steps=(Parse(), Build())), Plan(name="b", steps=(Parse(),))])


# ── the semantic invariants ───────────────────────────────────────────────────────────────────────

def _write(tmp: pathlib.Path, body: str) -> pathlib.Path:
    (tmp / "m.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp


def test_execution_fields_on_a_plan_time_type_are_caught(tmp_path: pathlib.Path) -> None:
    root = _write(tmp_path, '''
        class Variable:
            name: str
            started_at: datetime
            value: object
    ''')
    issues = list(NoExecutionFields([root]).check([]))
    assert issues and "started_at" in issues[0].message


def test_a_plan_time_type_without_them_is_silent(tmp_path: pathlib.Path) -> None:
    root = _write(tmp_path, '''
        class Variable:
            name: str
            type: type
    ''')
    assert list(NoExecutionFields([root]).check([])) == []


def test_a_private_synonym_is_caught(tmp_path: pathlib.Path) -> None:
    root = _write(tmp_path, "class DataFlowNode:\n    pass\n")
    issues = list(NoPrivateSynonym([root]).check([StepConcept]))
    assert issues and "Step" in issues[0].suggestion


def test_a_genuinely_new_name_is_allowed(tmp_path: pathlib.Path) -> None:
    """§19: ConceptLint MUST allow the vocabulary to evolve. False positives matter."""
    root = _write(tmp_path, "class RetryPolicy:\n    pass\n")
    assert list(NoPrivateSynonym([root]).check([StepConcept])) == []


def test_a_runtime_object_appended_to_a_plan_is_caught(tmp_path: pathlib.Path) -> None:
    root = _write(tmp_path, "plan.steps.append(Activity(started_at=now))\n")
    issues = list(PlanTimeOnly([root]).check([Activity, Entity]))
    assert issues and "Activity" in issues[0].message
