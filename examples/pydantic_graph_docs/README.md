# Pydantic Graph, compared against — using their own documented examples

Their examples are copied **verbatim** from
[pydantic.dev/docs/ai/graph/builder](https://pydantic.dev/docs/ai/graph/builder/) and sit in the
same files as ours, so the comparison is against what they ship rather than a strawman.

Everything here runs. `tests/test_pydantic_graph.py` executes all four files.

```bash
uv sync --extra pydantic-graph
uv run python3 -m examples.pydantic_graph_docs.stage1_counter
uv run python3 -m examples.pydantic_graph_docs.stage3_map_join
uv run python3 -m examples.pydantic_graph_docs.control_no_plan
```

## Stage 1 — their `simple_counter.py`, round-tripped

Three values, asserted equal: their hand-wired GraphBuilder, our Plan on `LocalRunner`, our Plan
compiled onto their runtime. All `2`.

The one substantive difference is not cosmetic. Their `increment` declares its input type as `None`
— *"I take nothing"* — and then reads and writes `ctx.state.value`. That dependency is real and
appears **nowhere in the graph**. Ours makes it an edge: `Increment --count--> DoubleIt`.

## Stage 2 — three implementations of one Step

One `Plan` object, never touched between arms, three entries in a dict.

```
  input             expected          exact    by_addition          cheap
  [12]                   144       144    ok      144    ok      120 WRONG
  [3, 20]                409       409    ok      409    ok      209 WRONG
```

`render_mermaid(plan, strategy)` draws the three arms with **identical topology and different
implementation labels**. A test strips the labels and asserts the renders are byte-identical
underneath — so *"the logical process was held constant"* is something a reader checks by looking.

## Stage 3 — their `parallel_processing.py`: map, join, reducer

Their vocabulary, kept. The fan-out is one line on the Step:

```python
class Square(Step):
    inputs, outputs = (number,), (squared,)   # int -> int, exactly their `square`
    map_over = (numbers, squares)             # list[int] in, list[int] out
```

Under `LocalRunner` that is a sequential loop. Compiled, it becomes their real `.map()` and
`join(reduce_list_append)`. **Same declaration, nothing edited.** Their documented output,
`[1, 4, 9, 16, 25]`, is asserted on both.

## The control arm — the same three arms with no Plan layer

`control_no_plan.py` is twelve lines and idiomatic. **It is deliberately a good control**: the first
version had three copy-pasted builders, which flattered us and would not have survived ten seconds
of scrutiny. There is no line-count claim here.

What survives a fair control is one thing:

> **`build(square_impl)` cannot produce a graph, a diagram, or a type check until an implementation
> exists.** A Plan validates and renders with nothing implemented at all.

## The diagrams — same workflow, rendered by each

```
THEIRS — graph.render()                    OURS — render_mermaid(plan)

stateDiagram-v2                            flowchart TD
  state map <<fork>>                         IN_numbers(["numbers: list"])
  square                                     Square
  state reduce_list_append <<join>>          Total
  total                                      OUT_total(["total: int"])

  [*] --> map                                IN_numbers -- numbers --> Square
  map --> square                             Square -- squares --> Total
  square --> reduce_list_append              Total --> OUT_total
  reduce_list_append --> total
  total --> [*]
```

- **Theirs carries no types on its edges**, and cannot: an edge holds whatever the function returned
  and there is no name for it. Ours labels every edge with the Variable that flows.
- **Theirs draws the machinery** — `map <<fork>>` and `reduce_list_append <<join>>` are nodes. Ours
  draws the process. Their picture answers *how will this execute*; ours answers *what is this
  workflow*. Both are correct.

## What we do NOT do

- **Cycles do not run.** A Plan may be cyclic — it constructs, wires, renders, and
  `topology.acyclic` reports it — but it cannot execute, and the reason is not the toposort: a Plan
  carries no termination predicate. Their `Feedback.run() -> WriteEmail | End[Email]` puts that
  predicate in the node body, which is the right place for it and is theirs. All three of their
  headline examples are cyclic state machines, and for those you want their engine.
- **`Fork` / `Join` are not first-class.** Only `map_over`.
- **No async runner.** `LocalRunner` refuses an `async def` rather than returning an un-awaited
  coroutine. A compiled graph awaits it fine.
- **At one arm this is pure overhead.** Measured at stage 1: one implementation, two steps, and the
  Plan layer costs a declaration and buys nothing. It starts paying at the second arm.

⚠️ And everything demonstrable here is small. The failure this exists for shows up at volume — one
codebase downstream has 18 variants of one extraction pipeline, 23 distinct step names, 47% of them
used exactly once, with `enrich`, `batch_enrich` and `enrich_one_finding` in a single file. A toy
cannot show that, and this page will not pretend it does.
