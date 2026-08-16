"""The typed dataflow contracts: Plan, Step, Variable.

Plan-time only. Execution belongs to a backend that wraps these from outside — see §11 and §13 of
the handoff, and `Plan.run` for the deliberately minimal executor.
"""
from conceptlint.dataflow.execution import (Activity, Agent, Entity, GraphError, Run, Used,
                                             WasAssociatedWith, WasDerivedFrom, WasGeneratedBy)
from conceptlint.dataflow.plan import (MultiStep, Plan, PlanError, check_arms,
                                       substitutable)
from conceptlint.dataflow.step import Step
from conceptlint.dataflow.variable import Variable

__all__ = [
    # plan time — what SHOULD happen
    "Plan", "MultiStep", "Step", "Variable", "PlanError", "substitutable", "check_arms",
    # execution — what DID happen
    "Run", "Activity", "Entity", "Agent", "GraphError",
    "Used", "WasGeneratedBy", "WasDerivedFrom", "WasAssociatedWith",
]
