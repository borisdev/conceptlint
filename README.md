# ConceptLint

**Semantic linting for Pydantic domain models.**

Catch duplicate, overloaded and drifting concepts before a coding agent writes your type system.

- **duplicate** — two names, one meaning: `Finding` and `ResearchFinding`, same fields
- **overloaded** — one name, two meanings: `Evidence` as a study, as support, as a citation
- **drifting** — a name that quietly changes meaning: `Variable` grows `started_at` and a value,
  and is now a runtime thing wearing a plan-time name

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

## Drift is read from git

The other two are visible in one snapshot. Drift is not — it is a claim about two points in time.
A docstring is a promise; the fields are what the model actually is:

```
docstring changed, fields changed    evolution — they decided, and said so    silent
docstring changed, fields same       a rewording                              silent
docstring same,    fields same       nothing happened                         silent
docstring same,    fields CHANGED    the promise no longer describes it       FLAG
```

```bash
conceptlint . --since HEAD~20
```

Silent with no git history: "cannot tell" is not a finding.

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

## Run it

Not on PyPI yet. From source:

```bash
git clone https://github.com/borisdev/conceptlint
cd conceptlint
uv sync
uv run conceptlint .                  # lint the models here
uv run conceptlint . --since HEAD~20  # include drift
```

`check` exits **1** on a finding and **0** in silence. There is no success message — a tool that
congratulates you on every clean run teaches you to stop reading it.

## Real-world example: a typed dataflow

This repository includes a small typed-dataflow package used as ConceptLint's first real
domain-model testbed. Its vocabulary is grounded in P-Plan and PROV-O, and mistakes encountered
while building it become ConceptLint eval cases.

**It demonstrates ConceptLint preserving a coherent domain type system. It is not ConceptLint's core
abstraction, and you do not need it.**

```python
from conceptlint.dataflow import Plan, Step, Variable


class ParseStudyStep(Step[Study, Findings]):
    consumes = Variable("study", Study)
    produces = Variable("findings", Findings)
```

Building this package exposed exactly the failures ConceptLint is meant to catch: near-duplicate
concepts, overloaded terms, and plan-time/runtime confusion.

One relationship is worth naming, because it is the point rather than a detail. **ConceptLint does
not decide that `Step` is the right word.** That domain chose an ontology in which `Step` already has
an established meaning; ConceptLint stops later code quietly changing it.

→ [`conceptlint/dataflow/README.md`](conceptlint/dataflow/README.md) for the architecture: the
plan-time/runtime split, why `Step ≠ Activity`, the execution graph, and how an executor wraps it.

## Evals

Tests verify mechanics; evals verify semantic behaviour. Each case holds **both directions**
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

Two of the five cases are **real mistakes made while building the dataflow package**, with the
commit that made them. That is where the corpus is meant to come from — a linter proven only on
fixtures its author invented is not proven.

## Status

Working: duplicate and overloaded detection on ordinary Pydantic models, drift against git history,
and the `Concept` layer for vocabulary you want to declare explicitly. 73 tests, 9 eval assertions.

**Not on PyPI.** Install from source.

**Evidence, stated honestly:** run against a production medical codebase — 169 Pydantic models
across four packages — it found **one genuine duplicate**, two names with identical docstrings and
identical fields in different files. That is a demonstration, not a study. No hit rate is claimed
because none was measured.
