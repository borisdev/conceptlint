"""Drift: the fields moved and the promise did not.

The other two failures are visible in one snapshot. Drift is not — *"a name that quietly changes
meaning"* is a claim about two points in time, and the previous check faked it with a hardcoded list
of runtime-sounding field names. That caught exactly one shape and called it a category.

## The signal

A model's docstring is a PROMISE about what it means. Its fields are what it actually is.

    docstring changed, fields changed     evolution — somebody decided, and said so
    docstring changed, fields same        a rewording
    docstring same,    fields same        nothing happened
    docstring same,    fields CHANGED     ← drift. The promise no longer describes the thing.

Only the last is reported. That asymmetry is the whole check: a developer who updates the docstring
has made a decision, and this must not nag them for it. Silence on three of four cases is what makes
the fourth worth reading.

## Why git rather than a heuristic

Because the alternative is guessing which fields "look runtime", which is what was there before and
is unfixable in general — a field named `value` is suspicious on a plan-time type and unremarkable
on a config. History does not guess.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
from dataclasses import dataclass

from workflow_plan.naming.records import COMMON_FIELDS, ModelRecord, discover_models


@dataclass(frozen=True)
class DriftFinding:
    """One model whose shape moved while its stated meaning stood still."""

    name: str
    file: str
    line: int
    was: tuple[str, ...]
    now: tuple[str, ...]
    docstring: str

    @property
    def added(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.now) - set(self.was)))

    @property
    def removed(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.was) - set(self.now)))

    def render(self) -> str:
        parts = []
        if self.added:
            parts.append(f"+{', +'.join(self.added)}")
        if self.removed:
            parts.append(f"-{', -'.join(self.removed)}")
        return (f"drift: {self.name} gained a different shape while its docstring stayed the same\n"
                f"  fields   : {' '.join(parts)}\n"
                f"  promise  : {self.docstring or '(none)'}\n"
                f"  declared : {self.file}:{self.line}\n"
                f"  need     : update the docstring if the meaning changed, or move the new fields "
                f"to the concept they belong to")


def _git(root: pathlib.Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _models_at(root: pathlib.Path, rev: str) -> dict[str, ModelRecord]:
    """Every model as it existed at `rev`, read from git rather than the working tree."""
    listing = _git(root, "ls-tree", "-r", "--name-only", rev)
    out: dict[str, ModelRecord] = {}
    for rel in listing.splitlines():
        if not rel.endswith(".py"):
            continue
        src = _git(root, "show", f"{rev}:{rel}")
        if not src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = tuple(b.id for b in node.bases if isinstance(b, ast.Name))
            bases += tuple(b.attr for b in node.bases if isinstance(b, ast.Attribute))
            if not ({"BaseModel", "RootModel"} & set(bases) or set(bases) & set(out)):
                continue
            out[node.name] = ModelRecord(
                name=node.name, docstring=ast.get_docstring(node) or "",
                fields=tuple(t.id for s in node.body if isinstance(s, ast.AnnAssign)
                             for t in [s.target] if isinstance(t, ast.Name) and not t.id.isupper()),
                bases=bases, file=rel, line=node.lineno)
    return out


def drifted(root: pathlib.Path, since: str = "HEAD~20",
            threshold: float = 0.5) -> list[DriftFinding]:
    """Models whose fields moved substantially while their docstring did not.

    `threshold` is the share of fields that must have changed. Renaming one field of eight is not
    drift; replacing half of them while the docstring stands is.

    Returns nothing when there is no git history, no `since` revision, or the model is new — all
    three are "cannot tell", and a checker that reports "cannot tell" as a finding is one people
    stop reading.
    """
    if not _git(root, "rev-parse", "--git-dir"):
        return []
    if not _git(root, "rev-parse", "--verify", "--quiet", since):
        # Shallow or young history: fall back to the first commit rather than reporting nothing.
        first = _git(root, "rev-list", "--max-parents=0", "HEAD").split()
        if not first:
            return []
        since = first[0]

    before = _models_at(root, since)
    findings: list[DriftFinding] = []

    for now in discover_models(root):
        was = before.get(now.name)
        if was is None:                                   # new model: nothing to compare
            continue
        if was.docstring.strip() != now.docstring.strip():  # they said so — not drift
            continue
        old, new = set(was.fields) - COMMON_FIELDS, set(now.fields) - COMMON_FIELDS
        if not old and not new:
            continue
        changed = len(old ^ new) / max(len(old | new), 1)
        if changed < threshold:
            continue
        findings.append(DriftFinding(name=now.name, file=now.file, line=now.line,
                                     was=was.fields, now=now.fields, docstring=now.docstring))
    return findings
