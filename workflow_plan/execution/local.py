"""`LocalRunner` and `execute` — the smallest thing that can actually run a Plan.

    run(plan, inputs, LocalRunner(strategy))

In-process, sequential, no retries, no concurrency, no durability. It exists to answer one
question — *does the declared process, plus these implementations, produce the expected result?* —
and to be the thing a Plan is proved against before anyone decides whether it needs a workflow
engine. Plenty of Plans never will.

## The two failures this refuses to have

**A coroutine returned instead of a result.** An `async def` bound into a synchronous Strategy
returns a coroutine object, which is truthy, has a repr, and flows into the next Step as though it
were data. Refused at the call site with the Step's name.

**A silently discarded or mis-shaped output.** A Step declaring two outputs whose implementation
returns one value has to fail here, because the alternative is one Variable holding the whole tuple
and the mismatch surfacing three Steps later as a type error about something unrelated.
"""
from __future__ import annotations

from typing import Any, Mapping, get_origin

from workflow_plan.execution.runner import StepRunner
from workflow_plan.execution.strategy import Strategy
from workflow_plan.plan.bindings import execution_order
from workflow_plan.plan.plan import Plan
from workflow_plan.plan.step import Step, wired_inputs


class ExecutionError(RuntimeError):
    """An execution that cannot proceed. Never raised for a Step's own failure.

    A Step's implementation raising is that Step's business and propagates untouched — wrapping it
    would bury the traceback the caller needs. This is raised only when the RUNNER cannot do its
    job: nothing bound, a coroutine it cannot await, an output shape that does not fit the
    declaration.
    """


class LocalRunner:
    """Perform a Step by calling whatever the Strategy bound to it. Satisfies `StepRunner`.

    Deliberately does not inherit from the Protocol — structural conformance is the property being
    demonstrated, and a test asserts `isinstance(LocalRunner({}), StepRunner)` holds anyway.
    """

    def __init__(self, strategy: Strategy) -> None:
        self.strategy = strategy

    def run(self, step: Step, inputs: dict[str, Any]) -> dict[str, Any]:
        cls = type(step)
        impl = self.strategy.get(cls)
        if impl is None:
            raise ExecutionError(
                f"no implementation bound for {cls.__name__}. Its Strategy has "
                f"{sorted(c.__name__ for c in self.strategy)} — run check_strategy(plan, strategy) "
                f"before executing and this is reported for every Step at once.")

        if cls.map_over is not None:
            return _run_mapped(cls, impl, inputs)

        result = impl(**inputs)

        if hasattr(result, "__await__"):
            result.close()  # else "coroutine was never awaited" fires far from the real error
            raise ExecutionError(
                f"{cls.__name__} is bound to an async implementation, which returned a coroutine "
                f"instead of a result. LocalRunner is synchronous by decision — see runner.py. "
                f"Nothing awaits this, so it would flow into the next Step as data.")

        return _outputs_by_name(cls, result)


def _run_mapped(cls: type[Step], impl: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Their `.map()` + `join`, run sequentially.

    The implementation is the PER-ITEM operation — `square: int -> int`, exactly theirs — so it is
    called once per element and the results are collected in order. That collection is their
    `reduce_list_append`, which is the reducer their own example uses.

    ⚠️ Sequential here, and that is not a limitation being hidden: `LocalRunner` has no concurrency
    by decision (see runner.py), so a mapped Step under it is a loop. Actual parallelism is what
    their engine is for, and `to_pydantic_graph` is where it belongs.
    """
    source, collected = cls.map_over
    item_var, out_var = cls.inputs[0], cls.outputs[0]

    items = inputs[source.name]
    try:
        iter(items)
    except TypeError:
        raise ExecutionError(
            f"{cls.__name__} maps over {source.name!r}, which arrived as "
            f"{type(items).__name__} and is not iterable. A mapped Step fans out over a "
            f"sequence.") from None

    results = []
    for i, item in enumerate(items):
        out = impl(**{item_var.name: item})
        if hasattr(out, "__await__"):
            out.close()
            raise ExecutionError(
                f"{cls.__name__} is bound to an async implementation; LocalRunner is synchronous "
                f"by decision. See runner.py.")
        _check_type(cls, out_var, out)
        results.append(out)
        del i
    return {collected.name: results}


def _outputs_by_name(cls: type[Step], result: Any) -> dict[str, Any]:
    """Map what an implementation returned onto what its Step declared it produces."""
    outs = cls.outputs
    if not outs:
        if result is not None:
            raise ExecutionError(
                f"{cls.__name__} declares no outputs but its implementation returned "
                f"{type(result).__name__}. Discarding it silently would hide either a wrong "
                f"declaration or a wrong implementation.")
        return {}

    if len(outs) == 1:
        _check_type(cls, outs[0], result)
        return {outs[0].name: result}

    if not isinstance(result, tuple) or len(result) != len(outs):
        got = f"a {len(result)}-tuple" if isinstance(result, tuple) else type(result).__name__
        raise ExecutionError(
            f"{cls.__name__} declares {len(outs)} outputs "
            f"({', '.join(v.name for v in outs)}) so its implementation must return a tuple of "
            f"{len(outs)}; got {got}.")
    for var, value in zip(outs, result):
        _check_type(cls, var, value)
    return {v.name: r for v, r in zip(outs, result)}


def _check_type(cls: type[Step], var: Any, value: Any) -> None:
    """Does the produced value match the Variable's declared type?

    ⚠️ Plain classes only. `list[Finding]` is a parameterized generic and `isinstance` cannot test
    its contents, so those are NOT CHECKED — which is not the same as checked and fine, and is why
    this says so here rather than leaving a reader to assume the types are enforced end to end.
    """
    declared = var.type
    if get_origin(declared) is not None or not isinstance(declared, type):
        return
    if not isinstance(value, declared):
        raise ExecutionError(
            f"{cls.__name__} declares {var.name!r} as {declared.__name__} and its implementation "
            f"produced {type(value).__name__}. The declaration and the code disagree about what "
            f"flows here; the next Step would receive the wrong thing.")


def run(plan: Plan, inputs: Mapping[str, Any], runner: StepRunner) -> dict[str, Any]:
    """Run every Step in dependency order. Returns every Variable produced, keyed by name.

    Named `run` because that is the verb in the libraries this sits above — `agent.run()`,
    `graph.run()`. It is a FUNCTION and not `Plan.run()`: a method would bake execution semantics
    into the declaration, which is the coupling this package exists to avoid.

    ⚠️ Returns a plain dict, not a provenance record. `workflow_plan.ontology.prov.Run` is
    `prov:Bundle` — one execution of a Plan, with an `Activity` per Step and an `Entity` per value —
    and it is written, validated and entirely unused. Populating it from here is a real feature and
    has not been built; this docstring says so rather than letting the return type imply it.

    Everything, not only `plan.outputs` — an intermediate is what you want when a run went wrong,
    and hiding it would make the runner's own output less useful than a print statement. The Plan's
    terminal Variables are named by `plan.outputs`, so taking that projection is one line.

    ⚠️ `execution_order` RAISES on a cycle rather than inventing an order. A Plan may legally be
    cyclic — `topology.acyclic` reports it, it is not part of what a Plan means — but nothing here
    can linearise one.
    """
    names = [v.name for v in plan.variables]
    if len(names) != len(set(names)):
        clashing = sorted({n for n in names if names.count(n) > 1})
        raise ExecutionError(
            f"Plan {plan.name!r} has different Variables sharing the name(s) {clashing}. Values "
            f"flow by name here, so one would overwrite the other. A Variable is (name, type), so "
            f"two of them can differ in type and collide in this dict.")

    missing = [v.name for v in plan.inputs if v.name not in inputs]
    if missing:
        raise ExecutionError(
            f"Plan {plan.name!r} expects {missing}, which was not supplied. Its signature is "
            f"{[v.name for v in plan.inputs]}.")

    env: dict[str, Any] = dict(inputs)
    for step in execution_order(plan):
        gathered = {v.name: env[v.name] for v in wired_inputs(step)}
        env.update(runner.run(step, gathered))
    return env
