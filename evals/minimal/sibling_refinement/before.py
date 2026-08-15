"""Two names circling one meaning, with no declared relationship."""
from conceptlint.core.concept import Concept


class EvidenceFinding(Concept):
    ID = "evidence_finding"
    DEFINITION = "Something a study reports."
    RATIONALE = "r"


class ResearchFinding(Concept):
    ID = "research_finding"
    DEFINITION = "Something a study reports."
    RATIONALE = "r"
