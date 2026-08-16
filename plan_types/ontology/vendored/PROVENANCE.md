# Where `p-plan.ttl` came from

    source    https://akswnc7.informatik.uni-leipzig.de/dstreitmatter/archivo/purl.org/
              net--p-plan/2025.02.19-202429/net--p-plan_type=parsed.ttl
    canonical http://purl.org/net/p-plan#
    snapshot  2025.02.19-202429  (DBpedia Archivo)
    retrieved 2026-08-15
    sha256    ab117107d93a4476ef095a397339a4fa3eaf69308e422e267cca2275bbdc6305

## Why a vendored copy and not a fetch

A test that reaches the network is a test that fails when someone else's server is down, and one
that silently starts passing for the wrong reason when a redirect changes. Worse here: the whole
point of `test_pplan_grounding.py` is that our claim of grounding is CHECKED, so the thing it checks
against must be a fixed artifact with a hash, not whatever a URL returns today.

⚠️ `http://purl.org/net/p-plan` and `https://vocab.linkeddata.es/p-plan/` both serve **HTML
documentation** regardless of the `Accept` header. Three attempts to content-negotiate RDF returned
a 7 KB XHTML page with HTTP 200 — a response that looks like success and parses as nothing. Archivo
is used because it serves the parsed Turtle at a stable URL.

## Refreshing it

Deliberately manual. P-Plan has been stable since 2014 and an ontology that silently updated under
a conformance test would defeat the test.

```bash
curl -sL -o conceptlint/ontologies/pplan/vendored/p-plan.ttl \
  "https://akswnc7.informatik.uni-leipzig.de/dstreitmatter/archivo/purl.org/net--p-plan/<snapshot>/net--p-plan_type=parsed.ttl"
sha256sum conceptlint/ontologies/pplan/vendored/p-plan.ttl   # update this file
uv run pytest tests/test_pplan_grounding.py -v                # see what moved
```

A refresh that changes a test outcome is a finding, not a chore: it means the ontology we claim to
be grounded in said something new.
