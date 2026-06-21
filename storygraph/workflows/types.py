"""Shared workflow result types."""

from __future__ import annotations

from dataclasses import dataclass

from storygraph.models.candidate import CandidateFact
from storygraph.models.context import ContextPack
from storygraph.models.continuity import ContinuityReport
from storygraph.models.draft import Draft
from storygraph.models.proposal import ProposalArtifact
from storygraph.models.workflow import WorkflowRun


@dataclass(frozen=True)
class SceneRunResult:
    context_pack: ContextPack
    draft: Draft | None
    continuity_report: ContinuityReport | None
    candidates: list[CandidateFact]
    workflow_run: WorkflowRun | None = None
    proposal: ProposalArtifact | None = None
