"""Two surfaces on one question: what is this thing called, and does the name already mean something?

    declared_term   terms WE declare — a base class, six fields, read as a declaration
    records         models ANYBODY writes — ordinary Pydantic, read off disk by AST

The second is the default surface and the one `docs/gtm.md` protects: a user annotates nothing. The
first is for this package's own vocabulary, where the annotation costs nothing because nobody
outside writes these types.
"""
from workflow_plan.naming.declared_term import DeclaredTerm, declared

__all__ = ["DeclaredTerm", "declared"]
