"""The docker-compose property, as two executable rules.

A named volume in compose must be declared at the top level before a service may mount it, and that
single constraint is what stops one name meaning several things: there is exactly one declared
object and every reference must point at it.

These reproduce it for `PlanDependency`. Neither is clever; the value is entirely in the rule being
mandatory rather than conventional.
"""
from __future__ import annotations

from workflow_plan.invariants.invariant import InvariantCategory, SemanticInvariant
from workflow_plan.plan.plan import Plan


def _declared(plan: Plan) -> None:
    undeclared = [s for s in plan.used_services if s not in plan.services]
    if not undeclared:
        return
    names = ", ".join(sorted(str(s.name) for s in undeclared))
    raise DECLARED_SERVICES.violated(
        f"Plan {plan.name!r} has PlanStep(s) using undeclared service(s): {names}. Add them to the "
        f"Plan's `services=(...)`. A service referenced but never declared is how one word comes to "
        f"mean three things — which is the failure this rule exists to make impossible.")


DECLARED_SERVICES: SemanticInvariant[Plan] = SemanticInvariant(
    id="topology.declared_services",
    category=InvariantCategory.TOPOLOGY,
    statement="Every PlanDependency a PlanStep uses is declared in its Plan's `services`.",
    why=("Stolen from docker-compose, where a named volume must be declared top-level before any "
         "service may mount it. Observed failure: a conversation used 'retriever' for three "
         "different things across an hour because no declared object owned the word. The dataflow "
         "vocabulary was precise; the infrastructure vocabulary was not declared at all."),
    check=_declared,
)


def _no_orphans(plan: Plan) -> None:
    used = set(plan.used_services)
    orphans = [s for s in plan.services if s not in used]
    if not orphans:
        return
    names = ", ".join(sorted(str(s.name) for s in orphans))
    raise NO_ORPHAN_SERVICES.violated(
        f"Plan {plan.name!r} declares service(s) no PlanStep uses: {names}. Either a PlanStep should say "
        f"`uses = (...)`, or the declaration is stale. A Plan that overstates its dependencies "
        f"makes a deployment decision on evidence that is not there.")


NO_ORPHAN_SERVICES: SemanticInvariant[Plan] = SemanticInvariant(
    id="topology.no_orphan_services",
    category=InvariantCategory.TOPOLOGY,
    statement="Every declared PlanDependency is used by at least one PlanStep.",
    why=("The other direction, and it is not symmetric decoration. `services` is what a reader "
         "consults to decide where a Plan can run — 'needs a 9.5 GB file on local disk, so it "
         "cannot run on a container app'. A stale entry there does not merely clutter, it argues "
         "against a deployment that would actually work."),
    check=_no_orphans,
)

ALL: tuple[SemanticInvariant[Plan], ...] = (DECLARED_SERVICES, NO_ORPHAN_SERVICES)
