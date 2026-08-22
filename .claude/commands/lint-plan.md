---
description: Run workflow-plan lint over this repo and report name-collision violations
---

Run `workflow-plan lint` against the current repository and report what it says.

## Run it

```bash
uv run workflow-plan lint .
```

If the console script is missing from the venv even though the package is installed — it has
happened — use the module rather than concluding the tool is absent:

```bash
uv run python3 -m workflow_plan.cli lint .
```

⚠️ `conceptlint` is RETIRED. It is still installed, and it exits 2 with the replacement command
rather than linting anything. If you see *"`conceptlint` is retired"*, that is not a broken venv.

## Report

Group by rule id. There are two families and they render identically, so name which one fired:

    ambiguity  canonical-reuse  near-duplicate  explicit-refinement
        the DECLARED vocabulary — classes inheriting `DeclaredTerm`

    naming.*  typing.*  topology.*  provenance.*
        ordinary Pydantic models read off disk, no base class required

For each violation give the two file:line locations and one sentence on whether it looks real or is
a known-deliberate pair.

If `.conceptlint-baseline` exists, compare the count and say whether it rose.

## ⚠️ Say what was NOT checked

This is the part that matters, because silence here has already been read as a clean codebase twice:

- **A subdirectory scan sees less than a whole-repo scan.** A class is only recognised if its base
  was found in the same run, so linting `libs/foo` alone misses every subclass whose base lives
  elsewhere. If you scanned a subdirectory, say so and say what that hides. (Issue #5. `BaseModel`,
  `RootModel` and `DeclaredTerm` are exempt — they are recognised by name, whatever the file order.)
- **`PlanStep` subclasses may be invisible.** A user's own Step base is subject to the file-order
  problem above. If the repo declares Steps and none appear in the output, report that as NOT
  CHECKED, not as clean.
- **A zero count is not automatically good.** Exiting 0 with no output can mean "nothing to look at"
  as easily as "nothing wrong". Distinguish the two.
- **A count that FELL is not automatically good either.** It can mean a finding stopped existing, or
  it can mean discovery stopped finding it — measured 2026-08-22, when moving a base class between
  directories silently dropped two real duplicates and the number read as progress.

Finish with one line: what is worth acting on, and what is noise.
