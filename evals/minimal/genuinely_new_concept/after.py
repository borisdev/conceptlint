"""Vocabulary must be allowed to grow when the distinction is real."""
from conceptlint.core.concept import Concept


class RetryPolicy(Concept):
    ID = "retry_policy"
    DEFINITION = "How many times an Activity may be re-attempted, and how long between attempts."
    RATIONALE = "Retry belongs to execution; encoding it in a Step would put a runtime concern in a declaration."
