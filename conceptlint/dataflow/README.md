# The typed dataflow package

> A real package, used as ConceptLint's first domain-model testbed.
>
> **ConceptLint does not require any of this.** It lints ordinary Pydantic models and needs no
> `Plan`, no `Step`, no P-Plan, no PROV-O. This package exists because building it is what exposed
> the failures ConceptLint catches — and because a linter proven only on fixtures its author wrote
> is not proven.

## Why the vocabulary is borrowed

ConceptLint does not decide that `Step` is the right word. **This domain chose an ontology in which
`Step` already has an established meaning**, and ConceptLint's job is to stop later code quietly
changing it. That is the interesting relationship: the ontology supplies the meaning, ConceptLint
defends it.

The nouns come from [P-Plan](http://purl.org/net/p-plan#) and [PROV-O](https://www.w3.org/TR/prov-o/):

```
PLAN / DEFINITION TIME              EXECUTION / RUNTIME
Plan
  └── Step          realized as     Activity
        └── Variable  instantiated as  Entity
```

**`Step ≠ Activity`**, even where an execution framework maps them one to one. That mapping is a
property of the framework, not of the concepts — and the moment code believes otherwise, *"the
definition is wrong"* and *"that run failed"* become the same sentence with opposite fixes.

Temporal's `Activity` is our `Activity`, not our `Step`. Anyone who reads it the other way is wrong
by exactly one level and has no reason to suspect it.

## Plan time

```python
from conceptlint.dataflow import Plan, Step, Variable


class ParseStudyStep(Step[Study, Findings]):
    consumes = Variable("study", Study)
    produces = Variable("findings", Findings)

    def run(self, value: Study) -> Findings:
        ...


EVIDENCE_CASE_GRAPH = Plan(
    name="evidence_case_graph",
    steps=(ParseStudyStep(), BuildEvidenceGraphStep()),
)
```

`Variable[T]` carries a **type**, not a string. An earlier version wired steps by artifact-kind
strings, so a typo silently rewired the graph: it still built, nothing type-checked, and the mistake
surfaced much later as a shape error somewhere else.

`Plan` validates at declaration — the types must line up, and a runtime object among the steps is
refused with a message saying why. Two Plans with the same `shape()` are **substitutable**, which is
what makes competing implementations comparable rather than merely looking comparable.

## Execution

`Run`, `Activity`, `Entity`, `Agent` and the four PROV edges (`Used`, `WasGeneratedBy`,
`WasDerivedFrom`, `WasAssociatedWith`) record what happened. Referential integrity is validated, not
assumed: a dangling id would make lineage return a *shorter answer* instead of an error, and "derives
from nothing" would be indistinguishable from "is a root".

**This is not an execution framework.** No retry, durability, checkpointing, fan-out or parallelism.
It records what happened; it does not decide what happens. A backend — Temporal, LangGraph,
whatever — wraps Steps from outside:

```python
class ParseStudyStep(Step[Study, Findings]):
    ...


@activity.defn                                    # the framework wraps the Step
async def execute_parse_study(study: Study) -> Findings:
    return ParseStudyStep().run(study)
```

Never the reverse. `@activity.defn` on the `Step` subclass couples a domain concept to one executor.

## Comparing implementations

`AIEvalTrial` holds competing Plans, one corpus, one judge, one rubric — and refuses arms whose
`shape()` differs, because an implementation producing something else is not losing, it is in a
different trial. The most useful function is `comparable(a, b)`: two results may sit beside each
other only if metric, corpus digest, judge and rubric version all match.

## What this taught ConceptLint

Two eval cases in `evals/minimal/` came from mistakes made building this package, with the commit
recorded in `provenance.yaml`:

| | |
|---|---|
| `variable_entity_collapse` | a plan-time `Variable` grew `started_at` and a value — a runtime type wearing a plan-time name |
| `sibling_refinement` | two concepts refining one parent were flagged as duplicates, so the documented fix did not silence the finding |

That is the loop the project runs on: build something real, make a semantic mistake, turn it into a
regression fixture.
