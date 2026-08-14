"""Semantic invariants over the dataflow vocabulary — the ones a type signature cannot express.

Three rules, and each exists because the distinction it guards is one this codebase has already
watched collapse:

    plan-time-only          an Activity or Entity appearing in a Plan
    no-execution-fields     a Variable growing timestamps and actual values
    no-private-synonym      a class named for a concept that already exists

⚠️ These read DECLARATIONS. They are not runtime assertions and they do not import the code under
test where it can be avoided — a linter that must import cannot run on the broken state it exists
to describe.
"""
from __future__ import annotations

import ast
import pathlib
import re
from typing import Iterable, Sequence

from conceptlint.core.concept import Concept
from conceptlint.core.invariant import ConceptIssue, Invariant
from conceptlint.ontologies.pplan.concepts import REALIZES

#: Fields that mean "this already happened". A plan-time type carrying one has become a runtime
#: type without anyone renaming it, which is the Variable/Entity collapse.
EXECUTION_FIELDS = frozenset({
    "started_at", "ended_at", "finished_at", "duration", "elapsed",
    "run_id", "outcome", "error", "content_hash", "value", "actual",
})

#: Plan-time class names, and the runtime names that must not appear beside them in a Plan.
_RUNTIME_NAMES = frozenset({r.__name__ for r in REALIZES})


class PlanTimeOnly(Invariant):
    """A Plan holds Steps and Variables. Never Activities or Entities."""

    ID = "plan-time-only"
    LAW = "one-concept-one-meaning"
    WHY = ("A graph that cannot tell 'we parse papers' from 'we parsed pmid:123 at 10:04' answers "
           "neither question. Once a runtime object is in the definition graph, every consumer "
           "downstream has to guess which kind of node it is holding.")

    def __init__(self, roots: Sequence[pathlib.Path] = ()) -> None:
        self.roots = tuple(roots)

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        for path in _python_files(self.roots):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                # `plan.steps.append(activity)` / `Plan(steps=[... Activity() ...])`
                if not isinstance(node, ast.Call):
                    continue
                src = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
                if "steps" not in src:
                    continue
                for rt in _RUNTIME_NAMES:
                    if re.search(rf"\b{rt}\b", src):
                        yield ConceptIssue(
                            self.ID,
                            f"{path.name}:{node.lineno} puts {rt} into a Plan's steps",
                            [rt, "Plan"],
                            f"a Plan holds Steps. {rt} is runtime — it belongs to an execution "
                            f"record, not a declaration")
                        break


class NoExecutionFields(Invariant):
    """A plan-time type must not carry fields that only a run can have."""

    ID = "no-execution-fields"
    LAW = "one-concept-one-meaning"
    WHY = ("A Variable that grows `started_at` and `value` has quietly become an Entity, and the "
           "name no longer says which it is. The collapse is invisible because every field added "
           "looked individually reasonable.")

    def __init__(self, roots: Sequence[pathlib.Path] = ()) -> None:
        self.roots = tuple(roots)

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        plan_time = {"Variable", "Step", "Plan"}
        for path in _python_files(self.roots):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
                bases |= {b.attr for b in node.bases if isinstance(b, ast.Attribute)}
                bases |= {b.value.id for b in node.bases
                          if isinstance(b, ast.Subscript) and isinstance(b.value, ast.Name)}
                # ⚠️ The class's OWN name counts, not only its bases. The failure §15 describes is
                # `Variable` itself growing timestamps — the collapse happens in the canonical type
                # far more often than in a subclass of it. The first version checked bases only and
                # was silent on exactly the case it was written for.
                if not (bases & plan_time) and node.name not in plan_time:
                    continue
                fields = {t.id for s in node.body if isinstance(s, ast.AnnAssign)
                          for t in [s.target] if isinstance(t, ast.Name)}
                leaked = sorted(fields & EXECUTION_FIELDS)
                if leaked:
                    yield ConceptIssue(
                        self.ID,
                        f"{node.name} is plan-time but declares {leaked}",
                        [node.name],
                        "those belong to an Activity or Entity — the runtime side of the pair")


class NoPrivateSynonym(Invariant):
    """A class named for a meaning that a declared Concept already owns."""

    ID = "no-private-synonym"
    LAW = "one-meaning-one-concept"
    WHY = ("`DataFlowNode` is what an agent reaches for because it sounds more computer-sciencey "
           "than `Step`. Both mean the same thing, and once both exist code chooses by which "
           "import was nearer.")

    def __init__(self, roots: Sequence[pathlib.Path] = ()) -> None:
        self.roots = tuple(roots)

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        owned = {a.lower(): c for c in concepts for a in c.ALSO_KNOWN_AS}
        declared_names = {c.__name__ for c in concepts}
        for path in _python_files(self.roots):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef) or node.name in declared_names:
                    continue
                owner = owned.get(node.name.lower())
                if owner is not None:
                    yield ConceptIssue(
                        self.ID,
                        f"{path.name}:{node.lineno} declares {node.name}, which is a known name "
                        f"for {owner.__name__}",
                        [node.name, owner.__name__],
                        f"use {owner.__name__} — that meaning already has a canonical concept")


def _python_files(roots: Sequence[pathlib.Path]) -> Iterable[pathlib.Path]:
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            yield root
        elif root.is_dir():
            yield from sorted(p for p in root.rglob("*.py") if ".venv" not in p.parts)
