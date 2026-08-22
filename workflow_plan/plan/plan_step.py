"""`PlanStep` — one planned unit of work, with typed inputs and outputs.

Grounded in [p-plan:Step](http://purl.org/net/p-plan#Step), and this time the grounding is
*checked*: `workflow_plan.invariants.provenance` verifies the IRI names a real term, and
`tests/test_pplan_grounding.py` asserts the axioms below against the vendored ontology.

    p-plan:hasInputVar    PlanStep -> Variable   NO cardinality restriction
    p-plan:hasOutputVar   PlanStep -> Variable   NO cardinality restriction
    p-plan:isOutputVarOf  Variable -> PlanStep   owl:FunctionalProperty — ONE producer

So a PlanStep consumes **0..N** Variables and produces **0..N**. It is not a function of one argument,
and modelling it as one is what went wrong.

## What was here before, and why it was wrong

`consumes: ClassVar[Variable]` and `produces: ClassVar[Variable]` — singular — written the same day
`ONTOLOGY_IRI` was set to `p-plan#Step` **from memory**. A `Plan` then validated its steps as a
pairwise chain, a relation P-Plan does not have.

It survived a month because no real pipeline was expressed in it. The first one that was —
nobsmed's `evidence_first` — could not be: its fifth step needs the paste, the extracted claims and
the screened papers *at once*, and a chain where each PlanStep receives only its predecessor's output
cannot carry that. The options were to weaken every `Variable` to `object` and smuggle a bundle
through, or to read the ontology. The ontology already had the answer.

## The vocabulary is P-Plan's, not ours

`inputs` and `outputs`, because `hasInputVar` and `hasOutputVar` are what the ontology calls them.
Not `consumes`/`produces`, which were ours and which drifted; not `scope`, which would describe an
executor's name lookup rather than the relation — a PlanStep input is **bound to a typed Variable**, not
resolved from an environment.

## ⚠️ `run()` was here, and removing it is the point

A PlanStep DECLARES a transformation. It does not perform one. `run()` said otherwise for as long as it
existed, and said it in the place that makes the claim structural:

    def run(self, **values: Any) -> Any:     # the implementation is A METHOD ON THIS CLASS
        raise NotImplementedError            # so there is one, and any second is an override

That signature asserts one implementation per PlanStep. There is not one. `ExtractClaims` is a stable
operation with several ways to perform it — a cheap model, an expensive one, an ensemble — and none
of them is the real one the others override. Which one runs is chosen by a `Strategy`, outside the
declaration and per execution: `workflow_plan.execution`.

Declaring `ExtractClaimsV1` and `ExtractClaimsV2` as separate Steps instead is not a workaround. It
is `naming.naming_drift` — several names for one concept — which is the failure this package exists
to report.

What the removal cost, measured before it was made rather than argued afterwards:

    nothing called it      not in workflow_plan/, tests/, evals/ or examples/
    the sole "impl"        examples/evidence_case_graph/flow.py took a POSITIONAL `value` against
                           the keywords-only contract below — and did not import at all, so
                           neither fault was reachable by any check
    downstream             15 overrides in nobsmed's plans.py, every one of them raising

`run` is RETIRED rather than merely deleted — see `_RETIRED`. Deleting it would let a subclass
declare `run` again and get the privileged implementation back with nothing to say so.
"""
from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from workflow_plan.naming.declared_term import DeclaredTerm
from workflow_plan.plan.plan_dependency import PlanDependency
from workflow_plan.plan.variable import Variable

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class PlanStep(DeclaredTerm, Generic[InputT, OutputT]):
    """Subclass it and declare `inputs` and `outputs`. That is the whole of it.

    Both are class-level because they are the DECLARATION: the shape of a pipeline must be readable
    without constructing anything, which is what lets a Plan be validated before a single PlanStep has
    been implemented.

    ⚠️ There is no `run`. A PlanStep says WHAT transformation exists; a `Strategy` says HOW it is
    performed, and a `StepRunner` performs it — `workflow_plan.execution`. A PlanStep you cannot execute
    is not an unfinished PlanStep, it is a PlanStep nobody has bound yet, and the two must not look alike.
    """

    #: ── the `DeclaredTerm` declaration ───────────────────────────────────────────────────────
    #:
    #: These six were a toy `class PlanStep(Concept)` in `conceptlint/ontologies/pplan/` until
    #: 2026-08-22, declared BESIDE this class rather than on it. So the linter checked a
    #: description of PlanStep while the real one drifted, and reported the two as a duplicate name —
    #: which was the only true thing it could say about the arrangement.
    ID: ClassVar[str] = "step"
    DEFINITION: ClassVar[str] = (
        "One declared unit inside a Plan: the inputs it consumes, the outputs it produces."
    )
    RATIONALE: ClassVar[str] = (
        "The declaration and one run of it were both called 'step', so 'the step failed' could mean "
        "the definition is wrong or that one execution errored — opposite actions from one sentence."
    )

    #: P-Plan grounding. Checked — see `ontologies/invariants.GroundedCitation`, which exists
    #: because this exact field was once a citation nobody had read.
    ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Step"

    #: ⚠️ `DataFlowNode` is listed so it stays dead. It is the synonym a coding agent reaches for
    #: because it sounds more computer-sciencey than PlanStep. `Task` and `Operator` are Airflow's.
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("DataFlowNode", "Task", "Operator")

    #: p-plan:hasInputVar — 0..N. A PlanStep with several inputs is the ordinary case, not a special one.
    inputs: ClassVar[tuple[Variable[Any], ...]] = ()

    #: p-plan:hasOutputVar — 0..N.
    outputs: ClassVar[tuple[Variable[Any], ...]] = ()

    #: Their `.map()`, declared. `(source, collected)` — two LIST Variables. The PlanStep itself stays
    #: the per-item operation, so `Square` is `int -> int` exactly as their `square` is, and the
    #: Plan wires `numbers -> Square -> squares`.
    #:
    #:     class Square(PlanStep):
    #:         inputs, outputs = (number,), (squared,)     # int -> int, ONE item
    #:         map_over = (numbers, squares)               # list[int] in, list[int] out
    #:
    #: The vocabulary is theirs — `map`, `join`, `reducer` — because a Plan that fans out is
    #: describing the same thing pydantic-graph and LangGraph already have words for, and inventing
    #: a third word for it would be the drift this package reports.
    #:
    #: ⚠️ Why not put it on the edge, where they put it: our edges are DERIVED. Two Steps are
    #: connected when they share a Variable, so there is no edge object to hang `.map()` on. The
    #: PlanStep is the only declared thing in the neighbourhood.
    map_over: ClassVar[tuple[Variable[Any], Variable[Any]] | None] = None

    #: Services this PlanStep needs REACHABLE. Not values, not edges — see `service.py`. Every entry
    #: must appear in the owning Plan's `services`, enforced by `topology.declared_services`,
    #: which is the docker-compose property that stops the name meaning three things.
    uses: ClassVar[tuple["PlanDependency", ...]] = ()

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
            "restriction, so a PlanStep has 0..N. Leaving `consumes` in place does not error at "
            "import: `inputs` defaults to () and the Plan reports no ports at all.",
        "produces":
            "`outputs` is a TUPLE of Variables. p-plan:hasOutputVar carries no cardinality "
            "restriction, so a PlanStep has 0..N. Leaving `produces` in place does not error at "
            "import: `outputs` defaults to () and the Plan reports no ports at all.",
        "run":
            "a PlanStep DECLARES a transformation; it does not perform one. A method here is one "
            "implementation privileged over every other, so a second way of doing the same "
            "operation becomes an override rather than a peer. Bind implementations with a "
            "Strategy instead — `from workflow_plan.execution import SequentialRunner, run` — which "
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
            # PlanStep, and its ports are its inner Plan's free and terminal Variables — computed, not
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

        if cls.__dict__.get("map_over") is not None:
            m = cls.map_over
            if not (isinstance(m, tuple) and len(m) == 2
                    and all(isinstance(v, Variable) for v in m)):
                raise TypeError(
                    f"{cls.__name__}.map_over must be (source, collected) — two list Variables, "
                    f"the one fanned out and the one collected into. Got {m!r}.")
            if len(cls.inputs) != 1 or len(cls.outputs) != 1:
                raise TypeError(
                    f"{cls.__name__} maps over {m[0].name!r}, so it is the PER-ITEM operation and "
                    f"must declare exactly one input and one output — theirs is `square: int -> "
                    f"int`. Got {len(cls.inputs)} in, {len(cls.outputs)} out. A mapped PlanStep with a "
                    f"fan-in has no meaning: there is no second list to zip against.")
            if m[0] in cls.inputs or m[1] in cls.outputs:
                raise TypeError(
                    f"{cls.__name__}.map_over names the LIST Variables, and inputs/outputs name the "
                    f"ITEM. Using the same Variable for both says the step consumes the whole list "
                    f"and one of its items at once.")

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


def wired_inputs(step: Any) -> tuple[Variable[Any], ...]:
    """What the PLAN connects to this PlanStep's input side.

    Equal to `step.inputs` unless the PlanStep maps, in which case the Plan sees the LIST it fans out
    from while the implementation sees one item. Everything structural — bindings, every topology
    and typing invariant, the diagram, the execution order — reads this, so a mapped PlanStep is an
    ordinary node in all of them and no invariant has to learn about `map_over`.
    """
    m = getattr(step, "map_over", None)
    return (m[0],) if m else tuple(step.inputs)


def wired_outputs(step: Any) -> tuple[Variable[Any], ...]:
    """What the PLAN connects to this PlanStep's output side. See `wired_inputs`."""
    m = getattr(step, "map_over", None)
    return (m[1],) if m else tuple(step.outputs)
