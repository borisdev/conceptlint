"""Render a Plan. Every arrow is read from the bindings; nothing here is hand-authored.

    render_mermaid(plan)

A hand-drawn pipeline diagram is a claim about the code that stops being true the moment a Step
moves, and nothing tells you. Deriving it makes that impossible: add an input and the picture
changes with no edit here.

⚠️ No domain concepts appear in this module. It renders `Plan`, `Step` and `Variable` and knows
nothing about what any of them mean — which is what lets the same renderer draw a medical evidence
build and anything else.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from plan_types.plan import bindings
from plan_types.plan.plan import Plan
from plan_types.plan.variable import Variable

_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _label(step: object) -> str:
    """`KeepOnlyCitedOmissions` -> `Keep Only Cited Omissions`.

    Splits on lower→UPPER and on the tail of a run of capitals, so `PICOSet` reads `PICO Set`. An
    earlier version did only the first and rendered `AskModelForAMap` as "Ask Model For AMap" —
    visible the moment the output was read, which is the argument for reading generated output
    rather than trusting the generator.
    """
    return _SPLIT.sub(" ", type(step).__name__)


def _type_name(t: Any) -> str:
    return getattr(t, "__name__", str(t))


def _node(plan: Plan, index: int) -> str:
    return f"{re.sub(r'[^A-Za-z0-9_]', '_', plan.name)}_{index}"


def _port(prefix: str, v: Variable[Any]) -> str:
    return f"{prefix}_{re.sub(r'[^A-Za-z0-9_]', '_', v.name)}"


def render_mermaid(plan: Plan) -> str:
    """A mermaid `flowchart TD` of the Plan's actual structure.

    Free Variables enter as ports, terminal Variables leave as ports, and every internal arrow is
    a producer→consumer edge labelled with the Variable that flows. A Step with three inputs shows
    three arrows — which is the whole reason this reads from bindings rather than from step order.
    """
    idx = {id(s): i for i, s in enumerate(plan.steps)}
    lines = ["```mermaid", "flowchart TD"]

    for v in plan.inputs:
        lines.append(f'  {_port("IN", v)}(["{v.name}: {_type_name(v.type)}"])')
    for i, s in enumerate(plan.steps):
        lines.append(f'  {_node(plan, i)}["{_label(s)}"]')
    for v in plan.outputs:
        lines.append(f'  {_port("OUT", v)}(["{v.name}: {_type_name(v.type)}"])')

    free = set(plan.inputs)
    for i, s in enumerate(plan.steps):
        for v in s.inputs:
            if v in free:
                lines.append(f'  {_port("IN", v)} -- {v.name} --> {_node(plan, i)}')

    for e in bindings.edges(plan):
        lines.append(
            f"  {_node(plan, idx[id(e.producer)])} -- {e.variable.name} --> "
            f"{_node(plan, idx[id(e.consumer)])}")

    terminal = set(plan.outputs)
    for i, s in enumerate(plan.steps):
        for v in s.outputs:
            if v in terminal:
                lines.append(f'  {_node(plan, i)} --> {_port("OUT", v)}')

    ports = [_port("IN", v) for v in plan.inputs] + [_port("OUT", v) for v in plan.outputs]
    if ports:
        lines.append("  classDef port fill:#fff,stroke:#333,stroke-width:1px,color:#333;")
        lines.append(f"  class {','.join(ports)} port;")
    lines.append("```")
    return "\n".join(lines)


def render_family(plans: Sequence[Plan]) -> str:
    """Alternative implementations as one node each, sharing ports, machinery nested inside.

    ⚠️ Refuses Plans that are not substitutable. Drawing them as interchangeable would be the
    diagram asserting something the types do not support — and a picture is believed faster than
    a docstring.
    """
    shapes = {p.shape() for p in plans}
    if len(shapes) > 1:
        raise ValueError(
            "render_family draws these as interchangeable, so they must BE interchangeable; "
            f"got {len(shapes)} distinct shapes")

    ins, outs = next(iter(shapes))
    lines = ["```mermaid", "flowchart TD"]
    for t in ins:
        lines.append(f'  IN_{_type_name(t)}(["{_type_name(t)}"])')

    for plan in plans:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", plan.name)
        lines.append(f'  subgraph {safe}["{plan.name} — {len(plan.steps)} steps"]')
        lines.append("    direction TB")
        for i, s in enumerate(plan.steps):
            lines.append(f'    {_node(plan, i)}["{_label(s)}"]')
        idx = {id(s): i for i, s in enumerate(plan.steps)}
        for e in bindings.edges(plan):
            lines.append(f"    {_node(plan, idx[id(e.producer)])} --> "
                         f"{_node(plan, idx[id(e.consumer)])}")
        lines.append("  end")

    for t in outs:
        lines.append(f'  OUT_{_type_name(t)}(["{_type_name(t)}"])')

    # Derived, so a rewiring changes the picture with no edit here.
    for plan in plans:
        free, terminal = set(plan.inputs), set(plan.outputs)
        for i, s in enumerate(plan.steps):
            if free & set(s.inputs):
                for t in ins:
                    lines.append(f"  IN_{_type_name(t)} --> {_node(plan, i)}")
                break
        for i, s in enumerate(plan.steps):
            if terminal & set(s.outputs):
                for t in outs:
                    lines.append(f"  {_node(plan, i)} --> OUT_{_type_name(t)}")
    lines.append("```")
    return "\n".join(lines)
