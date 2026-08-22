# Handoff: the rename pass

**Written 2026-08-22.** For a session starting cold. The WHAT is
[issue #6](https://github.com/borisdev/workflow-plan/issues/6) — every rename, with the reason each
was chosen, and the order to do them in. This file is the context that issue assumes.

## Where things are

```
repo      github.com/borisdev/workflow-plan     (renamed from plan-types today; the old URL 301s)
main      green, tagged v0.7.0, 164 tests, working tree clean
packages  plan_types/  — the library
          conceptlint/ — the linter, being folded in
```

`v0.7.0` removed and **retired** `Step.run()`. A subclass declaring `run` raises at import. That is
deliberate: a retired name that still parses is worse than one that breaks the build.

## ⚠️ Read before touching anything on this VM

**A corpus run is live.** Three workers, from `/home/borisdev/workspace/nobsmed-v2`, using that
checkout's `.venv`:

```
.venv/bin/python apps/extraction-worker/worker.py --queue-db data/corpus_queue.sqlite --run-id corpus2
```

In **that** checkout: no `git checkout`, no `uv sync`, no `uv lock`, no `uv run`. Any of them can
mutate `.venv` under running workers. One session already switched branches there and pointed a
running job at code missing its own fixes; nothing broke because nothing restarted, which is luck.
Use `git worktree add` — a worktree gets its own `.venv`.

This repo (`~/workspace/conceptlint`) has no live job. Work here freely.

**Two other sessions are active on nobsmed**, with PRs open. Do not touch `libs/workflow` or
`libs/case_build`; a `cutting-edge → main` merge is pending Boris's demo QA.

## Nothing downstream sees this work

nobsmed pins `plan-types = { git = ..., tag = "v0.6.0" }` in `libs/workflow/pyproject.toml` and
`libs/case_build/pyproject.toml`. The only consumer of `v0.7.0` is this repo. So every rename in #6
is internal until someone bumps a tag, and no migration is owed.

## Three things that cost time today — do not rediscover them

**`lint.py`'s `main()` is not a duplicate.** It already imports `AMBIGUOUS_REFERENCE` and
`NAMING_DRIFT` from `plan_types` and runs them over ordinary Pydantic models; its own comment calls
the two "two surfaces on ONE engine". Deleting the file wholesale removes the CLI, the CI gate and
`/lint-plan` in one move. Only the four `Invariant` subclasses are redundant, and they keep their
logic — they just read `DeclaredTerm`s instead of `Concept`s.

**`drift.py` has no equivalent.** It compares a name's *meaning* across two commits. Every rule in
`plan_types` reads a single snapshot. Keep it.

**Step subclasses are discovered by accident.** `discover_models` records a class only if its base
was already found, walking files alphabetically. Our Steps resolve via an **unrelated** `class
Step(Concept)` in `conceptlint/ontologies/pplan/concepts.py`, which sorts before `examples/`. Delete
that file without making `DeclaredTerm` the real base first and Step linting silently stops
reporting. Issue #5.

## How to check your work

```bash
uv run pytest -q                        # 164 today
uv run conceptlint .                    # 6 violations, matching .conceptlint-baseline
uv run python3 -m examples.hello.flow
uv sync --extra pydantic-graph && uv run python3 -m examples.pydantic_graph_docs.stage3_map_join
```

⚠️ The `conceptlint` console script goes missing from `.venv` sometimes even when the package is
installed. Fall back to the module rather than concluding the tool is absent:

```python
import sys; from conceptlint.core.lint import main
sys.argv = ["conceptlint", "."]; raise SystemExit(main())
```

⚠️ **The CI self-lint gate lints `.`, not one directory, and that is deliberate.** It was
`plan_types/` only, and a duplicate `Square` sat unreported in `examples/` until someone asked
whether the linter was earning its place. The six baseline violations are known-deliberate pairs.

## A PreToolUse hook is installed and it BLOCKS

`~/.claude/settings.json` runs `conceptlint.integrations.pre_write` on every Write/Edit. It exits 2
and refuses a write that introduces a Pydantic model duplicating an existing one. That is intended.
If it fires, read the message — it names the existing model and its file:line.

It uses the `args` exec form on purpose. With a shell string, `2>/dev/null` discards the message and
`|| true` masks the exit code; either leaves a hook that runs and reports nothing.

⚠️ It only sees **new Pydantic models**. A new `PlanStep` subclass produces nothing.

## What "done" looks like

Issue #6, in its stated order, ending at `v0.8.0`. Then two features, in this order:

1. **One diagram showing a base plan with per-step variations.** `render_family` covers whole-plan
   alternatives; this is the per-step analogue and the more useful one.
2. **Logfire instrumentation.** `Activity` already carries `step_name`, `started_at`, `ended_at`,
   `duration_secs`, `outcome`, `error` — that is a span, and `Run` (`prov:Bundle`) is the trace.
   `pydantic_graph.GraphBuilder` already takes `auto_instrument`, so this extends a mechanism their
   users have rather than adding one.

## The audience, because it decides naming arguments

Pydantic AI and Pydantic Graph developers, and Samuel Colvin. That is why `run()` rather than
`execute()`, why `Executor` and `Orchestrator` were rejected as Airflow/Temporal vocabulary, and why
`PlanStep` is worth the churn — `pydantic_graph.Step` exists and means an executable node.

When a naming question comes up, check what **they** call it before reaching for a general term.
