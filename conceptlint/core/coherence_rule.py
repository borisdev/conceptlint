"""`CoherenceRule` — a rule that keeps the vocabulary coherent, and `CoherenceIssue` — what it reports.

## What "coherent" means here, exactly

    One term    -> One meaning     a term must not quietly acquire a second meaning
    One meaning -> One term        a meaning must not quietly acquire a second name

That bijection IS the definition, it is `DeclaredTerm`'s own docstring, and every rule below states
which half it serves in `LAW`. This is the difference between this and the `CoherenceInvariant` that
issue #6 refuses: coherence OF A PLAN has no definition anyone could write, so naming a type after it
would be the overclaim this package exists to report. Coherence of a VOCABULARY is two laws and four
executable rules.

⚠️ These names were `ConceptRule`/`ConceptIssue` for one commit, and before that `Invariant`. Both
were wrong in the same direction: `Concept` is retired — it is `DeclaredTerm` — and naming the rules
after a dead type is exactly the objection issue #6 raises against the old `conceptlint` CLI. The
rules do not check concepts. They check whether the words in a conversation and the words in the
code still mean one thing each.

A rule that cannot execute is a preference. This module exists so the difference is structural
rather than a matter of intent: a `CoherenceRule` without a working `check()` fails registration, so
"we decided X" and "X is enforced" cannot be confused.

⚠️ `check()` returns issues; it does not raise and it does not print. A rule that decides how to
report is a rule you cannot compose, batch, or count.
"""
from __future__ import annotations

from typing import ClassVar, Iterable, Sequence

from workflow_plan.naming.declared_term import DeclaredTerm


class CoherenceIssue:
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
        return f"CoherenceIssue({self.rule!r}, {self.message!r})"

    def render(self) -> str:
        """A traceback, not a paragraph."""
        lines = [f"{self.rule}: {self.message}"]
        if self.concepts:
            lines += [f"  concepts : {', '.join(self.concepts)}"]
        if self.suggestion:
            lines += [f"  need     : {self.suggestion}"]
        return "\n".join(lines)


class CoherenceRule:
    """One rule over the declared vocabulary.

    Subclassing registers it, same as `DeclaredTerm`. `LAW` says which of the two laws it serves, so
    a reader can tell whether a rule is load-bearing or a convenience someone added — and so the set
    of rules can be checked against the definition rather than against taste.
    """

    ID: ClassVar[str] = ""
    LAW: ClassVar[str] = ""      # "one-concept-one-meaning" | "one-meaning-one-concept"
    WHY: ClassVar[str] = ""      # the failure it prevents, not a restatement of the rule

    def check(self, concepts: Sequence[type[DeclaredTerm]]) -> Iterable[CoherenceIssue]:
        raise NotImplementedError


def validate(cls: type[CoherenceRule]) -> None:
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
    if cls.check is CoherenceRule.check:
        raise TypeError(f"{cls.__name__} does not implement check(). A rule that cannot run "
                        f"reports nothing and is indistinguishable from a rule that passed.")


def registered() -> list[CoherenceRule]:
    """Every CoherenceRule subclass, instantiated, in a stable order.

    ⚠️ Refuses one that does not declare `ID`, `LAW`, `WHY`, or does not override `check`. A rule
    with no `check` would register, run, find nothing, and read exactly like a rule that passed —
    which is the failure mode this module was written to make impossible.
    """
    out: list[CoherenceRule] = []
    stack = [CoherenceRule]
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if cls is CoherenceRule:
            continue
        validate(cls)
        out.append(cls())
    return sorted(out, key=lambda i: i.ID)
