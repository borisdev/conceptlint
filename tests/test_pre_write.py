"""The hook that interrupts before a model is written.

Its value is entirely in when it stays SILENT. A hook that comments on ordinary edits is removed
within a day, and the useful interrupt goes with it — so most of these tests assert silence.
"""
from __future__ import annotations

import pathlib
import textwrap

from conceptlint.integrations.pre_write import review

EXISTING = '''
    from pydantic import BaseModel

    class Finding(BaseModel):
        """A proposition extracted from a source."""
        text: str
        source_id: str
'''


def _repo(tmp: pathlib.Path) -> pathlib.Path:
    (tmp / "models.py").write_text(textwrap.dedent(EXISTING), encoding="utf-8")
    return tmp


def test_a_near_duplicate_names_the_model_that_already_exists(tmp_path: pathlib.Path) -> None:
    msg = review(textwrap.dedent('''
        from pydantic import BaseModel

        class ResearchFinding(BaseModel):
            """A proposition from research."""
            text: str
            source_id: str
    '''), _repo(tmp_path), path="new.py")
    assert msg and "Finding" in msg and "models.py:4" in msg


def test_a_genuinely_new_model_asks_the_four_questions(tmp_path: pathlib.Path) -> None:
    """Not a block. The agent may have a good reason; the hook makes the question unavoidable."""
    msg = review(textwrap.dedent('''
        from pydantic import BaseModel

        class RetryPolicy(BaseModel):
            attempts: int
            backoff: float
    '''), _repo(tmp_path), path="retry.py")
    assert msg
    for option in ("reuse", "extend", "compose", "split"):
        assert option in msg
    assert "`kind` discriminator" in msg


def test_editing_an_existing_model_is_silent(tmp_path: pathlib.Path) -> None:
    """The noise case. A name that exists anywhere is being edited, not invented — the first
    version inverted this and fired on every edit to a model."""
    msg = review(textwrap.dedent('''
        from pydantic import BaseModel

        class Finding(BaseModel):
            """A proposition extracted from a source."""
            text: str
            source_id: str
            pmid: str
    '''), _repo(tmp_path), path="models.py")
    assert msg is None


def test_a_file_with_no_models_is_silent(tmp_path: pathlib.Path) -> None:
    assert review("def helper():\n    return 1\n", _repo(tmp_path), path="util.py") is None


def test_unparseable_content_is_silent(tmp_path: pathlib.Path) -> None:
    """Mid-edit source is not the hook's business."""
    assert review("class Broken(BaseModel:\n", _repo(tmp_path), path="x.py") is None


def test_a_plain_class_is_not_a_domain_model(tmp_path: pathlib.Path) -> None:
    assert review("class Helper:\n    pass\n", _repo(tmp_path), path="h.py") is None


def test_it_fails_open_on_an_unreadable_repo(tmp_path: pathlib.Path) -> None:
    """A convenience must never be able to stop work."""
    msg = review("from pydantic import BaseModel\n\nclass X(BaseModel):\n    a: str\n",
                 tmp_path / "does-not-exist", path="x.py")
    assert msg is None or "X" in msg


# ── CLI guards ────────────────────────────────────────────────────────────────────────────────────

def test_a_path_that_does_not_exist_is_an_error_not_silence(tmp_path: pathlib.Path) -> None:
    """Silence is the pass, so anything that makes the tool silent for the WRONG reason is worse
    than an error. `conceptlint install-rule` was parsed as a PATH, found nothing, and exited 0 —
    reading exactly like a clean repo."""
    from conceptlint.core.lint import main
    assert main([str(tmp_path / "nope")]) == 2


def test_the_agent_rule_installs_and_uninstalls(tmp_path: pathlib.Path) -> None:
    from conceptlint.integrations import claude_code
    rule = tmp_path / "domain-language.md"
    assert claude_code.install(rule) == rule
    assert "Speak the same words in prose as in code" in rule.read_text(encoding="utf-8")
    assert claude_code.uninstall(rule) is True
    assert claude_code.uninstall(rule) is False


def test_the_rule_names_the_words_that_actually_drifted() -> None:
    """`workflow` and `dataflow` are in it by name, because that is the pair that drifted for a
    week without anything noticing."""
    text = (pathlib.Path(__file__).resolve().parents[1]
            / "conceptlint" / "integrations" / "agent_rule.md").read_text(encoding="utf-8")
    for word in ("workflow", "dataflow", "activity", "step"):
        assert word in text
