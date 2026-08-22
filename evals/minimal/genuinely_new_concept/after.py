"""Vocabulary must be allowed to grow when the distinction is real."""
from workflow_plan.naming.declared_term import DeclaredTerm


class RetryPolicy(DeclaredTerm):
    ID = "retry_policy"
    DEFINITION = "How many times an Activity may be re-attempted, and how long between attempts."
    RATIONALE = "Retry belongs to execution; encoding it in a PlanStep would put a runtime concern in a declaration."
