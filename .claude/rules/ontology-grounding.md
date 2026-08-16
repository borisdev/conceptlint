# Never cite an ontology you have not read

## What happened, 2026-08-15

`conceptlint/dataflow/step.py` was written with:

```python
ONTOLOGY_IRI: ClassVar[str] = "http://purl.org/net/p-plan#Step"   # "P-Plan grounding"
```

written **from memory**, and then `Step` was given a single `consumes` and a single `produces`, and
`Plan` was validated as a pairwise chain. The actual ontology says none of that:

| P-Plan says | we implemented |
|---|---|
| `hasInputVar` — no cardinality restriction | one input |
| `hasOutputVar` — no cardinality restriction | one output |
| `isOutputVarOf` **is** `owl:FunctionalProperty` | not modelled |
| `MultiStep` — a Plan that IS a Step | not modelled |
| ordering via transitive `isPrecededBy` | declaration order |

It surfaced only when a real builder — `evidence_first`, whose fifth step needs three earlier values
at once — could not be expressed. The package was **wrong for a month and green the whole time.**

## The rule

**An `ONTOLOGY_IRI` is a citation. A citation with no path back to the source is decoration with the
authority of a fact.**

Nobody lied. That is the point: an unverifiable claim and a verified one are *indistinguishable at
the call site*, so writing one from recall feels identical to having read the spec.

Concretely:

1. **Vendor the ontology before citing it.** `conceptlint/ontologies/<name>/vendored/` with a
   `PROVENANCE.md` carrying the source URL, retrieval date and sha256.
2. **Read the axioms you depend on.** Cardinality, functional properties, domain and range — not the
   class names, which are the part memory gets right and which prove nothing.
3. **Say which constraints are OURS.** P-Plan does not require acyclicity. If we want a DAG, that is
   our constraint, and labelling it as grounding is the same error one level down.
4. **A citation you cannot check is a FINDING, not a pass.** `GroundedCitation` reports an IRI whose
   ontology is not vendored. *"We cannot check this"* and *"this is fine"* must never render the same.

## What enforces it

| | |
|---|---|
| `conceptlint/ontologies/invariants.py` — `GroundedCitation` | the cited term exists in a vendored ontology |
| `tests/test_pplan_grounding.py` | the AXIOMS we depend on, read from the vendored Turtle |
| four `xfail(strict=True)` in that file | each known divergence fails when it starts passing, so a fix must delete the marker |

⚠️ The semantic half is **not** automatable. That the cited term *means* what we implement is a
reading, not a decision procedure — an invariant pretending otherwise would be a judgement dressed
as a rule. The tests carry it, named, one `xfail` per divergence.

## The fetch trap, which cost three attempts

`http://purl.org/net/p-plan` and `https://vocab.linkeddata.es/p-plan/` serve **HTML documentation
regardless of the `Accept` header**. Three fetches returned HTTP 200 with a 7 KB XHTML page — a
response shaped exactly like success that parses as nothing.

So the fixture asserts it parsed more than ten subjects. Without that, an error page saved as
`p-plan.ttl` makes every grounding assertion vacuously pass — the exact class of failure in
`.claude/rules/checks.md`: *a check that passed because it did not touch what was broken.*

Use [DBpedia Archivo](https://archivo.dbpedia.org/) or the W3C's own `.ttl`, and verify the first
bytes are RDF.

## Applies to any external authority

The word "ontology" is not the point. A `pmid`, a DOI, an RFC number, a `guideline_id` — anything
naming a source outside this repo is the same shape, and gets the same treatment: vendor or resolve
it, check the identifier exists, and never let *unchecked* render as *checked*.
