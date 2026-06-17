"""Continuity checks against a Context Pack."""

from __future__ import annotations

from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.common import EvidenceItem
from storygraph.models.context import ContextPack
from storygraph.models.continuity import ContinuityIssue, ContinuityProvenance, ContinuityReport
from storygraph.models.draft import Draft


class RuleBasedContinuityChecker:
    def check(self, *, context_pack: ContextPack, draft: Draft) -> ContinuityReport:
        issues: list[ContinuityIssue] = []
        lowered_text = draft.text.lower()

        for boundary in context_pack.knowledge_boundaries:
            for secret_id in boundary.does_not_know:
                if secret_id.lower() in lowered_text:
                    issues.append(
                        ContinuityIssue(
                            id=new_id("issue"),
                            issue_type="knowledge_boundary_violation",
                            severity="high",
                            description=(
                                f"{boundary.character_id} appears to know {secret_id}, "
                                "but the Context Pack marks it as unknown."
                            ),
                            violated_nodes=[boundary.character_id, secret_id],
                            evidence=[
                                EvidenceItem(
                                    kind="draft_text",
                                    ref=draft.id,
                                    quote=secret_id,
                                    note="Secret ID appears in draft text.",
                                )
                            ],
                            suggestion="Rewrite the moment as an ambiguous clue rather than explicit knowledge.",
                            blocking=False,
                        )
                    )

        for required in context_pack.must_include:
            if required and required.lower() not in lowered_text:
                issues.append(
                    ContinuityIssue(
                        id=new_id("issue"),
                        issue_type="missing_required_element",
                        severity="medium",
                        description=f"Required scene element is missing: {required}",
                        violated_nodes=[context_pack.scene_id],
                        evidence=[
                            EvidenceItem(
                                kind="context_pack",
                                ref=context_pack.scene_id,
                                quote=required[:120],
                                note="Item listed in must_include.",
                            )
                        ],
                        suggestion="Add the required element without changing canon directly.",
                        blocking=False,
                    )
                )

        for forbidden in context_pack.must_not_violate:
            marker = forbidden.lower()
            if marker and marker in lowered_text:
                issues.append(
                    ContinuityIssue(
                        id=new_id("issue"),
                        issue_type="unsupported_new_fact",
                        severity="critical",
                        description=f"Draft directly contains a forbidden hard constraint: {forbidden}",
                        violated_nodes=[context_pack.scene_id],
                        evidence=[
                            EvidenceItem(
                                kind="draft_text",
                                ref=draft.id,
                                quote=forbidden[:120],
                                note="Hard constraint appeared in draft text.",
                            )
                        ],
                        suggestion="Remove or soften this revelation so it remains outside the POV knowledge.",
                        blocking=True,
                    )
                )

        for banned_pattern in context_pack.style_constraints.banned_patterns:
            marker = banned_pattern.lower()
            if marker and marker in lowered_text:
                issues.append(
                    ContinuityIssue(
                        id=new_id("issue"),
                        issue_type="style_drift",
                        severity="medium",
                        description=f"Draft uses a banned style pattern: {banned_pattern}",
                        violated_nodes=[context_pack.scene_id],
                        evidence=[
                            EvidenceItem(
                                kind="context_pack",
                                ref=context_pack.scene_id,
                                quote=banned_pattern[:120],
                                note="Pattern listed in style_constraints.banned_patterns.",
                            )
                        ],
                        suggestion="Remove or rewrite the banned pattern while preserving scene facts.",
                        blocking=False,
                    )
                )

        status = "pass" if not issues else "needs_revision"
        if any(issue.blocking or issue.severity == "critical" for issue in issues):
            status = "blocked"
        return ContinuityReport(
            project_id=context_pack.project_id,
            scene_id=context_pack.scene_id,
            draft_id=draft.id,
            context_pack_id=f"context_{context_pack.scene_id}",
            status=status,  # type: ignore[arg-type]
            summary="No continuity issues found." if not issues else f"Found {len(issues)} issue(s).",
            issues=issues,
            checked_dimensions=self._checked_dimensions(context_pack),
            provenance=ContinuityProvenance(
                graph_query_ids=context_pack.provenance.graph_query_ids,
                context_pack_ref=f"context_{context_pack.scene_id}",
            ),
            created_at=utc_now(),
        )

    @staticmethod
    def _checked_dimensions(context_pack: ContextPack) -> list[str]:
        dimensions: list[str] = ["knowledge_boundary"]
        if context_pack.timeline_position:
            dimensions.append("timeline")
        if context_pack.location_id:
            dimensions.append("location_state")
        if context_pack.relevant_world_rules:
            dimensions.append("world_rule")
        if context_pack.unresolved_foreshadowing:
            dimensions.append("foreshadowing")
        if context_pack.style_constraints.banned_patterns:
            dimensions.append("style_constraint")
        return dimensions
