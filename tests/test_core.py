"""The semantic kernel: registration, the four checks, and the refusal to register a dead rule.

Every check below is exercised in BOTH directions — the shape it must catch, and the legal shape it
must stay silent on. §19: false positives matter. A checker that only ever fires is a checker people
turn off, and then the true findings stop arriving too.
"""
from __future__ import annotations

from typing import ClassVar

import pytest

from conceptlint.core.concept import Concept
from conceptlint.core.invariant import ConceptIssue, Invariant, registered
from conceptlint.core.lint import (Ambiguity, CanonicalReuse, ExplicitRefinement, NearDuplicate,
                                   words)


def _c(name: str, *, id: str = "", definition: str = "d", refines=None, aka=()) -> type[Concept]:
    """A throwaway Concept. Declared locally so the module registry stays untouched."""
    return type(name, (Concept,), {
        "ID": id or name.lower(), "DEFINITION": definition,
        "RATIONALE": "r", "REFINES": refines, "ALSO_KNOWN_AS": tuple(aka),
    })


def _rules(inv: Invariant, *concepts: type[Concept]) -> list[ConceptIssue]:
    return list(inv.check(list(concepts)))


# ── tokenisation ──────────────────────────────────────────────────────────────────────────────────

def test_camel_case_splits_into_words() -> None:
    assert words("ClinicalFinding") == {"clinical", "finding"}
    assert words("AIEvalTrial") == {"eval", "trial"}   # short tokens dropped: "AI" is noise here


# ── law one: one concept, one meaning ─────────────────────────────────────────────────────────────

def test_two_concepts_claiming_one_wire_tag_is_ambiguity() -> None:
    issues = _rules(Ambiguity(), _c("Study", id="evidence"), _c("Citation", id="evidence"))
    assert [i.rule for i in issues] == ["ambiguity"]
    assert "evidence" in issues[0].message


def test_an_alias_that_is_someone_elses_name_is_ambiguity() -> None:
    """A retired word reused as a canonical name: the string now points at two concepts."""
    finding = _c("Finding")
    issues = _rules(Ambiguity(), _c("Claim", aka=("Finding",)), finding)
    assert issues and "Finding" in issues[0].message


def test_distinct_concepts_are_silent() -> None:
    assert _rules(Ambiguity(), _c("Study"), _c("Citation")) == []


# ── law two: one meaning, one concept ─────────────────────────────────────────────────────────────

def test_a_name_containing_a_canonical_name_needs_a_declared_relationship() -> None:
    finding = _c("Finding")
    issues = _rules(CanonicalReuse(), _c("ResearchFinding"), finding)
    assert issues and issues[0].rule == "canonical-reuse"
    assert "REFINES = Finding" in issues[0].suggestion


def test_declaring_the_refinement_silences_it() -> None:
    """The escape hatch must work, or every finding is unfixable and the tool gets ignored."""
    finding = _c("Finding")
    assert _rules(CanonicalReuse(), _c("ClinicalFinding", refines=finding), finding) == []


def test_a_private_synonym_of_a_declared_alias_is_caught() -> None:
    step = _c("Step", aka=("DataFlowNode",))
    issues = _rules(CanonicalReuse(), _c("DataFlowNode"), step)
    assert issues and "Step" in issues[0].suggestion


def test_two_names_circling_one_meaning_is_a_near_duplicate() -> None:
    issues = _rules(NearDuplicate(), _c("EvidenceFinding"), _c("ResearchFinding"))
    assert issues and issues[0].rule == "near-duplicate"
    assert "finding" in issues[0].message


def test_a_shared_parent_silences_the_near_duplicate() -> None:
    finding = _c("Finding")
    issues = _rules(NearDuplicate(),
                    _c("EvidenceFinding", refines=finding), _c("ResearchFinding", refines=finding),
                    finding)
    assert issues == [], "a declared common parent IS the explicit distinction"


def test_a_near_duplicate_is_reported_once_not_twice() -> None:
    """Symmetric pairs must not double-report — noise is how a linter loses its reader."""
    issues = _rules(NearDuplicate(), _c("EvidenceFinding"), _c("ResearchFinding"))
    assert len(issues) == 1


# ── the escape hatch has to mean something ────────────────────────────────────────────────────────

def test_a_refinement_repeating_its_parents_definition_is_flagged() -> None:
    parent = _c("Finding", definition="Something a study reports.")
    child = _c("ClinicalFinding", definition="Something a study reports.", refines=parent)
    issues = _rules(ExplicitRefinement(), child, parent)
    assert issues and "verbatim" in issues[0].message


def test_a_refinement_cycle_is_flagged() -> None:
    a = _c("A")
    b = _c("B", refines=a)
    a.REFINES = b
    assert _rules(ExplicitRefinement(), a, b)


def test_a_genuine_refinement_passes() -> None:
    parent = _c("Finding", definition="Something a study reports.")
    child = _c("ClinicalFinding", definition="A finding about one patient's care.", refines=parent)
    assert _rules(ExplicitRefinement(), child, parent) == []


# ── a rule that cannot run must not register ──────────────────────────────────────────────────────

def test_an_invariant_with_no_check_is_refused() -> None:
    """It would register, run, find nothing, and read exactly like a rule that passed."""
    type("Hollow", (Invariant,), {"ID": "hollow", "LAW": "one-concept-one-meaning", "WHY": "w"})
    with pytest.raises(TypeError, match="does not implement check"):
        registered()


def test_an_invariant_with_no_stated_failure_is_refused() -> None:
    type("Vague", (Invariant,), {"ID": "vague", "LAW": "one-concept-one-meaning",
                                 "check": lambda self, c: []})
    with pytest.raises(TypeError, match="missing WHY"):
        registered()
