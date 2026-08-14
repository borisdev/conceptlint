"""`Step[InputT, OutputT]` — one declared unit of computation.

    Step: InputType -> OutputType

That signature IS the contract. Two Steps with the same input and output are substitutable, and
`Plan` can check it rather than a human hoping — which is the whole reason the previous builders,
declared as bare functions with divergent keyword arguments, only LOOKED interchangeable.

⚠️ A Step is plan-time. It has no id worth joining on, no timestamps, no outcome. Running one
produces an `Activity`, which has nothing else. `@activity.defn` on a Step subclass is the coupling
§13 names as an architectural failure: the execution framework wraps the Step, never the reverse.
"""
from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from conceptlint.dataflow.variable import Variable

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class Step(Generic[InputT, OutputT]):
    """Subclass it, declare `consumes` and `produces`, implement `run`.

    The two Variables are class-level because they are part of the DECLARATION — you must be able
    to read the shape of a pipeline without constructing anything, which is what lets a Plan be
    validated before a single Step has been implemented.
    """

    #: P-Plan grounding, read by ConceptLint. Not RDF infrastructure — an identifier and nothing more.
    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Step"

    consumes: ClassVar[Variable[Any]]
    produces: ClassVar[Variable[Any]]

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        # Abstract intermediates are legal and common; only a Step that declares one side without
        # the other is a mistake, and it is one that would otherwise surface as an AttributeError
        # deep inside Plan validation.
        has = [f for f in ("consumes", "produces") if f in cls.__dict__ or hasattr(cls, f)]
        if len(has) == 1:
            raise TypeError(
                f"{cls.__name__} declares {has[0]} but not the other. A half-declared Step cannot "
                f"be wired or substituted — declare both, or neither if it is an abstract base.")

    def run(self, value: InputT) -> OutputT:
        raise NotImplementedError

    @classmethod
    def shape(cls) -> tuple[type, type]:
        """`(input type, output type)`. Two Steps with equal shapes are substitutable.

        This is what makes an eval arm checkable: a trial holds Steps and refuses one whose shape
        differs, instead of discovering the mismatch when a run produces the wrong thing.
        """
        return cls.consumes.type, cls.produces.type

    def __repr__(self) -> str:
        try:
            i, o = self.shape()
            return (f"{type(self).__name__}({getattr(i, '__name__', i)} -> "
                    f"{getattr(o, '__name__', o)})")
        except AttributeError:                    # an abstract Step declaring neither side
            return f"{type(self).__name__}(undeclared)"
