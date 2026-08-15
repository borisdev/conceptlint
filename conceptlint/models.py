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

#: Words that appear in almost every definition sentence and so distinguish nothing. Kept short on
#: purpose: a long stop-list starts deleting the domain nouns that carry the whole signal.
_STOP = frozenset({
    "a", "an", "the", "of", "for", "to", "in", "on", "and", "or", "is", "are", "was", "were", "be",
    "it", "its", "this", "that", "these", "those", "with", "from", "by", "as", "at", "one", "we",
})


def _content(sentence: str) -> set[str]:
    """The words in a definition that carry meaning, lowercased."""
    return {w for w in re.findall(r"[A-Za-z_]+", sentence.lower())
            if w not in _STOP and len(w) > 2}


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

    @property
    def definition(self) -> str:
        """The first sentence of the docstring — what the author says this MEANS.

        A docstring's opening line is the closest thing plain Pydantic has to a declared definition,
        which is why `Concept.DEFINITION` is not needed to read one. Everything after it is usually
        rationale, examples, or warnings: real content, but not the claim about identity.
        """
        head = self.docstring.strip().split("\n\n", 1)[0]
        return re.split(r"(?<=[.!?])\s", head.strip(), maxsplit=1)[0].strip()

    def definition_overlap(self, other: ModelRecord) -> float:
        """How much of the stated meaning is shared. 0.0 when either side states none.

        ⚠️ Empty is not agreement. Two undocumented models are not two models that agree — treating
        a blank as a match would fire on every pair in an undocumented codebase, which is the sort
        of result that gets a checker switched off in an afternoon.
        """
        a, b = _content(self.definition), _content(other.definition)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)


def discover_models(root: pathlib.Path) -> list[ModelRecord]:
    """Every Pydantic model under `root`, read from source. Never imported.

    A linter that must import cannot run on the half-finished state a repo is in while someone is
    talking to an agent about it — which is exactly when a duplicate concept gets introduced.
    """
    found: dict[str, ModelRecord] = {}      # by name, for base resolution
    every: list[ModelRecord] = []           # every declaration, including repeated names
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
            rec = ModelRecord(
                name=node.name, docstring=ast.get_docstring(node) or "",
                fields=fields, bases=bases, file=rel, line=node.lineno)
            found[node.name] = rec
            every.append(rec)
    return every


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


#: How much of a stated definition must be shared before two models are claiming the same meaning.
#: Higher than the field bar because prose is noisier: field names are chosen once and reused, while
#: two authors describing the same thing rarely pick the same words unless one copied the other —
#: which is exactly the case worth catching.
DEFINITION_THRESHOLD = 0.8


def near_duplicates(models: Sequence[ModelRecord],
                    threshold: float = 0.6
                    ) -> Iterable[tuple[ModelRecord, ModelRecord, float, str]]:
    """Pairs that look like one concept wearing two names.

    A shared head noun is required, and then EITHER corroborating signal:

        fields      the shape is the same          `Finding` / `ResearchFinding`
        definition  the stated meaning is the same `InterventionProtocol` / `Protocol`

    The head noun alone is noise — `UserRequest` and `SearchRequest` share one and are properly
    distinct. So is either corroborator alone: two unrelated models both carrying `text` and
    `source_id` may be coincidence, and two one-line docstrings can collide by accident.

    ⚠️ Fields were the only corroborator until 2026-08-15, and that made the check fragile in the
    one direction it could not report: **rename the fields and the finding disappears**, while the
    duplicate meaning it was reporting is untouched. Found on nobsmed, where `InterventionProtocol`
    and `Protocol` had NINE identical fields *and* a word-for-word identical docstring — two
    independent signals, of which only one was being read. A checker that depends on the shape
    surviving is measuring the shape, not the concept.

    Yields `(first, second, score, signal)`; `signal` names which corroborator fired, because
    "these have the same fields" and "these claim the same meaning" want different fixes.
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
            meaning = a.definition_overlap(b)

            if overlap >= threshold:
                score, signal = overlap, "fields"
            elif meaning >= DEFINITION_THRESHOLD:
                score, signal = meaning, "definition"
            else:
                continue

            seen.add(key)
            first, second = index[key[0]], index[key[1]]
            yield (first, second, score, signal)


#: A directory whose whole job is to hold parallel copies of a vocabulary. Two `Finding` classes in
#: `versions/v3_0/` and `versions/v4_0/` are not one name with two meanings — the namespace already
#: says which is which, and flagging them means flagging versioning itself.
#:
#: ⚠️ Found by running on a real codebase: 19 of 20 hits were versioned IRs. A checker that fires on
#: an intentional pattern that often does not survive first contact.
VERSION_DIRS = frozenset({"versions", "version", "_versions", "legacy", "deprecated"})


def _versioned(m: ModelRecord) -> bool:
    return bool(VERSION_DIRS & set(pathlib.PurePosixPath(m.file).parts))


def overloaded(models: Sequence[ModelRecord]) -> Iterable[tuple[ModelRecord, ModelRecord]]:
    """One name, two meanings: the same class name declared twice with different shapes.

    Requires no declarations of any kind — just two files. `Protocol` as a treatment regimen and
    `Protocol` as a network contract is one word carrying two meanings, and every import site has to
    know which module it came from to know what it got.

    ⚠️ Same name and the SAME shape is not reported here. That is a duplicate, and `near_duplicates`
    already covers it; reporting both would make one mistake produce two findings.
    """
    by_name: dict[str, list[ModelRecord]] = {}
    for m in models:
        by_name.setdefault(m.name, []).append(m)

    for name, group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a.file == b.file:
                    continue          # a redefinition in one file is a different bug
                if _versioned(a) or _versioned(b):
                    continue
                if _overlap(set(a.fields), set(b.fields)) >= 0.8:
                    continue          # same name, same shape: a duplicate, not an overload
                yield (a, b)
