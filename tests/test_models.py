"""Reading ordinary Pydantic — and, more importantly, when to say nothing.

Every FLAG case here has a PASS twin. A checker that fires on names alone is one people uninstall,
and then the true findings stop arriving too.
"""
from __future__ import annotations

import pathlib
import textwrap

import pytest

from workflow_plan.naming.records import discover_models, near_duplicates


def _write(tmp: pathlib.Path, body: str) -> pathlib.Path:
    (tmp / "models.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp


def _pairs(tmp: pathlib.Path) -> list[tuple[str, str]]:
    return [(a.name, b.name) for a, b, _, _ in near_duplicates(discover_models(tmp))]


def test_no_base_class_is_required(tmp_path: pathlib.Path) -> None:
    """The whole Pydantic pitch: ordinary models remain the source of truth."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Finding(BaseModel):
            """A proposition extracted from a source."""
            text: str
            source_id: str
    ''')
    (m,) = discover_models(root)
    assert m.name == "Finding"
    assert m.docstring == "A proposition extracted from a source."
    assert m.fields == ("text", "source_id")


def test_the_killer_demo(tmp_path: pathlib.Path) -> None:
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Finding(BaseModel):
            """A proposition extracted from a source."""
            text: str
            source_id: str

        class ResearchFinding(BaseModel):
            """A proposition extracted from a research source."""
            text: str
            source_id: str
    ''')
    assert _pairs(root) == [("Finding", "ResearchFinding")]


def test_inheritance_IS_the_explicit_refinement(tmp_path: pathlib.Path) -> None:
    """Python already has a way to declare 'this narrows that'. Demanding a second declaration is
    the annotate-everything tax this approach exists to avoid."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Finding(BaseModel):
            """A proposition extracted from a source."""
            text: str
            source_id: str

        class ClinicalFinding(Finding):
            """A finding about one patient's care."""
            patient_id: str
    ''')
    assert _pairs(root) == []


def test_a_shared_head_noun_alone_is_not_enough(tmp_path: pathlib.Path) -> None:
    """`UserRequest` and `SearchRequest` share a noun and are properly distinct."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class UserRequest(BaseModel):
            user_id: str
            email: str

        class SearchRequest(BaseModel):
            query: str
            limit: int
    ''')
    assert _pairs(root) == []


def test_shared_fields_alone_are_not_enough(tmp_path: pathlib.Path) -> None:
    """Two unrelated models both carrying `text` is coincidence, not a collision."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Comment(BaseModel):
            text: str
            author: str

        class Caption(BaseModel):
            text: str
            author: str
    ''')
    assert _pairs(root) == []


def test_boilerplate_fields_do_not_create_collisions(tmp_path: pathlib.Path) -> None:
    """Half the models in any repo have `id` and `name`. Counting those would flag everything."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class StudyRecord(BaseModel):
            id: str
            name: str
            pmid: str

        class PatientRecord(BaseModel):
            id: str
            name: str
            mrn: str
    ''')
    assert _pairs(root) == []


def test_a_project_model_base_is_followed(tmp_path: pathlib.Path) -> None:
    """A class inheriting a discovered model IS a model — that is how a house style is picked up."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Base(BaseModel):
            pass

        class Finding(Base):
            text: str
            source_id: str

        class ResearchFinding(Base):
            text: str
            source_id: str
    ''')
    assert _pairs(root) == [("Finding", "ResearchFinding")]


def test_a_pair_is_reported_once(tmp_path: pathlib.Path) -> None:
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Finding(BaseModel):
            text: str
            source_id: str

        class ResearchFinding(BaseModel):
            text: str
            source_id: str
    ''')
    assert len(_pairs(root)) == 1


def test_unparseable_source_does_not_stop_the_scan(tmp_path: pathlib.Path) -> None:
    """A repo mid-edit is exactly when a duplicate gets introduced."""
    (tmp_path / "broken.py").write_text("def (:", encoding="utf-8")
    _write(tmp_path, '''
        from pydantic import BaseModel

        class Finding(BaseModel):
            text: str
    ''')
    assert [m.name for m in discover_models(tmp_path)] == ["Finding"]


def test_fields_from_a_shared_base_do_not_count(tmp_path: pathlib.Path) -> None:
    """Found on a real codebase, not imagined.

    Two `CoherenceRule` subclasses — genuinely different rules — scored 100% because `id`, `refines`
    and `scope` all come from the base. Counting inherited fields flags every pair of siblings
    under any base class, forever.
    """
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Rule(BaseModel):
            id: str
            scope: list
            refines: str

        class StatusRule(Rule):
            """A status claiming the literature must carry it."""

        class BuilderRule(Rule):
            """Out of a builder every edge is unsearched."""
    ''')
    assert _pairs(root) == []


def test_a_real_duplicate_survives_the_base_discount(tmp_path: pathlib.Path) -> None:
    """The discount must not silence a genuine collision between siblings."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Base(BaseModel):
            id: str

        class Finding(Base):
            """A proposition extracted from a source."""
            text: str
            source_id: str

        class ResearchFinding(Base):
            """A proposition extracted from a research source."""
            text: str
            source_id: str
    ''')
    assert _pairs(root) == [("Finding", "ResearchFinding")]


# ── overloaded: one name, two meanings ────────────────────────────────────────────────────────────

def _two_files(tmp: pathlib.Path, a: str, b: str) -> pathlib.Path:
    for sub, body in (("a", a), ("b", b)):
        (tmp / sub).mkdir()
        (tmp / sub / "models.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp


def test_one_name_two_shapes_is_overloaded(tmp_path: pathlib.Path) -> None:
    from workflow_plan.naming.records import overloaded
    root = _two_files(tmp_path, '''
        from pydantic import BaseModel

        class Protocol(BaseModel):
            """A treatment regimen."""
            dose: str
            route: str
    ''', '''
        from pydantic import BaseModel

        class Protocol(BaseModel):
            """A network communication contract."""
            host: str
            port: int
    ''')
    assert [a.name for a, _ in overloaded(discover_models(root))] == ["Protocol"]


def test_one_name_one_shape_is_a_duplicate_not_an_overload(tmp_path: pathlib.Path) -> None:
    """Reporting both would make one mistake produce two findings."""
    from workflow_plan.naming.records import overloaded
    body = '''
        from pydantic import BaseModel

        class Protocol(BaseModel):
            """A treatment regimen."""
            dose: str
            route: str
    '''
    assert list(overloaded(discover_models(_two_files(tmp_path, body, body)))) == []


def test_a_versioned_namespace_is_not_an_overload(tmp_path: pathlib.Path) -> None:
    """Found on a real codebase: 19 of 20 hits were parallel versioned IRs.

    `versions/v3_0/Finding` and `versions/v4_0/Finding` are not one name with two meanings — the
    namespace already says which is which. Flagging them means flagging versioning itself, and a
    checker that fires on an intentional pattern does not survive first contact.
    """
    from workflow_plan.naming.records import overloaded
    for v in ("v3_0", "v4_0"):
        d = tmp_path / "versions" / v
        d.mkdir(parents=True)
        (d / "models.py").write_text(textwrap.dedent(f'''
            from pydantic import BaseModel

            class Finding(BaseModel):
                """A proposition."""
                text: str
                {"source_id: str" if v == "v3_0" else "provenance: str"}
        '''), encoding="utf-8")
    assert list(overloaded(discover_models(tmp_path))) == []


def test_discovery_keeps_repeated_names(tmp_path: pathlib.Path) -> None:
    """The index was keyed by name, so the second declaration overwrote the first — which made the
    overloaded case structurally invisible to the tool meant to find it."""
    root = _two_files(tmp_path, '''
        from pydantic import BaseModel

        class Protocol(BaseModel):
            dose: str
    ''', '''
        from pydantic import BaseModel

        class Protocol(BaseModel):
            host: str
    ''')
    assert [m.name for m in discover_models(root)] == ["Protocol", "Protocol"]


# --- the definition signal ----------------------------------------------------------------------
#
# Fields were the only corroborator until 2026-08-15, which left the check fragile in exactly the
# direction it could not report: rename the fields and the finding vanishes while the duplicated
# MEANING is untouched. Every case below has a PASS twin, for the reason at the top of this file.


def _signals(tmp: pathlib.Path) -> list[tuple[str, str, str]]:
    return [(a.name, b.name, sig) for a, b, _, sig in near_duplicates(discover_models(tmp))]


def test_the_same_stated_meaning_is_caught_when_the_fields_were_renamed(
        tmp_path: pathlib.Path) -> None:
    """The regression. Identical docstring, deliberately disjoint field names.

    Under the old field-only rule these scored 0% and were silently a pass — the duplicate concept
    was fully visible in the source and the checker was looking at the wrong column.
    """
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class TreatmentProtocol(BaseModel):
            """A named course of treatment with its dosing schedule."""
            protocol_label: str
            schedule_text: str

        class Protocol(BaseModel):
            """A named course of treatment with its dosing schedule."""
            title: str
            regimen: str
    ''')
    assert ("Protocol", "TreatmentProtocol", "definition") in _signals(root)


def test_two_undocumented_models_are_not_two_models_that_agree(tmp_path: pathlib.Path) -> None:
    """Empty is not agreement.

    The PASS twin for the test above, and the one that decides whether this ships: a blank matching
    a blank would fire on every same-noun pair in an undocumented codebase.
    """
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class TreatmentProtocol(BaseModel):
            protocol_label: str
            schedule_text: str

        class Protocol(BaseModel):
            title: str
            regimen: str
    ''')
    assert _pairs(root) == []


def test_different_meanings_under_a_shared_noun_stay_silent(tmp_path: pathlib.Path) -> None:
    """`UserRequest` / `SearchRequest` in definition form — the noise case."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class UserRequest(BaseModel):
            """What a person asked us to do on their behalf."""
            actor_id: str
            intent: str

        class SearchRequest(BaseModel):
            """Query parameters sent to the literature index."""
            terms: str
            limit: int
    ''')
    assert _pairs(root) == []


def test_fields_still_win_when_both_signals_are_present(tmp_path: pathlib.Path) -> None:
    """One mistake must produce ONE finding, and it should name the stronger evidence.

    Shape is the more objective of the two, so it is reported when both agree.
    """
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class ResearchFinding(BaseModel):
            """One measured result extracted from a paper."""
            claim: str
            pmid: str

        class Finding(BaseModel):
            """One measured result extracted from a paper."""
            claim: str
            pmid: str
    ''')
    sigs = _signals(root)
    assert len(sigs) == 1, "two signals must not produce two findings for one mistake"
    assert sigs[0][2] == "fields"


def test_a_shared_definition_without_a_shared_noun_is_not_enough(tmp_path: pathlib.Path) -> None:
    """The head noun stays mandatory. Prose collides; two signals or nothing."""
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Alpha(BaseModel):
            """A named course of treatment with its dosing schedule."""
            one: str

        class Beta(BaseModel):
            """A named course of treatment with its dosing schedule."""
            two: str
    ''')
    assert _pairs(root) == []


# --- the overload that lives in a SENTENCE -------------------------------------------------------


def test_a_term_claimed_by_two_declarations_is_overloaded(tmp_path: pathlib.Path) -> None:
    """Two `Finding` classes means the WORD "finding" has two referents.

    The first version of this counted distinct NAMES, so two classes both called `Finding` deduped
    to one and it reported nothing — on a codebase where the code-level check finds fifteen.
    """
    from workflow_plan.naming.records import overloaded_terms
    (tmp_path / "a.py").write_text(textwrap.dedent('''
        from pydantic import BaseModel
        class Finding(BaseModel):
            """A measured result."""
            claim: str
    '''), encoding="utf-8")
    (tmp_path / "b.py").write_text(textwrap.dedent('''
        from pydantic import BaseModel
        class Finding(BaseModel):
            """Something a reviewer noticed."""
            note: str
    '''), encoding="utf-8")
    assert "finding" in overloaded_terms(discover_models(tmp_path))


def test_versioned_copies_are_not_an_overloaded_term(tmp_path: pathlib.Path) -> None:
    """`versions/v3_0/Finding` and `versions/v4_0/Finding` are one meaning at two times.

    The PASS twin. Before this filter, `protocol` on nobsmed looked five-ways ambiguous and three
    of the five were versions of each other — a question with a boring answer, asked constantly.
    """
    from workflow_plan.naming.records import overloaded_terms
    for v in ("v3_0", "v4_0"):
        d = tmp_path / "versions" / v
        d.mkdir(parents=True)
        (d / "m.py").write_text(textwrap.dedent(f'''
            from pydantic import BaseModel
            class Finding(BaseModel):
                """A measured result, {v}."""
                claim: str
        '''), encoding="utf-8")
    assert overloaded_terms(discover_models(tmp_path)) == {}


def test_a_retired_word_is_reported_even_though_it_is_unambiguous(tmp_path: pathlib.Path) -> None:
    """The case that actually bites: one right answer, and the wrong word was used anyway.

    Boris's standing complaint is me writing "workflow" when the type is `Plan`. That is not
    ambiguity — nothing competes for it — so a check that only reported multi-claimant terms would
    stay silent on the exact failure it was built for.
    """
    from workflow_plan.naming.records import claimed_by
    (tmp_path / "m.py").write_text(textwrap.dedent('''
        from pydantic import BaseModel
        class Plan(BaseModel):
            """An ordered set of steps, defined before anything runs."""
            ALSO_KNOWN_AS = ("Workflow", "Pipeline")
            steps: tuple
    '''), encoding="utf-8")
    hits = claimed_by(discover_models(tmp_path), "I will add a stage to the workflow")
    assert "workflow" in hits
    assert [m.name for m in hits["workflow"]] == ["Plan"]


def test_enrichment_needs_no_base_class(tmp_path: pathlib.Path) -> None:
    """`ALSO_KNOWN_AS` is read off a plain class. Requiring a base would be the tax we refuse."""
    (tmp_path / "m.py").write_text(textwrap.dedent('''
        class Activity:
            """What actually happened when a PlanStep ran."""
            ONTOLOGY_IRI = "http://www.w3.org/ns/prov#Activity"
            ALSO_KNOWN_AS = ("StepRun", "TaskInstance")
    '''), encoding="utf-8")
    found = {m.name: m for m in discover_models(tmp_path)}
    assert found["Activity"].also_known_as == ("StepRun", "TaskInstance")
    assert found["Activity"].ontology_iri.endswith("#Activity")


# --- two exclusions that make this checker QUIETER, each with the case it must still catch -------


def test_versioned_copies_are_not_near_duplicates(tmp_path: pathlib.Path) -> None:
    """`overloaded()` has always skipped versions/; this function never did.

    One intentional pattern was noise in one checker and understood in the other — 14 of 55 findings
    on a real codebase. The namespace already says which Finding is which.
    """
    for v in ("v3_0", "v4_0"):
        d = tmp_path / "versions" / v
        d.mkdir(parents=True)
        (d / "m.py").write_text(textwrap.dedent('''
            from pydantic import BaseModel
            class ResearchFinding(BaseModel):
                """A measured result."""
                claim: str
                pmid: str
        '''), encoding="utf-8")
    assert _pairs(tmp_path) == []


def test_two_copies_OUTSIDE_versions_are_still_flagged(tmp_path: pathlib.Path) -> None:
    """The PASS twin for the exclusion above. The same pair in ordinary dirs must still fire."""
    for d in ("alpha", "beta"):
        sub = tmp_path / d
        sub.mkdir()
        (sub / "m.py").write_text(textwrap.dedent('''
            from pydantic import BaseModel
            class ResearchFinding(BaseModel):
                """A measured result."""
                claim: str
                pmid: str
        '''), encoding="utf-8")
    assert _pairs(tmp_path), "a duplicate outside versions/ must still be reported"


def test_the_private_twin_is_a_declaration_not_a_duplicate(tmp_path: pathlib.Path) -> None:
    """`_Claim` beside `Claim` — the underscore IS Python's "internal variant of that".

    ⚠️ NAME FOR NAME. `_WireClaim` beside `Claim` is NOT exempt and should not be: the underscore
    says "internal", it does not say "internal version of Claim". My first triage counted every
    private class as a twin and overstated this category by more than half.
    """
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class Claim(BaseModel):
            """What the plan asserts."""
            text: str
            subject: str

        class _Claim(BaseModel):
            """What the plan asserts — the wire form."""
            text: str
            subject: str
    ''')
    assert _pairs(root) == []


def test_two_unrelated_privates_are_NOT_exempt(tmp_path: pathlib.Path) -> None:
    """The PASS twin, and the reason the check compares NAMES rather than just the underscore.

    Exempting every private class would silence a whole namespace. `_ClaimCache` is not the private
    variant of `Claim` — it is a different concept that happens to be internal.
    """
    root = _write(tmp_path, '''
        from pydantic import BaseModel

        class ClaimRecord(BaseModel):
            """One asserted claim."""
            text: str
            subject: str

        class _ClaimHolder(BaseModel):
            """One asserted claim."""
            text: str
            subject: str
    ''')
    assert _pairs(root), "only a name-for-name twin is exempt"
