"""Two names circling one meaning, with no declared relationship."""
from workflow_plan.naming.declared_term import DeclaredTerm


class EvidenceFinding(DeclaredTerm):
    ID = "evidence_finding"
    DEFINITION = "Something a study reports."
    RATIONALE = "r"


class ResearchFinding(DeclaredTerm):
    ID = "research_finding"
    DEFINITION = "Something a study reports."
    RATIONALE = "r"
