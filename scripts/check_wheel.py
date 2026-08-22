"""Import every shipped package from the BUILT WHEEL, run from outside the source tree.

The only check in this repo that touches the artifact. Every other one imports the working tree,
where `[tool.hatch.build.targets.wheel] packages` is never consulted — which is exactly how the
tree between v0.3.1 and v0.4.0 produced a wheel containing neither `workflow_plan` (never listed) nor
`conceptlint.dataflow` (deleted), while 116 tests passed throughout.

⚠️ An editable install cannot catch this by construction: it puts the source tree on `sys.path`, so
the module resolves regardless of what the build config says. Run this from a temp dir, never the
repo, or the tree satisfies the import and the check passes on a broken wheel.
"""
import importlib
import pathlib
import sys

#: Every module a consumer is entitled to import. Add to this when a package starts shipping one.
REQUIRED = [
    "workflow_plan",
    "workflow_plan.invariants",
    "workflow_plan.plan",
    "workflow_plan.execution",
    "conceptlint.core.lint",
]

#: Names re-exported at the top level, so a consumer's import line is one swap.
REQUIRED_NAMES = ["Plan", "Step", "Variable", "check_arms", "PlanError", "validate",
                  "render_mermaid"]


def main() -> int:
    cwd = pathlib.Path.cwd().resolve()
    if (cwd / "workflow_plan").is_dir():
        print(f"REFUSING to run inside the source tree ({cwd}) — the tree would satisfy every "
              f"import and this check would pass on a broken wheel.", file=sys.stderr)
        return 2

    problems = []
    for name in REQUIRED:
        try:
            importlib.import_module(name)
        except Exception as exc:
            problems.append(f"{name}: {type(exc).__name__}: {exc}")

    if not problems:
        import workflow_plan
        missing = [n for n in REQUIRED_NAMES if not hasattr(workflow_plan, n)]
        if missing:
            problems.append("workflow_plan is missing top-level names: " + ", ".join(missing))

    if problems:
        print("NOT IN THE WHEEL:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(f"every required module imports from the built wheel (cwd={cwd})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
