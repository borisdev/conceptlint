"""The four checks, and the driver that runs them.

All deterministic. §21 of the handoff is explicit that similarity is a signal and not the judge, and
that model infrastructure waits until an eval shows deterministic checks are insufficient. None has
yet, so there is none here.

The checks divide by which law they serve:

    one-concept-one-meaning     Ambiguity          one term, two meanings
    one-meaning-one-concept     CanonicalReuse     a new name for an existing meaning
                                NearDuplicate      two names circling one meaning
                                ExplicitRefinement a declared narrowing that is not one

⚠️ `REFINES` is what clears the second group. That is the design: the checks do not forbid similar
concepts, they forbid UNDECLARED ones. Every finding has a legal resolution that is one line of code.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Iterable, Sequence

from conceptlint.core.concept import Concept, declared
from conceptlint.core.invariant import ConceptIssue, Invariant, registered

_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def words(name: str) -> set[str]:
    """`ClinicalFinding` -> {clinical, finding}."""
    return {w.lower() for w in _WORD.findall(name.replace("_", " ")) if len(w) > 2}


def _ancestry(c: type[Concept]) -> list[type[Concept]]:
    out, seen, cur = [], set(), c.REFINES
    while cur is not None and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = cur.REFINES
    return out


def _related(a: type[Concept], b: type[Concept]) -> bool:
    """Is their relationship already declared — as ancestor, descendant, OR sibling?

    ⚠️ The sibling case is not a nicety. `EvidenceFinding` and `ResearchFinding` both refining
    `Finding` HAVE stated how they relate; flagging them anyway would mean the documented fix does
    not silence the finding, which is the fastest way to teach someone the tool is broken. Caught by
    `test_a_shared_parent_silences_the_near_duplicate` — the first version only looked up the chain.
    """
    up_a, up_b = _ancestry(a), _ancestry(b)
    return b in up_a or a in up_b or bool(set(up_a) & set(up_b))


class Ambiguity(Invariant):
    """One term, two meanings."""

    ID = "ambiguity"
    LAW = "one-concept-one-meaning"
    WHY = ("A term that means two things cannot be used in a sentence without the reader picking "
           "one. `Evidence` as a study, as support for a claim, and as a citation is three "
           "concepts wearing one word, and every downstream type inherits the confusion.")

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        by_id: dict[str, list[type[Concept]]] = {}
        by_name: dict[str, list[type[Concept]]] = {}
        for c in concepts:
            by_id.setdefault(c.ID, []).append(c)
            by_name.setdefault(c.__name__.lower(), []).append(c)

        for cid, group in sorted(by_id.items()):
            if len(group) > 1:
                yield ConceptIssue(
                    self.ID, f"the wire tag {cid!r} is claimed by {len(group)} concepts",
                    [c.__name__ for c in group],
                    "give each its own ID — a stored record cannot say which one it meant")

        # A retired or alternate word reused as somebody else's canonical name: the same string now
        # points at two concepts, which is the first law broken through the back door.
        for c in concepts:
            for aka in c.ALSO_KNOWN_AS:
                for other in by_name.get(aka.lower(), []):
                    if other is not c:
                        yield ConceptIssue(
                            self.ID,
                            f"{c.__name__} lists {aka!r} as an alias, but {other.__name__} IS that name",
                            [c.__name__, other.__name__],
                            "drop the alias, or rename one — the word cannot mean both")


class CanonicalReuse(Invariant):
    """A new name for a meaning that already has one."""

    ID = "canonical-reuse"
    LAW = "one-meaning-one-concept"
    WHY = ("`ResearchFinding` beside a canonical `Finding` is either a refinement or a synonym. "
           "Left undeclared it becomes a second vocabulary, and code starts choosing between them "
           "by which import was nearer.")

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        for c in concepts:
            for other in concepts:
                if c is other or _related(c, other):
                    continue
                # `other`'s whole name inside `c`'s name: ResearchFinding contains Finding.
                if other.__name__ != c.__name__ and other.__name__ in c.__name__:
                    yield ConceptIssue(
                        self.ID,
                        f"{c.__name__} contains the canonical name {other.__name__} "
                        f"but declares no relationship to it",
                        [c.__name__, other.__name__],
                        f"reuse {other.__name__}, or declare "
                        f"`REFINES = {other.__name__}` if it genuinely narrows it")

            for other in concepts:
                if c is other:
                    continue
                if c.__name__.lower() in {a.lower() for a in other.ALSO_KNOWN_AS}:
                    yield ConceptIssue(
                        self.ID,
                        f"{c.__name__} is a name {other.__name__} records as meaning ITSELF",
                        [c.__name__, other.__name__],
                        f"use {other.__name__} — that meaning already has a canonical concept")


class NearDuplicate(Invariant):
    """Two names circling one meaning, neither containing the other."""

    ID = "near-duplicate"
    LAW = "one-meaning-one-concept"
    WHY = ("`EvidenceFinding` and `ResearchFinding` share their head noun and declare no common "
           "parent. Either one meaning has two names, or a distinction exists that nobody wrote "
           "down — and the second is only discoverable by reading both definitions.")

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        seen: set[tuple[str, str]] = set()
        for c in concepts:
            for other in concepts:
                if c is other or _related(c, other):
                    continue
                if other.__name__ in c.__name__ or c.__name__ in other.__name__:
                    continue  # containment is CanonicalReuse's finding, not a second report
                shared = words(c.__name__) & words(other.__name__)
                if not shared:
                    continue
                key = tuple(sorted((c.__name__, other.__name__)))
                if key in seen:
                    continue
                seen.add(key)
                yield ConceptIssue(
                    self.ID,
                    f"{key[0]} and {key[1]} share {sorted(shared)} and declare no common parent",
                    list(key),
                    "give both a shared parent via REFINES, merge them, or make the "
                    "distinction explicit in their definitions")


class ExplicitRefinement(Invariant):
    """A declared narrowing that does not narrow anything."""

    ID = "explicit-refinement"
    LAW = "one-meaning-one-concept"
    WHY = ("`REFINES` is the escape hatch every other check points at, so it has to mean something. "
           "A refinement whose definition matches its parent's is a duplicate that learned the "
           "password.")

    def check(self, concepts: Sequence[type[Concept]]) -> Iterable[ConceptIssue]:
        for c in concepts:
            parent = c.REFINES
            if parent is None:
                continue
            if parent is c or c in _ancestry(parent):
                yield ConceptIssue(self.ID, f"{c.__name__} refines itself, directly or in a cycle",
                                   [c.__name__], "point REFINES at a genuine parent, or remove it")
                continue
            if not getattr(parent, "ID", ""):
                yield ConceptIssue(
                    self.ID, f"{c.__name__} refines {parent.__name__}, which is not a declared Concept",
                    [c.__name__], "REFINES must point at a Concept subclass with an ID")
                continue
            if c.DEFINITION.strip().lower() == parent.DEFINITION.strip().lower():
                yield ConceptIssue(
                    self.ID,
                    f"{c.__name__} refines {parent.__name__} but repeats its definition verbatim",
                    [c.__name__, parent.__name__],
                    "say what NARROWS, or delete the child and use the parent")


def lint(concepts: Sequence[type[Concept]] | None = None) -> list[ConceptIssue]:
    """Run every registered invariant. Empty list means pass — there is no passing issue."""
    subjects = list(concepts) if concepts is not None else declared()
    out: list[ConceptIssue] = []
    for inv in registered():
        out.extend(inv.check(subjects))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="conceptlint", description=__doc__.split("\n")[0])
    p.add_argument("--import", dest="modules", action="append", default=[],
                   help="module to import so its Concepts register (repeatable)")
    p.add_argument("--list", action="store_true", help="show the declared vocabulary and exit")
    p.add_argument("path", nargs="?", default=".", type=pathlib.Path,
                   help="directory or file to check (default: cwd)")
    p.add_argument("--since", default="HEAD~20",
                   help="revision to compare against for drift (default: HEAD~20)")
    p.add_argument("--install-rule", action="store_true",
                   help="write the agent rule to ~/.claude/rules/ and exit")
    p.add_argument("--uninstall-rule", action="store_true", help="remove it and exit")
    args = p.parse_args(argv)

    if args.install_rule or args.uninstall_rule:
        from conceptlint.integrations import claude_code
        if args.install_rule:
            print(f"wrote {claude_code.install()}")
            print("Claude Code reads rules at the START of a session — open a new one.")
        else:
            print("removed" if claude_code.uninstall() else "nothing to remove")
        return 0

    # ⚠️ A path that does not exist must not read as "your code is clean". Silence is the pass, so
    # anything that makes the tool silent for the WRONG reason is worse than an error.
    if not args.path.exists():
        print(f"no such path: {args.path}", file=sys.stderr)
        return 2

    import importlib
    for m in args.modules:
        importlib.import_module(m)

    concepts = declared()
    if args.list:
        for c in concepts:
            grounded = f"  <{c.ONTOLOGY_IRI}>" if c.ONTOLOGY_IRI else ""
            refines = f"  refines {c.REFINES.__name__}" if c.REFINES else ""
            print(f"{c.__name__:<22} {c.ID:<18}{refines}{grounded}")
        print(f"\n{len(concepts)} concept(s)")
        return 0

    issues = lint(concepts)

    # Ordinary Pydantic models — no base class required. This is the DEFAULT surface: every repo
    # has models long before it has declared Concepts, and requiring declarations first is the
    # "annotate your whole codebase" tax nobody pays.
    from conceptlint.models import discover_models, near_duplicates, overloaded

    found_models = discover_models(args.path)

    for first, second in overloaded(found_models):
        issues.append(ConceptIssue(
            "overloaded",
            f"{first.name} is declared twice with different shapes",
            [f"{first.name} ({first.file}:{first.line})",
             f"{second.name} ({second.file}:{second.line})"],
            "one name, two meanings — every import site has to know which module it "
            "came from to know what it got. Rename one, or merge them"))

    for first, second, overlap in near_duplicates(found_models):
        issues.append(ConceptIssue(
            "near-duplicate-model",
            f"{first.name} and {second.name} share a head noun and "
            f"{overlap:.0%} of their fields",
            [f"{first.name} ({first.file}:{first.line})",
             f"{second.name} ({second.file}:{second.line})"],
            "the same concept, an explicit subtype, or intentionally distinct? "
            "consolidate, inherit, or make the difference visible in the fields"))

    # Drift needs two points in time, so it reads git rather than the working tree. Silent when
    # there is no history to compare against — "cannot tell" is not a finding.
    from conceptlint.drift import drifted
    for d in drifted(args.path, since=args.since):
        issues.append(ConceptIssue(
            "drift",
            f"{d.name} changed shape while its docstring stayed the same",
            [f"{d.name} ({d.file}:{d.line})"],
            "update the docstring if the meaning changed, or move the new fields to the "
            "concept they belong to"))

    if not issues:
        return 0                       # silence is the pass
    for i in issues:
        print(i.render(), file=sys.stderr)
        print(file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
