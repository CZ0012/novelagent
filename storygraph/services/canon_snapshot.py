"""Immutable, bounded project canon evidence; no Draft/Source or graph writes."""

from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import re

from storygraph.core.errors import ContractError
from storygraph.models.generation_review import CanonFact, CanonSnapshot
from storygraph.services.graph_query import GraphQueryService


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _longform_scene_metadata(scene, project):
    """Recognize applied-plan provenance, never waive arbitrary suffix-ID fields."""
    blueprint_id = scene.properties.get("longform_blueprint_id")
    local_id = scene.properties.get("longform_scene_id")
    if (not isinstance(blueprint_id, str) or not 0 < len(blueprint_id) <= 200
            or project.properties.get("longform_blueprint_id") != blueprint_id
            or not isinstance(local_id, str)
            or re.fullmatch(r"v\d{2}_c\d{3}_s\d{2}", local_id) is None):
        return False
    expected = f"scene_lp_{hashlib.sha256(blueprint_id.encode()).hexdigest()[:16]}_{local_id}"
    return scene.id == expected


def build_canon_snapshot(
    graph, *, project_id: str, scene_id: str | None = None,
    max_facts: int = 256, max_chars: int = 60000, target_text: str = "",
    purpose: str = "scene",
) -> CanonSnapshot:
    """Fingerprint *all* scoped canon; prioritize scene evidence within prompt limits.

    Exceeding a bound always marks incomplete coverage, never implies global clearance.
    In-memory/JSON stores are copied under their mutation guard. Other backends must
    provide the same read snapshot supported by GraphQueryService.
    """
    if max_facts < 1 or max_chars < 1:
        raise ContractError("Canon evidence bounds must be positive.")
    if purpose not in {"scene", "plan"} or (purpose == "plan" and scene_id is not None):
        raise ContractError("Canon evidence purpose and scene scope are incompatible.")
    guard = getattr(graph, "persistence_guard", None)
    with guard() if callable(guard) else nullcontext():
        snapshot = GraphQueryService(graph)._snapshot()
        project = snapshot.nodes.get(project_id)
        if project is None or project.type != "Project" or project.status != "CANON":
            raise ContractError("Review project is unavailable.")
        nodes = {
            n.id: n.model_copy(deep=True) for n in snapshot.nodes.values()
            if n.status == "CANON" and (
                n.id == project_id if n.type == "Project"
                else n.properties.get("project_id") == project_id
            )
        }
        project = nodes[project_id]
        if scene_id is not None:
            scene = nodes.get(scene_id)
            if scene is None or scene.type != "Scene":
                raise ContractError("Review scene is outside the project.")
        missing: list[str] = []
        relations = []
        invalid_relations = []
        for r in snapshot.relationships.values():
            if r.status != "CANON" or r.properties.get("project_id") != project_id:
                continue
            if r.source_id not in nodes or r.target_id not in nodes:
                missing.append("invalid_relation_endpoints")
                invalid_relations.append({
                    "id": r.id, "type": r.type, "status": r.status,
                    "source_id": r.source_id, "target_id": r.target_id,
                    "properties": r.properties,
                })
                continue
            relations.append(r.model_copy(deep=True))

    records = []
    for node in nodes.values():
        records.append(CanonFact(id=node.id, kind="node", text=canonical_json({
            "id": node.id, "type": node.type, "status": node.status,
            "properties": node.properties,
        })))
    for relation in relations:
        records.append(CanonFact(id=relation.id, kind="relation", text=canonical_json({
            "id": relation.id, "type": relation.type, "status": relation.status,
            "source_id": relation.source_id, "target_id": relation.target_id,
            "properties": relation.properties,
        })))
    canonical = sorted(records, key=lambda fact: (fact.kind, fact.id))
    # Corrupt scoped edges affect freshness without exposing foreign endpoint content.
    fingerprint = content_hash(canonical_json({
        "project_id": project_id, "facts": [f.model_dump() for f in canonical],
        "missing_context": sorted(set(missing)),
        "invalid_relations": sorted(invalid_relations, key=lambda item: item["id"]),
    }))
    relevant = {project_id}
    relation_ids = set()
    if purpose == "plan":
        # Proposed-world internal review needs story canon, not the entire expanded grid.
        relevant.update(n.id for n in nodes.values() if n.type not in {"Scene", "Chapter"})
        narrative = [n for n in nodes.values() if n.type in {"Scene", "Chapter"} and any(
            isinstance(n.properties.get(key), str) and n.properties[key].strip()
            for key in ("summary", "outcome", "purpose")
        )]
        def narrative_order(node):
            chapter = nodes.get(node.properties.get("chapter_id"))
            props = {**(chapter.properties if chapter else {}), **node.properties}
            return tuple(value if isinstance(value, int) else 0 for value in (
                props.get("volume_index"), props.get("chapter_index"), props.get("scene_index"),
            )) + (node.id,)
        relevant.update(n.id for n in sorted(narrative, key=narrative_order)[-12:])
        if target_text:
            relevant.update(n.id for n in narrative if n.id in target_text or any(
                isinstance(n.properties.get(key), str) and len(n.properties[key]) >= 2
                and n.properties[key] in target_text for key in ("title", "name")
            ))
        # Existing relationship boundaries need their scene metadata for interpretation.
        for relation in relations:
            if relation.source_id in relevant and relation.target_id in relevant:
                for key in ("valid_from_scene", "valid_until_scene"):
                    boundary = relation.properties.get(key)
                    if isinstance(boundary, str) and boundary in nodes:
                        relevant.add(boundary)
        relation_ids.update(r.id for r in relations if r.type not in {
            "HAS_CHAPTER", "HAS_SCENE", "NEXT_SCENE",
        } and r.source_id in relevant and r.target_id in relevant)
        records_for_prompt = [f for f in records
                              if f.id in (relevant if f.kind == "node" else relation_ids)]
        # A correction preserves its audit predecessor, but that superseded
        # assertion is not an active story fact for a new plan.
        from storygraph.services.temporal_state import get_state_assertions
        from storygraph.stores.memory_graph import InMemoryGraphStore

        frozen = InMemoryGraphStore()
        frozen.nodes = nodes
        frozen.relationships = {relation.id: relation for relation in relations}
        assertion_ids = {n.id for n in nodes.values()
                         if n.properties.get("event_kind") == "temporal_state_assertion_v1"}
        active_ids = set()
        for subject_id in {nodes[ref].properties.get("subject_id") for ref in assertion_ids}:
            try:
                active_ids.update(node.id for node in get_state_assertions(
                    frozen, project_id=project_id, subject_id=subject_id, active_only=True,
                ))
            except (ContractError, ValueError, TypeError):
                missing.append("temporal_state_unresolved")
            except Exception:
                # Invalid canonical chains are unavailable evidence, not an
                # invitation to cite superseded or foreign state.
                missing.append("temporal_state_unresolved")
        records_for_prompt = [fact for fact in records_for_prompt
                              if fact.id not in assertion_ids or fact.id in active_ids]
    elif scene_id:
        relevant.add(scene_id)
        longform_metadata = _longform_scene_metadata(nodes[scene_id], project)
        plan_metadata_fields = {"longform_blueprint_id", "longform_scene_id",
                                "causal_dependencies", "foreshadowing_seed_ids", "foreshadowing_payoff_ids"}
        for key, value in nodes[scene_id].properties.items():
            if longform_metadata and key in plan_metadata_fields:
                # Proposal provenance/local plan IDs stay unchanged in storage.
                # Actual planning semantics and scope come from reviewed edges below.
                continue
            if isinstance(value, str) and value in nodes:
                relevant.add(value)
                expected_type = {"chapter_id": "Chapter", "pov_character_id": "Character",
                                 "location_id": "Location", "previous_scene_id": "Scene",
                                 "style_profile_id": "StyleProfile"}.get(key)
                if expected_type and nodes[value].type != expected_type:
                    missing.append("invalid_scene_reference_type")
            elif isinstance(value, list):
                relevant.update(v for v in value if isinstance(v, str) and v in nodes)
                if key.endswith("_ids") or key == "required_characters":
                    if any(not isinstance(v, str) or v not in nodes for v in value):
                        missing.append("missing_scene_reference")
                    if key == "required_characters" and any(
                        isinstance(v, str) and v in nodes and nodes[v].type != "Character"
                        for v in value
                    ):
                        missing.append("invalid_scene_reference_type")
            elif key.endswith("_id") and value and isinstance(value, str):
                missing.append("missing_scene_reference")
        # Prose can mention an established entity that is absent from scene metadata.
        if target_text:
            for node in nodes.values():
                names = [node.properties.get(k) for k in ("name", "title")]
                aliases = node.properties.get("aliases", [])
                if isinstance(aliases, list):
                    names.extend(aliases)
                if any(isinstance(name, str) and len(name) >= 2 and name in target_text
                       for name in names):
                    relevant.add(node.id)
        # Freeze each frontier: hierarchy never floods the entire novel into a scene.
        hierarchy = {"HAS_CHAPTER", "HAS_SCENE", "PART_OF"}
        frontier = relevant - {project_id}
        for _ in range(2):
            next_frontier = set()
            for relation in relations:
                endpoints = {relation.source_id, relation.target_id}
                if relation.type in hierarchy:
                    # Include the exact scene's parent only, never its siblings.
                    if scene_id not in endpoints:
                        continue
                elif not endpoints.intersection(frontier):
                    continue
                relation_ids.add(relation.id)
                next_frontier.update(endpoints - relevant - {project_id})
            relevant.update(next_frontier)
            frontier = {ref for ref in next_frontier
                        if nodes[ref].type not in {"Scene", "Chapter", "Project"}}
        relevant.update(n.id for n in nodes.values()
                        if n.type in {"WorldRule", "Secret", "StyleProfile"})
        for node in nodes.values():
            if node.type == "Foreshadowing" and any(
                isinstance(value, str) and value in relevant
                for value in node.properties.values()
            ):
                relevant.add(node.id)
        # Include long-range seed/payoff metadata that points to the scene or its actors.
        for relation in relations:
            endpoints = {relation.source_id, relation.target_id}
            if relation.type in {"SEEDED_IN", "PAID_OFF_IN", "POINTS_TO"} and (
                endpoints.intersection(relevant)
                and any(nodes[ref].type == "Foreshadowing" for ref in endpoints)
            ):
                relevant.update(endpoints)
                relation_ids.add(relation.id)
        # Preserve all relationships between selected entities, including temporal facts.
        relation_ids.update(r.id for r in relations
                            if r.type not in hierarchy
                            and r.source_id in relevant and r.target_id in relevant)
        records_for_prompt = [f for f in records
                              if f.id in (relevant if f.kind == "node" else relation_ids)]
    else:
        records_for_prompt = records
    if scene_id:
        # Use a frozen graph for projection so a concurrent commit cannot mix an
        # old fingerprint with a newer state value. Future assertion text is not
        # needed to write the present scene.
        from storygraph.services.temporal_state import get_state_assertions, resolve_temporal_state
        from storygraph.stores.memory_graph import InMemoryGraphStore

        frozen = InMemoryGraphStore()
        frozen.nodes = nodes
        frozen.relationships = {relation.id: relation for relation in relations}
        if purpose == "scene" and _longform_scene_metadata(nodes[scene_id], project):
            from storygraph.services.context_pack_builder import ContextPackBuilder

            for key in ("chapter_id", "pov_character_id", "location_id", "style_profile_id"):
                ref = nodes[scene_id].properties.get(key)
                if not isinstance(ref, str) or ref not in nodes:
                    missing.append("missing_scene_reference")
            required = nodes[scene_id].properties.get("required_characters")
            if not isinstance(required, list) or not required:
                missing.append("missing_scene_reference")
            gaps = []
            ContextPackBuilder(frozen)._approved_scene_plan(
                project_id=project_id, scene=nodes[scene_id],
                output_language=project.properties.get("language", "zh-CN"), missing_context=gaps)
            missing.extend(gap.kind for gap in gaps)
            blueprint_id = nodes[scene_id].properties["longform_blueprint_id"]
            prefix = hashlib.sha256(blueprint_id.encode()).hexdigest()[:16]
            for field, kind, edge in (("causal_dependencies", "scene", "CAUSES"),
                    ("foreshadowing_seed_ids", "foreshadowing", "SEEDED_IN"),
                    ("foreshadowing_payoff_ids", "foreshadowing", "PAID_OFF_IN")):
                declared = nodes[scene_id].properties.get(field)
                if isinstance(declared, list):
                    actual = {r.source_id for r in relations if r.target_id == scene_id
                              and r.type == edge and r.properties.get("planning_only") is True}
                    expected = {f"{kind}_lp_{prefix}_{ref}" for ref in declared if isinstance(ref, str)}
                    if not expected.issubset(actual):
                        missing.append("missing_scene_plan_relation")
            previous = nodes[scene_id].properties.get("previous_scene_id")
            if any(r.type == "NEXT_SCENE" and r.target_id == scene_id
                   and r.source_id != previous for r in relations):
                missing.append("missing_scene_reference")
        projections, used_assertions = {}, set()
        entry_knowledge = {
            subject_id: frozen.get_character_knowledge(subject_id, scene_id=scene_id,
                timeline_position=nodes[scene_id].properties.get("timeline_position"), at_scene_start=True)
            for subject_id in sorted(relevant) if nodes[subject_id].type == "Character"
        }
        for subject_id in sorted(relevant):
            subject = nodes[subject_id]
            if subject.type not in {"Character", "Item"}:
                continue
            initial = subject.properties.get("initial_state") or {}
            tracked = set(initial) if isinstance(initial, dict) else set()
            tracked.update(node.properties["field"] for node in get_state_assertions(
                frozen, project_id=project_id, subject_id=subject_id,
            ))
            if not tracked:
                continue
            projection = resolve_temporal_state(
                frozen, project_id=project_id, subject_id=subject_id,
                scene_id=scene_id, fields=sorted(tracked), at_scene_start=True,
            )
            projections[subject_id] = projection
            for value in projection.states:
                if value.status == "resolved":
                    used_assertions.update(value.assertion_refs)
            if not projection.complete:
                missing.append("temporal_state_unresolved")
        selected_ids = {fact.id for fact in records_for_prompt} | used_assertions
        records_for_prompt = []
        for fact in records:
            if fact.id not in selected_ids:
                continue
            node = nodes.get(fact.id) if fact.kind == "node" else None
            if fact.kind == "relation":
                relation = frozen.relationships[fact.id]
                if relation.type in {"KNOWS_SECRET", "BELIEVES_FALSELY", "SUSPECTS", "HIDES_FROM"}:
                    boundary = entry_knowledge.get(relation.source_id)
                    if boundary is not None and relation.id not in boundary.source_refs:
                        continue
            if (node and node.properties.get("event_kind") == "temporal_state_assertion_v1"
                    and fact.id not in used_assertions):
                continue
            if fact.id in projections:
                payload = json.loads(fact.text)
                payload["state_at_scene_entry"] = projections[fact.id].model_dump(mode="json")
                fact = fact.model_copy(update={"text": canonical_json(payload)})
            if fact.id in entry_knowledge:
                payload = json.loads(fact.text)
                payload["knowledge_at_scene_entry"] = {
                    "scene_id": scene_id, "at_scene_start": True,
                    **entry_knowledge[fact.id].model_dump(mode="json"),
                }
                fact = fact.model_copy(update={"text": canonical_json(payload)})
            records_for_prompt.append(fact)
    def priority(fact):
        if fact.id in relevant:
            return (0, fact.kind, fact.id)
        if fact.kind == "node" and nodes[fact.id].type in {
            "WorldRule", "Secret", "Foreshadowing", "StyleProfile",
        }:
            return (1, fact.kind, fact.id)
        if fact.kind == "relation":
            return (2, fact.kind, fact.id)
        return (3, fact.kind, fact.id)
    selected: list[CanonFact] = []
    used = 0
    for fact in sorted(records_for_prompt, key=priority):
        size = len(canonical_json(fact.model_dump()))
        if len(selected) >= max_facts or used + size > max_chars:
            missing.append("canon_evidence_truncated")
            continue
        selected.append(fact)
        used += size
    # Do not cite a relation whose endpoints were omitted from the actual prompt.
    node_ids = {f.id for f in selected if f.kind == "node"}
    relation_map = {r.id: r for r in relations}
    selected = [f for f in selected if f.kind == "node" or (
        relation_map[f.id].source_id in node_ids and relation_map[f.id].target_id in node_ids
    )]
    if len(selected) < len(records_for_prompt):
        missing.append("canon_evidence_truncated")
    if purpose != "plan" and not any(n.type not in {"Project", "Chapter", "Scene"} for n in nodes.values()):
        missing.append("insufficient_story_canon")
    if len({f.id for f in records}) != len(records):
        missing.append("ambiguous_canon_ids")
    return CanonSnapshot(
        project_id=project_id, scene_id=scene_id, facts=tuple(selected),
        scope="plan" if purpose == "plan" else ("scene" if scene_id else "project"),
        fingerprint=fingerprint, complete=not missing,
        missing_context=tuple(sorted(set(missing))), total_facts=len(records),
        omitted_unrelated_facts=len(records) - len(records_for_prompt),
    )
