# A Step declares, a Strategy implements, a Runner executes

Four ChatGPT handoffs about this repo, consolidated. They converge on one decision, contradict each
other in three places, and one of them contradicts this repo's own vocabulary. This doc is the
decision, the disagreements resolved, and what was measured rather than argued.

---

## The decision, in code

```diff
  class Step(Generic[InputT, OutputT]):
      inputs:  ClassVar[tuple[Variable[Any], ...]] = ()
      outputs: ClassVar[tuple[Variable[Any], ...]] = ()

-     def run(self, **values: Any) -> Any:
-         """Execute. Keyword arguments are the input Variables, by name."""
-         raise NotImplementedError
```

```python
# how it is performed — outside the declaration, chosen per execution
fast    = {MakeOutline: outline_by_sentence, Summarize: summarize_fast}
precise = {MakeOutline: outline_by_sentence, Summarize: summarize_precise}

execute(plan, {"document": doc}, LocalRunner(fast))
execute(plan, {"document": doc}, LocalRunner(precise))
```

**The `plan` object is not touched between those two lines.**

---

## Why — the argument that actually carries it

The weak argument is YAGNI: nothing called `run()`, so delete it. True, and it sounds like tidying.

The real argument is that **the signature was a false claim about the domain**:

```python
def run(self, **values: Any) -> Any:   # the implementation is A METHOD ON THIS CLASS
    raise NotImplementedError          # so there is one, and any second is an override
```

`ExtractClaims` is one stable operation with several ways to perform it — a cheap model, an
expensive one, an ensemble — and none of them is the *real* one that the others override. A method
on the class privileges whichever implementation got there first.

The alternative people reach for when the method is in the way is worse:

```python
class ExtractClaimsV1(Step): ...    # not three operations.
class ExtractClaimsV2(Step): ...    # three names for one concept —
class ExtractClaimsEnsemble(Step): ...  # `naming.naming_drift`, committed inside the
                                        # package built to report it.
```

So the implementation moves out of the declaration, and *which* implementation runs becomes a
property of an execution rather than of the process.

---

## ⚠️ One word was already taken, and three of the handoffs used it wrong

Every handoff calls the Step→implementation mapping **"bindings"**. This repo already has that word:

    binding    how VARIABLES connect STEPS      plan_types/plan/bindings.py — producers, consumers,
                                                edges, execution_order
    ???        which IMPLEMENTATION performs     the new thing
               a Step

Two concepts, one word, in one package. That is `naming.ambiguous_reference` — *one name, many
concepts* — and it would have shipped inside the module written to catch it.

**Shipped as `Strategy`**, which is the handoffs' own gloss (*"different strategies for performing
the same operation"*) and is what makes `plan_types/plan/bindings.py` still mean exactly what it
meant. One rename reverses it if you disagree; the thing that must not happen is the collision.

Grounding, stated plainly: P-Plan and PROV-O have **no term** for *"the code that will perform this
Step if it runs."* `p-plan:Step` is the intended operation, `prov:Activity` is one execution of it,
and this is neither. So `Strategy` is ours, deliberately uncited — the same call as `Step.uses`, and
for the same reason.

---

## Where the four handoffs disagree

| question | the positions | resolution, and why |
|---|---|---|
| where the implementation attaches | **A**: `Step.run()`, "portable domain vocabulary" · **B**: not on Step, `bind()` + callable · **C**: `step.impl`, called by a Protocol · **D**: a `bindings` map, resolved by a runner | **D.** A privileges one implementation. C puts strategy back on the declarative graph, which C's own author warns against three paragraphs later. B and D are the same idea; D is the one with a worked eval-arm example. |
| sync or async | **B**: "PlanTypes should remain sync/async-neutral" · **C, D**: `async def run(...)` in the Protocol | **Sync.** An `async def` on the Protocol is not neutral — it forces every implementation of every Step to be a coroutine, including `lambda x: x + 1`. An `AsyncStepRunner` when a real async implementation exists. |
| how the implementation is called | **D**: `extract_claims_v1(paper: Paper)` — positional · **D, same page**: `impl(**inputs)` — keyword | **Keyword**, and `Variable.name` therefore becomes part of the contract. A Step with three inputs called positionally is one reorder away from a mis-wire the types cannot catch when two inputs share a type. `check_strategy` reports a parameter-name mismatch at declaration time. |
| repo layout | **A**: top-level `plan/` + `execution/` | Adopted as `plan_types/plan/` + `plan_types/execution/`, which is where `plan/` already was. |
| runtime state and deps | **A**: `EvidenceBuildState`, `NoBSmedDeps` injected per execution | **Not built.** No caller. Note that `plan_types/plan/service.py` is already the *plan-time* half — what a Step needs reachable — and `typing.plan_time_only` refuses the runtime half onto plan types by rule. |

---

## Evidence — measured before the change, not argued after

**Nothing called `run()`.** Not in `plan_types/`, `tests/`, `evals/` or `examples/`.

**The only implementation of it in this repo did not import.**
`examples/evidence_case_graph/flow.py` still declared `consumes`/`produces`, retired 2026-08-16:

```
TypeError: ParseStudyStep.consumes is retired — use `inputs`, a TUPLE of Variables.
```

It had been dead since the P-Plan DAG correction, and **no test imported it**, so no check could
have caught that or the second fault on the line below — `def run(self, value: Study)`, positional,
against a base class whose docstring warns positional args silently mis-wire. An example nobody
imports is not an example, it is a claim. `tests/test_execution.py::test_examples_import_and_run`
now runs both examples end to end.

**The type contradicted its own module.** `plan_types/plan/plan.py` has said this the whole time:

> ⚠️ `run()` is not the centre of this … An execution adapter wraps Steps from outside. Never the
> reverse.

**Downstream, 15 overrides that all raise.** nobsmed's `plans.py`, every one
`raise NotImplementedError(_DECLARATION_ONLY)`.

---

## What shipped

```
plan_types/plan/step.py          run() removed; `run` added to _RETIRED
plan_types/execution/strategy.py Strategy, Implementation, check_strategy
plan_types/execution/runner.py   StepRunner Protocol — sync, runtime_checkable
plan_types/execution/local.py    LocalRunner, execute, ExecutionError
examples/hello/flow.py           NEW — domain-free, two arms, the README's 60 seconds
examples/evidence_case_graph/    rewritten to nobsmed's real fan-in shape, two arms
tests/test_execution.py          NEW — 20 tests
scripts/check_wheel.py           plan_types.execution added to REQUIRED
README.md                        60 seconds, the four-layer diagram, Status
```

142 tests pass, up from 122.

**`_RETIRED`, not deletion.** Deleting `run()` would let a subclass declare it again and get the
privileged implementation back with nothing to say so. The error names its replacement:

```
TypeError: AskModelForCausalMap.run is retired — use a Strategy. a Step DECLARES a
transformation; it does not perform one. A method here is one implementation privileged over
every other, so a second way of doing the same operation becomes an override rather than a peer.
```

⚠️ The old `__init_subclass__` built its message with `'Input' if old == 'consumes' else 'Output'`,
so retiring a **third** name would have explained it as being about `hasOutputVar`. Each retired
name now carries its own sentence.

**What the runner refuses, loudly, rather than accepting quietly:**

| | why |
|---|---|
| an `async def` implementation | returns a coroutine — truthy, with a repr, flowing onward as though it were data |
| a Step with 2 outputs whose impl returns 1 value | else one Variable holds the whole tuple and the mismatch surfaces three Steps later |
| a Step with 0 outputs whose impl returns something | discarding it hides a wrong declaration *or* a wrong implementation |
| a produced value of the wrong declared type | plain classes only — parameterized generics are reported **NOT CHECKED**, never as a pass |
| two Variables sharing a name | a Variable is `(name, type)`, so two can differ in type and collide in a name-keyed environment |

---

## ⚠️ Breaking change for nobsmed — measured, and it corrects my own earlier note

I previously wrote that nobsmed's 15 `run()` overrides *"still import and work as ordinary methods."*
**That is wrong.** It described deleting `run()`; what shipped retires it, which is stricter. Run
against the built wheel, using `plans.py`'s exact class shape:

```
BREAKS AT IMPORT: TypeError: AskModelForCausalMap.run is retired — use a Strategy...
without run(): Plan('arm', 1 steps, 2 variables)
```

**Contained by the pin.** nobsmed has `plan-types = { git = ..., tag = "v0.6.0" }`
(`pyproject.toml:68`), so nothing moves until that tag is bumped — deliberately, not by luck.

On bump, one nobsmed commit fixes all of it:

| site | what happens | fix |
|---|---|---|
| `plans.py` — 15 `def run(...)` overrides | **ImportError at module import** | delete all 15 |
| `plans.py` — `_DECLARATION_ONLY` | orphaned | delete |
| `test_plans.py:56-65` — asserts `run()` raises | tests a method that no longer exists | delete the test |
| `plan_diagram.py:190` — "Every `run()` raises" | stale prose | reword |
| anything **calling** `Step.run` | none exist — verified by grep | — |

**A loud break is the right one here.** The quiet alternative leaves 15 methods in the file that a
reader reasonably takes as evidence that Steps execute — which is the thing that was false. And the
fix is mechanical: delete, do not rewrite.

---

## Advice — where I would push back on the handoffs

**"A dictionary plus a LocalRunner is sufficient to prove the architecture."** It proves the
architecture; it does not give it a consumer. nobsmed's builders are not decomposed into Steps
(`plans.py` says so and calls it separate work with its own risk), so **nothing in production binds
a Strategy yet.** The examples and tests are real; the production caller is not there. Worth
knowing before this reads as load-bearing.

**Handoff D §1 asks to edit nobsmed's `plans.py`.** Different repo, different PR, and gated on the
tag bump above.

**`Step(Generic[InputT, OutputT])` is still declared and is now entirely vestigial.** `InputT` and
`OutputT` are unused — the README already says that one-in-one-out signature "died to a real
builder." Left alone here to keep this diff about one thing; it should go.

**Do not add the Temporal / LangGraph / Pydantic Graph adapters yet.** Each is a real dependency
bought to serve zero callers. The Protocol is three lines; an adapter can be written the day someone
has a workflow that needs durability.

---

## Not built, and what would justify each

- **`AsyncStepRunner`** — one real async implementation to run. Today the honest state is that async
  is *refused*, not *supported*, and it says so at the call site.
- **Strategy per Step *instance*** — a Plan holding two instances of one Step class that need
  different implementations. Keyed on the class today.
- **Return-type checking for generics** — `list[Finding]` cannot be tested by `isinstance`. Reported
  NOT CHECKED. A real mis-wire that slipped through would justify a deeper check.
- **Runtime state / dependency injection** (`EvidenceBuildState`, `NoBSmedDeps`) — a Step
  implementation that genuinely needs per-execution context beyond its closure.

---

## Deliberately out of scope

The **A/B counterfactual experiment** from the process-spec handoff: fork an official Pydantic Graph
example, evolve it with Claude Code alone vs Claude Code + PlanTypes, same requirement changes to
both arms, and measure. That is GTM evidence, not this decision, and it deserves its own issue.

`docs/counterfactual.md`'s rule applies to it in advance: **`no_effect` and `refutes` are results.**
The claim to test is *does a separate typed process specification help a coding agent preserve
coherence as requirements evolve* — not *PlanTypes makes Claude better.*
