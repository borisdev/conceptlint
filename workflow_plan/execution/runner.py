"""`StepRunner` — the boundary between a Plan and whatever performs it.

    Plan / Step / Variable / Strategy      what to do, and how it is implemented
            |
            v
        StepRunner                         Protocol: one Step, in and out
            |
            +-- LocalRunner                here. In-process, sequential, no retries.
            +-- (Temporal, PydanticGraph, LangGraph)   NOT BUILT. See below.

## Protocol, not a base class

Nothing has to inherit from anything. `LocalRunner` satisfies this by having the method, and so
would an adapter living in another package that has never heard of `workflow_plan` — which is the
point, since an execution backend should not have to import a specification library to be usable
with one. A base class would also accumulate helpers, state and hooks over time, and every one of
them would be execution semantics leaking back toward the declaration.

## ⚠️ Synchronous, and that is a decision rather than an oversight

Two of the four handoffs that produced this module disagreed: one argued workflow-plan must stay
sync/async-neutral, the other wrote `async def run(...)` into the Protocol, which is not neutral —
it forces every implementation of every Step to be a coroutine, including `lambda x: x + 1`.

So: sync now. An `AsyncStepRunner` lands when there is a real async implementation to run, and not
before — `docs/design.md` §6. What must NOT happen in the meantime is a sync runner silently
accepting an `async def` and returning an un-awaited coroutine, which is a result-shaped object that
is not a result. `check_strategy` reports it and `LocalRunner` refuses it.

## What this deliberately does not do

No retries, no timeouts, no concurrency, no durability, no checkpointing. Those are the reasons to
reach for Temporal or LangGraph, and a Plan that never needs them should never pay for them. An
exception means the execution failed and stops.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from workflow_plan.plan.step import Step


@runtime_checkable
class StepRunner(Protocol):
    """Perform one Step with its inputs already gathered, and return its outputs by name.

    `inputs` and the return value are both keyed by Variable NAME, so a runner never has to know
    what a Plan is — only what a Step declares. That is what keeps `execute()` (which does know
    about Plans) separable from the mechanics of running one Step.
    """

    def run(self, step: Step, inputs: dict[str, Any]) -> dict[str, Any]:
        ...
