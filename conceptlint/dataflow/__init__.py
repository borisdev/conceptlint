"""The typed dataflow contracts: Plan, Step, Variable.

Plan-time only. Execution belongs to a backend that wraps these from outside — see §11 and §13 of
the handoff, and `Plan.run` for the deliberately minimal executor.
"""
from conceptlint.dataflow.plan import Plan, PlanError, check_arms, substitutable
from conceptlint.dataflow.step import Step
from conceptlint.dataflow.variable import Variable

__all__ = ["Plan", "PlanError", "Step", "Variable", "substitutable", "check_arms"]
