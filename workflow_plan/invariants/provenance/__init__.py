"""Provenance rules. ⚠️ They take DIFFERENT SUBJECTS, so there is no combined `ALL`.

    grounded_citation    reads declared MODELS      Sequence[ModelRecord]
    measured_duration    reads a run's ACTIVITIES   Sequence[Activity]

`validate(subject, invariants)` hands one subject to every rule it is given, so a union of these two
is a list nobody can pass anywhere. Building one anyway was the first thing tried here and it broke
`test_this_packages_own_citations_resolve` immediately — the duration rule received ModelRecords.

`ALL` therefore keeps meaning the citation set, which is what every existing caller passes.
"""
from workflow_plan.invariants.provenance.grounded_citation import (ALL, GROUNDED_CITATION, ONTOLOGIES,
                                                                terms_in)
from workflow_plan.invariants.provenance.measured_duration import (ALL as DURATION_ALL,
                                                                MEASURED_DURATION, TOLERANCE_SECS)

__all__ = ["GROUNDED_CITATION", "ONTOLOGIES", "terms_in", "ALL",
           "MEASURED_DURATION", "TOLERANCE_SECS", "DURATION_ALL"]
