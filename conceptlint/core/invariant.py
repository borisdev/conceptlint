"""`Invariant` — a semantic rule that RUNS, and `ConceptIssue` — what it reports.

A rule that cannot execute is a preference. This module exists so the difference is structural
rather than a matter of intent: an `Invariant` without a working `check()` fails registration, so
"we decided X" and "X is enforced" cannot be confused.

⚠️ `check()` returns issues; it does not raise and it does not print. A rule that decides how to
report is a rule you cannot compose, batch, or count.
"""
from __future__ import annotations

from typing import ClassVar, Iterable, Sequence

from workflow_plan.naming.declared_term import DeclaredTerm


class ConceptIssue:
    """One finding. Its existence IS the problem — there is no passing issue.

    Silence is the pass. A linter that reports what it checked and found fine trains the reader to
    skim, and then the one line that matters arrives in the same voice as forty that do not.
    """

    __slots__ = ("rule", "message", "concepts", "suggestion")

    def __init__(self, rule: str, message: str,
                 concepts: Sequence[str] = (), suggestion: str = "") -> None:
        self.rule = rule
        self.message = message
        self.concepts = tuple(concepts)
        self.suggestion = suggestion

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ConceptIssue({self.rule!r}, {self.message!r})"

    def render(self) -> str:
        """A traceback, not a paragraph."""
        lines = [f"{self.rule}: {self.message}"]
        if self.concepts:
            lines += [f"  concepts : {', '.join(self.concepts)}"]
        if self.suggestion:
            lines += [f"  need     : {self.suggestion}"]
        return "\n".join(lines)


class Invariant:
    """A semantic rule over the declared concepts.

    Subclassing registers it, same as `DeclaredTerm`. `LAW` says which of the two laws it serves, so a
    reader can tell whether a rule is load-bearing or a convenience someone added.
    """

    ID: ClassVar[str] = ""
    LAW: ClassVar[str] = ""      # "one-concept-one-meaning" | "one-meaning-one-concept"
    WHY: ClassVar[str] = ""      # the failure it prevents, not a restatement of the rule

    def check(self, concepts: Sequence[type[DeclaredTerm]]) -> Iterable[ConceptIssue]:
        raise NotImplementedError


def validate(cls: type[Invariant]) -> None:
    """Refuse a rule that cannot report. Split out so a test can check ONE class.

    ⚠️ It was inline in `registered()`, and two tests each leaked a bad subclass into the global
    registry — so whichever ran first decided which error the other saw. Order-dependent, and it
    only surfaced once the suite grew. A check that passes or fails on test order is the flakiness
    that gets a suite muted.
    """
    missing = [f for f in ("ID", "LAW", "WHY") if not getattr(cls, f, "")]
    if missing:
        raise TypeError(f"{cls.__name__} is missing {', '.join(missing)}. "
                        f"A rule with no stated law and no stated failure is a preference.")
    if cls.check is Invariant.check:
        raise TypeError(f"{cls.__name__} does not implement check(). A rule that cannot run "
                        f"reports nothing and is indistinguishable from a rule that passed.")


def registered() -> list[Invariant]:
    """Every Invariant subclass, instantiated, in a stable order.

    ⚠️ Refuses one that does not declare `ID`, `LAW`, `WHY`, or does not override `check`. A rule
    with no `check` would register, run, find nothing, and read exactly like a rule that passed —
    which is the failure mode this module was written to make impossible.
    """
    out: list[Invariant] = []
    stack = [Invariant]
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if cls is Invariant:
            continue
        validate(cls)
        out.append(cls())
    return sorted(out, key=lambda i: i.ID)
