"""A seeded vocabulary is a guess about someone else's words. Two rules keep it from lying.

`vocabularies/dataflow.py` is the one place a model's prior knowledge beats extraction: nothing in a
repo says Airflow's `DAG`, Prefect's `flow` and Temporal's `workflow` are three names for one
concept. But it is still a claim made by someone who has not read your code, and it arrives while
you are typing — the register where a false positive costs the most.

    correctness   a DECLARED CLASS beats a seeded alias
    relevance     a seed for a canonical term you do not have is not advice, it is noise
"""
from __future__ import annotations

import pathlib
import textwrap

from conceptlint.models import discover_models
from conceptlint.vocabularies.dataflow import (
    AMBIGUOUS_ACROSS_FRAMEWORKS, DATAFLOW, applicable, seeded_aliases,
)


def test_a_declared_class_beats_a_seeded_alias(tmp_path: pathlib.Path) -> None:
    """The rule the whole file depends on.

    `Pipeline` as a real class means "pipeline" is a live word with a referent. A seed insisting it
    means `Plan` would report a dead word for a class that is alive — and on nobsmed exactly this
    happens with `Run`, so one collision in twenty is the real rate, not a hypothetical.
    """
    (tmp_path / "m.py").write_text(textwrap.dedent('''
        from pydantic import BaseModel
        class Plan(BaseModel):
            """Steps defined before anything runs."""
            steps: tuple
        class Pipeline(BaseModel):
            """A deployment pipeline, which is a different thing entirely."""
            stages: tuple
    '''), encoding="utf-8")
    names = {m.name for m in discover_models(tmp_path)}
    ok = applicable(names)
    assert "pipeline" not in ok, "a declared class must suppress its seeded alias"
    assert ok["dag"][0] == "Plan", "unclaimed aliases still apply"


def test_a_seed_for_a_concept_you_do_not_have_is_dropped(tmp_path: pathlib.Path) -> None:
    """Relevance. Measured: 25 seeds drop to 3 against nobsmed, which declares only `Run`."""
    (tmp_path / "m.py").write_text(textwrap.dedent('''
        from pydantic import BaseModel
        class Finding(BaseModel):
            """Nothing to do with dataflows."""
            claim: str
    '''), encoding="utf-8")
    assert applicable({m.name for m in discover_models(tmp_path)}) == {}


def test_every_alias_carries_a_source() -> None:
    """A claim needs provenance, or this file is doing what the product exists to catch."""
    for canonical, aliases in DATAFLOW.items():
        for alias, source in aliases:
            assert alias and alias == alias.lower(), f"{canonical}: {alias!r} must be lowercased"
            assert source.strip(), f"{canonical}/{alias} asserts a synonym with no source"


def test_the_genuinely_ambiguous_words_are_not_seeded_as_synonyms() -> None:
    """`task` and `job` mean different LEVELS in different frameworks.

    Seeding either would assert a mapping that is wrong in at least one popular framework, and a
    seed that is confidently wrong is worse than an absent one — the reader has no reason to check.
    They are listed as words to ask about instead.
    """
    aliases = seeded_aliases()
    for word in AMBIGUOUS_ACROSS_FRAMEWORKS:
        assert word not in aliases, f"{word!r} is ambiguous across frameworks; it must not resolve"


def test_no_alias_is_also_a_canonical_term() -> None:
    """`Step` must never be seeded as an alias of something else, or the table contradicts itself."""
    canon = {c.lower() for c in DATAFLOW}
    for alias in seeded_aliases():
        assert alias not in canon, f"{alias!r} is both canonical and an alias"
