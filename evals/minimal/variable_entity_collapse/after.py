"""The plan-time type keeps only plan-time fields. The run's data belongs to an Entity."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Variable:
    name: str
    type: type
