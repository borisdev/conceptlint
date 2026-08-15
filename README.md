# ConceptLint

**Semantic linting for Pydantic domain models.**

Catch near-duplicate, overloaded and drifting concepts before coding agents bake them into your type
system.

> *"Claude keeps inventing abstractions instead of reusing the ones we already have."*

Agent-generated code compiles. Tests pass. Types validate. And the domain model quietly stops
meaning one thing.

## 30 seconds

You have this:

```python
class Finding(BaseModel):
    """A proposition extracted from a source."""
    text: str
    source_id: str
```

An agent adds this:

```python
class ResearchFinding(BaseModel):
    """A proposition extracted from a research source."""
    text: str
    source_id: str
```

```console
$ conceptlint .
near-duplicate-model: Finding and ResearchFinding share a head noun and 100% of their fields
  concepts : Finding (models.py:4), ResearchFinding (models.py:10)
  need     : the same concept, an explicit subtype, or intentionally distinct?
             consolidate, inherit, or make the difference visible in the fields
```

**No new base classes. No schema language. No second ontology to maintain.** Ordinary Pydantic stays
the source of truth — ConceptLint reads the names, docstrings, fields and inheritance already there.

Make the relationship explicit and it goes quiet:

```python
class ClinicalFinding(Finding):
    """A finding about one patient's care."""
    patient_id: str
```

Python's own inheritance *is* the declaration. Nothing further is asked of you.

## Two signals, both required

A shared head noun **and** overlapping fields. Either alone is noise: `UserRequest` and
`SearchRequest` share a noun and are properly distinct; two unrelated models both carrying `text` is
coincidence. Boilerplate fields (`id`, `name`, `created_at`) are ignored — half the models in any
repo have them.

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


## Evals

Tests verify mechanics; evals verify semantic behaviour (§20). Each case holds **both directions**
of one lesson:

```
evals/minimal/<failure>/
    before.py         the mistake — must FLAG
    after.py          the fix     — must PASS
    expected.yaml     which rules before.py must trip
    provenance.yaml   where it came from
```

`after.py` is the more valuable half: a fix that does not silence the finding is how someone learns
to ignore a linter.

```bash
uv run python3 -m evals.runner
```

Two of the five cases are **real mistakes made while building this package**, with the commit that
made them — not imagined failures. Per §16, that is where the corpus is supposed to come from.

## Status

Phases 1–3 and 5 of the build handoff: the semantic kernel, the ontology seed, the typed dataflow
core, one real Plan, and the eval corpus.

**Not built:** the execution graph (`Activity`/`Entity` exist as concepts, not yet as classes), and
any trial machinery for comparing arms — `check_arms()` is the one line of it that a use case
already needed. Both wait for a real blocker, per §30.
