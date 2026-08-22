"""`AIEvalTrial` — competing Plans, one corpus, one judge, and numbers that may be compared.

Ported from `nobs.case_ir.trial` and rewritten onto conceptlint's types: `Workflow` -> `Plan`,
`Grounded`/`Vocab` -> `DeclaredTerm`/`ALSO_KNOWN_AS`. The domain half (a medical gold corpus, a PICO
measurement) stayed behind — this package must not learn a domain.

## The shape

    AIEvalTrial   arms[Plan] + corpus[EvalCase] + judge + rubric   ← everything SHARED
    EvalCase      id + inputs + expected                            ← the only thing that varies
    Result        one number, plus the provenance that makes it comparable

Everything an arm needs to be comparable is on the trial, not repeated per case. That is what makes
`len(arms) x len(corpus)` results stackable.

## What is deliberately absent

`Conduct` and `Capability` — the two Invariant flavours in the original — are not here.
`Conduct.__subclasses__()` and `Capability.__subclasses__()` were both EMPTY in the source repo:
declared, tested against toy classes in their own test file, and never used. §30 asks what concrete
blocker requires a thing. Nothing did.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, ClassVar

from workflow_plan.naming.declared_term import DeclaredTerm
from workflow_plan.plan.plan import Plan


class TrialError(Exception):
    """A trial that cannot be declared. Raised at declaration, never mid-run."""


# ── the data ──────────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EvalCase:
    """One row. The input value, and what a correct answer would be — if anyone knows.

    `expected is None` is a legitimate state and means JUDGED, not unlabelled-by-oversight: some
    tasks have no gold answer and a rubric decides. It must never be read as "expected nothing".
    """

    id: str
    inputs: str
    expected: Any | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.inputs:
            raise TrialError("an EvalCase needs an id and inputs")


def digest(corpus: tuple[EvalCase, ...]) -> str:
    """A content hash of the corpus.

    ⚠️ COMPUTED, never typed by hand. In the source repo the corpus digest was hand-written, so a
    corpus that quietly changed still reported the old digest — and numbers from two different
    datasets sat in one table looking comparable. This is the whole reason `EvalCase` is a type
    rather than a loose string.
    """
    h = hashlib.sha256()
    for c in sorted(corpus, key=lambda c: c.id):
        h.update(c.id.encode())
        h.update(c.inputs.encode())
        h.update(repr(c.expected).encode())
    return h.hexdigest()[:16]


# ── how a number was produced ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Judge:
    """What scores an arm's output.

    ⚠️ Must not be the system under test. A judge sharing the subject's blind spots agrees with it,
    and the agreement is invisible because both halves are wrong the same way. `temperature=0` so a
    verdict is reproducible: a sampled judge scores the same run differently tomorrow, which quietly
    makes every stored number incomparable with every future one.
    """

    model: str
    temperature: float = 0.0


@dataclass(frozen=True)
class Rubric:
    """The criteria, versioned. Text a human can disagree with.

    Criteria buried in a regex or a prompt cannot be reviewed, so a wrong verdict is
    indistinguishable from a wrong pattern.
    """

    version: str
    criteria: str


@dataclass(frozen=True)
class Result:
    """One number, and everything needed to know what it may be compared with."""

    arm: str
    case_id: str
    metric: str
    value: float
    corpus_digest: str
    judge: str
    rubric: str


def comparable(a: Result, b: Result) -> bool:
    """May these two numbers be put beside each other?

    The most useful function in the module. Two values from different corpora, judges or rubric
    versions are not a comparison — they are a table that looks like one.
    """
    return ((a.metric, a.corpus_digest, a.judge, a.rubric)
            == (b.metric, b.corpus_digest, b.judge, b.rubric))


def _render_shape(shape: tuple[tuple[type, ...], tuple[type, ...]]) -> str:
    """`(str, int) -> (dict,)` — readable in an error a human has to act on."""
    ins, outs = shape
    fmt = lambda ts: "(" + ", ".join(getattr(t, "__name__", str(t)) for t in ts) + ")"  # noqa: E731
    return f"{fmt(ins)} -> {fmt(outs)}"


# ── the trial ─────────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AIEvalTrial(DeclaredTerm):
    """One task, its competing arms, the corpus they are read against, and the rules — fixed first.

    Named `AIEvalTrial` rather than `Trial` or `AITrial`: `Trial` reads as a clinical trial, and
    `AITrial` still does not say what it is FOR. This one only evaluates.
    """

    ID: ClassVar[str] = "ai_eval_trial"
    DEFINITION: ClassVar[str] = (
        "A comparison of Plans that share one contract, read against one corpus with one judge."
    )
    RATIONALE: ClassVar[str] = (
        "Two builders' numbers were being compared without recording the corpus, the judge or the "
        "rubric version, so nobody could tell which past numbers were legally comparable."
    )
    #: `Trial` reads as a clinical trial; `AITrial` still does not say what it is FOR.
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("Trial", "AITrial", "Experiment", "Benchmark")

    name: str
    arms: tuple[Plan, ...]
    corpus: tuple[EvalCase, ...]
    judge: Judge
    rubric: Rubric
    control: str = ""                    # the arm name the others are read against, if any
    results: tuple[Result, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if len(self.arms) < 1:
            raise TrialError(f"trial {self.name!r} has no arms")
        if not self.corpus:
            raise TrialError(f"trial {self.name!r} has no corpus — there is nothing to read arms against")

        # ⚠️ Membership is a TYPE CHECK, not a judgement. Arms are comparable only if they end at
        # the same place; an arm producing something else is not losing, it is in a different trial.
        shapes = {a.shape() for a in self.arms}
        if len(shapes) > 1:
            raise TrialError(
                f"trial {self.name!r}: arms must share one shape, got "
                # A shape is now (input types, output types) — TUPLES, since P-Plan puts no
                # cardinality on hasInputVar/hasOutputVar. `.__name__` on the old scalar form
                # raised AttributeError here the moment the DAG correction landed.
                f"{sorted(_render_shape(s) for s in shapes)}")

        names = [a.name for a in self.arms]
        if len(set(names)) != len(names):
            raise TrialError(f"trial {self.name!r} has two arms with one name: {sorted(names)}")
        if self.control and self.control not in names:
            raise TrialError(f"trial {self.name!r} names control {self.control!r}, which is not an arm")

    @property
    def corpus_digest(self) -> str:
        return digest(self.corpus)

    def shape(self) -> tuple[type, type]:
        """The contract every arm shares."""
        return self.arms[0].shape()

    def record(self, arm: str, case_id: str, metric: str, value: float) -> Result:
        """Build a Result already stamped with this trial's provenance.

        The stamping is the point: a caller cannot produce a number here and forget which corpus,
        judge or rubric it came from, because it never gets to supply them.
        """
        if arm not in {a.name for a in self.arms}:
            raise TrialError(f"{arm!r} is not an arm of trial {self.name!r}")
        return Result(arm=arm, case_id=case_id, metric=metric, value=value,
                      corpus_digest=self.corpus_digest,
                      judge=self.judge.model, rubric=self.rubric.version)
