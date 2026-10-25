"""Reviewed append-only state memory with conservative narrative chronology."""

import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.config import StoryGraphSettings
from storygraph.models.candidate import CandidateFact, ProposedGraphPatch, SourceSpan
from storygraph.models.common import EvidenceItem
from storygraph.models.temporal_state import TemporalStatePatch
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.review_service import ReviewService
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.services.temporal_state import resolve_temporal_state, temporal_slot_fingerprint
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.graph_factory import open_configured_graph_store
from storygraph.stores.graph_neo4j import Neo4jGraphStore
from storygraph.stores.json_graph import load_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore


@pytest.fixture
def setup():
    graph = InMemoryGraphStore()
    for ref, label, properties in [
        ("p", "Project", {"language": "zh-CN"}),
        ("hero", "Character", {"project_id": "p", "initial_state": {"life_status": "alive", "physical_state": "healthy"}}),
        ("other", "Character", {"project_id": "p"}),
        ("a", "Location", {"project_id": "p"}), ("b", "Location", {"project_id": "p"}),
        ("item", "Item", {"project_id": "p", "initial_state": {"owner_id": "hero", "location_id": "a"}}),
        *[(f"s{i}", "Scene", {"project_id": "p"}) for i in range(1, 5)],
    ]:
        graph.seed_canon_node(node_id=ref, node_type=label, properties=properties)
    for i in range(1, 4):
        graph.seed_canon_relation(relation_id=f"next{i}", relation_type="NEXT_SCENE",
            source_id=f"s{i}", target_id=f"s{i+1}", properties={"project_id": "p"})
    drafts, candidates = SQLiteDraftStore(), InMemoryCandidateStore()
    return graph, drafts, candidates


def candidate(setup, *, ref="fact_natural_one", subject="hero", field="life_status", value="dead", scene="s2"):
    graph, drafts, _ = setup
    draft = drafts.create_draft(project_id="p", scene_id=scene, content_language="zh-CN", text="这是明确发生的状态变化。")
    patch = TemporalStatePatch(field=field, value=value, valid_from_scene=scene,
        source_text_sha256=content_hash(draft.text), expected_slot_fingerprint=temporal_slot_fingerprint(
            graph, project_id="p", subject_id=subject, field=field))
    return CandidateFact(id=ref, project_id="p", fact_type="CharacterState", subject_id=subject,
        relation=field, source_scene_id=scene, source_draft_id=draft.id,
        source_span=SourceSpan(start_offset=0, end_offset=len(draft.text), quote=draft.text),
        confidence=0.9, rationale="作者确认这一状态变化。", evidence=[EvidenceItem(
            kind="draft_text", ref=draft.id, quote=draft.text, note=canonical_json({
                "method": "natural_state_extraction_v1", "draft_version": draft.version,
                "text_sha256": content_hash(draft.text), "temporal_scope": {"scene_id": scene},
            }))], proposed_graph_patch=ProposedGraphPatch(operation="append_state", target=subject,
                properties=patch.model_dump(), source_ref=draft.id), created_at="now")


def accept(setup, fact):
    graph, drafts, candidates = setup
    service = ReviewService(candidates, graph, draft_store=drafts)
    service.submit([fact])
    return service.accept(fact.id, reviewer="author")


def value(graph, scene, *, subject="hero", field="life_status", **kwargs):
    return resolve_temporal_state(graph, project_id="p", subject_id=subject, scene_id=scene,
                                   fields=[field], **kwargs).states[0]


def test_alive_early_dead_after_reviewed_death_and_entry_uses_baseline(setup):
    graph, _, _ = setup
    fact = candidate(setup)
    original = graph.get_node("hero").model_dump()
    accept(setup, fact)
    assert value(graph, "s1").value == "alive"
    assert value(graph, "s2", at_scene_start=True).value == "alive"
    assert value(graph, "s2").value == "dead"
    assert value(graph, "s3", at_scene_start=True).value == "dead"
    assert graph.get_node("hero").model_dump() == original
    assert "state_" + fact.id in graph.nodes
    assert not any(r.source_ref == fact.source_draft_id for r in graph.relationships.values())


def test_out_of_order_injury_then_healing_queries_story_order_not_accept_order(setup):
    graph, _, _ = setup
    accept(setup, candidate(setup, ref="fact_natural_heal", field="physical_state", value="healthy", scene="s4"))
    accept(setup, candidate(setup, ref="fact_natural_injure", field="physical_state", value="injured", scene="s2"))
    assert value(graph, "s1", field="physical_state").value == "healthy"
    assert value(graph, "s3", field="physical_state").value == "injured"
    assert value(graph, "s4", field="physical_state", at_scene_start=True).value == "injured"
    assert value(graph, "s4", field="physical_state").value == "healthy"


@pytest.mark.parametrize("field,new", [("owner_id", "other"), ("location_id", "b"), ("owner_id", None)])
def test_exclusive_item_state_resolves_one_value_and_preserves_prior_scene(setup, field, new):
    graph, _, _ = setup
    accept(setup, candidate(setup, subject="item", field=field, value=new))
    assert value(graph, "s1", subject="item", field=field).value == ("hero" if field == "owner_id" else "a")
    assert value(graph, "s3", subject="item", field=field).value == new
    assert value(graph, "s3", subject="item", field=field).status == "resolved"


def test_missing_baseline_is_unknown_not_inferred_alive(setup):
    graph, _, _ = setup
    accept(setup, candidate(setup, subject="other"))
    assert value(graph, "s1", subject="other").status == "unknown"
    assert value(graph, "s2", subject="other", at_scene_start=True).status == "unknown"
    assert value(graph, "s3", subject="other").value == "dead"


def test_slot_cas_rejects_concurrent_stale_candidate_without_graph_delta(setup):
    graph, drafts, candidates = setup
    first, second = candidate(setup, ref="fact_natural_first"), candidate(setup, ref="fact_natural_second", scene="s3")
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([first, second])
    review.accept(first.id, reviewer="one")
    before = (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises((GraphStoreError, ContractError)):
        review.accept(second.id, reviewer="two")
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    assert candidates.get(second.id).review.status == "pending"


def test_direct_exact_commit_retry_is_idempotent_and_assertion_immutable(setup):
    graph, _, _ = setup
    fact = accept(setup, candidate(setup))
    before = (len(graph.nodes), len(graph.event_log.list()))
    graph.commit_candidate_fact(fact, reviewer="author", rationale=fact.rationale)
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises(GraphStoreError, match="immutable"):
        graph.update_node("state_" + fact.id, {"value": "alive"}, reviewer="author", rationale="edit", source_ref="manual")


def test_malformed_assertion_value_never_becomes_resolved_state(setup):
    graph, _, _ = setup
    fact = candidate(setup)
    accept(setup, fact)
    graph.nodes["state_" + fact.id].properties["value"] = "invented-life-status"
    assert value(graph, "s3").status == "ambiguous"


@pytest.mark.parametrize("kind", ["missing", "cycle", "branch"])
def test_missing_cyclic_or_incomparable_chronology_fails_closed(setup, kind):
    graph, _, _ = setup
    accept(setup, candidate(setup))
    if kind == "missing":
        del graph.relationships["next2"]
    elif kind == "cycle":
        graph.seed_canon_relation(relation_id="loop", relation_type="NEXT_SCENE", source_id="s3", target_id="s1",
                                  properties={"project_id": "p"})
    else:
        graph.seed_canon_node(node_id="branch", node_type="Scene", properties={"project_id": "p"})
        graph.seed_canon_relation(relation_id="fork", relation_type="NEXT_SCENE", source_id="s1", target_id="branch",
                                  properties={"project_id": "p"})
    assert value(graph, "branch" if kind == "branch" else "s3").status == "ambiguous"


def test_reject_and_defer_never_append_state(setup):
    graph, drafts, candidates = setup
    for index, action in enumerate(("reject", "defer")):
        fact = candidate(setup, ref=f"fact_natural_reject{index}")
        service = ReviewService(candidates, graph, draft_store=drafts)
        service.submit([fact])
        getattr(service, action)(fact.id, reviewer="author")
        assert "state_" + fact.id not in graph.nodes


def test_neo4j_rejects_before_read_or_mutation(setup):
    fact = candidate(setup)
    graph = object.__new__(Neo4jGraphStore)
    graph._snapshot = lambda: pytest.fail("unsupported backend must reject before snapshot")
    with pytest.raises(GraphStoreError, match="local JSON/memory"):
        graph.commit_candidate_fact(fact, reviewer="author", rationale="reviewed")


def test_json_commit_persists_assertion_and_event_and_failure_compensates(setup, monkeypatch):
    graph, drafts, candidates = setup
    persisted = []
    graph.temporal_persist_snapshot = lambda staged: persisted.append(staged)
    fact = candidate(setup)
    accept(setup, fact)
    assert len(persisted) == 1
    assert "state_" + fact.id in persisted[0].nodes
    assert persisted[0].event_log.get("evt_state_" + fact.id)
    another = candidate(setup, ref="fact_natural_failure", field="physical_state", value="injured")
    def fail(_):
        raise OSError("synthetic persistence failure")
    graph.temporal_persist_snapshot = fail
    service = ReviewService(candidates, graph, draft_store=drafts)
    service.submit([another])
    before = (len(graph.nodes), len(graph.event_log.list()))
    with pytest.raises(OSError):
        service.accept(another.id, reviewer="author")
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    assert candidates.get(another.id).review.status == "pending"


def test_json_factory_registers_staged_durable_hook(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    configured = open_configured_graph_store(settings)
    graph = configured.graph
    graph.temporal_persist_snapshot(graph)
    assert load_json_graph(settings.graph_path).nodes == {}


def test_real_json_restart_preserves_asof_history_and_commit_evidence(setup, tmp_path):
    original, drafts, _ = setup
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    graph = open_configured_graph_store(settings).graph
    graph.nodes, graph.relationships, graph.event_log = original.nodes, original.relationships, original.event_log
    fact = candidate((graph, drafts, InMemoryCandidateStore()))
    accept((graph, drafts, InMemoryCandidateStore()), fact)
    restarted = open_configured_graph_store(settings).graph
    assert value(restarted, "s1").value == "alive"
    assert value(restarted, "s3").value == "dead"
    assert restarted.event_log.get("evt_state_" + fact.id).target == "state_" + fact.id


def test_competing_review_threads_have_one_slot_cas_winner(setup):
    graph, drafts, _ = setup
    barrier = Barrier(2)
    class RacingCandidates(InMemoryCandidateStore):
        def update_if_pending(self, fact):
            result = super().update_if_pending(fact)
            barrier.wait(timeout=3)
            return result
    candidates = RacingCandidates()
    first = candidate((graph, drafts, candidates), ref="fact_natural_race1")
    second = candidate((graph, drafts, candidates), ref="fact_natural_race2", value="alive")
    review = ReviewService(candidates, graph, draft_store=drafts)
    review.submit([first, second])
    def decide(fact):
        try:
            review.accept(fact.id, reviewer="author")
            return "accepted"
        except (ContractError, GraphStoreError):
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, (first, second)))
    assert sorted(results) == ["accepted", "conflict"]
    assert len([n for n in graph.nodes if n.startswith("state_fact_natural_race")]) == 1
    assert sorted(candidates.get(f.id).review.status for f in (first, second)) == ["accepted", "pending"]


def ready_context_graph(setup):
    graph, _, _ = setup
    graph.seed_canon_node(node_id="chapter", node_type="Chapter", properties={"project_id": "p"})
    graph.nodes["hero"].properties["name"] = "林烬"
    for i in range(1, 5):
        graph.nodes[f"s{i}"].properties.update({
            "chapter_id": "chapter", "pov_character_id": "hero", "location_id": "a",
            "goal": "找出账簿的真相", "conflict": "守卫堵住大门", "timeline_position": f"第{i}日",
            "required_characters": ["hero"],
        })
    return graph


class CapturedWriter:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        import json
        self.requests.append(request)
        return LLMResponse(json.dumps({"text": "林烬走进钟楼，检查遗留的账簿。", "summary": "他抵达钟楼。",
                                       "self_check": []}, ensure_ascii=False))


def test_context_and_actual_writer_payload_never_include_future_death(setup):
    import json
    graph = ready_context_graph(setup)
    fact = candidate(setup, scene="s3")
    accept(setup, fact)
    pack = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id="s1", target_tokens=12000)
    life = next(state for projection in pack.temporal_states for state in projection.states
                if state.field == "life_status")
    assert life.value == "alive" and life.assertion_refs == ("hero",)
    provider = CapturedWriter()
    LLMSceneWriter(provider=provider, model="offline").draft(pack)
    payload = json.loads(provider.requests[0].messages[-1].content)
    assert payload["context_pack"]["temporal_states"][0]["at_scene_start"] is True
    assert "state_" + fact.id not in provider.requests[0].messages[-1].content
    assert fact.source_span.quote not in provider.requests[0].messages[-1].content
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s1")
    assert "state_" + fact.id not in {f.id for f in snapshot.facts}
    assert fact.source_span.quote not in snapshot.model_dump_json()
    hero = json.loads(next(f.text for f in snapshot.facts if f.id == "hero"))
    assert next(v for v in hero["state_at_scene_entry"]["states"] if v["field"] == "life_status")["value"] == "alive"


def test_context_snapshot_and_writer_use_late_state_but_death_scene_entry_stays_alive(setup):
    import json
    graph = ready_context_graph(setup)
    fact = candidate(setup, scene="s3")
    accept(setup, fact)
    for scene, expected in (("s3", "alive"), ("s4", "dead")):
        pack = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id=scene, target_tokens=12000)
        life = next(v for p in pack.temporal_states for v in p.states if v.field == "life_status")
        assert life.value == expected
        snapshot = build_canon_snapshot(graph, project_id="p", scene_id=scene)
        hero = json.loads(next(f.text for f in snapshot.facts if f.id == "hero"))
        assert next(v for v in hero["state_at_scene_entry"]["states"] if v["field"] == "life_status")["value"] == expected
        assert ("state_" + fact.id in {f.id for f in snapshot.facts}) == (scene == "s4")


def test_missing_baseline_in_tracked_future_state_blocks_before_provider(setup):
    graph = ready_context_graph(setup)
    del graph.nodes["hero"].properties["initial_state"]["life_status"]
    accept(setup, candidate(setup, scene="s3"))
    pack = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id="s1", target_tokens=12000)
    assert any(gap.kind == "temporal_state_unresolved" and gap.severity == "critical" for gap in pack.missing_context)
    provider = CapturedWriter()
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=provider, model="offline").draft(pack)
    assert provider.requests == []
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s1")
    assert not snapshot.complete and "temporal_state_unresolved" in snapshot.missing_context


def test_cross_project_initial_state_ref_never_leaks_foreign_content(setup):
    graph = ready_context_graph(setup)
    graph.seed_canon_node(node_id="q", node_type="Project", properties={"language": "zh-CN"})
    graph.seed_canon_node(node_id="foreign_location", node_type="Location",
                          properties={"project_id": "q", "description": "FOREIGN_PRIVATE_SENTINEL"})
    graph.nodes["hero"].properties["initial_state"]["location_id"] = "foreign_location"
    pack = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id="s1", target_tokens=12000)
    assert any(gap.kind == "temporal_state_unresolved" for gap in pack.missing_context)
    assert "FOREIGN_PRIVATE_SENTINEL" not in pack.model_dump_json()
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s1")
    assert not snapshot.complete and "FOREIGN_PRIVATE_SENTINEL" not in snapshot.model_dump_json()


def test_generic_candidate_cannot_mutate_assertion_or_reset_initial_baseline(setup):
    graph, drafts, candidates = setup
    fact = accept(setup, candidate(setup))
    for index, subject, properties in (
        (0, "state_" + fact.id, {"value": "alive"}),
        (1, "hero", {"initial_state": {"life_status": "dead"}}),
    ):
        original = candidate(setup, ref=f"manual_candidate_{index}", field="physical_state", value="injured")
        update = original.model_copy(update={"subject_id": subject, "evidence": [],
            "proposed_graph_patch": ProposedGraphPatch(operation="update_node", target=subject,
                properties=properties, source_ref=original.source_draft_id)})
        before = (len(graph.nodes), len(graph.event_log.list()))
        with pytest.raises((GraphStoreError, ContractError)):
            ReviewService(candidates, graph, draft_store=drafts).submit([update])
        assert before == (len(graph.nodes), len(graph.event_log.list()))


def test_generic_event_cannot_be_converted_into_reserved_assertion(setup):
    graph, _, _ = setup
    graph.seed_canon_node(node_id="ordinary_event", node_type="Event", properties={"project_id": "p"})
    before = graph.get_node("ordinary_event").model_dump()
    with pytest.raises(GraphStoreError, match="immutable"):
        graph.update_node("ordinary_event", {"event_kind": "temporal_state_assertion_v1", "value": "dead"},
                          reviewer="author", rationale="generic edit", source_ref="manual")
    assert graph.get_node("ordinary_event").model_dump() == before


@pytest.mark.parametrize("initial_owner", ["other", "missing"])
def test_future_inventory_item_stays_hidden_until_transfer_or_explicit_name(setup, initial_owner):
    graph = ready_context_graph(setup)
    item = graph.nodes["item"]
    item.properties.update({"name": "月痕匣", "description": "FUTURE_ITEM_DESCRIPTION_SENTINEL"})
    if initial_owner == "missing":
        del item.properties["initial_state"]["owner_id"]
    else:
        item.properties["initial_state"]["owner_id"] = initial_owner
    transfer = candidate(setup, subject="item", field="owner_id", value="hero", scene="s3")
    accept(setup, transfer)
    for scene in ("s1", "s3"):
        pack = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id=scene, target_tokens=12000)
        assert "item" not in {entity["id"] for entity in pack.canon_entities}
        assert "月痕匣" not in pack.model_dump_json()
        assert "FUTURE_ITEM_DESCRIPTION_SENTINEL" not in pack.model_dump_json()
        assert not any(gap.kind == "temporal_state_unresolved" and gap.ref == "item"
                       for gap in pack.missing_context)
        snapshot = build_canon_snapshot(graph, project_id="p", scene_id=scene)
        assert "FUTURE_ITEM_DESCRIPTION_SENTINEL" not in snapshot.model_dump_json()
    late = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id="s4", target_tokens=12000)
    assert "item" in {entity["id"] for entity in late.canon_entities}
    assert "月痕匣" in late.model_dump_json() and "FUTURE_ITEM_DESCRIPTION_SENTINEL" in late.model_dump_json()
    ownership = next(v for p in late.temporal_states if p.subject_id == "item"
                     for v in p.states if v.field == "owner_id")
    assert ownership.status == "resolved" and ownership.value == "hero"
    graph.nodes["s1"].properties["goal"] = "寻找月痕匣的线索"
    named = ContextPackBuilder(graph, setup[1]).build(project_id="p", scene_id="s1", target_tokens=12000)
    assert "月痕匣" in named.model_dump_json() and "FUTURE_ITEM_DESCRIPTION_SENTINEL" in named.model_dump_json()
    named_snapshot = build_canon_snapshot(graph, project_id="p", scene_id="s1", target_text="寻找月痕匣的线索")
    assert "item" in {fact.id for fact in named_snapshot.facts}
