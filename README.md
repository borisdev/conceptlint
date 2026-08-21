# PlanTypes

**Declarative, typed workflow plans, separated from execution.**

LangGraph, Temporal and [Pydantic Graph](https://pydantic.dev/docs/ai/graph/builder/) *execute* a
workflow, and each is good at it. This is the layer above: the workflow plan you settle — and can
validate, draw and argue about — **before** you pick an engine, or instead of picking one, since
plenty of workflows never need retries or durability.

## The plan exists before the code does

That is the whole claim, and it is one snippet:

```python
document = Variable("document", Document)
outline  = Variable("outline", Outline)
summary  = Variable("summary", Summary)

class MakeOutline(Step):
    inputs, outputs = (document,), (outline,)

class Summarize(Step):
    inputs, outputs = (document, outline), (summary,)   # fans in — needs both

plan = Plan(name="summarize_document", steps=(MakeOutline(), Summarize()),
            declared_inputs=(document,))

validate(plan, [*topology.ALL, *typing.ALL])   # → []
print(render_mermaid(plan))
print(plan.shape())                            # → ((Document,), (Summary,))
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

**Not one line of that workflow is implemented.** No prompt, no model, no function body, no runtime.
The process is checked, drawn and type-checked anyway — because a Step declares *what a
transformation is*, and nothing more.

Every arrow is read from the bindings, so adding an input changes the picture with no edit to the
renderer. A hand-drawn diagram is a claim about the code that stops being true the moment a Step
moves, and nothing tells you.

## How it is performed comes later, and is chosen per run

```python
def summarize_fast(document: Document, outline: Outline) -> Summary: ...
def summarize_precise(document: Document, outline: Outline) -> Summary: ...

fast    = {MakeOutline: outline_by_sentence, Summarize: summarize_fast}
precise = {MakeOutline: outline_by_sentence, Summarize: summarize_precise}

execute(plan, {"document": doc}, LocalRunner(fast))
execute(plan, {"document": doc}, LocalRunner(precise))
```

**The `plan` object is not touched between those two lines.** An experiment can therefore say *the
logical process was held constant, only the implementation of `Summarize` changed* — and mean it,
because the same declaration served both arms.

The alternative is to declare `SummarizeV1` and `SummarizeV2` as separate Steps, and that is not a
workaround: it is two names for one concept, the `naming.naming_drift` this package reports.

## How is this different from Pydantic Graph?

It is not a competitor and does not want to be one. Pydantic Graph already owns steps, typed
execution, edges, branching, `map`, `join`, reducers, state, dependency injection, execution and
rendering — all of it well. `plan_types.execution.pydantic_graph` **compiles a Plan onto it**, using
its real primitives, and `tests/test_pydantic_graph.py` asserts both runtimes return the same
answer.

The difference is what a Step *is*. Theirs is executable — the function is both the node and the
implementation. Ours is a declaration, so several implementations are peers rather than one being
privileged and the rest overrides.

That shows up in the diagram. Same workflow — their `parallel_processing.py`, `map` → `square` →
join → total — rendered by each:

```
THEIRS — graph.render()                    OURS — render_mermaid(plan)

stateDiagram-v2                            flowchart TD
  state map <<fork>>                         IN_numbers(["numbers: list"])
  square                                     Square
  state reduce_list_append <<join>>          Total
  total                                      OUT_total(["total: int"])

  [*] --> map                                IN_numbers -- numbers --> Square
  map --> square                             Square -- squares --> Total
  square --> reduce_list_append              Total --> OUT_total
  reduce_list_append --> total
  total --> [*]
```

Two real differences, and neither is a rendering gap:

- **Theirs has no types on its edges.** It cannot: an edge carries whatever the function returned,
  and there is no name for it. Ours labels every edge with the Variable that flows.
- **Theirs draws the machinery** — `map <<fork>>` and `reduce_list_append <<join>>` are nodes. Ours
  draws the process; the fan-out is a property of `Square` and does not appear. Their picture
  answers *how will this execute*, ours answers *what is this workflow*. Both are correct.

And the fan-out is one declaration on the Step, in their vocabulary:

```python
class Square(Step):
    inputs, outputs = (number,), (squared,)   # int -> int, exactly their `square`
    map_over = (numbers, squares)             # list[int] in, list[int] out
```

Under `LocalRunner` that is a sequential loop. Compiled, it is their real `.map()` and
`join(reduce_list_append)`. **Same declaration, nothing edited.** Their documented output,
`[1, 4, 9, 16, 25]`, is asserted on both.

**→ [`examples/pydantic_graph_docs/`](examples/pydantic_graph_docs/)** — their own docs examples,
copied verbatim, run through this layer, with a control arm that uses no Plan at all.

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

HOW IT IS RUN          StepRunner ── Protocol       LocalRunner     ── here
                                                    Pydantic Graph  ── here, optional extra
                                                    Temporal        ── not built
                                                    LangGraph       ── not built

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

### Why a borrowed vocabulary rather than our own

Because a Plan is meant to be **handed over**, and a private schema cannot be.

`p-plan:Step` has a definition we did not write, published at an address anyone can resolve. That
makes a Plan legible to three audiences at once, none of whom need to read each other's code:

```
someone who owns WHAT THE PROCESS IS        writes and validates the Plan
                                            no prompt, no model, no function body, no runtime
                    │
                    ▼
someone who owns HOW IT IS PERFORMED        binds a Strategy — this model, that prompt
                    │
                    ▼
someone who owns HOW IT RUNS                picks the engine, the concurrency, the retries
```

They are working on **one artifact**, not three documents that have to be kept in sync. The Plan a
product owner can argue about in a PRD is the same object an engineer compiles onto Pydantic Graph —
because the thing that makes it arguable (typed Steps, named edges, no runtime detail) is the same
thing that makes it compilable.

And the vocabulary being **standard** rather than ours is what leaves the door open past this
package: another tool that speaks P-Plan means the same thing by `Step` that we do, and a model
asked to produce a `p-plan:Plan` is being asked for a term with a published definition it can be
held to — not a private shape it has to infer from examples.

⚠️ **A door, not a feature.** There is **no RDF import or export** — no Turtle, no JSON-LD, no
`rdflib` anywhere in the package. What exists is a vocabulary whose every citation is checked
against a vendored copy of the ontology. That is the precondition for interoperating with something
else that speaks P-Plan; it is not the interoperation, and this README is not going to imply
otherwise while `grep -rn rdflib plan_types/` returns nothing.

## Status — honest

**Works today:** typed Plans, the four invariant categories, `render_mermaid` (with an optional
Strategy overlay), P-Plan/PROV-O grounding with vendored ontologies, `Strategy` + `check_strategy`,
`LocalRunner`, `map_over` fan-out, and `to_pydantic_graph` — which emits Pydantic Graph's real
`.map()` and `join`, not a loop wearing the name. 158 tests.

### What it does NOT do, stated plainly

These are the first four objections anyone will raise, so they are answered here rather than waited
for:

| | |
|---|---|
| **cycles do not run** | A Plan may BE cyclic — it constructs, wires, renders, and `topology.acyclic` reports it. But it cannot execute, and the reason is not the toposort: **a Plan carries no termination predicate**. Their `Feedback.run()` returns `WriteEmail \| End[Email]` and the predicate lives in the node body, which is the right place for it and is theirs. `MultiStep.until` declares an iterative region; collapsing a strongly connected component into one is designed, not built. |
| **`Fork` / `Join` are not first-class** | Only `map_over`. Pydantic Graph 2.x has both as concepts; a Plan can currently declare a fan-out over a list and nothing else. |
| **no async runner** | `LocalRunner` is synchronous by decision and REFUSES an `async def` rather than returning an un-awaited coroutine. A compiled graph awaits it fine. |
| **at one arm, this is overhead** | Measured, not conceded reluctantly: with a single implementation and two steps, a Plan costs a declaration and buys nothing. It starts paying when there is a second arm, or a second reader. |

**Not built:** RDF import/export (no Turtle, no JSON-LD, no `rdflib` — the P-Plan grounding is a
checked vocabulary, not a serialization format), Temporal and LangGraph adapters, persistence,
retries, scheduling, concurrency, embedding-based similarity, agent-hook integration.

⚠️ **And the honest scale caveat.** Everything demonstrable here is small. The failure this is built
for shows up at volume: one codebase downstream has **18 variants of one extraction pipeline, 23
distinct step names, 47% of them used exactly once**, with `enrich` and `enrich_one_finding`
coexisting in the same file. A toy cannot show that, and this README will not pretend the toy does.

## Settled: PlanTypes is the product

Are semantic invariants the general product, with PlanTypes as the first ontology-grounded use
case — or is PlanTypes the product, with invariants as a subsystem inside it?

**Decided 2026-08-20: PlanTypes is the product.**

Not because the first framing is wrong, but because it cannot be argued yet. A general
semantic-invariant product needs a corpus of trial and error that does not exist, and it is hard to
grasp before it is demonstrated — which is a bad combination for the thing you lead with. *"Settle
the workflow plan before the execution details"* is one sentence, and it works today.

So `conceptlint` stays, as **a supporting semantic linter rather than a second product**. The code
is still arranged so it could split into its own package, and that option is worth keeping. What
changes is which one gets explained first, and which one the repo is named after.
