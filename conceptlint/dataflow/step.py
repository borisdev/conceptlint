"""`Step` — one planned unit of work, with typed inputs and outputs.

Grounded in [p-plan:Step](http://purl.org/net/p-plan#Step), and this time the grounding is
*checked*: `conceptlint/ontologies/invariants.py` verifies the IRI names a real term, and
`tests/test_pplan_grounding.py` asserts the axioms below against the vendored ontology.

    p-plan:hasInputVar    Step -> Variable   NO cardinality restriction
    p-plan:hasOutputVar   Step -> Variable   NO cardinality restriction
    p-plan:isOutputVarOf  Variable -> Step   owl:FunctionalProperty — ONE producer

So a Step consumes **0..N** Variables and produces **0..N**. It is not a function of one argument,
and modelling it as one is what went wrong.

## What was here before, and why it was wrong

`consumes: ClassVar[Variable]` and `produces: ClassVar[Variable]` — singular — written the same day
`ONTOLOGY_IRI` was set to `p-plan#Step` **from memory**. A `Plan` then validated its steps as a
pairwise chain, a relation P-Plan does not have.

It survived a month because no real pipeline was expressed in it. The first one that was —
nobsmed's `evidence_first` — could not be: its fifth step needs the paste, the extracted claims and
the screened papers *at once*, and a chain where each Step receives only its predecessor's output
cannot carry that. The options were to weaken every `Variable` to `object` and smuggle a bundle
through, or to read the ontology. The ontology already had the answer.

## The vocabulary is P-Plan's, not ours

`inputs` and `outputs`, because `hasInputVar` and `hasOutputVar` are what the ontology calls them.
Not `consumes`/`produces`, which were ours and which drifted; not `scope`, which would describe an
executor's name lookup rather than the relation — a Step input is **bound to a typed Variable**, not
resolved from an environment.
"""
from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from conceptlint.dataflow.variable import Variable

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class Step(Generic[InputT, OutputT]):
    """Subclass it, declare `inputs` and `outputs`, implement `run`.

    Both are class-level because they are the DECLARATION: the shape of a pipeline must be readable
    without constructing anything, which is what lets a Plan be validated before a single Step has
    been implemented.
    """

    #: P-Plan grounding. Checked — see `ontologies/invariants.GroundedCitation`, which exists
    #: because this exact field was once a citation nobody had read.
    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Step"

    #: p-plan:hasInputVar — 0..N. A Step with several inputs is the ordinary case, not a special one.
    inputs: ClassVar[tuple[Variable[Any], ...]] = ()

    #: p-plan:hasOutputVar — 0..N.
    outputs: ClassVar[tuple[Variable[Any], ...]] = ()

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        for field in ("inputs", "outputs"):
            value = getattr(cls, field, ())
            if isinstance(value, Variable):
                raise TypeError(
                    f"{cls.__name__}.{field} is a single Variable; it must be a tuple. P-Plan puts "
                    f"no cardinality on hasInputVar/hasOutputVar, and the singular form is the bug "
                    f"this class was rewritten to remove — write `({value.name!r}-var,)`.")
            if not isinstance(value, tuple) or not all(isinstance(v, Variable) for v in value):
                raise TypeError(
                    f"{cls.__name__}.{field} must be a tuple of Variables, got {value!r}")

        # Duplicate names within one side would make a binding ambiguous, and the ambiguity would
        # surface as the wrong value arriving rather than as an error here.
        for field in ("inputs", "outputs"):
            names = [v.name for v in getattr(cls, field, ())]
            if len(names) != len(set(names)):
                raise TypeError(f"{cls.__name__}.{field} names a Variable twice: {names}")

    def run(self, **values: Any) -> Any:
        """Execute. Keyword arguments are the input Variables, by name.

        ⚠️ Keywords, not positional. A Step with three inputs called positionally is one argument
        reorder away from a silent mis-wire, and the type check that justifies this package would
        not catch it when two inputs share a type.
        """
        raise NotImplementedError

    @classmethod
    def shape(cls) -> tuple[tuple[type, ...], tuple[type, ...]]:
        """`(input types, output types)`. Two Steps with equal shapes are substitutable."""
        return tuple(v.type for v in cls.inputs), tuple(v.type for v in cls.outputs)

    def __repr__(self) -> str:
        ins = ", ".join(v.name for v in self.inputs) or "-"
        outs = ", ".join(v.name for v in self.outputs) or "-"
        return f"{type(self).__name__}({ins} -> {outs})"
