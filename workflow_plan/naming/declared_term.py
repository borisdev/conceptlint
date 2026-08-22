"""`DeclaredTerm` — one term in a vocabulary, and the two laws it exists to protect.

    One term    -> One meaning     a term must not quietly acquire a second meaning
    One meaning -> One term        a meaning must not quietly acquire a second name

Both laws are about SILENCE. Neither forbids a distinction; both forbid an undeclared one. A term
that genuinely refines another is legal and says so with `REFINES`. A word that genuinely means two
things is legal and says so by being two terms with a stated difference. What is illegal is drifting
into either state without anyone deciding.

## ⚠️ This is OUR base, and it is not asked of a user

`docs/gtm.md` decided that a user's domain models stay ordinary Pydantic — no `class Finding(...)`
annotation tax, because a linter that demands a codebase be annotated before it says anything is a
linter nobody runs. That decision is unchanged.

This is the other half: the types in THIS package are the vocabulary the package is about, nobody
outside writes them, and the tax is zero. The two look identical from a distance and must not be
conflated — `workflow_plan.naming.records` is still the surface that reads unannotated models.

## Why it lives here and not in `conceptlint`

It was `conceptlint.core.concept.Concept`. `conceptlint.core.lint` imports `workflow_plan`, so a base
in `conceptlint` that `workflow_plan.plan` had to inherit would close an import cycle. The direction
that works is the one that matches the fold-in: the library declares the vocabulary, the linter
reads it.
"""
from __future__ import annotations

from typing import ClassVar


class DeclaredTerm:
    """Subclass it, fill the class attributes, and you have declared a term.

    Not a Pydantic model and never instantiated on its own account: a DeclaredTerm is read as a
    DECLARATION, including by AST off disk before the module can import. It carries no `__init__`,
    no fields and no methods, so a frozen dataclass or a `Generic` can inherit it without acquiring
    behaviour it did not ask for — which is what lets `Plan`, `Variable` and `Service` keep being
    exactly the dataclasses they already were.
    """

    #: The stable wire tag. Survives renaming the class; nothing stored should key on `__name__`.
    ID: ClassVar[str] = ""

    #: What it means. One sentence. This is the "one meaning" the first law protects.
    DEFINITION: ClassVar[str] = ""

    #: What went wrong before it existed. The field that stops a term being deleted the first time
    #: it is inconvenient — and the one an agent cannot fill by paraphrasing the class name.
    RATIONALE: ClassVar[str] = ""

    #: External grounding, e.g. "http://purl.org/net/p-plan#Step".
    #:
    #: Present means the meaning is anchored OUTSIDE this repository and is not ours to drift.
    #: Absent means we chose the name, which is not a defect — most terms are ours — but it is the
    #: difference between "this is what P-Plan calls it" and "this is what somebody typed".
    ONTOLOGY_IRI: ClassVar[str] = ""

    #: The term this one narrows, when it genuinely narrows one.
    #:
    #: ⚠️ This is the escape hatch for law two, and it must stay explicit. `ClinicalFinding` beside
    #: `Finding` is either a refinement or a duplicate, and only a declaration can say which. An
    #: unset REFINES on an overlapping name is exactly the drift being checked for.
    REFINES: ClassVar[type[DeclaredTerm] | None] = None

    #: Words that mean this term but are NOT its name — including ones we retired.
    #:
    #: Recording a retired synonym is how a dead word stays dead: the lint can say "you wrote
    #: `DataFlowNode`, that meaning is `PlanStep`" instead of silently accepting a second
    #: vocabulary. It is why `PlanStep.ALSO_KNOWN_AS` lists `"Step"` — the rename does not make the
    #: old word available to something else.
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ()


def declared(root: type[DeclaredTerm] = DeclaredTerm) -> list[type[DeclaredTerm]]:
    """Every declared term, in a stable order.

    Registration IS subclassing — there is no register() call to forget. The cost is that a term in
    a module nobody imports does not exist, which `conceptlint.core.lint` handles by reading source
    rather than relying on imports.

    ⚠️ `ID` is read from the class's OWN `__dict__`, never inherited, and that is what makes this
    safe to put under `PlanStep`. `ID` is a ClassVar, so `class Square(PlanStep)` inherits
    `ID = "step"` for free — and every user Step in every example would then arrive here claiming
    the same wire tag, which `Ambiguity` reports as "the tag 'step' is claimed by N terms". The
    finding would be real given the input and useless given the intent. A declaration is something
    you WRITE; subclassing a declared term is using it.
    """
    out: list[type[DeclaredTerm]] = []
    stack = [root]
    seen: set[type[DeclaredTerm]] = set()
    while stack:
        cls = stack.pop()
        if cls in seen:          # MultiStep inherits Plan AND PlanStep — reachable twice
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
        if cls is not root and cls.__dict__.get("ID"):
            out.append(cls)
    return sorted(out, key=lambda c: c.__name__)
