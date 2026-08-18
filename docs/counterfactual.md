# The counterfactual question

Before a component exists, answer this. It is not a field yet and probably should not be one — a
required prose field becomes ceremony filled with *"because we need it"*. It is a question with a
required shape.

## The notation

Pearl writes `Y_x(u)` — *the value `Y` would take **for unit `u`**, had `X` been `x`*.

For a component `C` in a system producing output `Y`:

```
Y_do(C removed)(u)  ≠  Y(u)        for which u?
```

**Name the `u`. Then run it.**

That is the whole rule. Everything below is why the two halves are both load-bearing.

## Why "for which u" is the entire question

The naive version — *"would this be worse without it?"* — gets answered from whatever unit you
already have in front of you. That unit is almost never the one where the component matters, because
if it were, you would have noticed the component was necessary while writing it.

`u` is a specific input: one paste, one case, one file. Not a class of inputs. "Rare diseases" is not
a `u`; *"a 52M with Erdheim-Chester on vemurafenib"* is.

## Why "then run it" is not optional

A counterfactual you reason about is a hypothesis. `do()` is executable in almost every case that
matters here — comment the line out, set the constant to zero, pass the flag — and it takes minutes.

⚠️ A stated-but-unrun counterfactual must say so. **"Not measured" and "measured, no effect" are
different answers** and must never render the same. That is the same discipline as `NOT CHECKED` vs
`0 found` everywhere else in this package.

## The worked example, in full

`MIN_SUPPORT = 20` in a case-graph enricher: a relationship needed ≥20 sentences in SemMedDB before
it could be added as a node. The docstring said, plausibly:

> SemRep is a machine extractor and noisy; 20 independent sentences will not repeat a parse bug.
> This protects the sparse case.

Both sentences were true-sounding. One was false. Here is what running it produced:

| `u` | `Y_do(MIN_SUPPORT=0)(u)` | `Y(u)` at 20 | blocked |
|---|---|---|---|
| PCOS, dense | 5 nodes, support 160–493 | identical | **nothing** |
| aHUS, rare | 5 nodes, support 45–118 | identical | **nothing** |
| **Erdheim-Chester** | Cardiac Tamponade(5), Myocarditis(5), Secondary malignancy(5), Pancreatitis(3), Toxic nephropathy(3) | **0 nodes** | **all five** |

Cardiac tamponade and myocarditis are classic Erdheim-Chester manifestations — it is a histiocytosis
that infiltrates the heart. **The threshold deleted correct, clinically urgent findings.**

And structurally rather than by luck: support 3–5 *is* the entire literature for a rare disease.
There are not 20 papers on ECD cardiac tamponade. So a high absolute floor is calibrated for common
conditions and silently empties the feature for rare ones — the users who need it most.

Three things the exercise established that no amount of reading would have:

- it did **nothing** on both units where it was claimed to help
- it did **harm** on the one unit it was claimed to protect
- the docstring asserted the **opposite** of the measured effect, confidently, for as long as it existed

The author had never run a sparse case. Neither had anyone else, because nothing asked.

## What a good answer looks like

```
CLAIM     without MIN_SUPPORT, a single SemRep misparse can become a node on the map
UNIT      a rare-disease paste, where nothing else competes for the 5 available slots
RUN       do(MIN_SUPPORT=0) on the Erdheim-Chester case
RESULT    5 nodes added at support 3-5, all clinically correct — the claim is about
          support=1, and this unit did not produce one. NOT YET MEASURED for support=1.
```

Note the last line. The honest outcome of a counterfactual is frequently *"I still have not tested
the thing I said"* — and writing that down is worth more than a confident paragraph, because it is
the sentence that tells the next person what to run.

## What this is NOT

- **Not a justification.** *"It improves precision"* is unfalsifiable. `Y_do(...)(u)` is not.
- **Not a test.** A test asserts behaviour stays. This asks what happens when the component goes.
- **Not required to be positive.** `no_effect` and `refutes` are results. A question that can only
  be answered one way is decoration — the failure this whole package exists to report.
- **Not a field. Yet.** A `Counterfactual` dataclass was drafted and set aside: it would force every
  component into a shape validated on exactly one example. Ask the question, write the answer in the
  docstring, and revisit the type once enough answers exist to see their shape.

## For a coding agent

When you add a constant, a threshold, a filter, a step, or a guard — before writing the code:

1. State what the system does **instead**, without it.
2. Name the specific input where that difference appears. If you cannot name one, that is the
   finding: **you may be about to add something that changes nothing.**
3. Run it. It is usually one flag and ninety seconds.
4. Record the result **including "no effect"**, and including "not measured".

⚠️ If step 2 is hard, do not skip to step 3 with the input you already have. That input is the one
that will tell you the component is harmless, which is exactly what `MIN_SUPPORT = 20` was told for
as long as anybody looked at it.
