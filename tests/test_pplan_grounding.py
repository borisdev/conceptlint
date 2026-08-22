"""`ONTOLOGY_IRI` is a CITATION. This is the test that reads the source.

## Why this file exists

`dataflow/step.py` carries `ONTOLOGY_IRI = "http://purl.org/net/p-plan#Step"` with the comment
"P-Plan grounding, read by ConceptLint". That field is a claim about somebody else's ontology — and
it was written without reading it. The result: `Step` was given ONE `consumes` and ONE `produces`,
and `Plan` was validated as a pairwise chain, neither of which P-Plan says.

That is the same failure shape the product exists to catch: an assertion carrying a citation the
source does not support. An omission citing a PMID nobody fetched is the medical version; this is
the ontology version, and it survived because nothing read the source.

⚠️ So the rule is not "be careful". A claim about an external source is only grounded if something
reads that source and fails.

## What it checks

The vendored `p-plan.ttl` (see PROVENANCE.md — fixed snapshot, hashed) is parsed for the handful of
axioms our design depends on, and each is asserted against what we actually implement:

    hasInputVar  has no cardinality restriction   ->  a Step may consume MANY Variables
    hasOutputVar has no cardinality restriction   ->  a Step may produce MANY Variables
    isOutputVarOf IS owl:FunctionalProperty       ->  a Variable has exactly ONE producer
    isInputVarOf is NOT functional                ->  a Variable may feed MANY Steps
    MultiStep is both a Plan and a Step           ->  a Plan may appear as a Step

## The four known divergences are xfail(strict=True), not deletions

They are failing tests, on purpose. `strict=True` means each one FAILS if it starts passing, so
whoever fixes `dataflow` is forced to remove the marker rather than leaving a green test that no
longer describes anything. A comment saying "we know this is wrong" cannot do that.
"""
from __future__ import annotations

import pathlib
import re

import pytest

TTL = pathlib.Path(__file__).resolve().parents[1] / \
    "workflow_plan" / "ontology" / "vendored" / "p-plan.ttl"

PPLAN = "http://purl.org/net/p-plan#"


def _blocks(text: str) -> dict[str, str]:
    """`:Name` -> the Turtle statement block for it. Enough for a stable ontology, no rdflib.

    A parser dependency for a linter is weight, and P-Plan's serialisation is regular: each subject
    starts at column 0 and its predicates are indented until the terminating period.
    """
    out: dict[str, str] = {}
    current, buf = None, []
    for line in text.splitlines():
        if line.startswith(":") and not line.startswith(":  "):
            if current:
                out[current] = "\n".join(buf)
            current, buf = line[1:].strip(), [line]
        elif current:
            buf.append(line)
            if line.rstrip().endswith("."):
                out[current] = "\n".join(buf)
                current, buf = None, []
    if current:
        out[current] = "\n".join(buf)
    return out


@pytest.fixture(scope="module")
def pplan() -> dict[str, str]:
    assert TTL.exists(), f"vendored ontology missing at {TTL} — see PROVENANCE.md"
    blocks = _blocks(TTL.read_text(encoding="utf-8"))
    # If the snapshot were ever replaced by an HTML error page (which is how the first three
    # fetches "succeeded"), every assertion below would vacuously pass on an empty dict.
    assert len(blocks) > 10, f"parsed only {len(blocks)} subjects — is the vendored file real RDF?"
    return blocks


# ── what the ontology says ───────────────────────────────────────────────────────────────────────

def test_the_vendored_file_is_actually_p_plan(pplan):
    assert f"<{PPLAN}" in TTL.read_text(encoding="utf-8") or "p-plan#" in TTL.read_text(encoding="utf-8")
    for name in ("Plan", "Step", "Variable", "MultiStep", "hasInputVar", "hasOutputVar"):
        assert name in pplan, f"{name} absent — this is not the P-Plan ontology"


def test_hasinputvar_has_no_cardinality_restriction(pplan):
    """The axiom our design got wrong. A Step may take MANY inputs."""
    block = pplan["hasInputVar"]
    assert "FunctionalProperty" not in block
    assert "cardinality" not in block.lower()


def test_hasoutputvar_has_no_cardinality_restriction(pplan):
    block = pplan["hasOutputVar"]
    assert "FunctionalProperty" not in block
    assert "cardinality" not in block.lower()


def test_isoutputvarof_is_functional_so_a_variable_has_one_producer(pplan):
    """This one IS an ontology axiom — so 'one producer per Variable' is not ours to invent."""
    assert "FunctionalProperty" in pplan["isOutputVarOf"]


def test_isinputvarof_is_not_functional_so_a_variable_may_feed_many_steps(pplan):
    assert "FunctionalProperty" not in pplan["isInputVarOf"]


def test_multistep_is_both_a_plan_and_a_step(pplan):
    """A Plan may appear as a Step — the nested sub-DAG, named in the ontology."""
    block = pplan["MultiStep"]
    assert "Plan" in block and "Step" in block


def test_pplan_does_not_require_acyclicity(pplan):
    """⚠️ So a DAG constraint is OURS, and must be labelled as ours rather than as grounding."""
    text = TTL.read_text(encoding="utf-8")
    assert "acyclic" not in text.lower()
    assert "TransitiveProperty" in pplan["isPrecededBy"], "ordering is isPrecededBy, transitive"


# ── what WE implement, asserted against the above ────────────────────────────────────────────────

def test_every_ontology_iri_we_cite_exists_in_the_vendored_ontology(pplan):
    """A citation to a term that is not in the source is the cheapest version of this bug.

    ⚠️ Reads the `DeclaredTerm` registry rather than a hand-listed tuple of classes. The hand-list
    was `(Step, Variable, Plan)` plus a `dir()` sweep of the toy declarations in
    `conceptlint/ontologies/pplan/` — so `MultiStep` and `Service`, which both carry an IRI, were
    never checked by it, and adding a seventh term would have gone unchecked too. A guard over a
    list somebody remembers to extend is a guard that goes quiet exactly when the vocabulary grows.
    """
    import workflow_plan.plan  # noqa: F401 — the declarations must be imported to be declared
    from workflow_plan.naming.declared_term import declared

    cited = {c.ONTOLOGY_IRI for c in declared() if c.ONTOLOGY_IRI}

    assert cited, "nothing cites an ontology — this guard would be checking nothing"
    for iri in sorted(cited):
        if not iri.startswith(PPLAN):
            continue                      # PROV-O terms are checked by their own grounding test
        term = iri[len(PPLAN):]
        assert term in pplan, f"{iri} is cited but {term} is not in the P-Plan ontology"


def test_our_step_allows_many_inputs_like_the_ontology_does():
    """Was xfail until 2026-08-16. The marker was strict, so landing the fix forced its deletion."""
    from workflow_plan.plan import Step, Variable

    class ThreeIn(Step):
        inputs = (Variable("a", str), Variable("b", int), Variable("c", float))
        outputs = (Variable("d", dict),)

    assert len(ThreeIn.inputs) == 3, "P-Plan puts no cardinality on hasInputVar"


def test_our_step_allows_many_outputs_like_the_ontology_does():
    from workflow_plan.plan import Step, Variable

    class TwoOut(Step):
        inputs = (Variable("a", str),)
        outputs = (Variable("b", int), Variable("c", float))

    assert len(TwoOut.outputs) == 2, "P-Plan puts no cardinality on hasOutputVar"


def test_our_plan_does_not_assume_a_linear_chain():
    """Behaviour, not source text.

    The first version grepped `inspect.getsource` for "steps[1:]" — and then FAILED after the fix,
    because the new module docstring *describes* the old behaviour it replaced. A test that reads
    prose cannot tell an implementation from an explanation of why it is gone.
    """
    from workflow_plan.plan import Plan, Step, Variable, execution_order

    A, B, C, D = (Variable("a", str), Variable("b", int),
                  Variable("c", float), Variable("d", dict))

    class First(Step):                    # needs TWO inputs, so first/last cannot describe the Plan
        inputs, outputs = (A, B), (C,)

    class Second(Step):
        inputs, outputs = (C,), (D,)

    plan = Plan(name="fanin", steps=(First(), Second()))
    assert {v.name for v in plan.inputs} == {"a", "b"}, \
        "Plan inputs are the FREE variables, not steps[0].consumes"
    assert {v.name for v in plan.outputs} == {"d"}

    # And order is derived: declaring them backwards must not change the execution order.
    backwards = Plan(name="fanin", steps=(Second(), First()))
    assert [type(s).__name__ for s in execution_order(backwards)] == ["First", "Second"]


def test_we_model_multistep():
    """p-plan:MultiStep — rdfs:subClassOf both Plan and Step. Nesting is modelled, not faked."""
    from workflow_plan.plan import MultiStep, Plan, Step

    assert issubclass(MultiStep, Plan)
    assert hasattr(MultiStep, "decomposed_as_plan"), "p-plan:isDecomposedAsPlan"


# --- the invariant, ported to SemanticInvariant --------------------------------------------------


def test_grounded_citation_reports_a_term_that_does_not_exist():
    from workflow_plan.invariants import validate
    from workflow_plan.invariants.provenance import ALL as PROV
    from workflow_plan.naming.records import ModelRecord

    fake = ModelRecord(name="Fabricated", docstring="", fields=(), bases=(), file="f.py", line=1,
                       ontology_iri="http://purl.org/net/p-plan#Workflow")
    found = validate([fake], PROV)
    assert found and "not a term" in found[0].message


def test_an_unvendored_ontology_is_reported_not_silently_passed():
    """"We cannot check this" and "this is fine" must never render the same."""
    from workflow_plan.invariants import validate
    from workflow_plan.invariants.provenance import ALL as PROV
    from workflow_plan.naming.records import ModelRecord

    elsewhere = ModelRecord(name="Elsewhere", docstring="", fields=(), bases=(), file="f.py",
                            line=1, ontology_iri="http://schema.org/Thing")
    found = validate([elsewhere], PROV)
    assert found and "not vendored" in found[0].message


def test_this_packages_own_citations_resolve():
    """The shipped vocabulary, checked against the shipped ontologies."""
    from workflow_plan.invariants import validate
    from workflow_plan.invariants.provenance import ALL as PROV
    import workflow_plan.plan  # noqa: F401 — the declarations must be imported to be declared
    from workflow_plan.naming.declared_term import declared
    from workflow_plan.naming.records import ModelRecord

    cited = [ModelRecord(name=c.__name__, docstring="", fields=(), bases=(), file="x.py", line=1,
                         ontology_iri=c.ONTOLOGY_IRI)
             for c in declared()]
    assert [c.ontology_iri for c in cited if c.ontology_iri], "nothing cites — guard checks nothing"
    assert validate(cited, PROV) == []


def test_both_vendored_ontologies_parse_to_real_terms():
    """An HTML error page saved as .ttl parses to zero terms and passes everything vacuously."""
    from workflow_plan.invariants.provenance import ONTOLOGIES, terms_in

    for prefix, rel in ONTOLOGIES.items():
        assert len(terms_in(rel)) > 10, f"{prefix} -> {rel} yielded too few terms; is it RDF?"
