"""Build compact scene context packs from canon graph state."""

from __future__ import annotations

import math
import re
from contextlib import nullcontext

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.time import utc_now
from storygraph.models.context import (
    ContextBudget,
    ContextGap,
    ContextPack,
    ContextProvenance,
    KnowledgeBoundary,
    StyleConstraints,
    ApprovedScenePlan,
    PlannedCausalPrecondition,
    PlannedForeshadowingAction,
)
from storygraph.models.graph import GraphNode
from storygraph.models.project import OutputLanguage, localized
from storygraph.services.project_language import resolve_project_output_language
from storygraph.services.project_style import resolve_project_style
from storygraph.services.graph_query import GraphQueryService
from storygraph.services.temporal_state import get_state_assertions, resolve_temporal_state
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.graph_base import GraphStore
from storygraph.stores.style_sample_store import StyleSampleStore


class ContextPackBuilder:
    def __init__(
        self,
        graph_store: GraphStore,
        draft_store: SQLiteDraftStore | None = None,
        style_sample_store: StyleSampleStore | None = None,
        writer_visibility_resolver=None,
    ) -> None:
        self.graph_store = graph_store
        self.draft_store = draft_store
        self.style_sample_store = style_sample_store
        self.writer_visibility_resolver = writer_visibility_resolver

    def build(
        self,
        *,
        project_id: str,
        scene_id: str,
        target_tokens: int | None = None,
        author_instruction_refs: list[str] | None = None,
    ) -> ContextPack:
        guard = getattr(self.graph_store, "persistence_guard", None)
        with guard() if callable(guard) else nullcontext():
            auto_expand_budget = False
            if target_tokens is None:
                project = self.graph_store.get_node(project_id)
                if project.type != "Project":
                    raise ContractError("Context budget requires a canon Project.")
                auto_expand_budget = bool(project.properties.get("require_semantic_review")
                    or project.properties.get("longform_blueprint_id"))
                target_tokens = 8000 if auto_expand_budget else 4000
            if type(target_tokens) is not int or target_tokens < 1:
                raise ContractError("Context target_tokens must be a positive integer or omitted.")
            pack = self._build(project_id=project_id, scene_id=scene_id,
                               target_tokens=target_tokens,
                               auto_expand_budget=auto_expand_budget,
                               author_instruction_refs=author_instruction_refs)
            project = self.graph_store.get_node(project_id)
            pack.writer_visibility_required = bool(project.properties.get("require_semantic_review")
                                                    or project.properties.get("longform_blueprint_id"))
            if self.writer_visibility_resolver is not None:
                pack.writer_visibility = self.writer_visibility_resolver(pack)
                if pack.writer_visibility is not None:
                    pack.writer_visibility_required = True
            return pack

    def _build(
        self,
        *,
        project_id: str,
        scene_id: str,
        target_tokens: int = 4000,
        auto_expand_budget: bool = False,
        author_instruction_refs: list[str] | None = None,
    ) -> ContextPack:
        missing_context: list[ContextGap] = []
        output_language = resolve_project_output_language(self.graph_store, project_id)
        scoped_scene = self.graph_store.get_node(scene_id)
        self._ensure_scene_scope(project_id, scoped_scene)
        self._ensure_scene_reference_scope(project_id, scoped_scene)
        scene_context = self._query_scene_context(
            scene_id,
            output_language,
            missing_context,
        )
        scene = scene_context["scene"]
        props = scene.properties
        self._ensure_scene_scope(project_id, scene)
        graph_query_ids = self._graph_query_plan(scene_id=scene_id, props=props)
        scene_plan = self._approved_scene_plan(
            project_id=project_id, scene=scene, output_language=output_language,
            missing_context=missing_context,
        )

        required_characters = list(
            dict.fromkeys(
                [
                    props.get("pov_character_id"),
                    *props.get("required_characters", []),
                ]
            )
        )
        required_characters = [character_id for character_id in required_characters if character_id]
        self._report_missing_scene_fields(
            props,
            scene_id,
            output_language,
            missing_context,
        )
        self._report_missing_nodes(
            required_characters=required_characters,
            location_id=props.get("location_id"),
            scene_context=scene_context,
            output_language=output_language,
            missing_context=missing_context,
        )
        knowledge = []
        for character_id in required_characters:
            boundary = self._safe_character_knowledge(
                character_id=character_id,
                scene_id=scene_id,
                timeline_position=props.get("timeline_position"),
                output_language=output_language,
                missing_context=missing_context,
            )
            if boundary:
                knowledge.append(boundary)

        active_relationships = [
            self._relationship_text(relation)
            for relation in scene_context.get("active_relationships", [])
            if relation.type not in {"KNOWS_SECRET", "BELIEVES_FALSELY", "SUSPECTS", "HIDES_FROM"}
            or relation.id in {ref for boundary in knowledge for ref in boundary.source_refs}
        ]
        world_rules = [
            f"{node.id}: {node.properties.get('rule', node.properties.get('summary', ''))}"
            for node in scene_context.get("world_rules", [])
        ]
        seed_only = {action.id for action in scene_plan.foreshadowing_actions if action.action == "seed"} if scene_plan else set()
        foreshadowing = []
        for node in scene_context.get("unresolved_foreshadowing", []):
            clue = node.properties.get("clue_text")
            if not isinstance(clue, str) or not clue:
                clue = "" if node.id in seed_only else node.properties.get("hidden_meaning", "")
            foreshadowing.append(f"{node.id}: {clue if isinstance(clue, str) else ''}")

        previous_scene_summary = None
        draft_refs: list[str] = []
        previous_scene_id = props.get("previous_scene_id")
        if previous_scene_id and self.draft_store:
            draft = self.draft_store.latest_for_scene(project_id, previous_scene_id)
            if draft and draft.content_language == output_language:
                previous_scene_summary = draft.summary
                draft_refs.append(draft.id)
            elif draft:
                missing_context.append(
                    ContextGap(
                        kind="draft_language_mismatch",
                        ref=previous_scene_id,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh="上一场景草稿没有可信的当前项目语言快照。",
                            en=(
                                "The previous scene draft does not have a trusted snapshot "
                                "for the current project language."
                            ),
                        ),
                        source=scene_id,
                    )
                )
            else:
                missing_context.append(
                    ContextGap(
                        kind="missing_draft",
                        ref=previous_scene_id,
                        severity="medium",
                        message=localized(
                            output_language,
                            zh="场景引用了上一场景，但没有可用的草稿摘要。",
                            en=(
                                "Scene references a previous scene, but no draft summary "
                                "is available."
                            ),
                        ),
                        source=scene_id,
                    )
                )

        project_style = resolve_project_style(self.graph_store, project_id)
        style_props = {**project_style, **(props.get("style_constraints") or {})}
        style = StyleConstraints(
            pov=style_props.get(
                "pov",
                props.get("narrative_pov")
                or localized(
                    output_language,
                    zh="第三人称有限视角",
                    en="third-person limited",
                ),
            ),
            tense=style_props.get("tense"),
            tone=style_props.get("tone")
            or localized(output_language, zh="克制", en="restrained"),
            sentence_rhythm=style_props.get("sentence_rhythm"),
            diction=style_props.get("diction"),
            dialogue_style=style_props.get("dialogue_style"),
            banned_patterns=style_props.get("banned_patterns", []),
            profile_id=project_style.get("id"),
            profile_sha256=project_style.get("sha256"),
            rubric=style_props.get("rubric", []),
        )
        retrieved_style_samples = list(props.get("retrieved_style_samples", []))
        style_sample_refs = list(props.get("style_sample_refs", []))
        if self.style_sample_store:
            matches = self.style_sample_store.search(
                project_id=project_id,
                language=output_language,
                query=self._style_query(props, style),
                pov=style.pov,
                tone=style.tone,
                dialogue_style=style.dialogue_style,
                tags=props.get("style_tags", []),
                limit=3,
            )
            retrieved_style_samples.extend(
                self._style_sample_text(match.sample) for match in matches
            )
            style_sample_refs.extend(match.sample.id for match in matches)

        entity_ids = set(required_characters)
        if props.get("location_id"):
            entity_ids.add(props["location_id"])
        for boundary in knowledge:
            for field in ("knows", "does_not_know", "falsely_believes", "suspects", "hides"):
                entity_ids.update(getattr(boundary, field))
        planning_text = " ".join(str(props.get(key) or "") for key in
                                 ("title", "summary", "goal", "conflict", "outcome"))
        snapshot = GraphQueryService(self.graph_store)._snapshot()
        for node in snapshot.nodes.values():
            if (node.type != "Item" or node.status != "CANON"
                    or node.properties.get("project_id") != project_id):
                continue
            names = [node.properties.get("name"), *(node.properties.get("aliases") or [])]
            initial = node.properties.get("initial_state") or {}
            named = any(isinstance(name, str) and len(name) >= 2 and name in planning_text
                        for name in names)
            owner_history = get_state_assertions(self.graph_store, project_id=project_id,
                                                 subject_id=node.id, field="owner_id")
            owned = False
            if owner_history or (isinstance(initial, dict) and "owner_id" in initial):
                owner = resolve_temporal_state(
                    self.graph_store, project_id=project_id, subject_id=node.id,
                    scene_id=scene_id, fields=["owner_id"], at_scene_start=True,
                ).states[0]
                owned = owner.status == "resolved" and owner.value in required_characters
            if named or owned:
                entity_ids.add(node.id)
        canon_entities = []
        temporal_states = []
        for entity_id in sorted(entity_ids):
            try:
                entity = self.graph_store.get_node(entity_id)
            except GraphStoreError as exc:
                if exc.category != "not_found":
                    raise
                continue
            if entity.status != "CANON" or entity.properties.get("project_id") != project_id:
                raise ContractError("Context entity does not belong to the requested project.")
            # Structured facts only: no stored prose, source text or arbitrary prompt fields.
            fields = ("name", "aliases", "content", "description", "current_status", "role",
                      "desire", "fear", "arc_stage", "ability", "limitation", "truth_status",
                      "reveal_plan", "revealed_at_scene_id", "rules")
            canon_entities.append({"id": entity.id, "type": entity.type, "properties": {
                key: entity.properties[key] for key in fields if key in entity.properties
            }})
            initial_state = entity.properties.get("initial_state") or {}
            tracked = set(initial_state) if isinstance(initial_state, dict) else set()
            tracked.update(node.properties["field"] for node in get_state_assertions(
                self.graph_store, project_id=project_id, subject_id=entity_id,
            ))
            if tracked:
                projection = resolve_temporal_state(
                    self.graph_store, project_id=project_id, subject_id=entity_id,
                    scene_id=scene_id, fields=sorted(tracked), at_scene_start=True,
                )
                temporal_states.append(projection)
                if not projection.complete:
                    missing_context.append(ContextGap(
                        kind="temporal_state_unresolved", ref=entity_id, severity="critical",
                        message=localized(output_language,
                            zh="场景开始时的已跟踪人物或物品状态不完整，需确认初始状态或时间顺序。",
                            en="Tracked state at scene entry is unresolved; confirm its baseline and chronology."),
                    ))
        pack = ContextPack(
            project_id=project_id,
            output_language=output_language,
            scene_id=scene_id,
            chapter_id=props.get("chapter_id") or "",
            pov_character_id=props.get("pov_character_id") or "",
            location_id=props.get("location_id") or "",
            timeline_position=props.get("timeline_position") or "",
            scene_goal=props.get("goal") or "",
            conflict=props.get("conflict") or "",
            scene_plan=scene_plan,
            required_characters=required_characters,
            canon_entities=canon_entities,
            temporal_states=temporal_states,
            active_relationships=active_relationships,
            knowledge_boundaries=knowledge,
            must_include=props.get("must_include", []),
            must_not_violate=props.get("must_not_violate", []),
            unresolved_foreshadowing=foreshadowing,
            relevant_world_rules=world_rules,
            previous_scene_summary=previous_scene_summary,
            style_constraints=style,
            retrieved_style_samples=retrieved_style_samples,
            missing_context=missing_context,
            provenance=ContextProvenance(
                graph_query_ids=graph_query_ids,
                draft_refs=draft_refs,
                style_sample_refs=style_sample_refs,
                author_instruction_refs=author_instruction_refs or [],
                built_at=utc_now(),
            ),
            budget=ContextBudget(target_tokens=target_tokens),
        )
        if auto_expand_budget:
            # Use the same source snapshot. Only fields already eligible for
            # optional trimming are excluded from the essential-size probe.
            essential = pack.model_copy(update={"retrieved_style_samples": [], "previous_scene_summary": None})
            essential_tokens = self._estimate_tokens(essential)
            if essential_tokens > target_tokens:
                target_tokens = min(16000, math.ceil((essential_tokens+256)/2000)*2000)
                pack = pack.model_copy(update={"budget": pack.budget.model_copy(update={"target_tokens": target_tokens})})
        return self._apply_budget(pack, target_tokens)

    def _approved_scene_plan(self, *, project_id, scene, output_language, missing_context):
        """Approved planning metadata is an intention, never proof of a realized event."""
        graph = GraphQueryService(self.graph_store)._snapshot()
        def gap(kind):
            missing_context.append(ContextGap(kind=kind, ref=scene.id, severity="critical",
                message=localized(output_language,
                    zh="已批准场景规划的关联或字段缺失、越界或超出范围，需作者确认。",
                    en="Approved scene planning fields or links are missing, out of scope or over budget; author confirmation is required."),
                source=scene.id))
        def text(properties, key):
            value = properties.get(key)
            if value is None:
                return None
            if not isinstance(value, str) or len(value) > 4000:
                gap("invalid_scene_plan_field")
                return None
            return value if value.strip() else None
        def scoped(ref, expected):
            node = graph.nodes.get(ref)
            if node is None or node.status != "CANON" or node.type != expected or node.properties.get("project_id") != project_id:
                gap("missing_scene_plan_reference")
                return None
            return node
        outcome, emotional = text(scene.properties, "outcome"), text(scene.properties, "emotional_turn")
        length = scene.properties.get("target_length")
        if length is not None and (isinstance(length, bool) or not isinstance(length, int) or not 1 <= length <= 2000000):
            gap("invalid_scene_plan_field")
            length = None
        incoming = sorted((relation for relation in graph.relationships.values()
            if relation.status == "CANON" and relation.target_id == scene.id
            and relation.type in {"CAUSES", "SEEDED_IN", "PAID_OFF_IN"}
            and relation.properties.get("planning_only") is True), key=lambda relation: relation.id)
        causes, actions = [], []
        cause_count, action_count = 0, 0
        for relation in incoming:
            if relation.type == "CAUSES":
                cause_count += 1
                if cause_count > 30:
                    if cause_count == 31:
                        gap("scene_plan_dependency_limit")
                    continue
            else:
                action_count += 1
                if action_count > 30:
                    if action_count == 31:
                        gap("scene_plan_action_limit")
                    continue
            if relation.properties.get("project_id") != project_id:
                gap("missing_scene_plan_reference")
                continue
            if relation.type == "CAUSES":
                source = scoped(relation.source_id, "Scene")
                if source is None or source.id == scene.id:
                    if source is not None:
                        gap("invalid_scene_plan_dependency")
                    continue
                planned_summary = text(source.properties, "summary")
                planned_outcome = text(source.properties, "outcome")
                if planned_summary is None and planned_outcome is None:
                    gap("missing_scene_plan_field")
                causes.append(PlannedCausalPrecondition(scene_id=source.id, relation_id=relation.id,
                    planned_summary=planned_summary, planned_outcome=planned_outcome))
            else:
                clue = scoped(relation.source_id, "Foreshadowing")
                if clue is None:
                    continue
                action = "seed" if relation.type == "SEEDED_IN" else "payoff"
                clue_text = text(clue.properties, "clue_text")
                payoff = text(clue.properties, "hidden_meaning") if action == "payoff" else None
                if clue_text is None or (action == "payoff" and payoff is None):
                    gap("missing_scene_plan_field")
                seed_ids = []
                if action == "payoff":
                    seed_count = 0
                    for seed in sorted(graph.relationships.values(), key=lambda r: r.id):
                        if (seed.status != "CANON" or seed.type != "SEEDED_IN" or seed.source_id != clue.id
                                or seed.properties.get("planning_only") is not True):
                            continue
                        seed_count += 1
                        if seed_count > 30:
                            gap("scene_plan_dependency_limit")
                            break
                        if seed.properties.get("project_id") != project_id:
                            gap("missing_scene_plan_reference")
                            continue
                        seed_scene = scoped(seed.target_id, "Scene")
                        if seed_scene is not None:
                            seed_ids.append(seed_scene.id)
                    if not seed_ids:
                        gap("missing_scene_plan_seed")
                    if len(seed_ids) > 30:
                        gap("scene_plan_dependency_limit")
                        seed_ids = seed_ids[:30]
                actions.append(PlannedForeshadowingAction(id=clue.id, relation_id=relation.id,
                    action=action, clue_text=clue_text, planned_payoff=payoff,
                    seed_scene_ids=seed_ids, do_not_reveal_payoff=action == "seed"))
        # Local plan IDs retained on Scene properties are not resolved as graph IDs.
        # They can only expose missing declared links; actual inputs come from edges.
        for field, actual in (("causal_dependencies", len(causes)),
                ("foreshadowing_seed_ids", sum(action.action == "seed" for action in actions)),
                ("foreshadowing_payoff_ids", sum(action.action == "payoff" for action in actions))):
            declared = scene.properties.get(field)
            if declared is not None and (not isinstance(declared, list)
                    or any(not isinstance(ref, str) or not ref for ref in declared)
                    or len(set(declared)) != len(declared) or len(declared) > actual):
                gap("missing_scene_plan_relation")
        if outcome is None and emotional is None and length is None and not causes and not actions:
            return None
        # Summary cannot create approval/plan eligibility for a legacy scene.
        # Only an already-present plan receives its exact current-scene summary.
        summary = text(scene.properties, "summary")
        return ApprovedScenePlan(planned_summary=summary, planned_outcome=outcome, emotional_turn=emotional,
            target_length=length, causal_preconditions=causes, foreshadowing_actions=actions)

    @staticmethod
    def _relationship_text(relation) -> str:
        strength = relation.properties.get("strength")
        suffix = f" strength={strength}" if strength is not None else ""
        return f"{relation.source_id} {relation.type} {relation.target_id}{suffix}"

    def _query_scene_context(
        self,
        scene_id: str,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> dict:
        try:
            return self.graph_store.query_scene_context(scene_id)
        except GraphStoreError as exc:
            if exc.category != "not_found":
                raise
            scene = self.graph_store.get_node(scene_id)
            missing_context.append(
                ContextGap(
                    kind="incomplete_graph_context",
                    ref=scene_id,
                    severity="high",
                    message=localized(
                        output_language,
                        zh=f"图谱场景上下文查询不完整：{exc}",
                        en=f"Graph scene-context query was incomplete: {exc}",
                    ),
                    source=scene_id,
                )
            )
            return {
                "scene": scene,
                "characters": [],
                "location": None,
                "active_relationships": [],
                "world_rules": [],
                "unresolved_foreshadowing": [],
            }

    @staticmethod
    def _graph_query_plan(*, scene_id: str, props: dict) -> list[str]:
        required_characters = list(
            dict.fromkeys(
                [
                    props.get("pov_character_id"),
                    *props.get("required_characters", []),
                ]
            )
        )
        required_characters = [character_id for character_id in required_characters if character_id]
        plan = [
            f"context_pack_v1:query_scene_context:{scene_id}",
            f"context_pack_v1:query_world_rules:scene_scope:{scene_id}",
            f"context_pack_v1:query_foreshadowing:unresolved:{scene_id}",
        ]
        location_id = props.get("location_id")
        if location_id:
            plan.append(f"context_pack_v1:get_location_state:{location_id}")
        for character_id in required_characters:
            plan.append(f"context_pack_v1:get_character_state:{character_id}")
            plan.append(
                f"context_pack_v1:get_character_knowledge:{scene_id}:{character_id}"
            )
        return plan

    @staticmethod
    def _ensure_scene_scope(
        project_id: str,
        scene: GraphNode,
    ) -> None:
        if scene.type != "Scene" or scene.properties.get("project_id") != project_id:
            raise ContractError("Scene does not belong to the requested project.")

    def _ensure_scene_reference_scope(self, project_id: str, scene: GraphNode) -> None:
        props = scene.properties
        required_characters = props.get("required_characters", [])
        if not isinstance(required_characters, list):
            raise ContractError("Scene required_characters must be a list.")
        references = [
            (props.get("chapter_id"), "Chapter"),
            (props.get("pov_character_id"), "Character"),
            (props.get("location_id"), "Location"),
            (props.get("previous_scene_id"), "Scene"),
            *((character_id, "Character") for character_id in required_characters),
        ]
        for node_id, expected_type in references:
            if not node_id:
                continue
            try:
                node = self.graph_store.get_node(str(node_id))
            except GraphStoreError as exc:
                if exc.category == "not_found":
                    continue
                raise
            if (
                node.type != expected_type
                or node.properties.get("project_id") != project_id
            ):
                raise ContractError(
                    "Scene reference does not belong to the requested project."
                )

    @staticmethod
    def _report_missing_scene_fields(
        props: dict,
        scene_id: str,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> None:
        for field_name in [
            "chapter_id", "pov_character_id", "location_id", "timeline_position", "goal", "conflict",
        ]:
            if not props.get(field_name):
                required = field_name in {"chapter_id", "pov_character_id", "location_id"}
                missing_context.append(
                    ContextGap(
                        kind="missing_scene_field",
                        ref=field_name,
                        severity="critical" if required else "high",
                        message=localized(
                            output_language,
                            zh=f"场景 {scene_id} 尚未填写规划字段 {field_name}。",
                            en=f"Scene {scene_id} has no value for planning field {field_name}.",
                        ),
                        source=scene_id,
                    )
                )

    @staticmethod
    def _report_missing_nodes(
        *,
        required_characters: list[str],
        location_id: str | None,
        scene_context: dict,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> None:
        found_characters = {node.id for node in scene_context.get("characters", [])}
        for character_id in required_characters:
            if character_id not in found_characters:
                missing_context.append(
                    ContextGap(
                        kind="missing_node",
                        ref=character_id,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh=f"正典中没有找到必需角色 {character_id}。",
                            en=(
                                f"Required character {character_id} was not found in canon."
                            ),
                        ),
                    )
                )
        if location_id and scene_context.get("location") is None:
            missing_context.append(
                ContextGap(
                    kind="missing_node",
                    ref=location_id,
                    severity="critical",
                    message=localized(
                        output_language,
                        zh=f"正典中没有找到必需地点 {location_id}。",
                        en=f"Required location {location_id} was not found in canon.",
                    ),
                )
            )

    def _safe_character_knowledge(
        self,
        *,
        character_id: str,
        scene_id: str,
        timeline_position: str | None,
        output_language: OutputLanguage,
        missing_context: list[ContextGap],
    ) -> KnowledgeBoundary | None:
        try:
            return self.graph_store.get_character_knowledge(
                character_id,
                scene_id=scene_id,
                timeline_position=timeline_position,
                at_scene_start=True,
            )
        except GraphStoreError as exc:
            if exc.category != "not_found":
                raise
            already_reported = any(
                gap.kind == "missing_node" and gap.ref == character_id
                for gap in missing_context
            )
            if not already_reported:
                missing_context.append(
                    ContextGap(
                        kind="missing_node",
                        ref=character_id,
                        severity="critical",
                        message=localized(
                            output_language,
                            zh=f"无法为缺失角色 {character_id} 构建知识边界。",
                            en=(
                                "Cannot build knowledge boundary for missing character "
                                f"{character_id}."
                            ),
                        ),
                        source=scene_id,
                    )
                )
            return None

    @staticmethod
    def _style_query(props: dict, style: StyleConstraints) -> str:
        return " ".join(
            str(value)
            for value in [
                props.get("goal", ""),
                props.get("conflict", ""),
                props.get("emotional_turn", ""),
                style.pov,
                style.tone,
                style.dialogue_style,
                style.diction,
                style.sentence_rhythm,
            ]
            if value
        )

    @staticmethod
    def _style_sample_text(sample) -> str:
        snippet = sample.text.strip()
        if len(snippet) > 1200:
            snippet = snippet[:1197].rstrip() + "..."
        return f"{sample.id}: {snippet}"

    @staticmethod
    def _estimate_tokens(pack: ContextPack) -> int:
        serialized = pack.model_dump_json()
        # Conservative script-aware estimate, not a provider tokenizer. Chinese prose
        # cannot use the English four-characters-per-token heuristic.
        han = len(re.findall(r"[\u3400-\u9fff]", serialized))
        return max(1, han + math.ceil((len(serialized) - han) / 4))

    def _apply_budget(self, pack: ContextPack, target_tokens: int) -> ContextPack:
        working = pack
        dropped_items: list[str] = []
        trim_steps = [
            (
                "P6",
                "retrieved_style_samples",
                localized(pack.output_language, zh="风格样本", en="style samples"),
                lambda current: current.model_copy(update={"retrieved_style_samples": []}),
            ),
            (
                "P5",
                "previous_scene_summary",
                localized(
                    pack.output_language,
                    zh="上一场景摘要",
                    en="previous scene summary",
                ),
                lambda current: current.model_copy(update={"previous_scene_summary": None}),
            ),
        ]

        for priority, field_name, label, trim in trim_steps:
            estimated_tokens = self._estimate_tokens(working)
            if estimated_tokens <= target_tokens:
                break
            value = getattr(working, field_name)
            if not value:
                continue
            before = estimated_tokens
            working = trim(working)
            after = self._estimate_tokens(working)
            dropped_items.append(
                localized(
                    pack.output_language,
                    zh=(
                        f"{priority} 为满足预算已移除{label}；"
                        f"estimated_tokens {before}->{after}"
                    ),
                    en=(
                        f"{priority} dropped {label} to satisfy budget; "
                        f"estimated_tokens {before}->{after}"
                    ),
                )
            )

        final_estimate = self._estimate_tokens(working)
        if final_estimate > target_tokens:
            working = working.model_copy(update={"missing_context": [
                *working.missing_context,
                ContextGap(kind="context_budget_exceeded", ref=pack.scene_id,
                           severity="critical", message=localized(pack.output_language,
                               zh="必要的正典与风格上下文超出预算，需缩小场景范围或提高预算。",
                               en="Required canon and style exceed the context budget; narrow the scene or raise the budget.")),
            ]})
            dropped_items.append(
                localized(
                    pack.output_language,
                    zh=(
                        "受保护的正典与风格上下文仍超出目标 "
                        f"{final_estimate - target_tokens} tokens"
                    ),
                    en=(
                        "Protected canon and style context still exceeds target by "
                        f"{final_estimate - target_tokens} tokens"
                    ),
                )
            )
        final_estimate = self._estimate_tokens(working)
        return working.model_copy(
            update={
                "budget": working.budget.model_copy(
                    update={"estimated_tokens": final_estimate, "dropped_items": dropped_items}
                )
            }
        )
