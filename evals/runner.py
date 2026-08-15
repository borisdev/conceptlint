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

from conceptlint.core.concept import Concept
from conceptlint.core.invariant import ConceptIssue
from conceptlint.core.lint import lint
from conceptlint.dataflow.invariants import NoExecutionFields, NoPrivateSynonym, PlanTimeOnly
from conceptlint.ontologies.pplan.concepts import Activity, Entity, Plan, Step, Variable

MINIMAL = pathlib.Path(__file__).resolve().parent / "minimal"
SEED = [Plan, Step, Variable, Activity, Entity]


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


def _concepts_declared_in(path: pathlib.Path) -> list[type[Concept]]:
    """Concepts the subject file declares, built from its AST — never by importing it.

    Importing would run the subject, and half of these files are deliberately wrong. It also lets a
    case describe code that cannot execute, which is the state a repo is in mid-conversation.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    made: dict[str, type[Concept]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        if "Concept" not in bases and not (bases & set(made)):
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
        parent = next((made[b] for b in bases if b in made), Concept)
        made[node.name] = type(node.name, (parent,), attrs)
    return list(made.values())


def _seed_by_name(name: str) -> type[Concept] | None:
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
            missing = want_rules - rules
            ok = not missing
            detail = "" if ok else f"expected {sorted(missing)}, got {sorted(rules) or 'nothing'}"
        else:
            ok = not issues
            detail = "" if ok else f"the FIX still flags {sorted(rules)}"
        out.append(CaseResult(f"{case.name}/{fname}", ok, detail,
                              [i.render() for i in issues]))
    return out


def _lint_file(path: pathlib.Path) -> list[ConceptIssue]:
    concepts = SEED + _concepts_declared_in(path)
    issues = list(lint(concepts))
    for inv in (PlanTimeOnly([path]), NoExecutionFields([path]), NoPrivateSynonym([path])):
        issues.extend(inv.check(concepts))
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
