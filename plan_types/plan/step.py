"""`Step` — one planned unit of work, with typed inputs and outputs.

Grounded in [p-plan:Step](http://purl.org/net/p-plan#Step), and this time the grounding is
*checked*: `plan_types.invariants.provenance` verifies the IRI names a real term, and
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

## ⚠️ `run()` was here, and removing it is the point

A Step DECLARES a transformation. It does not perform one. `run()` said otherwise for as long as it
existed, and said it in the place that makes the claim structural:

    def run(self, **values: Any) -> Any:     # the implementation is A METHOD ON THIS CLASS
        raise NotImplementedError            # so there is one, and any second is an override

That signature asserts one implementation per Step. There is not one. `ExtractClaims` is a stable
operation with several ways to perform it — a cheap model, an expensive one, an ensemble — and none
of them is the real one the others override. Which one runs is chosen by a `Strategy`, outside the
declaration and per execution: `plan_types.execution`.

Declaring `ExtractClaimsV1` and `ExtractClaimsV2` as separate Steps instead is not a workaround. It
is `naming.naming_drift` — several names for one concept — which is the failure this package exists
to report.

What the removal cost, measured before it was made rather than argued afterwards:

    nothing called it      not in plan_types/, tests/, evals/ or examples/
    the sole "impl"        examples/evidence_case_graph/flow.py took a POSITIONAL `value` against
                           the keywords-only contract below — and did not import at all, so
                           neither fault was reachable by any check
    downstream             15 overrides in nobsmed's plans.py, every one of them raising

`run` is RETIRED rather than merely deleted — see `_RETIRED`. Deleting it would let a subclass
declare `run` again and get the privileged implementation back with nothing to say so.
"""
from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from plan_types.plan.service import Service
from plan_types.plan.variable import Variable

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class Step(Generic[InputT, OutputT]):
    """Subclass it and declare `inputs` and `outputs`. That is the whole of it.

    Both are class-level because they are the DECLARATION: the shape of a pipeline must be readable
    without constructing anything, which is what lets a Plan be validated before a single Step has
    been implemented.

    ⚠️ There is no `run`. A Step says WHAT transformation exists; a `Strategy` says HOW it is
    performed, and a `StepRunner` performs it — `plan_types.execution`. A Step you cannot execute
    is not an unfinished Step, it is a Step nobody has bound yet, and the two must not look alike.
    """

    #: P-Plan grounding. Checked — see `ontologies/invariants.GroundedCitation`, which exists
    #: because this exact field was once a citation nobody had read.
    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Step"

    #: p-plan:hasInputVar — 0..N. A Step with several inputs is the ordinary case, not a special one.
    inputs: ClassVar[tuple[Variable[Any], ...]] = ()

    #: p-plan:hasOutputVar — 0..N.
    outputs: ClassVar[tuple[Variable[Any], ...]] = ()

    #: Services this Step needs REACHABLE. Not values, not edges — see `service.py`. Every entry
    #: must appear in the owning Plan's `services`, enforced by `topology.declared_services`,
    #: which is the docker-compose property that stops the name meaning three things.
    uses: ClassVar[tuple["Service", ...]] = ()

    #: Names this class used to carry, mapped to what replaced them. A subclass still declaring one
    #: fails AT IMPORT — because in every case here the name still parses, and a name that parses
    #: while meaning nothing is worse than one that breaks the build.
    #:
    #: `consumes`/`produces` were singular and retired 2026-08-16. Observed downstream the moment
    #: v0.3.0 landed: both nobsmed arms became `shape=((), ())` and nothing raised, because `inputs`
    #: and `outputs` simply defaulted to ().
    #:
    #: `run` is the same shape of failure with a different consequence — it does not silently empty
    #: the declaration, it silently re-privileges one implementation. See the module docstring.
    _RETIRED: ClassVar[dict[str, str]] = {
        "consumes": "inputs", "produces": "outputs", "run": "a Strategy",
    }

    #: Why each retired name is retired, in the error a human has to act on. Kept beside the mapping
    #: rather than generated from it: the previous version built the sentence with
    #: `'Input' if old == 'consumes' else 'Output'`, which silently told anyone retiring a THIRD
    #: name that it was about `hasOutputVar`.
    _RETIRED_WHY: ClassVar[dict[str, str]] = {
        "consumes":
            "`inputs` is a TUPLE of Variables. p-plan:hasInputVar carries no cardinality "
            "restriction, so a Step has 0..N. Leaving `consumes` in place does not error at "
            "import: `inputs` defaults to () and the Plan reports no ports at all.",
        "produces":
            "`outputs` is a TUPLE of Variables. p-plan:hasOutputVar carries no cardinality "
            "restriction, so a Step has 0..N. Leaving `produces` in place does not error at "
            "import: `outputs` defaults to () and the Plan reports no ports at all.",
        "run":
            "a Step DECLARES a transformation; it does not perform one. A method here is one "
            "implementation privileged over every other, so a second way of doing the same "
            "operation becomes an override rather than a peer. Bind implementations with a "
            "Strategy instead — `from plan_types.execution import LocalRunner, execute` — which "
            "is per execution, so one Plan can run several ways without being edited.",
    }

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        for old, new in cls._RETIRED.items():
            if old in cls.__dict__:
                raise TypeError(
                    f"{cls.__name__}.{old} is retired — use {new}. {cls._RETIRED_WHY[old]}")
        for field in ("inputs", "outputs"):
            value = getattr(cls, field, ())
            # ⚠️ DERIVED ports are legal and are not tuples. `MultiStep` is a Plan that is also a
            # Step, and its ports are its inner Plan's free and terminal Variables — computed, not
            # declared, because declaring them a second time is the two-sources-of-truth this
            # package refuses everywhere else. A descriptor here means "derived"; leave it alone.
            if isinstance(getattr(cls, "__dict__", {}).get(field, None), property) or isinstance(
                    value, property):
                continue
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
            value = getattr(cls, field, ())
            if isinstance(value, property):   # derived — see the note above
                continue
            names = [v.name for v in value]
            if len(names) != len(set(names)):
                raise TypeError(f"{cls.__name__}.{field} names a Variable twice: {names}")

    @classmethod
    def shape(cls) -> tuple[tuple[type, ...], tuple[type, ...]]:
        """`(input types, output types)`. Two Steps with equal shapes are substitutable."""
        return tuple(v.type for v in cls.inputs), tuple(v.type for v in cls.outputs)

    def __repr__(self) -> str:
        ins = ", ".join(v.name for v in self.inputs) or "-"
        outs = ", ".join(v.name for v in self.outputs) or "-"
        return f"{type(self).__name__}({ins} -> {outs})"
