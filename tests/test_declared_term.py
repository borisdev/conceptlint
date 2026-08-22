"""`DeclaredTerm` as the shared base of the plan types — the two ways it goes quiet.

Both were found by running it on 2026-08-22, not by reading it, and both are silent failures: the
tool keeps working and says LESS. That is the shape `.claude/rules/checks.md` is about — a check
that passes because it no longer touches what it was checking.
"""
from __future__ import annotations

import pathlib

import plan_types.plan  # noqa: F401 — importing is what declares them
from plan_types.naming.declared_term import DeclaredTerm, declared
from plan_types.naming.records import MODEL_BASES, discover_models
from plan_types.plan import MultiStep, Plan, Service, Step, Variable

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_the_five_plan_types_are_declared_terms():
    """The point of the pass: one base, filled, instead of `ONTOLOGY_IRI` on each class ad hoc."""
    for cls in (Plan, Step, Variable, Service, MultiStep):
        assert issubclass(cls, DeclaredTerm), cls.__name__
        assert cls.ID, f"{cls.__name__} declares no ID"
        assert cls.DEFINITION, f"{cls.__name__} declares no DEFINITION"
        assert cls.RATIONALE, f"{cls.__name__} declares no RATIONALE"


def test_every_id_this_package_declares_is_unique():
    """`Ambiguity` reports this too. Asserted here so it fails at the commit, not at the lint.

    ⚠️ Scoped to `plan_types`, not to `declared()`, and the reason is worth keeping. `declared()`
    walks `__subclasses__()` of the LIVE process, so any throwaway subclass another test builds is
    in it permanently — `tests/test_core.py` makes a dozen and its helper docstring claims "the
    module registry stays untouched", which has never been true. A global assertion here would fail
    or pass on test ORDER, which is the flakiness `core.invariant.validate` was split out to stop.
    """
    ours = [c for c in declared() if c.__module__.startswith("plan_types.")]
    ids = [c.ID for c in ours]
    assert ids, "nothing declared — this guard would be checking nothing"
    assert len(ids) == len(set(ids)), f"a wire tag is claimed twice: {sorted(ids)}"


def test_subclassing_a_declared_term_does_not_declare_a_second_one():
    """⚠️ The failure that made `declared()` read `__dict__` instead of the attribute.

    `ID` is a ClassVar, so `class Square(Step)` inherits `ID = "step"` for free. Reading the
    inherited value, every user Step in every example arrives claiming the same wire tag, and
    `Ambiguity` reports "the tag 'step' is claimed by N terms" — a finding that is true of the
    input and useless as advice. Declaring is something you WRITE; subclassing is using.
    """
    class Square(Step):
        pass

    assert Square.ID == "step", "inheritance still carries the value — that part is intended"
    assert Square not in declared(), "an undeclared subclass must not enter the vocabulary"
    assert Step in declared()


def test_discovery_of_our_own_base_does_not_depend_on_file_order():
    """⚠️ The regression that dropped the repo's finding count from 6 to 4 and looked like a win.

    `discover_models` follows a base only once it has walked the file declaring it, in sorted
    order. The base moved from `conceptlint/core/` to `plan_types/naming/`, `evals/` stopped
    sorting after it, and two real duplicates went unreported. Naming the base in `MODEL_BASES` is
    what makes it order-independent; this asserts the consequence rather than the mechanism.
    """
    assert "DeclaredTerm" in MODEL_BASES

    found = discover_models(ROOT / "evals" / "minimal" / "sibling_refinement")
    assert {r.name for r in found} >= {"EvidenceFinding", "ResearchFinding"}, (
        "the deliberate duplicate pair is invisible to discovery — the linter is quieter than the "
        "codebase is clean")


def test_multistep_refines_the_word_it_reuses():
    """`REFINES` is the escape hatch for the naming laws, so it points at the reused WORD.

    `MultiStep` is `rdfs:subClassOf` both Plan and Step. Pointing REFINES at `Plan` is true and
    silences nothing: `canonical-reuse` still fires on the name containing `Step`. A documented fix
    that does not silence the finding teaches people the tool is broken.
    """
    assert MultiStep.REFINES is Step
    assert issubclass(MultiStep, Plan), "the Plan relation is carried by the Python base"
