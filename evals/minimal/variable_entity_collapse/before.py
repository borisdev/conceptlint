"""A Variable that has quietly become an Entity."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Variable:
    name: str
    type: type
    started_at: datetime      # only a run has this
    value: object             # and this is the actual value, not the kind
