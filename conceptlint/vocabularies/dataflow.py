"""What the Python dataflow-tooling world calls these things — the cross-framework Rosetta stone.

Boris, 2026-08-15: *"our earlier vocab aliases can be populated by you ... since you already know
the domain is software tooling to build data flows in python."*

Right, and this is the one place a model's prior knowledge is worth more than extraction. Nothing in
a repo says that Airflow's `DAG`, Prefect's `flow`, Dagster's `job` and Temporal's `workflow` are
four names for one concept. That is not in the code; it is in having read all four.

## The rule that decides whether this helps or lies

    A DECLARED CLASS ALWAYS BEATS A SEEDED ALIAS.

Everything below is a guess about a vocabulary, made by someone who has not read your repo. If your
codebase declares `class Run`, then "run" is a live word with a real referent, and a seed insisting
it means `Activity` would report a dead word for a class that is alive — noise, in the one register
where noise is fatal, because it arrives while someone is typing.

Measured on nobsmed the moment this was written: of twenty seeded terms, exactly one — `run` —
collides with a declared class. One is enough. The suppression is not a precaution, it is load
bearing.

## Provenance, because a claim needs a source

Every alias names the framework it comes from. An alias with no source is a word someone liked, and
this file would then be doing exactly what the product exists to catch: asserting past its evidence.

⚠️ The subtle one, and it is subtle enough that the dataflow README calls it out on its own:
**Temporal's `Activity` is our `Activity`, not our `Step`.** Anyone reading it the other way is
wrong by exactly one level and has no reason to suspect it. Likewise Airflow's `task` is plan-time
(a `Step`) while its `task instance` is runtime (an `Activity`) — the same word, one level apart,
which is why both appear below pointing at different canonical terms.
"""
from __future__ import annotations

#: canonical term -> (alias, where the alias comes from)
#:
#: Deliberately NOT exhaustive. Every entry is a word that a competent engineer would use as a
#: synonym without noticing they had switched vocabularies, which is the only kind worth seeding.
#: Generic words — "model", "data", "object", "item" — are excluded: they collide with everything
#: and firing on them is how this gets switched off.
DATAFLOW: dict[str, tuple[tuple[str, str], ...]] = {
    "Plan": (
        ("workflow", "Temporal"),
        ("dag", "Airflow"),
        ("flow", "Prefect / Metaflow"),
        ("pipeline", "Kubeflow / scikit-learn"),
        ("jobgraph", "Flink"),
    ),
    "Step": (
        ("operator", "Airflow"),
        ("op", "Dagster"),
        ("component", "Kubeflow"),
        ("stage", "Spark / CI vocabulary"),
    ),
    "Variable": (
        ("port", "Kubeflow / NiFi"),
        ("slot", "generic node-graph vocabulary"),
        ("xcom", "Airflow"),
    ),
    "Activity": (
        ("taskinstance", "Airflow — the RUNTIME half of `task`"),
        ("taskrun", "Prefect"),
        ("steprun", "Metaflow"),
        ("invocation", "generic"),
    ),
    "Entity": (
        ("artifact", "MLflow / Kubeflow"),
        ("asset", "Dagster"),
        ("target", "Luigi"),
    ),
    "Run": (
        ("flowrun", "Prefect"),
        ("pipelinerun", "Kubeflow"),
        ("dagrun", "Airflow"),
    ),
    "Agent": (
        ("worker", "Temporal / Celery"),
        ("executor", "Airflow / Spark"),
        ("runner", "generic CI vocabulary"),
    ),
}

#: ⚠️ `task` and `job` are deliberately ABSENT.
#:
#: Both are genuinely ambiguous ACROSS frameworks rather than merely synonymous: Airflow's `task` is
#: plan-time, Prefect's `task` is plan-time but its `task run` is runtime, and Dagster's `job` is a
#: whole Plan while Kubernetes' `Job` is one execution. Seeding either would assert a mapping that
#: is wrong in at least one popular framework — and a seed that is confidently wrong is worse than
#: an absent one, because the reader has no reason to check it.
#:
#: They belong in the AMBIGUOUS list instead: words to ask about, never to resolve.
AMBIGUOUS_ACROSS_FRAMEWORKS: dict[str, str] = {
    "task": "plan-time in Airflow/Prefect, runtime in Celery — say Step or Activity",
    "job": "a whole Plan in Dagster, one execution in Kubernetes — say Plan or Run",
    "node": "a Step in a DAG, a machine in a cluster — say Step or Worker",
    "execution": "a Run of a Plan, or one Activity — say which",
}


def seeded_aliases(vocabulary: dict[str, tuple[tuple[str, str], ...]] | None = None
                   ) -> dict[str, tuple[str, str]]:
    """alias -> (canonical term, the framework it comes from), lowercased."""
    out: dict[str, tuple[str, str]] = {}
    for canonical, aliases in (vocabulary or DATAFLOW).items():
        for alias, source in aliases:
            out[alias.lower()] = (canonical, source)
    return out


def applicable(declared_names: set[str],
               vocabulary: dict[str, tuple[tuple[str, str], ...]] | None = None
               ) -> dict[str, tuple[str, str]]:
    """The seeded aliases that are safe to use against a repo declaring `declared_names`.

    A seed is DROPPED when the alias is itself a declared class, and when its canonical term is not
    declared at all. The first is the correctness rule at the top of this file. The second is the
    relevance rule: telling someone "pipeline means Plan" in a repo that has no `Plan` is advice
    about a vocabulary they do not use.
    """
    lowered = {n.lower() for n in declared_names}
    return {alias: (canonical, source)
            for alias, (canonical, source) in seeded_aliases(vocabulary).items()
            if alias not in lowered and canonical.lower() in lowered}
