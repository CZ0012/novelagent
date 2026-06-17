"""Minimal scene workflow skeleton.

This is intentionally a typed service workflow rather than a set of autonomous chat agents.
It mirrors the LangGraph target shape while remaining runnable without external services.
"""

from __future__ import annotations

from dataclasses import dataclass

from storygraph.models.candidate import CandidateFact
from storygraph.models.context import ContextPack
from storygraph.models.continuity import ContinuityReport
from storygraph.models.draft import Draft
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.continuity_checker import RuleBasedContinuityChecker
from storygraph.services.scene_writer import RuleBasedSceneWriter
from storygraph.services.state_extraction import RuleBasedStateExtractor


@dataclass(frozen=True)
class SceneRunResult:
    context_pack: ContextPack
    draft: Draft
    continuity_report: ContinuityReport
    candidates: list[CandidateFact]


class SceneGenerationWorkflow:
    def __init__(
        self,
        *,
        context_builder: ContextPackBuilder,
        writer: RuleBasedSceneWriter,
        checker: RuleBasedContinuityChecker,
        extractor: RuleBasedStateExtractor,
    ) -> None:
        self.context_builder = context_builder
        self.writer = writer
        self.checker = checker
        self.extractor = extractor

    def run(self, *, project_id: str, scene_id: str) -> SceneRunResult:
        context_pack = self.context_builder.build(project_id=project_id, scene_id=scene_id)
        draft = self.writer.write_and_save(context_pack)
        report = self.checker.check(context_pack=context_pack, draft=draft)
        candidates: list[CandidateFact] = []
        if report.status != "blocked":
            candidates = self.extractor.extract(project_id=project_id, draft=draft)
        return SceneRunResult(
            context_pack=context_pack,
            draft=draft,
            continuity_report=report,
            candidates=candidates,
        )

