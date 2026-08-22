"""`Invariant` — a rule that can fail, and say why.

    DeclaredTerm  ->  generalized by  ->  Invariant

`DeclaredTerm` is a *type* you inherit from to declare a term. Requiring it of a whole codebase
before anything can be checked is a tax nobody pays, so it is not required of one: the more general
abstraction is not a type at all — **an invariant is a rule/check**, and a name collision between
two declared terms is one thing a rule can check.

⚠️ It was described here as *retired and replaced* until 2026-08-22, and that was never quite true
— `conceptlint.core.lint` had four rules reading it the whole time. It is now the shared base of
`Plan`, `PlanStep`, `Variable` and `PlanDependency`, which is the case where the tax is zero because
nobody outside this package writes those types. Optional for a user, load-bearing for us.

## Four categories, not one vague subsystem

    naming/       one name → many concepts, or many names → one concept
    typing/       a binding whose types do not line up
    topology/     a cycle, an unbound input, an orphan Variable
    provenance/   an ONTOLOGY_IRI that names a term nobody vendored

New categories should emerge from a real failure, not from symmetry.

## What a rule carries, and why each field is required

    id          stable, so a violation can be suppressed, tracked or resolved by identity rather
                than by matching its message text
    statement   what must be true, in one sentence — the thing a human agrees or disagrees with
    check       executable. A rule with no check is a preference; say so in prose instead.

⚠️ `check` RAISES rather than returning a bool. A boolean loses the detail — which PlanStep, which
Variable, which two names — and that detail is the entire value of the violation. `Violation` carries
the invariant's id so the message and the identity never drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Generic, Iterable, TypeVar

T = TypeVar("T")


class InvariantCategory(StrEnum):
    """What KIND of failure a rule detects. Metadata for reporting, not a type hierarchy."""

    NAMING = "naming"
    TYPING = "typing"
    TOPOLOGY = "topology"
    PROVENANCE = "provenance"


class Violation(Exception):
    """A rule found what it was looking for.

    Carries the invariant id so a caller can group, suppress or resolve by identity. A message
    alone would mean matching on prose, which changes every time someone improves the wording.
    """

    def __init__(self, invariant_id: str, message: str) -> None:
        super().__init__(f"{invariant_id}: {message}")
        self.invariant_id = invariant_id
        self.message = message


@dataclass(frozen=True)
class Invariant(Generic[T]):
    """One rule about a subject of type `T`.

    Frozen and generic: `Invariant[Plan]` and `Invariant[Sequence[ModelRecord]]`
    are the same abstraction over different subjects, which is what stops naming rules and topology
    rules needing separate machinery.
    """

    id: str
    statement: str
    check: Callable[[T], None]
    category: InvariantCategory = InvariantCategory.TOPOLOGY

    #: The failure this prevents — ideally an incident, not a restatement of `statement`.
    #: A rule whose reason is lost gets deleted the first time it is inconvenient.
    why: str = ""

    def __post_init__(self) -> None:
        for name in ("id", "statement"):
            if not getattr(self, name):
                raise ValueError(f"Invariant needs a non-empty {name}")
        if not callable(self.check):
            raise TypeError(
                f"{self.id}: `check` must be callable. A rule that cannot run is a preference, and "
                f"belongs in a docstring rather than a registry.")

    def violated(self, message: str) -> Violation:
        """Build the exception, so a check never has to repeat its own id."""
        return Violation(self.id, message)

    def holds(self, subject: T) -> bool:
        """Convenience for tests. Production callers want the Violation and its detail."""
        try:
            self.check(subject)
        except Violation:
            return False
        return True


def check(subject: T, invariants: Iterable[Invariant[T]]) -> list[Violation]:
    """Run every invariant and COLLECT the failures rather than stopping at the first.

    ⚠️ Deliberately not fail-fast. One cycle can cause three violations, and seeing all three is how
    a reader tells a single root cause from three separate problems. Stopping at the first turns
    every validation into a guessing game about what else is wrong.

    Returns a list so an empty result is the pass. There is no success object and no success
    message — a tool that congratulates you on every clean run teaches you to stop reading it.
    """
    found: list[Violation] = []
    for inv in invariants:
        try:
            inv.check(subject)
        except Violation as v:
            found.append(v)
        except Exception as exc:  # noqa: BLE001
            # ⚠️ A check that COULD NOT RUN is reported, not swallowed. Silently skipping it makes
            # "we did not look" indistinguishable from "we looked and it was fine" — the exact
            # inversion this package exists to prevent, one level up.
            found.append(Violation(inv.id, f"NOT CHECKED — {exc}"))
    return found
