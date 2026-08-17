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
from plan_types.invariants import topology, typing

PAPER    = Variable("paper", ClinicalStudy)
FINDINGS = Variable("findings", list[Finding])
SUMMARY  = Variable("summary", str)

class Extract(Step):
    inputs, outputs = (PAPER,), (FINDINGS,)

class Summarize(Step):
    inputs, outputs = (PAPER, FINDINGS), (SUMMARY,)   # fans in — needs both

plan = Plan(
    name="extract_and_summarize",
    steps=(Extract(), Summarize()),
    declared_inputs=(PAPER,),        # what the Plan expects to be handed
)

validate(plan, [*topology.ALL, *typing.ALL])          # → []
print(render_mermaid(plan))
```

```mermaid
flowchart TD
  IN_paper(["paper: ClinicalStudy"])
  s0["Extract"]
  s1["Summarize"]
  OUT_summary(["summary: str"])
  IN_paper -- paper --> s0
  IN_paper -- paper --> s1
  s0 -- findings --> s1
  s1 --> OUT_summary
```

Every arrow is read from the bindings. Add an input and the picture changes with no edit to the
renderer — a hand-drawn diagram is a claim about the code that stops being true the moment a Step
moves, and nothing tells you.

## Why this exists

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

```
domain types
    ↓
Plan / Step / Variable
    ↓
invariants
    ↓
visualization
    ↓
optional execution adapters  ── plain Python │ Temporal │ LangGraph
```

Most workflow systems fuse process design with orchestration semantics from the first line. PlanTypes
separates them, and the separation is the point: simpler debugging, fewer irrelevant runtime
concerns, and a specification a coding agent can change safely. Plenty of processes never need
retries or durability at all.

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
grounding with vendored ontologies, 116 tests.

**Not built:** execution adapters (Temporal, LangGraph), persistence, retries, scheduling, embedding
based similarity, and agent-hook integration. The pattern above describes what the artifact is
*for*; the hooks that would put it in an agent's loop are not wired yet.

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
