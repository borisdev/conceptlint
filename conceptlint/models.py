"""Read the semantics ALREADY PRESENT in ordinary Pydantic models.

No base class, no schema language, no second ontology. `class Finding(BaseModel)` is the source of
truth, and this module reads what it already says:

    name        the term
    docstring   the definition
    fields      the shape — the strongest duplicate signal there is
    bases       an EXPLICIT refinement, declared in the only way Python has

⚠️ That last line is why `Concept.REFINES` is not needed here. `class ClinicalFinding(Finding)` has
already declared the relationship; asking for a second declaration would be the "annotate your whole
codebase" tax this approach exists to avoid.

`Concept` stays, and stays optional — for the things ordinary Pydantic cannot express: an external
ontology IRI, a recorded rationale, and words you have retired and want to keep dead.

## Why field sets and not names alone

`Finding` and `ResearchFinding` share a head noun, which on its own means little — `UserRequest` and
`SearchRequest` share one too and are properly distinct. What makes the first pair suspicious is
that their FIELDS are identical. Two signals, both required, because a checker that fires on names
alone is one people turn off.
"""
from __future__ import annotations

import ast
import pathlib
import re
from typing import Iterable, Sequence

from pydantic import BaseModel

#: Bases that mean "this is a domain model". Pydantic first; a project's own model base is picked up
#: transitively, because a class inheriting a discovered model is itself a model.
MODEL_BASES = frozenset({"BaseModel", "RootModel"})

_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")

#: Field names too common to carry meaning. Two models both having `id` says nothing.
COMMON_FIELDS = frozenset({"id", "name", "type", "kind", "created_at", "updated_at", "metadata"})


def _overlap(a: set[str], b: set[str]) -> float:
    """Jaccard, minus the field names too common anywhere to carry meaning."""
    a, b = a - COMMON_FIELDS, b - COMMON_FIELDS
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def words(name: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(name) if len(w) > 2}


class ModelRecord(BaseModel):
    """One Pydantic model, as declared."""

    model_config = {"frozen": True}

    name: str
    docstring: str
    fields: tuple[str, ...]
    bases: tuple[str, ...]
    file: str
    line: int

    def shares_a_head_noun_with(self, other: ModelRecord) -> set[str]:
        return words(self.name) & words(other.name)

    def field_overlap(self, other: ModelRecord) -> float:
        """Jaccard over field names, ignoring fields too common to mean anything."""
        return _overlap(set(self.fields), set(other.fields))


def discover_models(root: pathlib.Path) -> list[ModelRecord]:
    """Every Pydantic model under `root`, read from source. Never imported.

    A linter that must import cannot run on the half-finished state a repo is in while someone is
    talking to an agent about it — which is exactly when a duplicate concept gets introduced.
    """
    found: dict[str, ModelRecord] = {}
    files = [root] if root.is_file() else sorted(
        p for p in root.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts)

    for path in files:
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
        rel = path.name if root.is_file() else path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = tuple(b.id for b in node.bases if isinstance(b, ast.Name))
            bases += tuple(b.attr for b in node.bases if isinstance(b, ast.Attribute))
            # A class inheriting a model IS a model — that is how a project's own base is followed.
            if not (set(bases) & MODEL_BASES or set(bases) & set(found)):
                continue
            fields = tuple(
                t.id for s in node.body if isinstance(s, ast.AnnAssign)
                for t in [s.target] if isinstance(t, ast.Name) and not t.id.isupper())
            found[node.name] = ModelRecord(
                name=node.name, docstring=ast.get_docstring(node) or "",
                fields=fields, bases=bases, file=rel, line=node.lineno)
    return list(found.values())


def _related(a: ModelRecord, b: ModelRecord, index: dict[str, ModelRecord]) -> bool:
    """Has the relationship already been declared — by inheritance, in either direction?

    Python's own mechanism IS the explicit refinement. Nothing further should be demanded.
    """
    def ancestry(m: ModelRecord, seen: set[str] | None = None) -> set[str]:
        seen = seen or set()
        for b in m.bases:
            if b in seen:
                continue
            seen.add(b)
            if b in index:
                ancestry(index[b], seen)
        return seen

    return b.name in ancestry(a) or a.name in ancestry(b)


def _ancestor_fields(m: ModelRecord, index: dict[str, ModelRecord]) -> set[str]:
    """Fields a model gets from its bases rather than declares itself."""
    out: set[str] = set()
    stack, seen = list(m.bases), set()
    while stack:
        b = stack.pop()
        if b in seen or b not in index:
            continue
        seen.add(b)
        out |= set(index[b].fields)
        stack.extend(index[b].bases)
    return out


def near_duplicates(models: Sequence[ModelRecord],
                    threshold: float = 0.6) -> Iterable[tuple[ModelRecord, ModelRecord, float]]:
    """Pairs that look like one concept wearing two names.

    BOTH signals required — a shared head noun AND overlapping fields. Either alone produces noise:
    `UserRequest`/`SearchRequest` share a noun and are properly distinct; two unrelated models both
    carrying `text` and `source_id` may be coincidence. Together they are worth asking about.
    """
    index = {m.name: m for m in models}
    seen: set[tuple[str, str]] = set()
    for a in models:
        for b in models:
            if a is b or _related(a, b, index):
                continue
            key = tuple(sorted((a.name, b.name)))
            if key in seen:
                continue
            if not a.shares_a_head_noun_with(b):
                continue
            # ⚠️ Fields both get from a SHARED BASE are that base's interface, not shared meaning.
            # Found on a real codebase: two Invariant subclasses — genuinely different rules —
            # scored 100% because `id`, `refines` and `scope` all come from Invariant. Counting
            # them would flag every pair of siblings under any base class, forever.
            inherited = _ancestor_fields(a, index) & _ancestor_fields(b, index)
            overlap = _overlap(set(a.fields) - inherited, set(b.fields) - inherited)
            if overlap < threshold:
                continue
            seen.add(key)
            yield (index[key[0]], index[key[1]], overlap)
