"""Synthetic storage/retrieval scale, not creative quality or real-model acceptance."""

import json
from time import perf_counter

import pytest

from storygraph.models.candidate import CandidateFact, ProposedGraphPatch, SourceSpan
from storygraph.models.common import EvidenceItem
from storygraph.models.generation_review import REVIEW_DIMENSIONS, GenerationReviewTarget
from storygraph.models.temporal_state import TemporalStatePatch
from storygraph.services.canon_snapshot import build_canon_snapshot, canonical_json, content_hash
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.review_service import ReviewService
from storygraph.services.semantic_review import SemanticReviewService, review_is_current
from storygraph.services.temporal_state import temporal_slot_fingerprint
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.json_graph import load_json_graph, save_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore


def seed_graph(scene_count=200, character_count=1):
    graph = InMemoryGraphStore()
    nodes = [("p", "Project", {"language": "zh-CN", "title": "合成长篇规模测试"}),
             ("place", "Location", {"project_id": "p", "name": "钟楼"}),
             ("secret", "Secret", {"project_id": "p", "description": "旧王朝的继承身份"}),
             ("rule", "WorldRule", {"project_id": "p", "rule": "潮能不能凭空产生"}),
             ("clue", "Foreshadowing", {"project_id": "p", "clue_text": "第一章留下的断印", "status": "unresolved"})]
    characters = [f"character_{i:02}" for i in range(character_count)]
    nodes.extend((ref, "Character", {"project_id": "p", "name": f"合成人物{i}",
                 "initial_state": {"life_status": "alive", "physical_state": "healthy"}})
                 for i, ref in enumerate(characters))
    for ref, label, properties in nodes:
        graph.seed_canon_node(node_id=ref, node_type=label, properties=properties)
    per_chapter = scene_count // 100
    for chapter in range(100):
        ref = f"chapter_{chapter:03}"
        graph.seed_canon_node(node_id=ref, node_type="Chapter",
            properties={"project_id": "p", "chapter_index": chapter + 1, "summary": "合成章节规划"})
        graph.seed_canon_relation(relation_id=f"contains_{chapter}", relation_type="HAS_CHAPTER",
            source_id="p", target_id=ref, properties={"project_id": "p"})
    for scene in range(scene_count):
        ref = f"scene_{scene:03}"
        chapter = f"chapter_{scene // per_chapter:03}"
        graph.seed_canon_node(node_id=ref, node_type="Scene", properties={
            "project_id": "p", "chapter_id": chapter, "scene_index": scene % per_chapter + 1,
            "pov_character_id": characters[0], "required_characters": characters,
            "location_id": "place", "timeline_position": f"第{scene + 1}日",
            "title": f"合成场景{scene + 1}", "goal": "追查断印的来源", "conflict": "守卫阻拦调查",
            **({"previous_scene_id": f"scene_{scene - 1:03}"} if scene else {}),
        })
        graph.seed_canon_relation(relation_id=f"scene_in_{scene}", relation_type="HAS_SCENE",
            source_id=chapter, target_id=ref, properties={"project_id": "p"})
        if scene:
            graph.seed_canon_relation(relation_id=f"next_{scene}", relation_type="NEXT_SCENE",
                source_id=f"scene_{scene - 1:03}", target_id=ref, properties={"project_id": "p"})
    for ref, label, scene in (("seed_early", "SEEDED_IN", "scene_000"),
                               ("payoff_late", "PAID_OFF_IN", f"scene_{scene_count - 1:03}")):
        graph.seed_canon_relation(relation_id=ref, relation_type=label, source_id="clue",
                                  target_id=scene, properties={"project_id": "p"})
    graph.seed_canon_relation(relation_id="future_knowledge", relation_type="KNOWS_SECRET",
        source_id=characters[0], target_id="secret", properties={
            "project_id": "p", "valid_from_scene": f"scene_{scene_count * 3 // 4:03}"})
    return graph


def append_death(graph, drafts, source):
    field = TemporalStatePatch(field="life_status", value="dead", valid_from_scene=source.scene_id,
        source_text_sha256=content_hash(source.text), expected_slot_fingerprint=temporal_slot_fingerprint(
            graph, project_id="p", subject_id="character_00", field="life_status"))
    quote = source.text[:40]
    candidate = CandidateFact(id="fact_natural_scale", project_id="p", fact_type="CharacterState",
        subject_id="character_00", relation="life_status", source_scene_id=source.scene_id,
        source_draft_id=source.id, source_span=SourceSpan(start_offset=0, end_offset=len(quote), quote=quote),
        confidence=0.9, rationale="合成状态变化，仅用于检验规模和来源边界。",
        evidence=[EvidenceItem(kind="draft_text", ref=source.id, quote=quote, note=canonical_json({
            "method": "natural_state_extraction_v1", "draft_version": source.version,
            "text_sha256": content_hash(source.text), "temporal_scope": {"scene_id": source.scene_id},
        }))], proposed_graph_patch=ProposedGraphPatch(operation="append_state", target="character_00",
            properties=field.model_dump(), source_ref=source.id), created_at="synthetic")
    review = ReviewService(InMemoryCandidateStore(), graph, draft_store=drafts)
    review.submit([candidate])
    review.accept(candidate.id, reviewer="synthetic-scale-check")


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic_500k")
    graph = seed_graph()
    drafts = SQLiteDraftStore(root / "drafts.sqlite")
    stored = []
    for scene in range(200):
        marker = f"SYNTHETIC_PROSE_ONLY_{scene:03}。"
        text = (marker + "这是一段只用于存储规模验收的合成正文，不代表创作质量。" * 120)[:2500]
        assert len(text) == 2500
        stored.append(drafts.create_draft(project_id="p", scene_id=f"scene_{scene:03}",
            content_language="zh-CN", text=text, summary=f"合成第{scene + 1}场的已保存摘要"))
    append_death(graph, drafts, stored[150])
    save_json_graph(graph, root / "graph.json")
    drafts.close()
    return root, tuple(d.id for d in stored)


class ReplayReview:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(json.dumps({"status": "pass", "summary": "离线协议验收通过，不证明模型创作质量。",
            "dimensions_checked": list(REVIEW_DIMENSIONS), "issues": []}, ensure_ascii=False))


def test_actual_half_million_character_corpus_survives_restart(corpus):
    root, ids = corpus
    graph, drafts = load_json_graph(root / "graph.json"), SQLiteDraftStore(root / "drafts.sqlite")
    assert len([n for n in graph.nodes.values() if n.type == "Chapter"]) == 100
    assert len([n for n in graph.nodes.values() if n.type == "Scene"]) == 200
    assert sum(len(drafts.get_draft(ref).text) for ref in ids) == 500000
    assert drafts.get_draft(ids[-1]).text.startswith("SYNTHETIC_PROSE_ONLY_199")
    assert "state_fact_natural_scale" in graph.nodes
    assert graph.event_log.get("evt_state_fact_natural_scale").source_ref == ids[150]
    drafts.close()


def test_longrange_context_and_review_are_bounded_and_canon_changes_expire_report(corpus):
    root, ids = corpus
    graph, drafts = load_json_graph(root / "graph.json"), SQLiteDraftStore(root / "drafts.sqlite")
    late = drafts.get_draft(ids[-1])
    pack = ContextPackBuilder(graph, drafts).build(project_id="p", scene_id=late.scene_id, target_tokens=12000)
    assert "第一章留下的断印" in pack.model_dump_json()
    assert "SYNTHETIC_PROSE_ONLY_" not in pack.model_dump_json()
    assert "secret" in pack.knowledge_boundaries[0].knows
    canon = build_canon_snapshot(graph, project_id="p", scene_id=late.scene_id, target_text=late.text)
    assert canon.complete
    assert {"clue", "seed_early", "payoff_late", "scene_000"} <= {fact.id for fact in canon.facts}
    assert canon.omitted_unrelated_facts > 500
    assert len(canon.facts) < 50 and len(canon.model_dump_json()) < 60000
    target = GenerationReviewTarget(project_id="p", target_type="draft", target_id=late.id,
        target_version=late.version, text=late.text, output_language="zh-CN", scene_id=late.scene_id)
    provider = ReplayReview()
    report = SemanticReviewService(provider, "offline-only").review(target=target, canon=canon)
    sent = provider.requests[0].messages[-1].content
    assert len(sent) < 100000 and "SYNTHETIC_PROSE_ONLY_199" in sent
    assert "SYNTHETIC_PROSE_ONLY_000" not in sent
    assert report.status == "pass" and review_is_current(report, target=target, canon=canon)
    graph.seed_canon_node(node_id="unrelated_new_canon", node_type="Location",
                          properties={"project_id": "p", "name": "另一处已审地点"})
    changed = build_canon_snapshot(graph, project_id="p", scene_id=late.scene_id, target_text=late.text)
    assert not review_is_current(report, target=target, canon=changed)
    drafts.close()


def test_future_knowledge_and_state_do_not_override_earlier_scene_inputs(corpus):
    root, _ = corpus
    graph, drafts = load_json_graph(root / "graph.json"), SQLiteDraftStore(root / "drafts.sqlite")
    early = ContextPackBuilder(graph, drafts).build(project_id="p", scene_id="scene_010", target_tokens=12000)
    assert "secret" not in early.knowledge_boundaries[0].knows
    assert "secret" in early.knowledge_boundaries[0].does_not_know
    assert "future_knowledge" not in early.knowledge_boundaries[0].source_refs
    life = next(state for projection in early.temporal_states for state in projection.states
                if state.field == "life_status")
    assert life.value == "alive" and "state_fact_natural_scale" not in life.assertion_refs
    assert "SYNTHETIC_PROSE_ONLY_150" not in early.model_dump_json()
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id="scene_010")
    assert "state_fact_natural_scale" not in {fact.id for fact in snapshot.facts}
    drafts.close()


@pytest.mark.parametrize("scene_count", [200, 500])
def test_100_chapter_context_and_review_snapshot_benchmark(scene_count):
    graph = seed_graph(scene_count, character_count=12)
    began = perf_counter()
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id=f"scene_{scene_count - 1:03}", target_tokens=24000)
    context_seconds = perf_counter() - began
    began = perf_counter()
    snapshot = build_canon_snapshot(graph, project_id="p", scene_id=f"scene_{scene_count - 1:03}")
    snapshot_seconds = perf_counter() - began
    print(f"SCALE {scene_count} scenes,100 chapters,12 tracked characters: context={context_seconds:.4f}s review_snapshot={snapshot_seconds:.4f}s facts={len(snapshot.facts)}")
    assert len(pack.temporal_states) == 12 and all(p.complete for p in pack.temporal_states)
    assert snapshot.complete and len(snapshot.facts) < 80
    assert context_seconds < 30 and snapshot_seconds < 30
