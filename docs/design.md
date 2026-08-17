# Design notes

Why the types are shaped the way they are. Every rule here exists because something failed once —
the failure is stated with the rule, because a rule whose reason is lost gets deleted the first time
it is inconvenient.

---

## 1. A Plan is not a DAG

The obvious modelling choice is a directed acyclic graph, and it is wrong as an *identity*.

Acyclicity is a **property some plans have**, not what a plan *is*. Bake it into the type and you
have ruled out every iterative process — refine-until-converged, retry-with-a-different-query,
anything with a feedback edge — before anyone asked for one. [P-Plan][pplan] has no acyclicity
axiom either; `isPrecededBy` is merely transitive.

So `Plan.__post_init__` refuses only genuinely incoherent input — a class where an instance belongs,
a runtime object in a plan-time container. It does **not** topologically sort. If you want
acyclicity, you opt in:

```python
validate(plan, [topology.ACYCLIC])
```

`execution_order()` is a separate function that raises on a cycle, because *asking for a linear
order* is where a cycle actually becomes a problem — not at construction.

**The general form:** the type refuses what is meaningless. An invariant refuses what is merely
wrong. Collapsing those two is how a type system starts making decisions nobody delegated to it.

---

## 2. Plan-time and runtime are different things

```
p-plan:Step      the intended operation        prov:Activity    one execution of it
p-plan:Variable  a named typed value slot      prov:Entity      the value that actually flowed
```

`Step ≠ Activity` and `Variable ≠ Entity`, **even where an execution framework maps them one to
one.** That mapping is a property of the framework, not of the concepts.

The failure, which really happened:

```python
class Variable(BaseModel):
    name: str
    value_type: type
    value: object          # ← added later
    started_at: datetime   # ← added later
```

Nothing broke. The docstring still said *"a named typed value slot in a plan"*, the tests still
passed, and `Variable` had quietly become a runtime record wearing a plan-time name. Everything
downstream reasoning about plan-time structure was now reasoning about execution state.

That is `typing.plan_time_only`, and it is a crude field-name list on purpose:

```
value, started_at, ended_at, finished_at, duration, status, result, error, retries, attempt
```

The alternative is inferring intent from types, which guesses. A field named `value` is suspicious
on a plan-time type and unremarkable on a config. The list is short, readable and arguable — which
is what a rule people will actually keep needs to be.

**Why it matters beyond tidiness:** once code believes `Step == Activity`, *"the definition is
wrong"* and *"that run failed"* become the same sentence with opposite fixes.

---

## 3. The four categories, and the failure each came from

Not one vague "linting" subsystem. Four kinds of wrong, because they are found differently.

### `naming/` — the two laws

```
one name  → one concept     (ambiguity)
one concept → one name      (drift)
```

Both are about coding agents specifically. **Ambiguity:** `Plan` and `EvidenceCaseGraph` both
present, someone says *"add validation to the graph"*, and the agent picks one silently — you find
out from the diff. **Drift:** `EvidenceCaseGraphBuilder` acquires the aliases *evidence assembler*
and *case graph generator*, and eventually an agent reads an alias as a **new architectural concept
and implements it a second time.** That is how a codebase grows a duplicate nobody decided to add.

Drift needs two corroborating signals — name overlap **plus** either field or definition overlap —
because a shared head noun alone is noise (`UserRequest` / `SearchRequest` are properly distinct).
Fields alone was the original rule and it was fragile in the one direction it could not report:
rename the fields and the finding vanishes while the duplicated meaning is untouched.

### `typing/` — bindings that look connected and move nothing

Sharing a `Variable` already guarantees type agreement: `Variable` is frozen on `(name, type)`, so
two Steps holding the same one hold the same type by construction. What the invariant catches is
what shape cannot — **two Variables with the same name and different types.** That reads as a
connection in the diagram and in the code review, and it is not one.

The design this replaced wired Steps by artifact-kind *strings*, where a typo silently rewired the
graph: it still built, nothing type-checked, and the mistake surfaced much later as a shape error
somewhere else entirely.

### `topology/` — cycles, unbound inputs, orphans, two producers

`single_producer` is the one with external grounding. P-Plan's `isOutputVarOf` **is** an
`owl:FunctionalProperty` — a Variable is the output of exactly one Step. Two producers for one
artifact is not a style preference; it is a wiring bug, and downstream it shows up as two
overlapping notions of the same concept, which then gets a second name, which is now a `naming/`
problem too.

### `provenance/` — a citation nobody can follow

See §5.

---

## 4. `declared_inputs`, and why a rule that cannot fire is worse than no rule

`topology.bound_inputs` should report a Step consuming a Variable nothing produces. The first
version derived the Plan's inputs — *"consumed here, produced by nothing here"*. Which means:

```
accidental gap          = consumed, produced by nothing
the Plan's own inputs   = consumed, produced by nothing
```

**The same set.** The rule could never fire. It was not weak, it was *undefined*, and it passed
every test because a rule that finds nothing looks exactly like a rule with nothing to find.

`Plan.declared_inputs` makes the distinction expressible: these are the Variables the Plan expects
to be **handed**; anything else unproduced is a gap.

⚠️ And omitting it does not silently pass. It reports **NOT CHECKED**:

```
topology.bound_inputs: NOT CHECKED — Plan 'evidence_first' declares no inputs,
so 'unbound' and 'the Plan signature' are the same set
```

Both real consumer arms hit exactly this on adoption day. The rule told them why.

---

## 5. Ontology grounding, and the rule that reads the source

A class can declare where its meaning comes from:

```python
class Step:
    ONTOLOGY_IRI = "http://purl.org/net/p-plan#Step"
```

That is a **citation**, and the failure it caused happened in this package. The IRI was written
**from memory**, and `Step` was then given exactly one input and one output — while P-Plan puts
**no cardinality at all** on `hasInputVar` / `hasOutputVar`:

```turtle
:hasInputVar  a owl:ObjectProperty ;
              rdfs:domain :Step ;
              rdfs:range  :Variable .
```

That is the entire definition. Nobody lied. The IRI looked authoritative and **no mechanism could
disagree with it.**

Two consequences worth separating:

- **We tightened what the ontology leaves free.** A real consumer's step needed three inputs at
  once — the paste, the extracted questions, and the screened papers. The cited-but-wrong signature
  could not express it.
- **We missed the one thing the ontology does constrain.** `isOutputVarOf` is functional. That is
  now `topology.single_producer`, and we did not have it.

So `provenance.grounded_citation` reads the vendored Turtle and fails when a cited term is not in
it. What it can and cannot decide, stated plainly:

```
can     the cited term EXISTS in an ontology we have vendored
cannot  the cited term MEANS what our implementation does
```

The second is a reading, not a decision procedure. A rule pretending otherwise would be judgement
dressed as a check — so that half lives in `tests/test_pplan_grounding.py`, which asserts the
specific axioms the design depends on.

⚠️ A citation to an ontology we have **not** vendored is REPORTED, not ignored. *"We cannot check
this"* and *"this is fine"* must never render the same.

**On conflict, the ontology wins.** Two honest moves: change the code to match, or delete the IRI
and own the design as ours. Never keep the citation and relax the check that caught the mismatch.

---

## 6. NOT CHECKED is not a pass

The rule that shapes every check in the package.

```
0 found       we looked, there was nothing
NOT CHECKED   we did not look
```

Rendering those the same is the most convincing shape a broken check can take, and it scales
horribly: in a related system, **120 items each swallowing their own exception turned one systemic
failure into 120 agreeing votes** — four independent variants all reporting "0 found". Consistency
reads as signal.

So `validate()` converts an unexpected exception into an explicit `NOT CHECKED — {exc}` finding
rather than dropping it. And it **collects** rather than stopping at the first failure: one cycle
can cause three findings, and seeing all three is how you tell one root cause from three problems.

---

## 7. When the Plan won't let you do it

A constraint that only says *no* gets deleted. The order:

```
1. reuse an existing type
2. adapt
3. compose
4. refine — declare the subtype relationship explicitly
5. keep the representation private to your implementation
6. only then, evolve the shared types
```

⚠️ **A real use-case blocker is evidence the shared types should change. An agent's implementation
convenience is not.** The test is whether anything other than the current diff gets worse if you
refuse.

`Step[InputT, OutputT]` died to step 6 and should have — a real builder could not express a
three-input step. Routing around it would have hidden a wrong signature. **The friction is
information.**

---

## 8. Do not build ahead of a user

Three abstractions were declared here before anything used them; one never existed outside a
docstring. **An abstraction with no caller is speculation with tests.**

Add the second implementation first, then extract the interface. Concretely, this is why there are
no execution adapters: Temporal and LangGraph are listed as *not built* rather than sketched, and
they stay that way until something needs to execute a Plan.

---

## 9. The failure this package still had to learn

Worth recording, because it is the one the tests could not catch.

The refactor moved `conceptlint/dataflow/` to `plan_types/` and did not update the build config. A
wheel built from HEAD contained neither module: `plan_types` was never listed in
`[tool.hatch.build.targets.wheel]`, and `conceptlint.dataflow` had been deleted. **116 tests passed
throughout**, because they import from the working tree and never from a built artifact.

The general lesson, and it generalises past packaging: **a test that does not exercise the artifact
you ship is testing something you do not ship.** Same shape as §4 — the check ran, went green, and
touched nothing that could break.

[pplan]: http://purl.org/net/p-plan#
