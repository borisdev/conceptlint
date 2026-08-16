"""The five nouns, grounded in P-Plan and PROV-O.

Five, and not a sixth. P-Plan and PROV-O between them define dozens of terms; importing the universe
would make this an ontology implementation, which §22 forbids. These five are the ones the typed
dataflow in `plan_types.plan` actually needs.

## The distinction the whole package exists to hold

    PLAN / DEFINITION TIME          EXECUTION / RUNTIME
    Plan                            —
      Step            realized as   Activity
      Variable       instantiated as Entity

A Step is not an Activity even when an execution framework maps them one-to-one. That mapping is a
property of the framework, not of the concepts — and the moment the code believes otherwise, "when
did it fail" and "is the definition wrong" become the same question with opposite answers.
"""
from __future__ import annotations

from typing import ClassVar

from conceptlint.core.concept import Concept

PPLAN = "http://purl.org/net/p-plan#"
PROV = "http://www.w3.org/ns/prov#"


class Plan(Concept):
    ID: ClassVar[str] = "plan"
    ONTOLOGY_IRI: ClassVar[str] = PPLAN + "Plan"
    DEFINITION: ClassVar[str] = "A declared composition of Steps: what should happen, not what did."
    RATIONALE: ClassVar[str] = (
        "Without a name for the declaration, the only thing left to point at is a particular run — "
        "so 'the pipeline is wrong' and 'that execution failed' collapse into one sentence with two "
        "opposite fixes."
    )
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("DataFlowGraph", "Workflow", "Pipeline")


class Step(Concept):
    ID: ClassVar[str] = "step"
    ONTOLOGY_IRI: ClassVar[str] = PPLAN + "Step"
    DEFINITION: ClassVar[str] = (
        "One declared unit inside a Plan: the input it consumes, the output it produces."
    )
    RATIONALE: ClassVar[str] = (
        "The declaration and one run of it were both called 'step', so 'the step failed' could mean "
        "the definition is wrong or that one execution errored — opposite actions from one sentence."
    )
    #: ⚠️ `DataFlowNode` is listed so it stays dead. It is the synonym a coding agent reaches for
    #: because it sounds more computer-sciencey than Step, and §29 names it specifically.
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("DataFlowNode", "Task", "Operator")


class Variable(Concept):
    ID: ClassVar[str] = "variable"
    ONTOLOGY_IRI: ClassVar[str] = PPLAN + "Variable"
    DEFINITION: ClassVar[str] = (
        "A typed placeholder connecting Steps in a Plan — the KIND of value, never a value."
    )
    RATIONALE: ClassVar[str] = (
        "Wiring Steps by artifact-kind STRINGS makes a typo a silent rewiring: the graph still "
        "builds, the types are unchecked, and the mistake surfaces as a shape error much later."
    )
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("DataFlowValue", "Port", "Slot")


class Activity(Concept):
    ID: ClassVar[str] = "activity"
    ONTOLOGY_IRI: ClassVar[str] = PROV + "Activity"
    DEFINITION: ClassVar[str] = "One execution of a Step, with its timing and outcome."
    RATIONALE: ClassVar[str] = (
        "Provenance attaches to the run, not the declaration. Without this, 'when did it fail' has "
        "no answer that is not also a claim about every other run."
    )
    #: ⚠️ Temporal's `Activity` lands HERE, not on Step. Anyone who knows Temporal and reads our
    #: `Step` as their `Activity` is wrong by exactly one level and has no reason to suspect it.
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("StepRun", "TaskInstance", "RuntimeStep")


class Entity(Concept):
    ID: ClassVar[str] = "entity"
    ONTOLOGY_IRI: ClassVar[str] = PROV + "Entity"
    DEFINITION: ClassVar[str] = "One actual value produced or consumed by an Activity."
    RATIONALE: ClassVar[str] = (
        "A Variable says `Findings`; an Entity is the findings from pmid:123 at 10:04, with an id "
        "worth joining on. Collapsing them leaves a graph that can answer neither question."
    )
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ("Artifact", "Dataset", "Value")


#: The plan-time/runtime pairing, as data. `plan_types.plan.invariants` reads this rather than
#: hardcoding the pairs, so adding a sixth concept cannot silently escape the distinction.
REALIZES: dict[type[Concept], type[Concept]] = {Activity: Step, Entity: Variable}
