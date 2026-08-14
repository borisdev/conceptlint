"""`Concept` — a canonical term, and the two laws it exists to protect.

    One Concept  -> One Meaning          a term must not quietly acquire a second meaning
    One Meaning  -> One Canonical Concept  a meaning must not quietly acquire a second term

Both laws are about SILENCE. Neither forbids a distinction; both forbid an undeclared one. A concept
that genuinely refines another is legal and says so with `REFINES`. A word that genuinely means two
things is legal and says so by being two concepts with a stated difference. What is illegal is
drifting into either state without anyone deciding.
"""
from __future__ import annotations

from typing import ClassVar


class Concept:
    """Subclass it, fill the class attributes, and you have declared a term.

    Not a Pydantic model and never instantiated: a Concept is read as a DECLARATION, including by
    AST off disk before the module can import. Instance behaviour would be weight nothing uses.
    """

    #: The stable wire tag. Survives renaming the class; nothing stored should key on `__name__`.
    ID: ClassVar[str] = ""

    #: What it means. One sentence. This is the "one meaning" the first law protects.
    DEFINITION: ClassVar[str] = ""

    #: What went wrong before it existed. The field that stops a concept being deleted the first
    #: time it is inconvenient — and the one an agent cannot fill by paraphrasing the class name.
    RATIONALE: ClassVar[str] = ""

    #: External grounding, e.g. "http://purl.org/net/p-plan#Step".
    #:
    #: Present means the meaning is anchored OUTSIDE this repository and is not ours to drift.
    #: Absent means we chose the name, which is not a defect — most concepts are ours — but it is
    #: the difference between "this is what P-Plan calls it" and "this is what somebody typed".
    ONTOLOGY_IRI: ClassVar[str] = ""

    #: The concept this one narrows, when it genuinely narrows one.
    #:
    #: ⚠️ This is the escape hatch for law two, and it must stay explicit. `ClinicalFinding` beside
    #: `Finding` is either a refinement or a duplicate, and only a declaration can say which. An
    #: unset REFINES on an overlapping name is exactly the drift being checked for.
    REFINES: ClassVar[type[Concept] | None] = None

    #: Words that mean this concept but are NOT its name — including ones we retired.
    #:
    #: Recording a retired synonym is how a dead word stays dead: the lint can say "you wrote
    #: `DataFlowNode`, that meaning is `Step`" instead of silently accepting a second vocabulary.
    ALSO_KNOWN_AS: ClassVar[tuple[str, ...]] = ()


def declared(root: type[Concept] = Concept) -> list[type[Concept]]:
    """Every declared Concept, deepest-first, in a stable order.

    Registration IS subclassing — there is no register() call to forget. The cost is that a concept
    in a module nobody imports does not exist, which `conceptlint.core.lint` handles by reading
    source rather than relying on imports.
    """
    out: list[type[Concept]] = []
    stack = [root]
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if cls is not root and cls.ID:
            out.append(cls)
    return sorted(out, key=lambda c: c.__name__)
