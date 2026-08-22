"""`workflow-plan` — the command line entry point.

Was `conceptlint`, a name pointing at `Concept`, which is retired. The package, the repo and the
command now say the same word.

## One command, subcommands under it

    workflow-plan lint [path]      the two lint surfaces — declared terms, and ordinary Pydantic

`lint` is the only subcommand today and the parser still demands one. A bare `workflow-plan` that
defaulted to linting would make "I typed the wrong thing" and "your code is clean" produce the same
silence, which is the failure this package exists to report.

⚠️ The implementation stays in `conceptlint.core.lint`. Moving it is the fold-in, not the rename,
and doing both in one pass would put a 1,200-line diff and a package move in the same review. The
import is at module level and does NOT cycle: `workflow_plan/__init__.py` does not import this
module, so by the time anything reaches `conceptlint.core.lint`'s `workflow_plan` imports, that
package is fully initialised.
"""
from __future__ import annotations

import sys

from conceptlint.core.lint import main as _lint

#: subcommand -> (handler, one-line help). The handler takes the remaining argv and returns a code.
SUBCOMMANDS = {
    "lint": (_lint, "check declared terms and ordinary Pydantic models for name collisions"),
}

RETIRED = {
    #: old console script -> what replaced it. Kept as an ERROR rather than an alias: a retired name
    #: that still works is how two vocabularies survive, and this repo has a rule about that.
    "conceptlint": "workflow-plan lint",
}


def _usage() -> str:
    lines = ["usage: workflow-plan <command> [args]", "", "commands:"]
    lines += [f"  {name:<10} {help_}" for name, (_, help_) in SUBCOMMANDS.items()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(_usage(), file=sys.stderr)
        # ⚠️ Non-zero even for --help. A CLI that exits 0 having done nothing is indistinguishable
        # from one that ran and found nothing, and every gate in this repo reads the exit code.
        return 2

    command, rest = args[0], args[1:]
    if command not in SUBCOMMANDS:
        print(f"unknown command: {command}\n\n{_usage()}", file=sys.stderr)
        return 2
    handler, _ = SUBCOMMANDS[command]
    return handler(rest)


def retired() -> int:
    """Entry point for every console script this one replaced. Fails loudly, names the successor."""
    called = sys.argv[0].rsplit("/", 1)[-1]
    replacement = RETIRED.get(called, "workflow-plan lint")
    print(f"`{called}` is retired — use `{replacement}`.\n"
          f"The name pointed at `Concept`, which is now `DeclaredTerm`; a command named after a "
          f"dead type is a second vocabulary that keeps working.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
