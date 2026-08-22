"""One Plan. Two strategies. Two runtimes. Nothing edited in between.

The workflow is Pydantic Graph's own email-feedback example, in its acyclic core — and with the
one thing that example does not have:

    user ──> WriteEmail ──> draft ──> Critique ──> feedback ──┐
                              │                                ├──> Revise ──> email
                              └────────────────────────────────┘

**`Revise` needs the draft AND the critique.** That is a fan-in, and it is not an exotic case: you
cannot revise a draft from the critique alone. In a node-returns-the-next-node model the draft has
to be carried in mutable state to be available two hops later; here it is an edge, so the
requirement is visible in the declaration and `topology.bound_inputs` can check it.

Run it:

    uv sync --extra pydantic-graph
    uv run python3 -m examples.pydantic_graph_demo.flow
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from workflow_plan import Plan, PlanStep, Variable, render_mermaid, check
from workflow_plan.execution import SequentialRunner, check_strategy, run
from workflow_plan.execution.pydantic_graph import to_pydantic_graph
from workflow_plan.invariants import topology, typing


@dataclass(frozen=True)
class User:
    name: str
    interests: tuple[str, ...]


@dataclass(frozen=True)
class Email:
    subject: str
    body: str


@dataclass(frozen=True)
class Critique:
    notes: tuple[str, ...]


user = Variable("user", User)
draft = Variable("draft", Email)
feedback = Variable("feedback", Critique)
email = Variable("email", Email)


class WriteEmail(PlanStep):
    """Write the first draft from what we know about the reader."""

    inputs, outputs = (user,), (draft,)


class CritiqueDraft(PlanStep):
    """Say what is wrong with it."""

    inputs, outputs = (draft,), (feedback,)


class Revise(PlanStep):
    """⚠️ THE FAN-IN. Needs the draft and the critique of it, at once."""

    inputs, outputs = (draft, feedback), (email,)


plan = Plan(
    name="email_with_feedback",
    steps=(WriteEmail(), CritiqueDraft(), Revise()),
    declared_inputs=(user,),
)


# ── implementations. Ordinary functions; no framework in sight ───────────────────────────────────

def write_terse(user: User) -> Email:
    return Email(subject="Hello", body=f"Hi {user.name}. {user.interests[0]}?")


def write_warm(user: User) -> Email:
    return Email(subject=f"{user.name}, something for you",
                 body=f"Hi {user.name} — we thought of you because you like "
                      f"{' and '.join(user.interests)}.")


def critique(draft: Email) -> Critique:
    notes = []
    if len(draft.body) < 60:
        notes.append("too short to be worth sending")
    if draft.subject.lower() in {"hello", "hi"}:
        notes.append("subject says nothing")
    return Critique(notes=tuple(notes))


def revise(draft: Email, feedback: Critique) -> Email:
    if not feedback.notes:
        return draft
    return Email(subject=draft.subject, body=draft.body + f"  [revised: {len(feedback.notes)} note(s)]")


terse = {WriteEmail: write_terse, CritiqueDraft: critique, Revise: revise}
warm = {WriteEmail: write_warm, CritiqueDraft: critique, Revise: revise}


async def main() -> None:
    print("invariants:", check(plan, [*topology.ALL, *typing.ALL]) or "[]")
    print(render_mermaid(plan))

    reader = User(name="Samuel", interests=("type safety", "graphs"))

    for arm, strategy in (("terse", terse), ("warm", warm)):
        assert check_strategy(plan, strategy) == ()

        local = run(plan, {"user": reader}, SequentialRunner(strategy))["email"]

        graph = to_pydantic_graph(plan, strategy)
        on_graph = (await graph.run(state={}, inputs={"user": reader}))["email"]

        assert local == on_graph, (
            f"{arm}: the two runtimes disagreed — {local!r} vs {on_graph!r}. That would mean the "
            f"Plan does not determine the result, which is the claim this file exists to check.")
        print(f"\n{arm}:")
        print(f"  SequentialRunner    {local.body}")
        print(f"  Pydantic Graph {on_graph.body}")
        print("  identical      ✓")


if __name__ == "__main__":
    asyncio.run(main())
