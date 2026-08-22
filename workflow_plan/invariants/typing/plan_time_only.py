"""A plan-time type must not carry runtime execution state.

The handoff's worked example, expressed as a `SemanticInvariant` over records read from ordinary
Pydantic rather than as a rule over `DeclaredTerm` subclasses — so it fires on a user's models,
which is where the Variable/Entity collapse actually happens.

    Variable   a named typed value SLOT in a plan       plan-time
    Entity     the value that actually flowed           runtime

The failure it exists for, which really happened:

    class Variable(BaseModel):
        name: str
        value_type: type
        value: object          # ← added later
        started_at: datetime   # ← added later

Nothing broke. The docstring still said "a named typed value slot in a plan", the tests still
passed, and `Variable` had quietly become a runtime record wearing a plan-time name. Everything
downstream that reasoned about plan-time structure was then reasoning about execution state.

⚠️ This is why `Step ≠ Activity` and `Variable ≠ Entity` are worth enforcing rather than merely
documenting: a runtime framework may map them one to one, and the moment code believes that, *"the
definition is wrong"* and *"that run failed"* become the same sentence with opposite fixes.

## Why a field-name list and not something cleverer

    value, started_at, ended_at, finished_at, duration, status, result, error, retries, attempt

Crude, and deliberately so. The alternative is inferring intent from types, which guesses — a field
named `value` is suspicious on a plan-time type and unremarkable on a config. The list is short,
readable and arguable, which is what a rule people will actually keep needs to be.
"""
from __future__ import annotations

from typing import Sequence

from workflow_plan.invariants.invariant import InvariantCategory, SemanticInvariant
from workflow_plan.naming.records import ModelRecord

#: Field names that describe an EXECUTION rather than a specification.
RUNTIME_FIELDS = frozenset({
    "value", "started_at", "ended_at", "finished_at", "duration", "elapsed",
    "status", "result", "error", "exception", "retries", "attempt", "run_id",
})

#: Types whose meaning is plan-time. Matched by name, because that is the claim being made — a
#: class called `Variable` asserts P-Plan's `Variable`, whatever module it sits in.
PLAN_TIME_NAMES = frozenset({"Plan", "Step", "Variable", "MultiStep"})


def _plan_time_only(models: Sequence[ModelRecord]) -> None:
    offences: list[str] = []
    for m in models:
        if m.name not in PLAN_TIME_NAMES:
            continue
        runtime = sorted(set(m.fields) & RUNTIME_FIELDS)
        if runtime:
            offences.append(f"{m.name} ({m.file}:{m.line}) has {', '.join(runtime)}")
    if offences:
        raise PLAN_TIME_ONLY.violated(
            "; ".join(offences) + ". A plan-time type describing an execution is a runtime record "
            "wearing a plan-time name — move the state to the runtime counterpart (Activity, "
            "Entity) and leave the specification describing what is INTENDED.")


PLAN_TIME_ONLY: SemanticInvariant[Sequence[ModelRecord]] = SemanticInvariant(
    id="typing.plan_time_only",
    category=InvariantCategory.TYPING,
    statement="A plan-time type (Plan, Step, Variable) must not carry runtime execution state.",
    why=("Observed: `Variable` gained `value` and `started_at`, kept its docstring, kept passing "
         "its tests, and silently became a runtime record. Nothing failed — which is why a "
         "docstring cannot enforce this and a rule has to."),
    check=_plan_time_only,
)

ALL: tuple[SemanticInvariant[Sequence[ModelRecord]], ...] = (PLAN_TIME_ONLY,)
