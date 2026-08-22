"""The central pair. Two distinct failures, symmetric and easy to conflate.

    one name  -> many concepts   ambiguous reference
    many names -> one concept    naming drift
"""
from workflow_plan.invariants.naming.ambiguous_reference import AMBIGUOUS_REFERENCE
from workflow_plan.invariants.naming.naming_drift import NAMING_DRIFT

ALL = (AMBIGUOUS_REFERENCE, NAMING_DRIFT)
__all__ = ["AMBIGUOUS_REFERENCE", "NAMING_DRIFT", "ALL"]
