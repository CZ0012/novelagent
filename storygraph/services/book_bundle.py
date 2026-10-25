"""Explicit reviewed whole-book application, atomic within local graph storage."""

import hashlib
import json
from types import SimpleNamespace

from storygraph.core.errors import GraphStoreError
from storygraph.models.longform import BlueprintRequest, LongformPlan
from storygraph.models.planning_run import BookBundle
from storygraph.models.proposal import ProposalRef
from storygraph.services.canon_snapshot import content_hash
from storygraph.services.longform_planning import (
    _clone, _hash, _local, _project, _snapshot, _specs, graph_plan_id,
    validate_blueprint, validate_expansion, _validate_clue_completion,
)
from storygraph.services.planning_run import PlanningRunService, branch_from_ref, branch_scenes, load_ref
from storygraph.services.project_language import resolve_project_output_language


def _invalid():
    return GraphStoreError("planning_bundle_invalid", "The accepted book manifest, review, source or application evidence does not match.")


def bundle_specs(graph, proposals, run, *, current=True):
    """Validate the complete proposed topology; return only whitelisted deltas."""
    branches = [branch_from_ref(proposals, step.proposal_ref, current=current) for step in run.steps]
    config = BlueprintRequest.model_validate({key: getattr(run.request, key) for key in BlueprintRequest.model_fields})
    blueprint = branches[0].blueprint
    if blueprint is None:
        raise _invalid()
    validate_blueprint(blueprint, config)
    blueprint_id = run.steps[0].proposal_ref.id
    for step, branch in zip(run.steps, branches):
        if (branch.run_id != run.id or branch.project_id != run.project_id or branch.output_language != run.output_language
                or branch.canon_fingerprint != run.canon_fingerprint or branch.step_index != step.index
                or branch.phase != step.phase or branch.previous_refs != [s.proposal_ref for s in run.steps[:step.index]]
                or step.index and branch.blueprint_ref != run.steps[0].proposal_ref):
            raise _invalid()
    seed_plan = LongformPlan(schema="longform_plan_v1", phase="blueprint", project_id=run.project_id,
        output_language=run.output_language, graph_snapshot=run.canon_fingerprint, request=config, blueprint=blueprint)
    nodes, relations, project_updates = _specs(graph, None, SimpleNamespace(id=blueprint_id), seed_plan)
    def relation(kind, source, target, props=None):
        ref = "rel_lp_" + hashlib.sha256(f"{source}:{kind}:{target}".encode()).hexdigest()[:32]
        relations[ref] = (kind, source, target, {"project_id": run.project_id, **(props or {})})
    entities = {entity.id: entity.kind for entity in blueprint.entities}
    def entity_id(local):
        return graph_plan_id(blueprint_id, entities[local].lower(), local)
    previous = None
    all_scene_ids = set()
    for index, branch in enumerate(branches[1:], 1):
        step = run.steps[index]
        from storygraph.models.longform import ExpansionRequest
        request = ExpansionRequest(parent_proposal_id=blueprint_id, parent_version=run.steps[0].proposal_ref.version,
            volume_index=step.volume_index, chapter_start=step.chapter_start, chapter_count=step.chapter_count)
        validate_expansion(branch.expansion, request, blueprint, config)
        _validate_clue_completion(branch.expansion, blueprint, config, branch_scenes(branches[:index]))
        for chapter in branch.expansion.chapters:
            local_chapter = f"v{step.volume_index:02d}_c{chapter.index:03d}"
            chapter_id = graph_plan_id(blueprint_id, "chapter", local_chapter)
            if chapter_id in nodes:
                raise _invalid()
            volume = blueprint.volumes[step.volume_index-1]
            nodes[chapter_id] = ("Chapter", {"project_id": run.project_id, "title": chapter.title,
                "summary": chapter.summary, "purpose": chapter.purpose,
                "chapter_index": (volume.index-1)*config.chapters_per_volume+chapter.index,
                "volume_index": volume.index, "volume_title": volume.title, "target_length": chapter.target_length,
                "longform_blueprint_id": blueprint_id})
            relation("HAS_CHAPTER", run.project_id, chapter_id)
            for number, scene in enumerate(chapter.scenes, 1):
                if scene.id in all_scene_ids:
                    raise _invalid()
                all_scene_ids.add(scene.id)
                scene_id = graph_plan_id(blueprint_id, "scene", scene.id)
                props = {**scene.model_dump(exclude={"id"}), "project_id": run.project_id,
                    "chapter_id": chapter_id, "scene_index": number, "longform_scene_id": scene.id,
                    "longform_blueprint_id": blueprint_id, "pov_character_id": entity_id(scene.pov_character_id),
                    "location_id": entity_id(scene.location_id), "required_characters": [entity_id(ref) for ref in scene.required_characters],
                    "previous_scene_id": previous, "style_profile_id": graph_plan_id(blueprint_id, "style", "profile")}
                nodes[scene_id] = ("Scene", props)
                relation("HAS_SCENE", chapter_id, scene_id)
                if previous:
                    relation("NEXT_SCENE", previous, scene_id)
                for dependency in scene.causal_dependencies:
                    if dependency not in all_scene_ids or dependency == scene.id:
                        raise _invalid()
                    relation("CAUSES", graph_plan_id(blueprint_id, "scene", dependency), scene_id, {"planning_only": True})
                for kind, refs in (("SEEDED_IN", scene.foreshadowing_seed_ids), ("PAID_OFF_IN", scene.foreshadowing_payoff_ids)):
                    for ref in refs:
                        relation(kind, graph_plan_id(blueprint_id, "foreshadowing", ref), scene_id, {"planning_only": True})
                previous = scene_id
    if len(all_scene_ids) != config.volume_count*config.chapters_per_volume*config.scenes_per_chapter:
        raise _invalid()
    if sum(props["target_length"] for kind, props in nodes.values() if kind == "Scene") != config.target_length:
        raise _invalid()
    return nodes, relations, project_updates


def apply_book_bundle(*, graph, proposals, runs, project_id, proposal_id, request, persist_snapshot, before_apply=None):
    local = _local(graph)
    with local.persistence_guard():
        _project(local, project_id)
        proposal = proposals.get(proposal_id)
        if (proposal.project_id != project_id or proposal.artifact_type != "outline_draft" or proposal.body_format != "structured_json"
                or proposal.status != "accepted" or proposal.review_decision.status != "accepted"
                or {(r.kind, r.ref) for r in proposal.target_refs} != {("project", project_id)}):
            raise _invalid()
        bundle = BookBundle.model_validate_json(proposal.body)
        original = BookBundle.model_validate_json(proposals.get(proposal_id, version=1).body)
        run = runs.get(bundle.run_id)
        if (bundle != original or run.project_id != project_id or bundle.project_id != project_id
                or proposal.content_language != bundle.output_language or bundle.output_language != run.output_language
                or bundle.canon_fingerprint != run.canon_fingerprint or run.bundle_proposal_id != proposal.id
                or bundle.blueprint_ref != run.steps[0].proposal_ref
                or bundle.expansion_refs != [s.proposal_ref for s in run.steps[1:]]
                or bundle.final_review_id != run.final_review_id or any(s.status != "passed" for s in run.steps)):
            raise _invalid()
        # Hash the persisted manifest, not future model defaults.
        source_ref = f"proposal:{proposal.id}:longform-book:{_hash(json.loads(proposal.body))}"
        marker_id = "evt_book_" + hashlib.sha256(source_ref.encode()).hexdigest()[:32]
        events = [e for e in local.event_log.list() if e.source_ref == source_ref]
        markers = [e for e in events if e.event_id == marker_id]
        completed = bool(markers)
        specs, rels, updates = bundle_specs(local, proposals, run, current=not completed)
        marker_props = {**updates, "longform_book_manifest": content_hash(proposal.body),
                        "longform_book_object_count": len(specs)+len(rels)}
        if completed:
            marker = markers[0]
            if len(markers) != 1 or marker.target != project_id or marker.operation != "update_node" or marker.payload != marker_props or not marker.reviewer or not marker.rationale or len(events) != len(specs)+len(rels)+1:
                raise _invalid()
            expected = {**{ref: ("create_node", (kind, props)) for ref, (kind, props) in specs.items()},
                        **{ref: ("create_relation", value) for ref, value in rels.items()}}
            seen = set()
            for event in events:
                if event.event_id == marker_id:
                    continue
                if event.target in seen or event.target not in expected or not event.reviewer or not event.rationale:
                    raise _invalid()
                seen.add(event.target)
                operation, value = expected[event.target]
                if event.operation != operation or event.payload.get("event_id") != event.event_id or event.payload.get("source_ref") != source_ref or event.payload.get("id") != event.target or event.payload.get("status") != "CANON":
                    raise _invalid()
                if operation == "create_node":
                    node = local.get_node(event.target)
                    if (node.type, event.payload.get("properties")) != value or node.properties.get("project_id") != project_id or event.payload.get("type") != value[0]:
                        raise _invalid()
                else:
                    relation = local.get_relationship(event.target)
                    if (relation.type, relation.source_id, relation.target_id, event.payload.get("properties")) != value or event.payload.get("type") != value[0] or event.payload.get("source_id") != value[1] or event.payload.get("target_id") != value[2] or relation.properties.get("project_id") != project_id:
                        raise _invalid()
            if seen != set(expected):
                raise _invalid()
        else:
            if events or proposal.derived_refs or run.status != "awaiting_review":
                raise _invalid()
            if run.seed_blueprint_ref is not None:
                load_ref(proposals, run.seed_blueprint_ref)
            if proposal.version != request.expected_version or resolve_project_output_language(local, project_id) != run.output_language or _snapshot(local, project_id).fingerprint != run.canon_fingerprint:
                raise GraphStoreError("planning_bundle_stale", "The book plan or canon changed; explicit reconciliation is required.")
            audit = PlanningRunService(graph=local, proposals=proposals, runs=runs, provider_factory=lambda _: None)
            for review_id in [s.review_id for s in run.steps]+[run.final_review_id]:
                result = audit.review(project_id, run.id, review_id)
                if result["report"]["status"] != "pass" or not result["current"]:
                    raise _invalid()
            if any(ref in local.nodes or ref in local.relationships for ref in [*specs, *rels]):
                raise _invalid()
            names = {(n.type, n.properties.get("name")) for n in local.nodes.values() if n.status == "CANON" and n.properties.get("project_id") == project_id and n.properties.get("name")}
            if any((kind, props.get("name")) in names for kind, props in specs.values() if props.get("name")):
                raise _invalid()
            indices = {p["chapter_index"] for kind, p in specs.values() if kind == "Chapter"}
            if any(n.type == "Chapter" and n.properties.get("project_id") == project_id and n.properties.get("chapter_index") in indices for n in local.nodes.values()):
                raise _invalid()
            if before_apply:
                before_apply()
            staged = _clone(local)
            provenance = {"source_ref": source_ref, "reviewer": request.reviewer, "rationale": request.rationale}
            for ref, (kind, props) in specs.items():
                staged.seed_canon_node(node_id=ref, node_type=kind, properties=props, **provenance)
            for ref, (kind, source, target, props) in rels.items():
                staged.seed_canon_relation(relation_id=ref, relation_type=kind, source_id=source, target_id=target, properties=props, **provenance)
            staged.update_node(project_id, marker_props, event_id=marker_id, **provenance)
            persist_snapshot(staged)
            local.nodes, local.relationships, local.event_log = staged.nodes, staged.relationships, staged.event_log
            events = [e for e in local.event_log.list() if e.source_ref == source_ref]
        refs = [ProposalRef(kind="longform_book_application", ref=proposal.id),
                *[ProposalRef(kind="graph_node", ref=ref) for ref in sorted(specs)],
                *[ProposalRef(kind="graph_relation", ref=ref) for ref in sorted(rels)],
                *[ProposalRef(kind="canon_event", ref=e.event_id) for e in events]]
        if {(r.kind, r.ref) for r in proposal.derived_refs} - {(r.kind, r.ref) for r in refs}:
            raise _invalid()
        proposal = proposals.record_derived_refs(proposal.id, derived_refs=refs, actor=request.reviewer,
            content_language=proposal.content_language, expected_version=proposal.version)
        current = runs.get(run.id)
        if current.status != "completed":
            runs.update(current.model_copy(update={"status": "completed"}), current.version)
        return {"proposal": proposal.model_dump(), "nodes": [local.get_node(ref).model_dump() for ref in sorted(specs)],
                "relationships": [local.get_relationship(ref).model_dump() for ref in sorted(rels)], "already_applied": completed}
