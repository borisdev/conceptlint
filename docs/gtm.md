
---

# Pydantic Beachhead (folded 2026-08-15)

## The decision

Pydantic is the **initial ecosystem**, not a permanent definition.

```
wedge        Semantic linting for Pydantic domain models.
long-term    Built for Pydantic first. Designed for typed domain models generally.
```

Dataclasses, Protocols, TypedDicts, TS/Zod — **not** now.

## Why Pydantic

It already carries the semantic surface: names, docstrings, field names and types, descriptions,
inheritance, validators, enums. And the philosophy fits — Pydantic has argued publicly that coding
agents benefit from type safety, putting this problem adjacent to their worldview.

```
Pydantic          makes domain structure explicit
Coding agents     rapidly modify that structure
ConceptLint       protects the vocabulary's coherence
```

Complement Pydantic. Do not introduce a competing semantic modeling framework.

## ⚠️ The product decision this forced, and how it was checked

**Do NOT require `class Finding(Concept)`.** Ordinary `class Finding(BaseModel)` stays the source of
truth.

This contradicted the build as it stood, and the contradiction was CHECKED rather than assumed: the
handoff's own killer demo was run against the linter and produced **zero issues**, because both
models were plain `BaseModel`s. The proposed README line would have been false the day it was
written. `conceptlint/models.py` exists because of that check.

`Concept` remains, **optional**, for what ordinary Pydantic cannot express: an external ontology
IRI, a recorded rationale, and retired words worth keeping dead.

**No new base classes. No schema language. No second ontology to maintain.**

## What is actually being sold

Not "AI-powered naming lint", not "an ontology framework for Pydantic", not "semantic similarity for
Python classes":

> Coding agents create locally reasonable code while gradually destroying the coherence of a
> project's domain language.

The two laws are unchanged. The Pydantic model layer is an unusually good place to enforce them.

## Outreach

**First target: Samuel Colvin.** One or two conversations, not mass outreach to the maintainer list.

**Do not ask** for adoption, integration, sponsorship, endorsement, or a change to Pydantic.
**Ask whether the problem is real** — far better signal. Keep it short enough to earn
*"interesting, show me"*.

## Sequence

```
tiny working ConceptLint → excellent Pydantic demo → README in ~30s
    → use it on the real domain package → capture GENUINE collisions
    → approach Samuel → "is this problem real?" → incorporate
    → Pydantic community → Claude Code / agentic audience
```

⚠️ **Step 4 is the one that has not been done, and it matters most.** ConceptLint must not look like
a toy invented to justify itself. The line to be able to say honestly:

> "I built this because Claude and I were developing a domain type system together and repeatedly
> hit this exact failure mode."

## Ready-for-outreach criterion

Under a minute:

```
coherent Pydantic domain model
    + agent introduces a plausible new model
    → conceptlint check
    → a meaningful warning ordinary linting, typing and validation all miss
```

Do not wait for completeness. **Do** wait for that.

## Keep the layers separate

```
beachhead          Pydantic developers using coding agents
problem            semantic drift in evolving domain type systems
product            ConceptLint
long-term category semantic discipline for human-agent software development
```

## Not yet

No marketing to all of Python, no second type system, no Pydantic plugin before demand, no request
for official integration, no branding weeks, no elaborate ontology, no required `Concept` superclass,
no asking users to annotate their codebase, no claiming similarity alone solves coherence, no mass
maintainer outreach.

One result that makes a Pydantic developer say: **"yes, my coding agent actually does this."**
