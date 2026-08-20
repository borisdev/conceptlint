"""The shape of a real builder: nobsmed's simple causal-map arm, declared and run.

    plan_text ──> AskModelForCausalMap ──> draft ──┐
        │                                           ├──> DropWhatThePasteDoesNotSupport ──> case_graph
        └───────────────────────────────────────────┘

⚠️ **The fan-in is the point.** The grounding step needs the DRAFT and the ORIGINAL PASTE at once —
a model asked for a causal map will invent an intervention nobody wrote down, and the only way to
drop those is to compare against what the patient actually said. A Step modelled as a function of
its predecessor's output cannot say this, and the earlier version of this file papered over it by
pretending the second step consumed only the draft.

Two strategies are bound to the first Step, because "ask a model for a map" is one operation with
several ways to do it — that is the case the `Strategy` layer exists for, and inventing
`AskModelForCausalMapV2` would be the naming drift this package reports.

Domain types are deliberately thin. This is an example inside a package that must not learn a
domain; the real `CaseGraph` lives in nobsmed.

    uv run python3 -m examples.evidence_case_graph.flow
"""
from __future__ import annotations

from dataclasses import dataclass

from plan_types import Plan, Service, Step, Variable, render_mermaid, validate
from plan_types.execution import LocalRunner, check_strategy, execute
from plan_types.invariants import topology, typing


@dataclass(frozen=True)
class CausalMap:
    """A set of claims of the form `intervention -> outcome`. The product, not the Plan."""

    edges: tuple[tuple[str, str], ...] = ()

    def __str__(self) -> str:
        return ", ".join(f"{a} -> {b}" for a, b in self.edges) or "(empty)"


plan_text = Variable("plan_text", str)
draft = Variable("draft", CausalMap)
case_graph = Variable("case_graph", CausalMap)

#: What the arm needs REACHABLE, as opposed to what flows through it. Declared at the top level and
#: referenced by name, docker-compose style: a Step reaching for an undeclared Service is refused.
llm = Service("llm_service", kind="api", why="every arm calls a model; runs anywhere with network")


class AskModelForCausalMap(Step):
    """One call: the paste in, a whole causal map out. Nothing retrieved, nothing cited."""

    inputs, outputs = (plan_text,), (draft,)
    uses = (llm,)


class DropWhatThePasteDoesNotSupport(Step):
    """Remove edges the paste never mentioned. Needs the draft AND the paste."""

    inputs, outputs = (draft, plan_text), (case_graph,)


plan = Plan(
    name="llm_causal_map",
    steps=(AskModelForCausalMap(), DropWhatThePasteDoesNotSupport()),
    declared_inputs=(plan_text,),
    services=(llm,),
)


# ── two ways to ask a model, neither of them the "real" one ──────────────────────────────────────

def ask_one_shot(plan_text: str) -> CausalMap:
    """Cheap: one edge per mentioned drug, straight to the stated goal."""
    goal = "symptom control"
    return CausalMap(edges=tuple((w.strip(".,"), goal) for w in plan_text.split()
                                 if w.istitle() and len(w) > 4))


def ask_with_mechanism(plan_text: str) -> CausalMap:
    """Expensive: routes each intervention through a mechanism node, and invents one edge."""
    edges = [(w.strip(".,"), f"{w.strip('.,').lower()} mechanism") for w in plan_text.split()
             if w.istitle() and len(w) > 4]
    edges.append(("Acupuncture", "symptom control"))  # ← nobody wrote this down
    return CausalMap(edges=tuple(edges))


def drop_ungrounded(draft: CausalMap, plan_text: str) -> CausalMap:
    """The grounding step. THIS is why the fan-in exists."""
    said = plan_text.lower()
    return CausalMap(edges=tuple((a, b) for a, b in draft.edges if a.lower() in said))


one_shot = {AskModelForCausalMap: ask_one_shot,
            DropWhatThePasteDoesNotSupport: drop_ungrounded}
with_mechanism = {AskModelForCausalMap: ask_with_mechanism,
                  DropWhatThePasteDoesNotSupport: drop_ungrounded}


def main() -> None:
    print("invariants:", validate(plan, [*topology.ALL, *typing.ALL]) or "[]")
    print(render_mermaid(plan))

    paste = "Metformin and Spironolactone for PCOS, plus Inositol daily."

    for arm, strategy in (("one_shot", one_shot), ("with_mechanism", with_mechanism)):
        problems = check_strategy(plan, strategy)
        if problems:
            raise SystemExit("\n".join(problems))
        env = execute(plan, {"plan_text": paste}, LocalRunner(strategy))
        print(f"{arm:>14}: draft {len(env['draft'].edges)} edges -> kept {env['case_graph']}")


if __name__ == "__main__":
    main()
