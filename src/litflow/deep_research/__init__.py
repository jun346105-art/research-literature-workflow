"""DeepResearch domain contracts without runtime or provider dependencies."""

from .contracts import (
    BriefApproval,
    BriefApprovalStatus,
    Citation,
    CitationRelation,
    Claim,
    ContractBundle,
    EvidenceLocator,
    EvidenceModality,
    EvidenceUnit,
    ResearchBrief,
    ResearchSubtask,
    ResearchTask,
    Source,
    SourceKind,
)
from .state import RunState, RunStatus, TransitionError

__all__ = [
    "BriefApproval",
    "BriefApprovalStatus",
    "Citation",
    "CitationRelation",
    "Claim",
    "ContractBundle",
    "EvidenceLocator",
    "EvidenceModality",
    "EvidenceUnit",
    "ResearchBrief",
    "ResearchSubtask",
    "ResearchTask",
    "Source",
    "SourceKind",
    "RunState",
    "RunStatus",
    "TransitionError",
]
