"""AIEvalTrial: what makes two numbers comparable, and what refuses arms that are not."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from plan_types.plan import Plan, Step, Variable
from conceptlint.eval import (AIEvalTrial, EvalCase, Judge, Result, Rubric, TrialError,
                              comparable, digest)


@dataclass(frozen=True)
class Paste:
    text: str = ""


@dataclass(frozen=True)
class Graph:
    n: int = 0


@dataclass(frozen=True)
class Other:
    n: int = 0


def _plan(name: str, out=Graph) -> Plan:
    step = type(f"S{name}", (Step,), {
        "inputs": (Variable("paste", Paste),), "outputs": (Variable("out", out),),
        "run": lambda self, v: out(),
    })
    return Plan(name=name, steps=(step(),))


CORPUS = (EvalCase(id="c1", inputs="45F PCOS on metformin"),
          EvalCase(id="c2", inputs="62M LDL 190 on atorvastatin"))
JUDGE = Judge(model="gpt-4.1")
RUBRIC = Rubric(version="r1", criteria="does the map name what nobody measured")


def _trial(**kw) -> AIEvalTrial:
    return AIEvalTrial(name="t", arms=(_plan("a"), _plan("b")), corpus=CORPUS,
                       judge=JUDGE, rubric=RUBRIC, **kw)


def test_arms_must_share_one_shape() -> None:
    """Membership is a type check. An arm producing something else is not losing — it is in a
    different trial."""
    with pytest.raises(TrialError, match="must share one shape"):
        AIEvalTrial(name="t", arms=(_plan("a"), _plan("b", out=Other)), corpus=CORPUS,
                    judge=JUDGE, rubric=RUBRIC)


def test_a_trial_with_no_corpus_is_refused() -> None:
    with pytest.raises(TrialError, match="no corpus"):
        AIEvalTrial(name="t", arms=(_plan("a"),), corpus=(), judge=JUDGE, rubric=RUBRIC)


def test_two_arms_cannot_share_a_name() -> None:
    with pytest.raises(TrialError, match="two arms with one name"):
        AIEvalTrial(name="t", arms=(_plan("a"), _plan("a")), corpus=CORPUS,
                    judge=JUDGE, rubric=RUBRIC)


def test_a_control_must_be_an_arm() -> None:
    with pytest.raises(TrialError, match="not an arm"):
        _trial(control="ghost")


# ── the digest is computed, which is the whole point ──────────────────────────────────────────────

def test_the_digest_changes_when_the_corpus_does() -> None:
    """Hand-typed digests are how numbers from two datasets end up in one table looking comparable."""
    assert digest(CORPUS) != digest(CORPUS + (EvalCase(id="c3", inputs="34F hypothyroid"),))


def test_the_digest_ignores_case_order() -> None:
    assert digest(CORPUS) == digest(tuple(reversed(CORPUS)))


# ── comparability ─────────────────────────────────────────────────────────────────────────────────

def test_record_stamps_provenance_the_caller_cannot_forget() -> None:
    t = _trial()
    r = t.record(arm="a", case_id="c1", metric="cited_rate", value=0.61)
    assert (r.corpus_digest, r.judge, r.rubric) == (t.corpus_digest, "gpt-4.1", "r1")


def test_results_from_one_trial_are_comparable() -> None:
    t = _trial()
    assert comparable(t.record("a", "c1", "cited_rate", 0.61),
                      t.record("b", "c1", "cited_rate", 0.13))


def test_a_different_corpus_makes_them_incomparable() -> None:
    """Two numbers from different datasets are not a comparison — they are a table that looks
    like one."""
    a = _trial().record("a", "c1", "cited_rate", 0.61)
    b = AIEvalTrial(name="t2", arms=(_plan("a"),),
                    corpus=CORPUS + (EvalCase(id="c3", inputs="more"),),
                    judge=JUDGE, rubric=RUBRIC).record("a", "c1", "cited_rate", 0.61)
    assert not comparable(a, b)


def test_a_different_rubric_version_makes_them_incomparable() -> None:
    a = _trial().record("a", "c1", "cited_rate", 0.61)
    b = AIEvalTrial(name="t", arms=(_plan("a"),), corpus=CORPUS, judge=JUDGE,
                    rubric=Rubric(version="r2", criteria="reworded")).record(
                        "a", "c1", "cited_rate", 0.61)
    assert not comparable(a, b)


def test_recording_for_an_arm_that_is_not_in_the_trial_is_refused() -> None:
    with pytest.raises(TrialError, match="is not an arm"):
        _trial().record("ghost", "c1", "m", 1.0)


def test_expected_none_means_judged_not_unlabelled() -> None:
    """A legitimate state, and it must not read as 'expected nothing'."""
    assert EvalCase(id="c", inputs="x").expected is None
