from plan_types.invariants.typing.compatible_bindings import (ALL, COMPATIBLE_BINDINGS,
                                                              DECLARED_SHAPES)

__all__ = ["COMPATIBLE_BINDINGS", "DECLARED_SHAPES", "ALL"]
from plan_types.invariants.typing.plan_time_only import PLAN_TIME_ONLY

ALL = (COMPATIBLE_BINDINGS, DECLARED_SHAPES)
"""Plan-subject rules. `PLAN_TIME_ONLY` takes ModelRecords, so it is not in this tuple —
mixing subject types in one collection is how a caller ends up passing the wrong thing."""

MODEL_RULES = (PLAN_TIME_ONLY,)
