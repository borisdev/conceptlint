"""Reading ordinary Pydantic — and, more importantly, when to say nothing.

Every FLAG case here has a PASS twin. A checker that fires on names alone is one people uninstall,
and then the true findings stop arriving too.
"""
from __future__ import annotations

import pathlib
import textwrap

import pytest

from conceptlint.models import discover_models, near_duplicates


def _write(tmp: pathlib.Path, body: str) -> pathlib.Path:
    (tmp / "models.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp


def _pairs(tmp: pathlib.Path) -> list[tuple[str, str]]:
    return [(a.name, b.name) for a, b, _ in near_duplicates(discover_models(tmp))]


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

    Two `Invariant` subclasses — genuinely different rules — scored 100% because `id`, `refines`
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
