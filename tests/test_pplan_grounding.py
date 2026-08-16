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
    "conceptlint" / "ontologies" / "pplan" / "vendored" / "p-plan.ttl"

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
    """A citation to a term that is not in the source is the cheapest version of this bug."""
    from conceptlint.dataflow import Plan, Step, Variable
    from conceptlint.ontologies.pplan import concepts

    cited = set()
    for mod in (Step, Variable, Plan):
        iri = getattr(mod, "ONTOLOGY_IRI", "")
        if iri:
            cited.add(iri)
    for name in dir(concepts):
        iri = getattr(getattr(concepts, name), "ONTOLOGY_IRI", "") if not name.startswith("_") else ""
        if isinstance(iri, str) and iri:
            cited.add(iri)

    assert cited, "nothing cites an ontology — this guard would be checking nothing"
    for iri in sorted(cited):
        if not iri.startswith(PPLAN):
            continue                      # PROV-O terms are checked by their own grounding test
        term = iri[len(PPLAN):]
        assert term in pplan, f"{iri} is cited but {term} is not in the P-Plan ontology"


def test_our_step_allows_many_inputs_like_the_ontology_does():
    """Was xfail until 2026-08-16. The marker was strict, so landing the fix forced its deletion."""
    from conceptlint.dataflow import Step, Variable

    class ThreeIn(Step):
        inputs = (Variable("a", str), Variable("b", int), Variable("c", float))
        outputs = (Variable("d", dict),)

    assert len(ThreeIn.inputs) == 3, "P-Plan puts no cardinality on hasInputVar"


def test_our_step_allows_many_outputs_like_the_ontology_does():
    from conceptlint.dataflow import Step, Variable

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
    from conceptlint.dataflow import Plan, Step, Variable

    A, B, C, D = (Variable("a", str), Variable("b", int),
                  Variable("c", float), Variable("d", dict))

    class First(Step):                    # needs TWO inputs, so first/last cannot describe the Plan
        inputs, outputs = (A, B), (C,)
        def run(self, **v): return 1.0

    class Second(Step):
        inputs, outputs = (C,), (D,)
        def run(self, **v): return {}

    plan = Plan(name="fanin", steps=(First(), Second()))
    assert {v.name for v in plan.inputs} == {"a", "b"}, \
        "Plan inputs are the FREE variables, not steps[0].consumes"
    assert {v.name for v in plan.outputs} == {"d"}

    # And order is derived: declaring them backwards must not change the execution order.
    backwards = Plan(name="fanin", steps=(Second(), First()))
    assert [type(s).__name__ for s in backwards.order()] == ["First", "Second"]


def test_we_model_multistep():
    """p-plan:MultiStep — rdfs:subClassOf both Plan and Step. Nesting is modelled, not faked."""
    from conceptlint.dataflow import MultiStep, Plan, Step

    assert issubclass(MultiStep, Plan)
    assert hasattr(MultiStep, "decomposed_as_plan"), "p-plan:isDecomposedAsPlan"


# --- the invariant, and the trap it fell into ----------------------------------------------------


def test_grounded_citation_is_registered_with_the_other_invariants():
    """⚠️ Registration is SUBCLASSING, so an Invariant in an unimported module does not exist.

    `GroundedCitation` was written, wired to nothing, and would have reported green forever —
    the exact failure it exists to catch, in the code catching it. `core/lint.py` imports the
    module for its side effect; this asserts the import is still there.
    """
    import conceptlint.core.lint  # noqa: F401 — the import IS the registration
    from conceptlint.core.invariant import registered

    assert "grounded-citation" in {i.ID for i in registered()}


def test_grounded_citation_reports_a_term_that_does_not_exist():
    from conceptlint.ontologies.invariants import GroundedCitation

    # ⚠️ NOT a Concept subclass. Registration is subclassing, so declaring one here would leak into
    # `declared()` for every test that ran afterwards — which is exactly what it did: this file
    # passed alone and failed in the suite. Same trap the Invariant registry hit once already.
    class Fabricated:
        ONTOLOGY_IRI = "http://purl.org/net/p-plan#Workflow"

    issues = list(GroundedCitation().check([Fabricated]))
    assert issues and "not a term" in issues[0].message


def test_an_unvendored_ontology_is_reported_not_silently_passed():
    """"We cannot check this" and "this is fine" must never render the same."""
    from conceptlint.ontologies.invariants import GroundedCitation

    class Elsewhere:                      # plain class, for the reason above
        ONTOLOGY_IRI = "http://schema.org/Thing"

    issues = list(GroundedCitation().check([Elsewhere]))
    assert issues and "not vendored" in issues[0].message


def test_every_real_citation_in_this_package_resolves():
    """The shipped vocabulary, checked against the shipped ontologies."""
    from conceptlint.core.concept import declared
    from conceptlint.ontologies import pplan  # noqa: F401
    from conceptlint.ontologies.invariants import GroundedCitation
    import conceptlint.ontologies.pplan.concepts  # noqa: F401

    # Filtered to concepts DECLARED IN THIS PACKAGE. Without it the assertion is at the mercy of
    # whatever any other test subclassed, and a global registry makes that action at a distance.
    concepts = [c for c in declared()
                if getattr(c, "__module__", "").startswith("conceptlint.")]
    assert concepts, "no Concepts registered — this guard would be checking nothing"
    assert [c for c in concepts if getattr(c, "ONTOLOGY_IRI", "")], "no citations to check"
    assert list(GroundedCitation().check(concepts)) == []


def test_both_vendored_ontologies_parse_to_real_terms():
    """An HTML error page saved as .ttl parses to zero terms and passes everything vacuously."""
    from conceptlint.ontologies.invariants import ONTOLOGIES, terms_in

    for prefix, rel in ONTOLOGIES.items():
        found = terms_in(rel)
        assert len(found) > 10, f"{prefix} -> {rel} yielded {len(found)} terms; is it really RDF?"
