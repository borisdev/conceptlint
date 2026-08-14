# ConceptLint

**Keeps human–agent development semantically precise, so coherent domain type systems can be built
without semantic drift.**

Coding agents are good at writing code and enthusiastic about inventing vocabulary. Ask one to add a
pipeline node and it writes `DataFlowNode` — beside the `Step` you already have. Ask it to record a
run and it puts timestamps on the plan-time type. Both compile. Both pass review.

ConceptLint declares the terms that matter and checks that they keep meaning one thing.

## The two laws

```
One Concept  →  One Meaning            a term must not quietly acquire a second meaning
One Meaning  →  One Canonical Concept  a meaning must not quietly acquire a second term
```

Neither forbids a distinction. Both forbid an **undeclared** one — every finding has a legal
resolution that is one line of code.

## Grounded, not invented

The first vocabulary comes from [P-Plan](http://purl.org/net/p-plan#) and
[PROV-O](https://www.w3.org/TR/prov-o/), because these nouns already have public meanings:

```
PLAN / DEFINITION TIME              EXECUTION / RUNTIME
Plan
  └── Step          realized as     Activity
        └── Variable  instantiated as  Entity
```

`Step ≠ Activity`, even where an execution framework maps them one to one. That is a property of the
framework, not of the concepts — and the moment code believes otherwise, *"the definition is wrong"*
and *"that run failed"* become the same sentence with opposite fixes.

## The typed dataflow it dogfoods

Not a fixture — a real package another project can depend on:

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

`Plan` validates at declaration: types must line up, and a runtime object in the steps is refused.
Two Plans with the same `shape()` are substitutable — which is what makes competing builders
comparable instead of merely looking comparable.

## Run it

```bash
uv sync
uv run pytest
uv run conceptlint --import conceptlint.ontologies.pplan.concepts --list
```

## Ontology is not the type system

```
Ontology        semantic foundation      what the nouns mean
Typed dataflow  executable contract      what the code must satisfy
ConceptLint     semantic guardrail       that the nouns keep meaning it
```

P-Plan says what a Step *is*. `Step[InputT, OutputT]` imposes a constraint P-Plan does not. Neither
replaces the other.

## What this is not

Not an RDF reasoner, not a full P-Plan or PROV-O implementation, not a workflow engine, not a
Temporal or LangGraph wrapper, not an ontology editor. Execution concerns — retry, durability,
checkpointing, fan-out, parallelism — belong to a backend that wraps Steps from outside.

## Status

Phases 1–3 of the build handoff: the semantic kernel, the ontology seed, and the typed dataflow
core, plus one real Plan. Evals for semantic drift are next, and they come from **real** mistakes
made while building this — not from imagined ones.
