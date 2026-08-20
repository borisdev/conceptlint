# PlanTypes

**From Claude Code Plan Mode to Plan Types.**

Turn an agent's plan into a typed process specification — one you can validate, draw, and hold it to.

Claude Code's Plan Mode says *"here's what I intend to do."* It's prose, it's gone when the conversation moves on,
and nothing checks that the code matches it. PlanTypes makes the same intent an artifact:

```
Plan
├── typed Steps
├── typed Variables
├── explicit dependencies
├── invariants
└── visualization
```

> **Plan Mode describes intent. PlanTypes makes the plan typed, inspectable, and testable.**

This is not a replacement for Claude Code or Cursor. It's the thing their plans should produce.

## 60 seconds

```python
from plan_types import Plan, Step, Variable, render_mermaid, validate
from plan_types.execution import LocalRunner, execute
from plan_types.invariants import topology, typing

document = Variable("document", Document)
outline  = Variable("outline", Outline)
summary  = Variable("summary", Summary)

class MakeOutline(Step):
    inputs, outputs = (document,), (outline,)

class Summarize(Step):
    inputs, outputs = (document, outline), (summary,)   # fans in — needs both

plan = Plan(
    name="summarize_document",
    steps=(MakeOutline(), Summarize()),
    declared_inputs=(document,),        # what the Plan expects to be handed
)

validate(plan, [*topology.ALL, *typing.ALL])            # → []
print(render_mermaid(plan))
```

```mermaid
flowchart TD
  IN_document(["document: Document"])
  summarize_document_0["Make Outline"]
  summarize_document_1["Summarize"]
  OUT_summary(["summary: Summary"])
  IN_document -- document --> summarize_document_0
  IN_document -- document --> summarize_document_1
  summarize_document_0 -- outline --> summarize_document_1
  summarize_document_1 --> OUT_summary
  classDef port fill:#fff,stroke:#333,stroke-width:1px,color:#333;
  class IN_document,OUT_summary port;
```

Every arrow is read from the bindings. Add an input and the picture changes with no edit to the
renderer — a hand-drawn diagram is a claim about the code that stops being true the moment a Step
moves, and nothing tells you. That block is generated from
[`examples/hello/flow.py`](examples/hello/flow.py), which `tests/test_execution.py` runs.

**Notice what a Step does not contain.** No prompt, no model name, no retry policy, no `run`. It
declares that an operation exists and what flows through it. How it is performed is chosen
separately, and chosen *per execution*:

```python
def summarize_fast(document: Document, outline: Outline) -> Summary: ...
def summarize_precise(document: Document, outline: Outline) -> Summary: ...

fast    = {MakeOutline: outline_by_sentence, Summarize: summarize_fast}
precise = {MakeOutline: outline_by_sentence, Summarize: summarize_precise}

execute(plan, {"document": doc}, LocalRunner(fast))       # Ninety seconds: Name the unit.
execute(plan, {"document": doc}, LocalRunner(precise))    # Ninety seconds: Name the unit; Then run it; …
```

**The `plan` object is not touched between those two lines.** That is the property worth having: an
experiment can say *the logical process was held constant, only the implementation of `Summarize`
changed* — and mean it, because the same declaration served both arms.

The alternative is to declare `SummarizeV1` and `SummarizeV2` as separate Steps, and that is not a
workaround, it is two names for one concept — the `naming.naming_drift` this package exists to
report, committed inside the package that reports it.

## Why this exists

![Rube Goldberg's Self-Operating Napkin, 1931 — public domain](https://upload.wikimedia.org/wikipedia/commons/a/a9/Rube_Goldberg%27s_%22Self-Operating_Napkin%22_%28cropped%29.gif)

**→ [Design notes](docs/design.md)** — why the types are shaped this way, and the failure behind
each invariant.

**→ [The counterfactual question](docs/counterfactual.md)** — what to answer before adding a
component, and the threshold that deleted the right answers for eighteen hours.

The workflow that motivates it:

> A developer builds substantial software architecture mostly through conversation with a coding
> agent — potentially from a phone, barely touching the editor.

That has characteristic failure modes, and they are not typos:

| | |
|---|---|
| terminology drift | the same thing acquires three names |
| ambiguous references | "the graph" now means two classes |
| duplicate concepts | an alias gets read as a new abstraction and implemented twice |
| incompatible I/O | two Steps that look connected and move nothing |
| accidental topology changes | a rewiring nobody decided on |
| architecture invented by the agent | abstractions that arrived without a decision |
| docs diverging from code | a diagram that was true last week |
| runtime detail obscuring design | retries and durability drowning the logic |

> **The framework constrains coding agents so they cannot casually invent architecture.**

Instead of

```
conversation → informal plan → agent writes code
```

the pattern becomes

```
conversation
    ↓
typed Plan
    ↓
validate + visualize + inspect
    ↓
agent writes code against the Plan
```

## When the Plan won't let you do it

A constraint that only ever says *no* gets deleted. So the useful half of the rule is what to do
instead, in order:

```
1. reuse an existing type
2. adapt
3. compose
4. refine — declare the subtype relationship explicitly
5. keep the representation private to your implementation
6. only then, evolve the shared types
```

⚠️ **A real use-case blocker is evidence the shared types should change. An agent's implementation
convenience is not.** The test is whether anything other than the current diff gets worse if you
refuse.

A Step you cannot express cleanly is information before it is an obstacle. This package's own
`Step[InputT, OutputT]` — one input, one output — died to a real builder whose step needed the
paste, the extracted questions **and** the screened papers at once. Routing around that would have
hidden the fact that the signature was wrong.

## The logical process first, the runtime later — or never

Four layers, and each one only knows about the one above it:

```
WHAT EXISTS            Variable ── typed slot          ┐
                       Step     ── one operation       │  plan-time
                       Plan     ── how Steps compose   │  imports nothing else
                       Service  ── what must be up     ┘

HOW IT IS PERFORMED    Strategy ── {Step: implementation}      chosen per execution
                                   several per Step, none privileged

HOW IT IS RUN          StepRunner ── Protocol            LocalRunner  ── here
                                                         Temporal     ── not built
                                                         LangGraph    ── not built

WHAT ACTUALLY RAN      prov:Activity, prov:Entity        ⚠️ NOT modelled by this package
```

The arrows only point down. `plan_types.plan` imports nothing from `plan_types.execution`, which is
what lets a specification be read, validated and drawn with no execution backend in the room — and
`scripts/check_wheel.py` imports both from a built wheel outside the source tree, because a layering
claim that only holds in an editable install is not a layering claim.

⚠️ **The bottom row is deliberately absent.** `p-plan:Step` is the intended operation;
`prov:Activity` is one execution of it. A runtime may map them one to one, and the moment code
believes that, *"the definition is wrong"* and *"that run failed"* become the same sentence with
opposite fixes.

Most workflow systems fuse process design with orchestration semantics from the first line.
PlanTypes separates them, and the separation is the point: simpler debugging, fewer irrelevant
runtime concerns, and a specification a coding agent can change safely. Plenty of processes never
need retries or durability at all — `LocalRunner` is sequential, in-process, and has no retries by
decision, not by omission.

⚠️ **A Plan is not a DAG.** A Plan *may* be acyclic — that's `topology.acyclic`, an invariant you
opt into. Building it into the type would rule out iterative processes before anyone asked for one,
and [P-Plan](http://purl.org/net/p-plan#) has no acyclicity axiom either.

## Invariants are executable rules

```python
SemanticInvariant(
    id="typing.plan_time_only",
    statement="A plan-time type must not carry runtime execution state.",
    why="Observed: `Variable` gained `value` and `started_at`, kept its docstring, kept passing "
        "its tests, and silently became a runtime record.",
    check=...,
)
```

Four concrete categories, not one vague subsystem:

| | catches |
|---|---|
| `naming/` | **ambiguous reference** — one name, many concepts · **naming drift** — many names, one concept |
| `typing/` | bindings whose types don't line up; plan-time types carrying runtime state |
| `topology/` | cycles, unbound inputs, orphan Variables, two producers for one Variable |
| `provenance/` | an `ONTOLOGY_IRI` naming a term nobody vendored |

⚠️ `declared_inputs` is not decoration. With inputs fully *derived* — "consumed here, produced by
nothing here" — an accidental gap and the Plan's own signature are **the same set**, so
`topology.bound_inputs` can never fire. Declaring them makes the distinction expressible. Omit it
and that rule reports NOT CHECKED, which is how this README was caught claiming `→ []` when it
returned a finding.

`validate()` **collects** rather than stopping at the first failure — one cycle can cause three
findings, and seeing all three is how you tell one root cause from three problems.

⚠️ And a check that *cannot run* reports **NOT CHECKED**, never a pass. "We didn't look" and "we
looked and it was fine" must never render the same.

## Grounded in P-Plan, and the grounding is checked

`Plan`, `Step` and `Variable` come from [P-Plan](http://purl.org/net/p-plan#); `Activity`, `Entity`
and `Agent` from [PROV-O](https://www.w3.org/TR/prov-o/). Plan-time and runtime, kept apart:

```
p-plan:Step      the intended operation
prov:Activity    one execution of it
```

⚠️ **`Step ≠ Activity`**, even where a runtime maps them one to one. That mapping is a property of
the framework, not of the concepts — and the moment code believes otherwise, *"the definition is
wrong"* and *"that run failed"* become the same sentence with opposite fixes.

The ontologies are **vendored with a hash**, and `provenance.grounded_citation` checks that every
cited IRI names a real term. That rule exists because this package once cited `p-plan#Step` from
memory and implemented something P-Plan doesn't describe. A citation nobody can follow is
decoration with the authority of a fact.

## Status — honest

**Works today:** typed Plans, the four invariant categories, `render_mermaid`, P-Plan/PROV-O
grounding with vendored ontologies, `Strategy` + `check_strategy`, and `LocalRunner` — sequential,
in-process, no retries. 142 tests.

**Not built:** an async runner, execution adapters (Temporal, LangGraph, Pydantic Graph),
persistence, retries, scheduling, concurrency, embedding-based similarity, and agent-hook
integration. The pattern above describes what the artifact is *for*; the hooks that would put it in
an agent's loop are not wired yet.

⚠️ **`LocalRunner` is synchronous, and an `async def` implementation is refused rather than
accepted.** Calling one from sync code returns a coroutine — truthy, with a repr, flowing into the
next Step as though it were data. `check_strategy` reports it before execution and the runner raises
at the call site. An `AsyncStepRunner` lands when there is a real async implementation to run.

Not on PyPI. From source:

```bash
git clone https://github.com/borisdev/plan-types && cd plan-types && uv sync
uv run pytest -q
```

## Open question, deliberately

Are semantic invariants the general product, with PlanTypes as the first ontology-grounded use
case — or is PlanTypes the product, with invariants as a subsystem inside it?

Not decided. The code is arranged so invariants *could* split into a standalone package later, and
that split has not been made. Worth arguing about in the open rather than settling early.
