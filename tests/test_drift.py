"""Drift needs two points in time. Three of four cases must stay silent.

    docstring changed, fields changed   evolution — they decided, and said so   silent
    docstring changed, fields same      a rewording                             silent
    docstring same,    fields same      nothing happened                        silent
    docstring same,    fields CHANGED   the promise no longer describes it      FLAG

That asymmetry is the check. A developer who updates the docstring has made a decision and must not
be nagged for it — silence on three cases is what makes the fourth worth reading.
"""
from __future__ import annotations

import pathlib
import subprocess
import textwrap

import pytest

from conceptlint.drift import drifted


def _repo(tmp: pathlib.Path, first: str, second: str) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    for k, v in (("user.email", "t@t.t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(tmp), "config", k, v], check=True)
    for body in (first, second):
        (tmp / "models.py").write_text(textwrap.dedent(body), encoding="utf-8")
        subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True)
        # --allow-empty: the "nothing changed" case commits identical content twice, and git
        # refuses that by default. The fixture must be able to express a no-op.
        subprocess.run(["git", "-C", str(tmp), "commit", "-qm", "x", "--allow-empty"],
                       check=True)
    return tmp


def _names(tmp: pathlib.Path) -> list[str]:
    return [d.name for d in drifted(tmp, since="HEAD~1")]


def test_fields_move_while_the_promise_stands(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path, '''
        from pydantic import BaseModel

        class Variable(BaseModel):
            """A typed placeholder connecting steps in a plan."""
            name: str
            type: str
    ''', '''
        from pydantic import BaseModel

        class Variable(BaseModel):
            """A typed placeholder connecting steps in a plan."""
            name: str
            started_at: str
            ended_at: str
            actual_value: str
    ''')
    assert _names(root) == ["Variable"]


def test_updating_the_docstring_is_a_decision_not_drift(tmp_path: pathlib.Path) -> None:
    """The most important silent case. Nagging someone for documenting a change teaches them to
    ignore the tool."""
    root = _repo(tmp_path, '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
            title: str
    ''', '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper, with the fields we index on."""
            pmid: str
            doi: str
            journal: str
    ''')
    assert _names(root) == []


def test_a_rewording_alone_is_silent(tmp_path: pathlib.Path) -> None:
    root = _repo(tmp_path, '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A paper."""
            pmid: str
            title: str
    ''', '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
            title: str
    ''')
    assert _names(root) == []


def test_no_change_is_silent(tmp_path: pathlib.Path) -> None:
    body = '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
            title: str
    '''
    assert _names(_repo(tmp_path, body, body)) == []


def test_one_field_of_many_is_not_drift(tmp_path: pathlib.Path) -> None:
    """Renaming one field of six is maintenance. Replacing half of them is a different concept."""
    root = _repo(tmp_path, '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
            title: str
            journal: str
            year: int
            doi: str
            abstract: str
    ''', '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
            title: str
            journal: str
            year: int
            doi: str
            summary: str
    ''')
    assert _names(root) == []


def test_a_brand_new_model_is_not_drift(tmp_path: pathlib.Path) -> None:
    """Nothing to compare against. 'Cannot tell' must never be reported as a finding."""
    root = _repo(tmp_path, '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
    ''', '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str

        class Finding(BaseModel):
            """A proposition."""
            text: str
            source_id: str
    ''')
    assert _names(root) == []


def test_a_directory_with_no_git_history_is_silent(tmp_path: pathlib.Path) -> None:
    (tmp_path / "models.py").write_text(
        "from pydantic import BaseModel\n\n\nclass A(BaseModel):\n    x: str\n", encoding="utf-8")
    assert drifted(tmp_path) == []


def test_boilerplate_churn_does_not_count(tmp_path: pathlib.Path) -> None:
    """Adding `id` and `created_at` to everything is a migration, not a meaning change."""
    root = _repo(tmp_path, '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            pmid: str
            title: str
    ''', '''
        from pydantic import BaseModel

        class Study(BaseModel):
            """A published paper."""
            id: str
            created_at: str
            pmid: str
            title: str
    ''')
    assert _names(root) == []
