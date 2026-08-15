"""The execution graph: typed provenance, and the integrity it refuses to assume."""
from __future__ import annotations

from datetime import datetime

import pytest

from conceptlint.dataflow.execution import (Activity, Agent, Entity, GraphError, Run, Used,
                                            WasAssociatedWith, WasDerivedFrom, WasGeneratedBy)

NOW = datetime(2026, 8, 15, 3, 0)


def _run() -> Run:
    r = Run(plan_name="evidence_case_graph")
    r.add(Entity(id="e:study"))
    r.add(Entity(id="e:findings", content_hash="sha:abc"))
    r.add(Activity(id="a:parse", step_name="ParseStudyStep", started_at=NOW))
    r.add(Agent(id="ag:1", name="evidence_first"))
    return r


def test_a_node_stamps_its_own_wire_tag() -> None:
    assert Entity(id="e:1").kind == "entity"
    assert Activity(id="a:1", step_name="s", started_at=NOW).kind == "activity"


def test_edges_that_resolve_are_accepted() -> None:
    r = _run()
    Run(plan_name="p", entities=r.entities, activities=r.activities, agents=r.agents,
        used=(Used(activity_id="a:parse", entity_id="e:study"),),
        generated=(WasGeneratedBy(entity_id="e:findings", activity_id="a:parse"),),
        derived=(WasDerivedFrom(entity_id="e:findings", source_id="e:study"),),
        associated=(WasAssociatedWith(activity_id="a:parse", agent_id="ag:1"),))


@pytest.mark.parametrize("kwargs,missing", [
    ({"used": (Used(activity_id="a:ghost", entity_id="e:study"),)}, "a:ghost"),
    ({"generated": (WasGeneratedBy(entity_id="e:ghost", activity_id="a:parse"),)}, "e:ghost"),
    ({"derived": (WasDerivedFrom(entity_id="e:findings", source_id="e:ghost"),)}, "e:ghost"),
    ({"associated": (WasAssociatedWith(activity_id="a:parse", agent_id="ag:ghost"),)}, "ag:ghost"),
])
def test_a_dangling_edge_is_refused_on_every_relation(kwargs, missing) -> None:
    """Lineage would otherwise return a SHORTER answer rather than an error, and 'derives from
    nothing' would be indistinguishable from 'is a root'."""
    r = _run()
    with pytest.raises(GraphError, match=missing):
        Run(plan_name="p", entities=r.entities, activities=r.activities, agents=r.agents, **kwargs)


def test_graph_error_is_not_a_valueerror_so_it_survives_pydantic() -> None:
    """Pydantic catches ValueError inside a validator and rewraps it, so `except GraphError` would
    silently never fire. This test is the reason GraphError subclasses Exception."""
    assert not issubclass(GraphError, ValueError)


def test_a_node_without_an_id_cannot_join_a_run() -> None:
    """A draft node legitimately has no id; being IN a graph is what makes one necessary."""
    with pytest.raises(GraphError, match="needs an id"):
        Run(plan_name="p").add(Entity(id=""))


def test_two_classes_cannot_claim_one_kind_tag() -> None:
    with pytest.raises(GraphError, match="is claimed by"):
        type("Rival", (Entity,), {"KIND": "entity"})


def test_a_subclass_keeps_its_fields_through_a_round_trip() -> None:
    """`SerializeAsAny` on the containers. Without it Pydantic serialises against the DECLARED type
    and a subclass's fields vanish ON WRITE — the bug the KINDS registry was built for."""
    class PaperEntity(Entity):
        KIND = "paper_entity"
        pmid: str

    r = Run(plan_name="p")
    r.add(PaperEntity(id="e:paper", pmid="pmid:123"))
    assert "pmid" in r.model_dump()["entities"]["e:paper"]
