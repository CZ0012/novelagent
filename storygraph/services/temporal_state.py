"""Append-only state memory and conservative scene-time projection."""

from __future__ import annotations

from contextlib import nullcontext

from pydantic import ValidationError

from storygraph.core.errors import GraphStoreError
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.graph import GraphNode
from storygraph.models.candidate import CandidateFact, ProposedGraphPatch, SourceSpan
from storygraph.models.common import EvidenceItem
from storygraph.models.temporal_state import (
    STATE_FIELDS, STATE_SUBJECT_TYPES, TemporalStatePatch, TemporalStateProjection, TemporalStateValue,
    TemporalStateCorrectionRequest,
)
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.graph_query import GraphQueryService


EVENT_KIND = "temporal_state_assertion_v1"


def _error(message="Temporal state input is invalid or stale."):
    return GraphStoreError("conflict_detected", message)


def _scoped_node(graph, project_id, node_id, expected=None):
    node = graph.get_node(node_id)
    if ((node.id != project_id if node.type == "Project" else
         node.properties.get("project_id") != project_id) or (expected and node.type not in expected)):
        raise _error()
    return node


def get_state_assertions(graph, *, project_id, subject_id, field=None, active_only=False):
    guard = getattr(graph, "persistence_guard", None)
    with guard() if callable(guard) else nullcontext():
        snapshot = GraphQueryService(graph)._snapshot()
        nodes = tuple(sorted((node.model_copy(deep=True) for node in snapshot.nodes.values()
            if node.type == "Event" and node.status == "CANON"
            and node.properties.get("event_kind") == EVENT_KIND
            and node.properties.get("project_id") == project_id
            and node.properties.get("subject_id") == subject_id
            and (field is None or node.properties.get("field") == field)), key=lambda n: n.id))
        if not active_only:
            return nodes
        fields = {node.properties.get("field") for node in nodes}
        if any(key not in STATE_FIELDS for key in fields):
            raise _error("Invalid temporal state assertion field.")
        return tuple(sorted((node for key in sorted(fields) for node in active_state_assertions(
            graph, project_id=project_id, subject_id=subject_id, field=key)), key=lambda node: node.id))


def temporal_slot_fingerprint(graph, *, project_id, subject_id, field):
    if field not in STATE_FIELDS:
        raise _error()
    subject = _scoped_node(graph, project_id, subject_id, STATE_SUBJECT_TYPES[field])
    initial = subject.properties.get("initial_state", {})
    if not isinstance(initial, dict):
        raise _error()
    return content_hash(canonical_json({
        "project_id": project_id, "subject_id": subject_id, "field": field,
        "baseline_present": field in initial, "baseline": initial.get(field),
        "assertions": [{"id": n.id, "properties": n.properties}
                       for n in get_state_assertions(graph, project_id=project_id,
                                                    subject_id=subject_id, field=field)],
    }))


def _assertion_properties(candidate, patch):
    properties = {
        "event_kind": EVENT_KIND, "project_id": candidate.project_id,
        "subject_id": candidate.subject_id, "field": patch.field, "value": patch.value,
        "valid_from_scene": patch.valid_from_scene, "candidate_fact_id": candidate.id,
        "source_scene_id": candidate.source_scene_id, "source_draft_id": candidate.source_draft_id,
        "source_text_sha256": patch.source_text_sha256,
        "source_span": candidate.source_span.model_dump(),
        "expected_slot_fingerprint": patch.expected_slot_fingerprint,
    }
    # Omitted defaults preserve pre-correction assertion/receipt content exactly.
    if patch.action == "correct":
        properties.update(action="correct", supersedes_assertion_id=patch.supersedes_assertion_id)
    return properties


def active_state_assertions(graph, *, project_id, subject_id, field):
    """Return active revision leaves; correction links never establish story time."""
    all_nodes = get_state_assertions(graph, project_id=project_id, subject_id=subject_id, field=field)
    by_id = {node.id: node for node in all_nodes}
    superseded, children = set(), {}
    for node in all_nodes:
        action, parent = node.properties.get("action", "assert"), node.properties.get("supersedes_assertion_id")
        if action == "assert":
            if parent is not None:
                raise _error("Invalid temporal correction chain.")
            continue
        if action != "correct" or not isinstance(parent, str) or parent not in by_id:
            raise _error("Invalid temporal correction chain.")
        prior = by_id[parent]
        if (prior.properties.get("valid_from_scene") != node.properties.get("valid_from_scene")
                or parent == node.id or parent in children):
            raise _error("Invalid temporal correction chain.")
        children[parent] = node.id
        superseded.add(parent)
    done = set()
    for start in by_id:
        path, current = set(), start
        while current not in done:
            if current in path:
                raise _error("Invalid temporal correction chain.")
            path.add(current)
            parent = by_id[current].properties.get("supersedes_assertion_id")
            if parent is None:
                break
            current = parent
        done.update(path)
    return tuple(node for node in all_nodes if node.id not in superseded)


def validate_temporal_candidate(graph, candidate):
    """Validate without mutation; caller repeats under the graph mutation guard."""
    from storygraph.stores.memory_graph import InMemoryGraphStore
    if not isinstance(graph, InMemoryGraphStore):
        raise GraphStoreError("backend_unavailable", "Temporal state commits currently require local JSON/memory Graph Store.")
    try:
        patch = TemporalStatePatch.model_validate(candidate.proposed_graph_patch.properties)
    except (ValidationError, ValueError, TypeError):
        raise _error() from None
    if candidate.proposed_graph_patch.target != candidate.subject_id or (
        patch.valid_from_scene != candidate.source_scene_id
    ):
        raise _error()
    _scoped_node(graph, candidate.project_id, candidate.project_id, {"Project"})
    _scoped_node(graph, candidate.project_id, candidate.source_scene_id, {"Scene"})
    _scoped_node(graph, candidate.project_id, candidate.subject_id, STATE_SUBJECT_TYPES[patch.field])
    if patch.field in {"location_id", "owner_id"} and patch.value is not None:
        _scoped_node(graph, candidate.project_id, patch.value,
                     {"Location"} if patch.field == "location_id" else {"Character", "Organization"})
    if candidate.object_id is not None and candidate.object_id != patch.value:
        raise _error()
    snapshot = GraphQueryService(graph)._snapshot()
    existing = snapshot.nodes.get("state_" + candidate.id)
    if existing is not None:
        if (existing.type != "Event" or existing.status != "CANON"
                or existing.properties != _assertion_properties(candidate, patch)
                or existing.source_ref != candidate.source_draft_id):
            raise _error("Temporal assertion identity conflict.")
        return patch
    if patch.expected_slot_fingerprint != temporal_slot_fingerprint(
        graph, project_id=candidate.project_id, subject_id=candidate.subject_id, field=patch.field,
    ):
        raise _error("Temporal state slot changed; review the current history.")
    active = active_state_assertions(graph, project_id=candidate.project_id,
                                    subject_id=candidate.subject_id, field=patch.field)
    if patch.action == "correct":
        previous = next((node for node in active if node.id == patch.supersedes_assertion_id), None)
        if previous is None or previous.properties.get("valid_from_scene") != patch.valid_from_scene:
            raise _error("Correction target is no longer active in this scene and slot.")
        if previous.properties.get("value") == patch.value:
            raise _error("Correction must change the asserted value.")
    elif any(n.properties.get("valid_from_scene") == patch.valid_from_scene for n in active):
        raise _error("A reviewed state already occupies this scene and field.")
    return patch


def commit_temporal_candidate(graph, candidate, *, reviewer, rationale):
    """Called only by Graph Store's accepted-candidate commit under its own guard."""
    if candidate.review.status not in {"accepted", "edited"} or candidate.status != "ACCEPTED_FOR_CANON":
        raise GraphStoreError("invalid_status_transition", "Temporal candidate requires explicit human acceptance")
    if not reviewer.strip() or not rationale.strip():
        raise GraphStoreError("missing_provenance", "Temporal state commit requires reviewer and rationale")
    patch = validate_temporal_candidate(graph, candidate)
    node_id, event_id = "state_" + candidate.id, "evt_state_" + candidate.id
    if node_id in graph.nodes:
        try:
            event = graph.event_log.get(event_id)
        except KeyError:
            raise _error("Temporal assertion has incomplete commit evidence.") from None
        if event.target != node_id or event.payload.get("assertion") != graph.nodes[node_id].model_dump():
            raise _error("Temporal assertion commit evidence differs.")
        return event
    now = utc_now()
    node = GraphNode(
        id=node_id, type="Event", status="CANON", created_at=now, updated_at=now,
        source_ref=candidate.source_draft_id, event_id=event_id, reviewer=reviewer,
        reviewed_at=now, rationale=rationale, properties=_assertion_properties(candidate, patch),
    )
    from storygraph.stores.memory_graph import InMemoryGraphStore
    from storygraph.stores.event_log import InMemoryEventLog
    staged_log = InMemoryEventLog()
    staged_log._events = list(graph.event_log.list())
    staged = InMemoryGraphStore(staged_log)
    staged.nodes, staged.relationships = dict(graph.nodes), dict(graph.relationships)
    staged.create_node(node, allow_canon=True)
    event = staged._record_event(operation="commit_candidate_fact", target=node_id,
        source_ref=candidate.source_draft_id, reviewer=reviewer, rationale=rationale,
        payload={"candidate": candidate.model_dump(), "assertion": node.model_dump()}, event_id=event_id)
    persist = getattr(graph, "temporal_persist_snapshot", None)
    if persist is not None:
        persist(staged)
    graph.nodes, graph.event_log = staged.nodes, staged.event_log
    return event


def resolve_temporal_state(graph, *, project_id, subject_id, scene_id, fields=None, at_scene_start=False):
    from storygraph.stores.memory_graph import InMemoryGraphStore
    guard = getattr(graph, "persistence_guard", None)
    with guard() if callable(guard) else nullcontext():
        snapshot = GraphQueryService(graph)._snapshot()
        local = InMemoryGraphStore()
        local.nodes = {ref: node.model_copy(deep=True) for ref, node in snapshot.nodes.items()}
        local.relationships = {ref: rel.model_copy(deep=True) for ref, rel in snapshot.relationships.items()}
        for event in snapshot.event_log.list():
            local.event_log.append(event.model_copy(deep=True))
    _scoped_node(local, project_id, project_id, {"Project"})
    subject = _scoped_node(local, project_id, subject_id)
    _scoped_node(local, project_id, scene_id, {"Scene"})
    requested = tuple(fields) if fields is not None else tuple(
        key for key in STATE_FIELDS if subject.type in STATE_SUBJECT_TYPES[key])
    if any(key not in STATE_FIELDS or subject.type not in STATE_SUBJECT_TYPES[key] for key in requested):
        raise _error()
    scene_ids = {n.id for n in local.nodes.values() if n.type == "Scene" and n.status == "CANON"
                 and n.properties.get("project_id") == project_id}
    from storygraph.services.scene_chronology import reliable_scene_order
    order = reliable_scene_order(local, project_id)
    reachable, cyclic = order.before, order.cyclic
    baseline = subject.properties.get("initial_state", {})
    states = []
    for field in requested:
        try:
            assertions = active_state_assertions(local, project_id=project_id, subject_id=subject_id, field=field)
        except GraphStoreError:
            states.append(TemporalStateValue(field=field, status="ambiguous", reason="temporal_correction_chain_invalid"))
            continue
        active, bad = [], cyclic
        for node in assertions:
            try:
                typed = TemporalStatePatch.model_validate({key: node.properties.get(key) for key in (
                    "field", "value", "valid_from_scene", "expected_slot_fingerprint", "source_text_sha256",
                )} | {key: node.properties[key] for key in ("action", "supersedes_assertion_id")
                       if key in node.properties})
                if typed.field in {"location_id", "owner_id"} and typed.value is not None:
                    _scoped_node(local, project_id, typed.value,
                        {"Location"} if typed.field == "location_id" else {"Character", "Organization"})
            except (ValueError, GraphStoreError):
                bad = True
                continue
            boundary = node.properties.get("valid_from_scene")
            if boundary not in scene_ids:
                bad = True
            elif boundary == scene_id:
                if not at_scene_start:
                    active.append(node)
            elif reachable(boundary, scene_id):
                active.append(node)
            elif not reachable(scene_id, boundary):
                bad = True
        latest = [n for n in active if not any(
            other.id != n.id and reachable(n.properties["valid_from_scene"], other.properties["valid_from_scene"])
            for other in active)]
        if bad or len(latest) > 1:
            states.append(TemporalStateValue(field=field, status="ambiguous",
                assertion_refs=tuple(n.id for n in assertions), reason="temporal_chronology_ambiguous"))
        elif latest:
            node = latest[0]
            states.append(TemporalStateValue(field=field, status="resolved", value=node.properties["value"],
                                             assertion_refs=(node.id,)))
        elif isinstance(baseline, dict) and field in baseline:
            try:
                TemporalStatePatch(field=field, value=baseline[field], valid_from_scene=scene_id,
                    expected_slot_fingerprint="0" * 64, source_text_sha256="0" * 64)
                if field in {"location_id", "owner_id"} and baseline[field] is not None:
                    _scoped_node(local, project_id, baseline[field],
                        {"Location"} if field == "location_id" else {"Character", "Organization"})
                states.append(TemporalStateValue(field=field, status="resolved", value=baseline[field],
                                                 assertion_refs=(subject.id,)))
            except (ValueError, GraphStoreError):
                states.append(TemporalStateValue(field=field, status="unknown", reason="invalid_initial_state"))
        else:
            states.append(TemporalStateValue(field=field, status="unknown", reason="missing_initial_state"))
    return TemporalStateProjection(project_id=project_id, subject_id=subject_id, scene_id=scene_id,
        at_scene_start=at_scene_start, states=tuple(states),
        complete=all(value.status == "resolved" for value in states))


def propose_state_correction(*, graph, draft_store, project_id,
                             request: TemporalStateCorrectionRequest) -> CandidateFact:
    """Explicit author action produces one unpersisted pending Candidate, never a write."""
    from storygraph.services.project_language import resolve_project_output_language
    from storygraph.services.natural_state_extraction import validate_natural_candidate_source
    if not isinstance(request, TemporalStateCorrectionRequest):
        request = TemporalStateCorrectionRequest.model_validate(request)
    previous = _scoped_node(graph, project_id, request.assertion_id, {"Event"})
    if previous.properties.get("event_kind") != EVENT_KIND:
        raise _error("Correction requires a temporal assertion.")
    subject = _scoped_node(graph, project_id, previous.properties.get("subject_id"))
    try:
        draft = draft_store.get_draft(request.source_draft_id).model_copy(deep=True)
    except Exception:
        raise _error("Correction source Draft is unavailable.") from None
    span = request.source_span
    if (draft.project_id != project_id or draft.scene_id != previous.properties.get("valid_from_scene")
            or draft.version != request.expected_draft_version
            or content_hash(draft.text) != request.expected_source_sha256
            or draft.content_language != resolve_project_output_language(graph, project_id)
            or not (0 <= span.start_offset < span.end_offset <= len(draft.text))
            or draft.text[span.start_offset:span.end_offset] != span.quote
            or not request.rationale.strip()):
        raise _error("Correction source scope, hash or exact span is stale.")
    patch = TemporalStatePatch(field=previous.properties["field"], value=request.value,
        valid_from_scene=draft.scene_id, source_text_sha256=request.expected_source_sha256,
        expected_slot_fingerprint=request.expected_slot_fingerprint,
        action="correct", supersedes_assertion_id=previous.id)
    candidate = CandidateFact(id=new_id("fact_temporal_correction"), project_id=project_id,
        fact_type="ItemState" if subject.type == "Item" else "CharacterState",
        subject_id=previous.properties["subject_id"], relation=patch.field, value=patch.value,
        source_scene_id=draft.scene_id, source_draft_id=draft.id,
        source_span=SourceSpan(**span.model_dump()), confidence=1.0, rationale=request.rationale,
        evidence=[EvidenceItem(kind="draft_text", ref=draft.id, quote=span.quote,
            note=canonical_json({"method": "temporal_state_correction_v1", "draft_version": draft.version,
                "text_sha256": request.expected_source_sha256, "temporal_scope": {"scene_id": draft.scene_id}})),
            EvidenceItem(kind="graph_fact", ref=previous.id,
                note=canonical_json({"previous_value": previous.properties["value"], "corrected_value": patch.value,
                                     "action": "author_requested_correction"})),
            EvidenceItem(kind="author_instruction", ref="temporal_state_correction", note=request.rationale)],
        proposed_graph_patch=ProposedGraphPatch(operation="append_state", target=previous.properties["subject_id"],
            properties=patch.model_dump(), source_ref=draft.id), created_at=utc_now())
    validate_natural_candidate_source(candidate, draft_store=draft_store)
    graph.validate_candidate_scope(candidate, expected_project_id=project_id)
    return candidate


def temporal_state_history(graph, *, project_id, subject_id, fields=None, limit=100):
    guard = getattr(graph, "persistence_guard", None)
    with guard() if callable(guard) else nullcontext():
        return _temporal_state_history(graph, project_id=project_id, subject_id=subject_id,
                                       fields=fields, limit=limit)


def _temporal_state_history(graph, *, project_id, subject_id, fields=None, limit=100):
    """Bounded author-facing evidence; fingerprint always covers the complete slot."""
    if not 1 <= limit <= 500:
        raise _error("History limit must be between 1 and 500.")
    subject = _scoped_node(graph, project_id, subject_id)
    requested = fields if fields is not None else [key for key in STATE_FIELDS if subject.type in STATE_SUBJECT_TYPES[key]]
    slots = []
    for field in requested:
        fingerprint = temporal_slot_fingerprint(graph, project_id=project_id, subject_id=subject_id, field=field)
        nodes = get_state_assertions(graph, project_id=project_id, subject_id=subject_id, field=field)
        active = {node.id for node in active_state_assertions(graph, project_id=project_id, subject_id=subject_id, field=field)}
        slots.append({"field": field, "slot_fingerprint": fingerprint, "total_assertions": len(nodes),
            "truncated": len(nodes) > limit, "assertions": [
                {"assertion": node.model_dump(mode="json"), "active": node.id in active}
                for node in sorted(nodes, key=lambda n: (n.created_at, n.id), reverse=True)[:limit]]})
    return {"project_id": project_id, "subject_id": subject_id, "slots": slots}
