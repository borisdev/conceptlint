"""`Plan` — a declared composition of Steps, validated before anything runs.

A Plan is plan-time and nothing else. It holds Steps, not Activities; Variables, not Entities. The
rule that keeps that true is in `invariants.py` and it is executable, because a distinction defended
only by a docstring is one this project has already watched drift twice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from conceptlint.dataflow.step import Step
from conceptlint.dataflow.variable import Variable


class PlanError(ValueError):
    """A Plan that cannot be built. Raised at declaration, never at run time."""


@dataclass(frozen=True)
class Plan:
    """An ordered composition of Steps whose types line up.

    Ordered, not a general DAG. §30 — seed it correctly rather than finish it. Fan-out and joins
    are real and will arrive with the first Plan that needs them; adding them now would be
    machinery with no use case, which is what §29 forbids.
    """

    name: str
    steps: tuple[Step[Any, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise PlanError("a Plan needs a name")
        if not self.steps:
            raise PlanError(f"Plan {self.name!r} has no steps")

        for s in self.steps:
            if isinstance(s, type):
                raise PlanError(
                    f"Plan {self.name!r} holds the CLASS {s.__name__}, not an instance. "
                    f"Declare `{s.__name__}()`.")
            if not isinstance(s, Step):
                raise PlanError(
                    f"Plan {self.name!r} holds {type(s).__name__}, which is not a Step. "
                    f"A Plan is plan-time: an Activity or any runtime object does not belong in it.")

        for upstream, downstream in zip(self.steps, self.steps[1:]):
            if not downstream.consumes.accepts(upstream.produces):
                raise PlanError(
                    f"Plan {self.name!r}: {type(upstream).__name__} produces "
                    f"{upstream.produces!r} but {type(downstream).__name__} consumes "
                    f"{downstream.consumes!r} — the types do not line up.")

    @property
    def consumes(self) -> Variable[Any]:
        return self.steps[0].consumes

    @property
    def produces(self) -> Variable[Any]:
        return self.steps[-1].produces

    def shape(self) -> tuple[type, type]:
        """The Plan's own contract. Two Plans with equal shapes are substitutable.

        This is the line that makes competing builders comparable: an eval trial holds Plans and
        refuses one whose shape differs, rather than finding out from the output.
        """
        return self.consumes.type, self.produces.type

    def run(self, value: Any) -> Any:
        """Execute in order. The simplest possible executor, and deliberately not a framework.

        No retry, durability, checkpointing, parallelism or interrupts — §11. An execution backend
        decides HOW computation runs; this package only says WHAT computation exists. When one of
        those is genuinely needed, it arrives as an adapter that wraps Steps from outside.
        """
        for s in self.steps:
            value = s.run(value)
        return value

    def __repr__(self) -> str:
        arrow = " -> ".join(type(s).__name__ for s in self.steps)
        return f"Plan({self.name!r}: {arrow})"


def substitutable(a: Plan, b: Plan) -> bool:
    """Do these two Plans have the same contract?

    The check an eval trial needs before putting two builders' numbers beside each other.
    """
    return a.shape() == b.shape()


def check_arms(arms: Sequence[Plan]) -> None:
    """Refuse a set of arms that do not share one shape.

    Not a trial type — that waits for a second real builder. This is the one line of it that is
    already needed, and it is what makes "interchangeable" enforced rather than asserted.
    """
    shapes = {a.shape() for a in arms}
    if len(shapes) > 1:
        raise PlanError(f"arms must share one shape; got {sorted(map(str, shapes))}")
