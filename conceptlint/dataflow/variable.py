"""`Variable[T]` — a typed plan-time placeholder.

The piece the previous dataflow attempt did not have. There, a Step declared `consumes: tuple[str,
...]` — artifact kinds as STRINGS — so a typo rewired the graph silently: it still built, nothing
type-checked, and the mistake surfaced much later as a shape error somewhere else.

A Variable carries the actual Python type, so wiring is checked by comparing types rather than
comparing spelling.

⚠️ A Variable is NOT a value. It is the KIND of value that will flow. `Variable[Findings]` says
"findings go here"; the findings from pmid:123 are an `Entity`, and live only in an execution graph.
Collapsing the two is the failure `evals/minimal/variable_entity_collapse` exists to catch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, get_args, get_origin

T = TypeVar("T")


@dataclass(frozen=True)
class Variable(Generic[T]):
    """A named, typed slot in a Plan."""

    name: str
    type: type[T]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a Variable needs a name — it is how a Step refers to it")
        if not isinstance(self.type, type) and get_origin(self.type) is None:
            raise TypeError(
                f"Variable {self.name!r} needs a TYPE, got {self.type!r}. A string here is the "
                f"string-keyed wiring this class exists to replace.")

    def accepts(self, other: Variable[Any]) -> bool:
        """May a value of `other` flow into this slot?

        Deliberately conservative: identical type, or `other.type` is a subclass. No structural
        matching, no coercion. §30 — do not add machinery without a use case that needs it, and a
        permissive rule here would let the first real mismatch through, which is the one case this
        check exists for.
        """
        mine, theirs = self.type, other.type
        if mine is theirs:
            return True
        if get_origin(mine) is not None or get_origin(theirs) is not None:
            return get_origin(mine) is get_origin(theirs) and get_args(mine) == get_args(theirs)
        try:
            return issubclass(theirs, mine)
        except TypeError:
            return False

    def __repr__(self) -> str:
        name = getattr(self.type, "__name__", repr(self.type))
        return f"Variable({self.name!r}: {name})"
