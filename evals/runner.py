"""Run the semantic evals: every `before.py` must FLAG, every `after.py` must PASS.

Tests verify mechanics; evals verify semantic behaviour (§20). The split matters because a check can
be mechanically perfect and semantically useless — the previous project shipped a scorer that ran
correctly and measured whether an agent had echoed its own vocabulary.

## The shape

    evals/minimal/<failure>/
        before.py         the mistake — must produce the named rules
        after.py          the fix     — must produce nothing
        expected.yaml     which rules before.py must trip
        provenance.yaml   where this came from; git proves it happened

⚠️ Both directions are required. A case that only asserts the flag cannot tell you the documented
fix actually works — and a fix that does not silence the finding is how someone learns to ignore a
linter. `after.py` is the more valuable half.
"""
from __future__ import annotations

import ast
import pathlib
import sys
from dataclasses import dataclass, field

from workflow_plan.naming.declared_term import DeclaredTerm
from conceptlint.core.invariant import ConceptIssue
from conceptlint.core.lint import lint
from workflow_plan.invariants import validate
from workflow_plan.invariants.typing.plan_time_only import PLAN_TIME_ONLY
from workflow_plan.naming.records import discover_models
from workflow_plan.plan import MultiStep, Plan, Service, Step, Variable

MINIMAL = pathlib.Path(__file__).resolve().parent / "minimal"

#: The vocabulary every subject file is checked AGAINST. Was five toy `Concept` declarations in
#: `conceptlint/ontologies/pplan/`; it is now the real types, which is the point of the base — a
#: case that reuses a canonical name is measured against the name the package actually ships.
SEED = [Plan, Step, Variable, Service, MultiStep]

#: eval rule name -> the rule that implements it today, or None if nothing does.
#:
#: ⚠️ Three of these four are None, and that is a FINDING rather than a formatting choice. This
#: runner has not imported since `e6aa37c` ("SemanticInvariant replacing Concept"), which removed
#: `PlanTimeOnly`, `NoExecutionFields` and `NoPrivateSynonym` — the class-based rules it called.
#: Nothing collected it (`testpaths` includes `evals/`, but there is no `test_*.py` there), so an
#: ImportError sat in the semantic half of the test strategy for as long as it took to notice.
#:
#: A case whose rule does not exist reports NOT CHECKED and FAILS. It must never report `ok`: "we
#: did not look" and "we looked and it was fine" rendering the same is the inversion this whole
#: package exists to prevent.
IMPLEMENTED_BY: dict[str, str | None] = {
    "near-duplicate": "near-duplicate",           # conceptlint.core.lint.NearDuplicate
    "plan-time-only": "typing.plan_time_only",    # workflow_plan.invariants.typing
    "no-private-synonym": None,                   # removed in e6aa37c, never rebuilt
    "no-execution-fields": None,                  # removed in e6aa37c, never rebuilt
}


def _yaml(path: pathlib.Path) -> dict[str, object]:
    """A two-line YAML reader. Adding PyYAML for `key: value` would be a dependency for nothing."""
    out: dict[str, object] = {}
    key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            out.setdefault(key, []).append(line[4:].strip())    # type: ignore[union-attr]
        elif ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            out[key] = val.strip() or []
    return out


def _concepts_declared_in(path: pathlib.Path) -> list[type[DeclaredTerm]]:
    """Concepts the subject file declares, built from its AST — never by importing it.

    Importing would run the subject, and half of these files are deliberately wrong. It also lets a
    case describe code that cannot execute, which is the state a repo is in mid-conversation.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    made: dict[str, type[DeclaredTerm]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        if "DeclaredTerm" not in bases and not (bases & set(made)):
            continue
        attrs: dict[str, object] = {"ID": "", "DEFINITION": "", "RATIONALE": "r",
                                    "REFINES": None, "ALSO_KNOWN_AS": ()}
        for stmt in node.body:
            targets = (stmt.targets if isinstance(stmt, ast.Assign)
                       else [stmt.target] if isinstance(stmt, ast.AnnAssign) else [])
            for t in targets:
                if not isinstance(t, ast.Name) or stmt.value is None:
                    continue
                if t.id == "REFINES" and isinstance(stmt.value, ast.Name):
                    attrs["REFINES"] = made.get(stmt.value.id) or _seed_by_name(stmt.value.id)
                else:
                    try:
                        attrs[t.id] = ast.literal_eval(stmt.value)
                    except (ValueError, SyntaxError):
                        pass
        parent = next((made[b] for b in bases if b in made), DeclaredTerm)
        made[node.name] = type(node.name, (parent,), attrs)
    return list(made.values())


def _seed_by_name(name: str) -> type[DeclaredTerm] | None:
    return next((c for c in SEED if c.__name__ == name), None)


@dataclass
class CaseResult:
    name: str
    passed: bool
    detail: str = ""
    issues: list[str] = field(default_factory=list)


def run_case(case: pathlib.Path) -> list[CaseResult]:
    expected = _yaml(case / "expected.yaml")
    want_rules = {r for r in expected.get("rules", [])}         # type: ignore[union-attr]
    out: list[CaseResult] = []

    for fname, must_flag in (("before.py", True), ("after.py", False)):
        path = case / fname
        if not path.exists():
            continue
        issues = _lint_file(path)
        rules = {i.rule for i in issues}
        if must_flag:
            # A rule nobody implements cannot be missing from the output for a reason the CODE is
            # responsible for. Separate the two, and never let the second read as a pass.
            unimplemented = sorted(r for r in want_rules if not IMPLEMENTED_BY.get(r))
            live = {IMPLEMENTED_BY[r] for r in want_rules if IMPLEMENTED_BY.get(r)}
            missing = live - rules
            ok = not missing and not unimplemented
            detail = ""
            if unimplemented:
                detail = f"NOT CHECKED — no rule implements {unimplemented}"
            elif missing:
                detail = f"expected {sorted(missing)}, got {sorted(rules) or 'nothing'}"
        else:
            ok = not issues
            detail = "" if ok else f"the FIX still flags {sorted(rules)}"
        out.append(CaseResult(f"{case.name}/{fname}", ok, detail,
                              [i.render() for i in issues]))
    return out


def _lint_file(path: pathlib.Path) -> list[ConceptIssue]:
    """Every rule that can run against one subject file, as `ConceptIssue`s.

    Two surfaces, both required: the declared vocabulary (SEED plus whatever the file declares) for
    the concept rules, and the file's ordinary models read off disk for the record rules. A case
    like `variable_entity_collapse` is a plain frozen dataclass — invisible to the first surface and
    the whole point of the second.
    """
    issues = list(lint(SEED + _concepts_declared_in(path)))
    issues += [ConceptIssue(v.invariant_id, v.message)
               for v in validate(discover_models(path), (PLAN_TIME_ONLY,))]
    return issues


def main() -> int:
    cases = sorted(p for p in MINIMAL.iterdir() if p.is_dir())
    if not cases:
        print("no eval cases found — a runner that finds nothing passes vacuously", file=sys.stderr)
        return 1

    results = [r for c in cases for r in run_case(c)]
    for r in results:
        print(f"  {'ok  ' if r.passed else 'FAIL'}  {r.name}{'  ' + r.detail if r.detail else ''}")
    failed = [r for r in results if not r.passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} eval assertions passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
