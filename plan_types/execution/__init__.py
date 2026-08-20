"""Execution: how a declared Plan is actually performed.

Nothing in `plan_types.plan` imports this. The dependency runs one way — a specification must be
readable, validatable and drawable without an execution backend in the room, which is the whole
claim the package makes.

    Step        what transformation exists      plan/
    Strategy    how it is performed             here
    StepRunner  the mechanics of performing it  here
"""
from plan_types.execution.local import ExecutionError, LocalRunner, execute
from plan_types.execution.runner import StepRunner
from plan_types.execution.strategy import Implementation, Strategy, check_strategy

__all__ = ["Strategy", "Implementation", "check_strategy",
           "StepRunner", "LocalRunner", "execute", "ExecutionError"]
