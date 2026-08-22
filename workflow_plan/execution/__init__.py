"""Execution: how a declared Plan is actually performed.

Nothing in `workflow_plan.plan` imports this. The dependency runs one way — a specification must be
readable, validatable and drawable without an execution backend in the room, which is the whole
claim the package makes.

    Step        what transformation exists      plan/
    Strategy    how it is performed             here
    StepRunner  the mechanics of performing it  here
"""
from workflow_plan.execution.local import ExecutionError, LocalRunner, run
from workflow_plan.execution.runner import StepRunner
from workflow_plan.execution.strategy import Implementation, Strategy, check_strategy

__all__ = ["Strategy", "Implementation", "check_strategy",
           "StepRunner", "LocalRunner", "run", "ExecutionError"]
