---
description: Run conceptlint over this repo and report semantic-invariant violations
---

Run conceptlint against the current repository and report what it says.

## Run it

The console script is often missing from a venv even when the package is installed, so fall back to
the module rather than concluding the tool is absent:

```bash
uv run conceptlint . 2>&1 || uv run python3 -c '' 2>/dev/null
```

If `conceptlint: command not found`, use the module directly with an interpreter that can import it:

```bash
/home/borisdev/workspace/conceptlint/.venv/bin/python3 - <<'PY'
import sys
from conceptlint.core.lint import main
sys.argv = ["conceptlint", "."]
raise SystemExit(main())
PY
```

## Report

Group by invariant id (`naming.ambiguous_reference`, `naming.naming_drift`, `typing.*`,
`topology.*`, `provenance.*`). For each violation give the two file:line locations and one sentence
on whether it looks real or is a known-deliberate pair.

If `.conceptlint-baseline` exists, compare the count and say whether it rose.

## ⚠️ Say what was NOT checked

This is the part that matters, because silence here has already been read as a clean codebase twice:

- **A subdirectory scan sees less than a whole-repo scan.** A class is only recognised if its base
  class was found in the same run, so linting `libs/foo` alone misses every subclass whose base
  lives elsewhere. If you scanned a subdirectory, say so and say what that hides.
- **`Step` subclasses are frequently invisible.** They are not Pydantic models, so they only appear
  when their base happens to be discovered first. Check whether any showed up; if the repo declares
  Steps and none appear in the output, report that as NOT CHECKED, not as clean.
- **A zero count is not automatically good.** `conceptlint <dir>` exiting 0 with no output can mean
  "nothing to look at" as easily as "nothing wrong". Distinguish the two.

Finish with one line: what is worth acting on, and what is noise.
