"""Continuity checks against a Context Pack."""

from __future__ import annotations

import re

from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.common import EvidenceItem
from storygraph.models.context import ContextPack
from storygraph.models.continuity import ContinuityIssue, ContinuityProvenance, ContinuityReport
from storygraph.models.draft import Draft
from storygraph.models.project import OutputLanguage, localized


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


class RuleBasedContinuityChecker:
    def check(self, *, context_pack: ContextPack, draft: Draft) -> ContinuityReport:
        issues: list[ContinuityIssue] = []
        lowered_text = draft.text.lower()

        if draft.content_language is None:
            issues.append(
                ContinuityIssue(
                    id=new_id("issue"),
                    issue_type="wrong_output_language",
                    severity="critical",
                    description=localized(
                        context_pack.output_language,
                        zh="历史草稿没有语言快照，无法证明它与当前项目语言一致。",
                        en=(
                            "The legacy draft has no language snapshot, so it cannot be "
                            "verified against the current project language."
                        ),
                    ),
                    violated_nodes=[context_pack.scene_id],
                    evidence=[
                        EvidenceItem(
                            kind="draft_text",
                            ref=draft.id,
                            note=localized(
                                context_pack.output_language,
                                zh="历史草稿的 content_language 未记录。",
                                en="The legacy Draft has no recorded content_language.",
                            ),
                        )
                    ],
                    suggestion=localized(
                        context_pack.output_language,
                        zh="请由作者将内容另存为当前项目语言的新草稿后再继续。",
                        en=(
                            "Have the author save the content as a new Draft in the current "
                            "project language before continuing."
                        ),
                    ),
                    blocking=True,
                )
            )
        elif draft.content_language != context_pack.output_language:
            issues.append(
                ContinuityIssue(
                    id=new_id("issue"),
                    issue_type="wrong_output_language",
                    severity="critical",
                    description=(
                        f"Draft content_language {draft.content_language} conflicts with the "
                        f"Context Pack output_language {context_pack.output_language}."
                    ),
                    violated_nodes=[context_pack.scene_id],
                    evidence=[
                        EvidenceItem(
                            kind="draft_text",
                            ref=draft.id,
                            note="Draft language snapshot does not match this generation run.",
                        )
                    ],
                    suggestion="Regenerate the draft using the frozen WorkflowRun language.",
                    blocking=True,
                )
            )

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
                            suggestion=(
                                "Rewrite the moment as an ambiguous clue rather than explicit "
                                "knowledge."
                            ),
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
                        description=(
                            f"Draft directly contains a forbidden hard constraint: {forbidden}"
                        ),
                        violated_nodes=[context_pack.scene_id],
                        evidence=[
                            EvidenceItem(
                                kind="draft_text",
                                ref=draft.id,
                                quote=forbidden[:120],
                                note="Hard constraint appeared in draft text.",
                            )
                        ],
                        suggestion=(
                            "Remove or soften this revelation so it remains outside the POV "
                            "knowledge."
                        ),
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
                        suggestion=(
                            "Remove or rewrite the banned pattern while preserving scene facts."
                        ),
                        blocking=False,
                    )
                )

        issues.extend(self._timeline_issues(context_pack=context_pack, draft=draft))
        issues.extend(self._location_state_issues(context_pack=context_pack, draft=draft))
        issues.extend(self._relationship_state_issues(context_pack=context_pack, draft=draft))
        issues.extend(self._world_rule_issues(context_pack=context_pack, draft=draft))
        issues.extend(self._foreshadowing_issues(context_pack=context_pack, draft=draft))
        issues.extend(self._causality_issues(context_pack=context_pack, draft=draft))
        issues.extend(self._pov_issues(context_pack=context_pack, draft=draft))

        if context_pack.output_language == "zh-CN":
            issues = [_localize_issue(issue) for issue in issues]

        status = "pass" if not issues else "needs_revision"
        if any(issue.blocking or issue.severity == "critical" for issue in issues):
            status = "blocked"
        return ContinuityReport(
            project_id=context_pack.project_id,
            output_language=context_pack.output_language,
            scene_id=context_pack.scene_id,
            draft_id=draft.id,
            context_pack_id=f"context_{context_pack.scene_id}",
            status=status,  # type: ignore[arg-type]
            summary=localized(
                context_pack.output_language,
                zh="未发现连续性问题。" if not issues else f"发现 {len(issues)} 个问题。",
                en="No continuity issues found."
                if not issues
                else f"Found {len(issues)} issue(s).",
            ),
            issues=issues,
            checked_dimensions=self._checked_dimensions(context_pack),
            provenance=ContinuityProvenance(
                graph_query_ids=context_pack.provenance.graph_query_ids,
                context_pack_ref=f"context_{context_pack.scene_id}",
            ),
            created_at=utc_now(),
        )

    def _timeline_issues(self, *, context_pack: ContextPack, draft: Draft) -> list[ContinuityIssue]:
        if not context_pack.timeline_position:
            return []
        conflict = _timeline_conflict(context_pack.timeline_position, draft.text)
        if conflict is None:
            return []
        quote, note = conflict
        return [
            ContinuityIssue(
                id=new_id("issue"),
                issue_type="timeline_conflict",
                severity="high",
                description=(
                    "Draft timeline wording conflicts with the Context Pack timeline position: "
                    f"{context_pack.timeline_position}"
                ),
                violated_nodes=[context_pack.scene_id],
                evidence=[
                    EvidenceItem(
                        kind="context_pack",
                        ref=context_pack.scene_id,
                        quote=context_pack.timeline_position[:120],
                        note="Expected scene timeline from the Context Pack.",
                    ),
                    EvidenceItem(
                        kind="draft_text",
                        ref=draft.id,
                        quote=quote[:120],
                        note=note,
                    ),
                ],
                suggestion="Align the draft's time reference with the Context Pack timeline.",
                blocking=False,
            )
        ]

    def _location_state_issues(
        self, *, context_pack: ContextPack, draft: Draft
    ) -> list[ContinuityIssue]:
        if not context_pack.location_id:
            return []
        expected_location = context_pack.location_id.lower()
        issues: list[ContinuityIssue] = []
        seen: set[str] = set()
        for match in re.finditer(r"\blocation_[a-z0-9_]+\b", draft.text, flags=re.IGNORECASE):
            found_location = match.group(0).lower()
            if found_location == expected_location or found_location in seen:
                continue
            seen.add(found_location)
            issues.append(
                ContinuityIssue(
                    id=new_id("issue"),
                    issue_type="location_conflict",
                    severity="high",
                    description=(
                        f"Draft places the scene at {found_location}, but the Context Pack "
                        f"location is {context_pack.location_id}."
                    ),
                    violated_nodes=[context_pack.location_id, found_location],
                    evidence=[
                        EvidenceItem(
                            kind="context_pack",
                            ref=context_pack.scene_id,
                            quote=context_pack.location_id,
                            note="Expected scene location ID.",
                        ),
                        EvidenceItem(
                            kind="draft_text",
                            ref=draft.id,
                            quote=match.group(0),
                            note="Conflicting location ID appears in draft text.",
                        ),
                    ],
                    suggestion=(
                        "Keep the scene anchored to the Context Pack location or revise the pack "
                        "after human review."
                    ),
                    blocking=False,
                )
            )
        return issues

    def _relationship_state_issues(
        self, *, context_pack: ContextPack, draft: Draft
    ) -> list[ContinuityIssue]:
        issues: list[ContinuityIssue] = []
        expected_relationships = [
            parsed
            for item in context_pack.active_relationships
            if (parsed := _parse_relationship(item))
        ]
        if not expected_relationships:
            return issues

        draft_relationships = [
            parsed
            for match in _RELATIONSHIP_RE.finditer(draft.text)
            if (parsed := _parse_relationship(match.group(0)))
        ]
        for expected in expected_relationships:
            for found in draft_relationships:
                if expected["source"] != found["source"] or expected["target"] != found["target"]:
                    continue
                conflict_note = _relationship_conflict_note(expected, found)
                if conflict_note is None:
                    continue
                issues.append(
                    ContinuityIssue(
                        id=new_id("issue"),
                        issue_type="relationship_conflict",
                        severity="medium",
                        description=(
                            "Draft states a relationship that conflicts with the active "
                            f"Context Pack relationship for {expected['source']} and "
                            f"{expected['target']}."
                        ),
                        violated_nodes=[expected["source"], expected["target"]],
                        evidence=[
                            EvidenceItem(
                                kind="context_pack",
                                ref=context_pack.scene_id,
                                quote=expected["raw"][:120],
                                note="Active relationship from the Context Pack.",
                            ),
                            EvidenceItem(
                                kind="draft_text",
                                ref=draft.id,
                                quote=found["raw"][:120],
                                note=conflict_note,
                            ),
                        ],
                        suggestion=(
                            "Keep relationship changes implicit or route them through candidate "
                            "fact review."
                        ),
                        blocking=False,
                    )
                )
        return issues

    def _world_rule_issues(
        self, *, context_pack: ContextPack, draft: Draft
    ) -> list[ContinuityIssue]:
        issues: list[ContinuityIssue] = []
        lowered_text = draft.text.lower()
        for rule in context_pack.relevant_world_rules:
            rule_ref, rule_text = _split_context_item(rule)
            if not rule_text:
                continue
            conflict_quote = _world_rule_conflict_quote(
                rule_ref=rule_ref,
                rule_text=rule_text,
                lowered_text=lowered_text,
            )
            if conflict_quote is None:
                continue
            issues.append(
                ContinuityIssue(
                    id=new_id("issue"),
                    issue_type="world_rule_conflict",
                    severity="high",
                    description=f"Draft conflicts with world rule: {rule_text}",
                    violated_nodes=[rule_ref or context_pack.scene_id],
                    evidence=[
                        EvidenceItem(
                            kind="context_pack",
                            ref=context_pack.scene_id,
                            quote=rule[:120],
                            note="Relevant world rule from the Context Pack.",
                        ),
                        EvidenceItem(
                            kind="draft_text",
                            ref=draft.id,
                            quote=conflict_quote[:120],
                            note="Draft text appears to negate or bypass the rule.",
                        ),
                    ],
                    suggestion="Revise the moment so the world rule still governs the scene.",
                    blocking=False,
                )
            )
        return issues

    def _foreshadowing_issues(
        self, *, context_pack: ContextPack, draft: Draft
    ) -> list[ContinuityIssue]:
        issues: list[ContinuityIssue] = []
        lowered_text = draft.text.lower()
        for item in context_pack.unresolved_foreshadowing:
            foreshadowing_ref, clue_text = _split_context_item(item)
            if not clue_text:
                continue
            payoff_quote = _premature_payoff_quote(foreshadowing_ref, lowered_text)
            if payoff_quote is not None:
                issues.append(
                    ContinuityIssue(
                        id=new_id("issue"),
                        issue_type="foreshadowing_mismatch",
                        severity="medium",
                        description=(
                            "Draft appears to resolve an unresolved foreshadowing item before "
                            "review."
                        ),
                        violated_nodes=[foreshadowing_ref or context_pack.scene_id],
                        evidence=[
                            EvidenceItem(
                                kind="context_pack",
                                ref=context_pack.scene_id,
                                quote=item[:120],
                                note="Unresolved foreshadowing from the Context Pack.",
                            ),
                            EvidenceItem(
                                kind="draft_text",
                                ref=draft.id,
                                quote=payoff_quote[:120],
                                note="Draft text uses payoff wording near the foreshadowing ID.",
                            ),
                        ],
                        suggestion=(
                            "Keep the clue unresolved unless a human-approved payoff is intended "
                            "here."
                        ),
                        blocking=False,
                    )
                )
                continue
            if not _has_content_overlap(clue_text, draft.text):
                issues.append(
                    ContinuityIssue(
                        id=new_id("issue"),
                        issue_type="foreshadowing_mismatch",
                        severity="low",
                        description="Draft does not preserve the unresolved foreshadowing clue.",
                        violated_nodes=[foreshadowing_ref or context_pack.scene_id],
                        evidence=[
                            EvidenceItem(
                                kind="context_pack",
                                ref=context_pack.scene_id,
                                quote=item[:120],
                                note="Unresolved foreshadowing expected by the Context Pack.",
                            )
                        ],
                        suggestion=(
                            "Seed the clue in the draft or remove it from the Context Pack "
                            "through review."
                        ),
                        blocking=False,
                    )
                )
        return issues

    def _causality_issues(
        self, *, context_pack: ContextPack, draft: Draft
    ) -> list[ContinuityIssue]:
        if not (
            context_pack.scene_goal
            or context_pack.conflict
            or context_pack.previous_scene_summary
        ):
            return []
        marker = _first_marker(
            draft.text,
            [
                "for no reason",
                "with no reason",
                "without cause",
                "without explanation",
                "nothing led to",
            ],
        )
        if marker is None:
            return []
        return [
            ContinuityIssue(
                id=new_id("issue"),
                issue_type="causal_gap",
                severity="medium",
                description=(
                    "Draft states an event without a cause despite scene goal/conflict context."
                ),
                violated_nodes=[context_pack.scene_id],
                evidence=[
                    EvidenceItem(
                        kind="draft_text",
                        ref=draft.id,
                        quote=marker[:120],
                        note="Causal-gap marker appears in draft text.",
                    )
                ],
                suggestion="Tie the event to the scene goal, conflict, or previous scene result.",
                blocking=False,
            )
        ]

    def _pov_issues(self, *, context_pack: ContextPack, draft: Draft) -> list[ContinuityIssue]:
        if "limited" not in context_pack.style_constraints.pov.lower():
            return []
        markers = [
            "unbeknownst to",
            "unknown to",
            "what the pov could not know",
            f"what {context_pack.pov_character_id.lower()} could not know",
            "the reader knew",
            "omniscient narrator",
            "omniscient explanation",
        ]
        marker = _first_marker(draft.text, markers)
        if marker is None:
            return []
        return [
            ContinuityIssue(
                id=new_id("issue"),
                issue_type="pov_leak",
                severity="medium",
                description=(
                    "Draft uses narrator knowledge that can exceed the limited POV constraint."
                ),
                violated_nodes=[context_pack.pov_character_id],
                evidence=[
                    EvidenceItem(
                        kind="context_pack",
                        ref=context_pack.scene_id,
                        quote=context_pack.style_constraints.pov,
                        note="POV style constraint from the Context Pack.",
                    ),
                    EvidenceItem(
                        kind="draft_text",
                        ref=draft.id,
                        quote=marker[:120],
                        note="Limited-POV leak marker appears in draft text.",
                    ),
                ],
                suggestion=(
                    "Filter the information through what the POV character can observe or infer."
                ),
                blocking=False,
            )
        ]

    @staticmethod
    def _checked_dimensions(context_pack: ContextPack) -> list[str]:
        dimensions: list[str] = ["knowledge_boundary", "language_consistency"]
        if context_pack.timeline_position:
            dimensions.append("timeline")
        if context_pack.location_id:
            dimensions.append("location_state")
        if context_pack.active_relationships:
            dimensions.append("relationship_state")
        if context_pack.relevant_world_rules:
            dimensions.append("world_rule")
        if context_pack.unresolved_foreshadowing:
            dimensions.append("foreshadowing")
        if context_pack.scene_goal or context_pack.conflict or context_pack.previous_scene_summary:
            dimensions.append("causality")
        if context_pack.style_constraints.pov:
            dimensions.append("pov")
        if context_pack.style_constraints.banned_patterns:
            dimensions.append("style_constraint")
        return dimensions


def _localize_issue(issue: ContinuityIssue) -> ContinuityIssue:
    return issue.model_copy(
        update={
            "description": _localized_checker_text(issue.description, "zh-CN"),
            "suggestion": _localized_checker_text(issue.suggestion, "zh-CN"),
            "evidence": [
                item.model_copy(
                    update={"note": _localized_checker_text(item.note, "zh-CN")}
                )
                for item in issue.evidence
            ],
        }
    )


def _localized_checker_text(text: str | None, language: OutputLanguage) -> str | None:
    if text is None or language == "en-US":
        return text
    structured_patterns = (
        (
            re.compile(
                r"^Draft content_language (?P<draft>\S+) conflicts with the Context Pack "
                r"output_language (?P<context>\S+)\.$"
            ),
            lambda match: (
                f"草稿的 content_language {match['draft']} 与上下文包的 "
                f"output_language {match['context']} 冲突。"
            ),
        ),
        (
            re.compile(
                r"^(?P<character>.+) appears to know (?P<secret>.+), but the Context Pack "
                r"marks it as unknown\.$"
            ),
            lambda match: (
                f"{match['character']} 似乎知道 {match['secret']}，"
                "但上下文包将其标记为未知。"
            ),
        ),
        (
            re.compile(
                r"^Draft places the scene at (?P<found>.+), but the Context Pack location is "
                r"(?P<expected>.+)\.$"
            ),
            lambda match: (
                f"草稿将场景置于 {match['found']}，"
                f"但上下文包的位置是 {match['expected']}。"
            ),
        ),
        (
            re.compile(
                r"^Draft states a relationship that conflicts with the active Context Pack "
                r"relationship for (?P<source>.+) and (?P<target>.+)\.$"
            ),
            lambda match: (
                "草稿陈述的关系与上下文包中的有效关系冲突："
                f"{match['source']} 与 {match['target']}。"
            ),
        ),
    )
    for pattern, renderer in structured_patterns:
        match = pattern.fullmatch(text)
        if match is not None:
            return renderer(match)
    replacements = (
        (
            "Draft content_language ",
            "草稿的 content_language ",
        ),
        (
            " conflicts with the Context Pack output_language ",
            " 与上下文包的 output_language 冲突：",
        ),
        (
            " appears to know ",
            " 似乎知道 ",
        ),
        (
            ", but the Context Pack marks it as unknown.",
            "，但上下文包将其标记为未知。",
        ),
        ("Required scene element is missing: ", "缺少必需的场景元素："),
        ("Draft directly contains a forbidden hard constraint: ", "草稿直接包含禁止违反的硬约束："),
        ("Draft uses a banned style pattern: ", "草稿使用了禁用的文风模式："),
        (
            "Draft timeline wording conflicts with the Context Pack timeline position: ",
            "草稿中的时间表述与上下文包的时间位置冲突：",
        ),
        ("Draft places the scene at ", "草稿将场景置于 "),
        (", but the Context Pack location is ", "，但上下文包的位置是 "),
        (
            "Draft states a relationship that conflicts with the active Context Pack relationship for ",
            "草稿陈述的关系与上下文包中以下对象的有效关系冲突：",
        ),
        ("Draft conflicts with world rule: ", "草稿违反世界规则："),
        (
            "Draft appears to resolve an unresolved foreshadowing item before review.",
            "草稿似乎在审核前解决了尚未回收的伏笔。",
        ),
        (
            "Draft does not preserve the unresolved foreshadowing clue.",
            "草稿未保留尚未回收的伏笔线索。",
        ),
        (
            "Draft states an event without a cause despite scene goal/conflict context.",
            "尽管存在场景目标或冲突上下文，草稿仍陈述了缺少原因的事件。",
        ),
        (
            "Draft uses narrator knowledge that can exceed the limited POV constraint.",
            "草稿使用了可能超出限知 POV 约束的叙述者知识。",
        ),
        ("Draft language snapshot does not match this generation run.", "草稿语言快照与本次生成运行不一致。"),
        ("Secret ID appears in draft text.", "草稿文本中出现了秘密 ID。"),
        ("Item listed in must_include.", "该项列于 must_include。"),
        ("Hard constraint appeared in draft text.", "草稿文本中出现了硬约束。"),
        (
            "Pattern listed in style_constraints.banned_patterns.",
            "该模式列于 style_constraints.banned_patterns。",
        ),
        ("Expected scene timeline from the Context Pack.", "上下文包中预期的场景时间线。"),
        ("Draft places the scene before the expected anchor event.", "草稿将场景置于预期锚点事件之前。"),
        ("Draft uses a different day offset from the same anchor event.", "草稿对同一锚点事件使用了不同的天数偏移。"),
        ("Draft reverses the expected after/before timeline relation.", "草稿颠倒了预期的先后时间关系。"),
        ("Draft reverses the expected before/after timeline relation.", "草稿颠倒了预期的先后时间关系。"),
        ("Expected scene location ID.", "预期的场景位置 ID。"),
        ("Conflicting location ID appears in draft text.", "草稿文本中出现了冲突的位置 ID。"),
        ("Active relationship from the Context Pack.", "上下文包中的有效关系。"),
        ("Draft uses a different relationship label for the same pair.", "草稿对同一对象组合使用了不同的关系标签。"),
        ("Draft relationship strength conflicts with the active relationship strength.", "草稿中的关系强度与有效关系强度冲突。"),
        ("Relevant world rule from the Context Pack.", "上下文包中的相关世界规则。"),
        ("Draft text appears to negate or bypass the rule.", "草稿文本似乎否定或绕过了该规则。"),
        ("Unresolved foreshadowing from the Context Pack.", "上下文包中尚未回收的伏笔。"),
        ("Draft text uses payoff wording near the foreshadowing ID.", "草稿文本在伏笔 ID 附近使用了回收措辞。"),
        ("Unresolved foreshadowing expected by the Context Pack.", "上下文包预期保留的未回收伏笔。"),
        ("Causal-gap marker appears in draft text.", "草稿文本中出现了因果缺口标记。"),
        ("POV style constraint from the Context Pack.", "上下文包中的 POV 文风约束。"),
        ("Limited-POV leak marker appears in draft text.", "草稿文本中出现了限知 POV 泄漏标记。"),
        ("Regenerate the draft using the frozen WorkflowRun language.", "请使用冻结的 WorkflowRun 语言重新生成草稿。"),
        ("Rewrite the moment as an ambiguous clue rather than explicit knowledge.", "将这一刻改写为含混线索，避免直接呈现明确知识。"),
        ("Add the required element without changing canon directly.", "加入必需元素，但不要直接更改正典。"),
        ("Remove or soften this revelation so it remains outside the POV knowledge.", "删除或弱化这次揭示，使其仍处于 POV 知识范围之外。"),
        ("Remove or rewrite the banned pattern while preserving scene facts.", "删除或改写禁用模式，同时保留场景事实。"),
        ("Align the draft's time reference with the Context Pack timeline.", "让草稿的时间指向与上下文包时间线一致。"),
        ("Keep the scene anchored to the Context Pack location or revise the pack after human review.", "保持场景位于上下文包指定的位置，或在人工审核后修订上下文包。"),
        ("Keep relationship changes implicit or route them through candidate fact review.", "保持关系变化为隐含状态，或将其提交候选事实审核。"),
        ("Revise the moment so the world rule still governs the scene.", "修改这一刻，使世界规则仍然约束该场景。"),
        ("Keep the clue unresolved unless a human-approved payoff is intended here.", "除非此处计划使用经人工批准的回收，否则请保持线索未解。"),
        ("Seed the clue in the draft or remove it from the Context Pack through review.", "在草稿中埋入线索，或通过审核将其从上下文包中移除。"),
        ("Tie the event to the scene goal, conflict, or previous scene result.", "将事件与场景目标、冲突或上一场景结果关联起来。"),
        ("Filter the information through what the POV character can observe or infer.", "仅通过 POV 角色能够观察或推断的内容呈现信息。"),
    )
    for source, target in replacements:
        if text == source:
            return target
        if text.startswith(source):
            return f"{target}{text[len(source):]}"
    return text


_RELATIONSHIP_RE = re.compile(
    r"\b(?P<source>[a-z][a-z0-9]*_[a-z0-9_]+)\s+"
    r"(?P<relation>[a-z_]{2,})\s+"
    r"(?P<target>[a-z][a-z0-9]*_[a-z0-9_]+)"
    r"(?:\s+strength=(?P<strength>-?\d+(?:\.\d+)?))?",
    flags=re.IGNORECASE,
)


def _timeline_conflict(expected: str, draft_text: str) -> tuple[str, str] | None:
    expected_text = _normalize(expected)
    draft = _normalize(draft_text)
    expected_day = re.search(
        r"\b(?P<count>\w+|\d+)\s+days?\s+after\s+(?P<anchor>[^.;,!?:]+)",
        expected_text,
    )
    if expected_day:
        expected_count = _number_value(expected_day.group("count"))
        anchor_pattern = _phrase_pattern(expected_day.group("anchor"))
        if anchor_pattern:
            before_match = re.search(rf"\b(?:before|prior to)\s+{anchor_pattern}", draft)
            if before_match:
                return (
                    before_match.group(0),
                    "Draft places the scene before the expected anchor event.",
                )
            for match in re.finditer(
                rf"\b(?P<count>\w+|\d+)\s+days?\s+after\s+{anchor_pattern}",
                draft,
            ):
                found_count = _number_value(match.group("count"))
                if (
                    expected_count is not None
                    and found_count is not None
                    and found_count != expected_count
                ):
                    return (
                        match.group(0),
                        "Draft uses a different day offset from the same anchor event.",
                    )

    after_anchor = _anchor_after_keyword(expected_text, "after")
    if after_anchor:
        anchor_pattern = _phrase_pattern(after_anchor)
        if anchor_pattern:
            match = re.search(rf"\b(?:before|prior to)\s+{anchor_pattern}", draft)
            if match:
                return match.group(0), "Draft reverses the expected after/before timeline relation."

    before_anchor = _anchor_after_keyword(expected_text, "before")
    if before_anchor:
        anchor_pattern = _phrase_pattern(before_anchor)
        if anchor_pattern:
            match = re.search(rf"\bafter\s+{anchor_pattern}", draft)
            if match:
                return match.group(0), "Draft reverses the expected before/after timeline relation."
    return None


def _parse_relationship(value: str) -> dict[str, object] | None:
    match = _RELATIONSHIP_RE.search(value)
    if not match:
        return None
    strength = None
    if match.group("strength") is not None:
        strength = float(match.group("strength"))
    return {
        "raw": match.group(0),
        "source": match.group("source").lower(),
        "relation": match.group("relation").upper(),
        "target": match.group("target").lower(),
        "strength": strength,
    }


def _relationship_conflict_note(
    expected: dict[str, object], found: dict[str, object]
) -> str | None:
    if expected["relation"] != found["relation"]:
        return "Draft uses a different relationship label for the same pair."
    expected_strength = expected.get("strength")
    found_strength = found.get("strength")
    if not isinstance(expected_strength, float) or not isinstance(found_strength, float):
        return None
    opposite_sign = (expected_strength < -0.05 < found_strength) or (
        expected_strength > 0.05 > found_strength
    )
    large_delta = abs(expected_strength - found_strength) >= 0.75
    if opposite_sign or large_delta:
        return "Draft relationship strength conflicts with the active relationship strength."
    return None


def _world_rule_conflict_quote(
    *, rule_ref: str, rule_text: str, lowered_text: str
) -> str | None:
    if rule_ref and rule_ref.lower() in lowered_text:
        index = lowered_text.index(rule_ref.lower())
        window = lowered_text[max(0, index - 80) : index + len(rule_ref) + 120]
        if any(
            marker in window
            for marker in [
                "breaks",
                "does not apply",
                "ignores",
                "no longer applies",
                "overrides",
                "violates",
            ]
        ):
            return window.strip()

    required_phrase = _required_phrase(rule_text)
    if not required_phrase:
        return None
    required_tokens = set(_content_tokens(required_phrase))
    if not required_tokens:
        return None
    for match in re.finditer(r"\bwithout\b.{0,140}", lowered_text):
        window = match.group(0)
        window_tokens = set(_content_tokens(window))
        common = required_tokens.intersection(window_tokens)
        if len(common) >= max(2, len(required_tokens) // 2):
            return window.strip()
    return None


def _premature_payoff_quote(foreshadowing_ref: str, lowered_text: str) -> str | None:
    if not foreshadowing_ref or foreshadowing_ref.lower() not in lowered_text:
        return None
    index = lowered_text.index(foreshadowing_ref.lower())
    window = lowered_text[max(0, index - 80) : index + len(foreshadowing_ref) + 120]
    if any(marker in window for marker in ["paid off", "payoff", "resolved", "revealed"]):
        return window.strip()
    return None


def _split_context_item(item: str) -> tuple[str, str]:
    if ":" not in item:
        return "", item.strip()
    ref, text = item.split(":", 1)
    return ref.strip(), text.strip()


def _required_phrase(rule_text: str) -> str:
    match = re.search(r"\brequires?\s+(?P<required>[^.;]+)", rule_text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group("required").strip()


def _first_marker(text: str, markers: list[str]) -> str | None:
    lowered = text.lower()
    for marker in markers:
        index = lowered.find(marker.lower())
        if index == -1:
            continue
        return text[index : index + len(marker)]
    return None


def _has_content_overlap(expected: str, draft_text: str) -> bool:
    expected_tokens = set(_content_tokens(expected))
    if not expected_tokens:
        return True
    draft_tokens = set(_content_tokens(draft_text))
    common = expected_tokens.intersection(draft_tokens)
    needed = max(2, (len(expected_tokens) + 1) // 2)
    return len(common) >= min(needed, len(expected_tokens))


def _content_tokens(value: str) -> list[str]:
    return [
        _stem_token(token)
        for token in re.findall(r"[a-z0-9_]+", value.lower())
        if token not in _STOP_WORDS and len(token) > 1
    ]


def _stem_token(token: str) -> str:
    if token.endswith("ier") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("ing") and len(token) > 5:
        return token[:-3]
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _number_value(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _NUMBER_WORDS.get(value.lower())


def _anchor_after_keyword(value: str, keyword: str) -> str:
    match = re.search(rf"\b{keyword}\s+(?P<anchor>[^.;,!?:]+)", value)
    return match.group("anchor").strip() if match else ""


def _phrase_pattern(value: str) -> str:
    tokens = re.findall(r"[a-z0-9_]+", value.lower())
    while tokens and tokens[0] in {"a", "an", "the"}:
        tokens.pop(0)
    if not tokens:
        return ""
    return r"(?:a|an|the)?\s*" + r"\s+".join(re.escape(token) for token in tokens)
