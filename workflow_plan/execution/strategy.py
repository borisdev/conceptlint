"""`Strategy` — which implementation performs each PlanStep, for one execution.

    PlanStep        WHAT transformation exists          plan-time, declared once
    Strategy    HOW it is performed, this time      chosen per execution
    StepRunner  the mechanics of performing it      sync, retries, durability, workers

A Strategy is an ordinary mapping. That is deliberate and it is the whole API:

    fast = {Summarize: summarize_fast}
    slow = {Summarize: summarize_precise}

The Plan is not edited between those two lines. That is the property worth having — an experiment
can then say *the logical process was held constant; only the implementation of `Summarize`
changed*, and mean it, because the same `Plan` object served both arms.

## ⚠️ `Strategy`, not `bindings` — the word was already taken

`workflow_plan.plan.bindings` means **how Variables connect Steps**: two Steps are bound when they
share a `Variable`. The handoffs that produced this module used "bindings" for **which
implementation satisfies a PlanStep**. Two concepts, one word, in one package — the exact thing
`naming.ambiguous_reference` reports, and it would have shipped inside the module built to prevent
it.

    binding     Variable wiring         workflow_plan/plan/bindings.py
    Strategy    PlanStep -> implementation  here

## Grounding, stated plainly

P-Plan has no term for this, and neither does PROV-O. `p-plan:Step` is the intended operation and
`prov:Activity` is one execution of it; *"the code that will perform this PlanStep if it runs"* is
neither. So `Strategy` is **ours, deliberately uncited** — the same call as `PlanStep.uses`, and for the
same reason: citing a term that does not say this would be the failure
`provenance.grounded_citation` exists to catch.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping

from workflow_plan.plan.plan import Plan
from workflow_plan.plan.plan_step import PlanStep

#: One way of performing a PlanStep. Called by keyword with the PlanStep's input Variable NAMES.
Implementation = Callable[..., Any]

#: PlanStep class -> the implementation that performs it. Keyed on the CLASS, since the class is the
#: declared operation; a Plan holding two instances of one PlanStep class cannot give them different
#: implementations, which has not been needed and is recorded here rather than designed around.
Strategy = Mapping[type[PlanStep], Implementation]


def check_strategy(plan: Plan, strategy: Strategy) -> tuple[str, ...]:
    """Findings about a Strategy against a Plan. Empty means every PlanStep can be called.

    Static, and honest about its limits: it reads signatures, so it can tell you that
    `summarize(doc)` will not accept the keyword `document`, and it CANNOT tell you what that
    function returns. Return shape is checked by the runner at execution — see `local.py`.

    ⚠️ Returns violations rather than raising, matching `check()`: one wrong signature usually
    produces several complaints, and seeing all of them is how you tell one root cause from three
    problems.
    """
    violations: list[str] = []
    for step in plan.steps:
        cls = type(step)
        impl = strategy.get(cls)
        if impl is None:
            violations.append(
                f"{cls.__name__} has no implementation in this Strategy. A PlanStep is a declaration; "
                f"something has to say how it is performed.")
            continue
        if not callable(impl):
            violations.append(f"{cls.__name__} is bound to {impl!r}, which is not callable.")
            continue
        if inspect.iscoroutinefunction(impl):
            violations.append(
                f"{cls.__name__} is bound to async {impl.__name__}. Every runner here is "
                f"synchronous, and calling it would return a coroutine that nobody awaits — a "
                f"result-shaped object that is not the result. Wrap it, or add an async runner.")
            continue
        violations.extend(_signature_findings(cls, impl))
    return tuple(violations)


def _signature_findings(cls: type[PlanStep], impl: Implementation) -> list[str]:
    """Can `impl(**{name: value for each of cls.inputs})` actually be called?

    ⚠️ This is where `Variable.name` stops being a label and becomes part of the contract. The
    runner calls by KEYWORD — a PlanStep with three inputs called positionally is one argument reorder
    away from a silent mis-wire that the types cannot catch when two inputs share a type. The cost
    is that renaming a Variable renames a parameter, and that cost is deliberate: it is visible
    here, at import, rather than at 3am as a value in the wrong slot.
    """
    # `cls.inputs` deliberately, not the wired ports: a mapped PlanStep's implementation is called
    # with ONE ITEM, so its parameter is the item's name. The list never reaches it.
    wanted = [v.name for v in cls.inputs]
    try:
        sig = inspect.signature(impl)
    except (TypeError, ValueError):  # builtins and C callables have no introspectable signature
        return [f"{cls.__name__}: cannot read the signature of {impl!r} — NOT CHECKED, "
                f"which is not the same as checked and fine."]

    params = sig.parameters
    takes_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())

    violations: list[str] = []
    if not takes_kwargs:
        unaccepted = [n for n in wanted if n not in params
                      or params[n].kind is inspect.Parameter.POSITIONAL_ONLY]
        if unaccepted:
            violations.append(
                f"{cls.__name__} declares input(s) {unaccepted} that {_name(impl)}{sig} will not "
                f"accept by keyword. The runner calls by Variable name, so the parameter has to be "
                f"spelled the same.")

    required = [n for n, p in params.items()
                if p.default is inspect.Parameter.empty
                and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                               inspect.Parameter.KEYWORD_ONLY,
                               inspect.Parameter.POSITIONAL_ONLY)]
    unfed = [n for n in required if n not in wanted]
    if unfed:
        violations.append(
            f"{_name(impl)}{sig} requires {unfed}, which {cls.__name__} does not declare as an "
            f"input. Either it is a Variable the PlanStep should consume — in which case the Plan is "
            f"missing an edge — or it is a dependency, which belongs in the implementation's "
            f"closure, not in the dataflow.")
    return violations


def _name(impl: Implementation) -> str:
    return getattr(impl, "__name__", repr(impl))
