# workflow-plan: current state

**Updated 2026-08-22, after the rename pass landed.** This file previously described that pass as
work to be done. It is done — issue #6 is closed, #7 merged, `v0.8.0` tagged. Left uncorrected it
would have been the first thing a new session read and the first thing it got wrong.

## The vocabulary, as it actually is

```python
from workflow_plan import (Plan, PlanStep, Variable, PlanDependency, MultiStep,
                           Invariant, Violation, check, check_arms, render_mermaid, substitutable)
from workflow_plan.execution import Strategy, StepRunner, SequentialRunner, run, check_strategy
from workflow_plan.ontology import Run, Activity, Entity, Agent
```

Renamed from what older docs and commit messages say:

    plan_types -> workflow_plan     Step -> PlanStep        Service -> PlanDependency
    SemanticInvariant -> Invariant  validate() -> check()   LocalRunner -> SequentialRunner
    Concept -> DeclaredTerm         execute() -> run()

`DeclaredTerm` is the shared base of the plan types. It carries `ID`, `DEFINITION`, `RATIONALE`,
`ONTOLOGY_IRI`, `REFINES`, `ALSO_KNOWN_AS` — so a retired word stays dead, and discovery stops
depending on which file the walker reaches first.

⚠️ **`Strategy` is unchanged and deliberately so.** Gang of Four, read without explanation.

## Verify in one command

```bash
uv run pytest -q        # 174
```

Anything that says `plan_types`, `Step` or `validate()` predates this and is describing a package
that no longer exists under those names.

## Who the audience is, because it settles naming arguments

Pydantic AI and Pydantic Graph developers. That is why `run()` and not `execute()`; why `Executor`
and `Orchestrator` were rejected as Airflow/Temporal vocabulary; and why `PlanStep` was worth the
churn — `pydantic_graph.Step` exists and means an executable node.

Check what **they** call a thing before reaching for a general term.

## What was decided NOT to build, and why

These sound obviously good and get re-proposed. They were tried and rejected on evidence:

- **`CoherenceInvariant`, `coherence_check`, `PlanCoherence`.** No example exists of a Plan that
  passes all rules and is incoherent. The closest — two `str` Variables and a step wired to the
  wrong one — is the types being too weak, not a coherence failure. Naming a type after an
  undefined property is the overclaim this library reports.
- **A holistic `check_everything(plan)`.** The rules take three different subjects: a `Plan`,
  classes read from source, and a completed run's `Activity` records. What is buildable is
  *completeness* — one command that runs everything applicable and reports the rest NOT CHECKED.
  That is worth doing and is not coherence.

## Next, in order

1. **One diagram showing a base plan with its per-step variations.** `render_family` covers
   whole-plan alternatives; this is the per-step analogue and the more useful one.
2. **Logfire instrumentation.** `Activity` already carries `step_name`, `started_at`, `ended_at`,
   `duration_secs`, `outcome`, `error` — that is a span; `Run` (`prov:Bundle`) is the trace.
   `pydantic_graph.GraphBuilder` already takes `auto_instrument`, so this extends a mechanism their
   users have rather than adding one. One Plan, three Strategies, one Logfire query: a regression
   attributable to a step AND an arm, because the step is a declared identity that survives its
   implementation changing.

## README work still outstanding

Agreed but not done:

- Open with **their** `simple_counter.py`, then the same thing as a Plan. Recognition before novelty.
- Reframe: *describes the SHAPE of a workflow, deliberately leaving out execution — retries,
  durability, fan-in/out, concurrency — so the algorithm can be worked on separately from the
  execution.*
- **Demote `to_pydantic_graph`.** Lead with the hand-written wrapper: you write the graph node, its
  body calls the Plan's bound implementation. Writing the graph by hand is easy, and a compiler that
  generates it invites "why would I let you generate my graph?", which has no good answer.
- Say which parts of the examples are theirs and which are ours. `square` is theirs;
  `square_exact` / `square_by_addition` / `square_cheap` and `Total` are ours.

## Two hazards on this VM

**A corpus run may still be live** from `~/workspace/nobsmed-v2`, using that checkout's `.venv`.
In **that** tree: no `git checkout`, no `uv sync`, no `uv lock`, no `uv run` — any can mutate
`.venv` under running workers. Use `git worktree add`. Check first:

```bash
pgrep -af "worker.py --queue-db"
```

This repo has no live job. Work here freely.

**A PreToolUse hook blocks writes.** `~/.claude/settings.json` runs
`conceptlint.integrations.pre_write` on every Write/Edit; it exits 2 and refuses a write that
introduces a Pydantic model duplicating an existing one. Intended. It only sees new **Pydantic
models** — a new `PlanStep` subclass produces nothing.

## The most reusable lesson from the day

**A blast radius measured before a merge is measured against the wrong tree.** A handoff said five
Steps needed migrating; it was true of `main` when written, and the merge made it 27. Twice in one
day a number was quoted from a tree that had moved underneath it.

Name the tree with the number: *"27 Steps on the post-merge tree"* survives. *"27 Steps"* does not.
