"""The distinction made explicit: both narrow one canonical Finding."""
from conceptlint.core.concept import Concept


class Finding(Concept):
    ID = "finding"
    DEFINITION = "Something a study reports."
    RATIONALE = "r"


class EvidenceFinding(Finding):
    ID = "evidence_finding"
    DEFINITION = "A finding used as support for a claim."
    RATIONALE = "r"
    REFINES = Finding


class ResearchFinding(Finding):
    ID = "research_finding"
    DEFINITION = "A finding as originally published, before any use is made of it."
    RATIONALE = "r"
    REFINES = Finding
