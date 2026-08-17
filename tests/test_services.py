"""`Service` — what a Step needs to EXIST, as opposed to what flows through it.

The docker-compose property: a named volume must be declared top-level before any service mounts it,
and that single mandatory rule is what stops one name meaning three things.
"""
from __future__ import annotations

from plan_types import Plan, Service, Step, Variable, validate
from plan_types.invariants import topology, typing as typing_inv

A = Variable("a", str)
B = Variable("b", str)
PUBMED = Service("pubmed", kind="api", why="literature retrieval; no local substrate")
DISK = Service("semmeddb", kind="file", why="9.5 GB on local disk — cannot run on a container app")


class Retrieves(Step):
    inputs, outputs, uses = (A,), (B,), (PUBMED,)


class Pure(Step):
    inputs, outputs = (A,), (B,)


def test_a_step_may_not_reach_for_an_undeclared_service():
    """The whole point, and the reason it is mandatory rather than conventional.

    A reference with no declaration is how 'retriever' came to mean three things in one
    conversation — the dataflow vocabulary was declared and precise, the infrastructure vocabulary
    was not declared at all.
    """
    plan = Plan(name="p", steps=(Retrieves(),), declared_inputs=(A,))
    findings = validate(plan, [topology.DECLARED_SERVICES])
    assert len(findings) == 1
    assert "pubmed" in str(findings[0])


def test_a_declared_service_nobody_uses_is_reported():
    """Not symmetric decoration. `services` is what a deploy decision reads, so a stale entry
    argues against a deployment that would actually work."""
    plan = Plan(name="p", steps=(Retrieves(),), declared_inputs=(A,), services=(PUBMED, DISK))
    findings = validate(plan, [topology.NO_ORPHAN_SERVICES])
    assert len(findings) == 1 and "semmeddb" in str(findings[0])


def test_a_plan_with_no_services_is_not_a_finding():
    """Most Plans need nothing reachable. Silence is the pass — a rule that fires on every pure
    Plan would be turned off within a week."""
    plan = Plan(name="pure", steps=(Pure(),), declared_inputs=(A,))
    assert validate(plan, list(topology.ALL)) == []


def test_services_are_not_variables():
    """A Service is not an edge. Modelling PubMed as a Variable would put a fake node in every
    diagram and make `single_producer` demand a producer for something nobody produces."""
    plan = Plan(name="p", steps=(Retrieves(),), declared_inputs=(A,), services=(PUBMED,))
    assert PUBMED not in plan.variables
    assert plan.inputs == (A,) and plan.outputs == (B,)


def test_a_service_carries_runtime_state_nowhere():
    """⚠️ `uses` is a REQUIREMENT, in the family of `inputs` — never a record that a call happened.

    If a `status` or `last_called` field ever lands on Service, `typing.plan_time_only` should be
    what catches it, because that is the boundary this whole package exists to keep.
    """
    from plan_types.invariants.typing.plan_time_only import RUNTIME_FIELDS

    fields = set(Service.__dataclass_fields__)
    assert not (fields & RUNTIME_FIELDS), f"Service grew runtime state: {fields & RUNTIME_FIELDS}"


def test_the_grounding_is_honest_about_what_it_does_not_claim():
    """PROV-O names the THING; nothing names the plan-time REQUIREMENT.

    `prov:SoftwareAgent` is real and cited. `prov:wasAssociatedWith` links an Activity — an
    execution that already happened — so citing it for `Step.uses` would mean something it does not
    say. That is the failure `provenance.grounded_citation` exists for.
    """
    from plan_types.invariants.provenance.grounded_citation import ONTOLOGIES, terms_in

    assert Service.ONTOLOGY_IRI.startswith("http://www.w3.org/ns/prov#")
    assert "SoftwareAgent" in terms_in(ONTOLOGIES["http://www.w3.org/ns/prov#"])
