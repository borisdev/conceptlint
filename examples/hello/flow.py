"""One Plan, two ways of performing it — the whole idea, in a domain nobody has to learn.

    document ──> Outline ──> outline ──┐
       │                                ├──> Summarize ──> summary
       └────────────────────────────────┘

`Summarize` fans in: it needs the outline AND the original document. That is the ordinary case, not
an advanced one, and it is what a Step modelled as a function of its predecessor's output cannot
express.

Run it:

    uv run python3 -m examples.hello.flow
"""
from __future__ import annotations

from dataclasses import dataclass

from plan_types import Plan, Step, Variable, render_mermaid, validate
from plan_types.execution import LocalRunner, check_strategy, execute
from plan_types.invariants import topology, typing


# ── what flows ───────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Document:
    title: str
    body: str


@dataclass(frozen=True)
class Outline:
    points: tuple[str, ...]


@dataclass(frozen=True)
class Summary:
    text: str


# ── the declaration ──────────────────────────────────────────────────────────────────────────────
#
# Lowercase, because these are names bound to Variables, not conventional constants — and
# `SUMMARY = Variable("summary", ...)` says the word twice in two cases for no gain.

document = Variable("document", Document)
outline = Variable("outline", Outline)
summary = Variable("summary", Summary)


class MakeOutline(Step):
    """Pull the points out of a document."""

    inputs, outputs = (document,), (outline,)


class Summarize(Step):
    """Write the summary. Needs the outline and the document it came from."""

    inputs, outputs = (document, outline), (summary,)


plan = Plan(
    name="summarize_document",
    steps=(MakeOutline(), Summarize()),
    declared_inputs=(document,),
)


# ── how it is performed — several ways, none of them privileged ──────────────────────────────────
#
# Ordinary functions. Parameter names match the Variable names because the runner calls by keyword:
# a Step with two inputs called positionally is one reorder away from a mis-wire that the types
# cannot catch when both inputs are strings.

def outline_by_sentence(document: Document) -> Outline:
    return Outline(points=tuple(s.strip() for s in document.body.split(".") if s.strip()))


def summarize_fast(document: Document, outline: Outline) -> Summary:
    """The cheap one: the first point, and stop."""
    first = outline.points[0] if outline.points else document.title
    return Summary(text=f"{document.title}: {first}.")


def summarize_precise(document: Document, outline: Outline) -> Summary:
    """The careful one: every point, in order."""
    return Summary(text=f"{document.title}: " + "; ".join(outline.points) + ".")


#: Two arms. Note what is NOT here: a second Plan, and a `SummarizeV2` Step. There is one operation
#: called `Summarize` and two ways of doing it, which is what the words already meant.
fast = {MakeOutline: outline_by_sentence, Summarize: summarize_fast}
precise = {MakeOutline: outline_by_sentence, Summarize: summarize_precise}


def main() -> None:
    findings = validate(plan, [*topology.ALL, *typing.ALL])
    print("invariants:", findings or "[]")
    print(render_mermaid(plan))

    doc = Document(title="Ninety seconds", body="Name the unit. Then run it. Record the result")

    for arm, strategy in (("fast", fast), ("precise", precise)):
        problems = check_strategy(plan, strategy)
        if problems:
            raise SystemExit("\n".join(problems))
        result = execute(plan, {"document": doc}, LocalRunner(strategy))
        print(f"{arm:>8}: {result['summary'].text}")


if __name__ == "__main__":
    main()
