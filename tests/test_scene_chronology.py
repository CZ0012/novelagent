"""Automatic narrative imports must never prove future world state."""
import hashlib
import time

import pytest

from storygraph.services.scene_chronology import (
    PROOF_KEY, automatic_scene_links, parse_scene_interval, reliable_scene_edges, reliable_scene_order,
)
from storygraph.services.longform_planning import graph_plan_id
from storygraph.services.temporal_state import resolve_temporal_state
from storygraph.services.temporal_state import temporal_slot_fingerprint
from storygraph.models.temporal_state import TemporalStatePatch
from storygraph.models.candidate import CandidateFact, ProposedGraphPatch, SourceSpan
from storygraph.models.common import EvidenceItem
from storygraph.services.review_service import ReviewService
from storygraph.services.canon_snapshot import content_hash, canonical_json
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.core.errors import ContractError
from storygraph.core.ids import slug_id
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.json_graph import save_json_graph, load_json_graph
from test_temporal_state import candidate, accept
import test_longform_planning as longform_tests
import test_planning_run as planning_tests
from test_longform_planning import blueprint, expansion
from test_longform_planning import accept as accept_plan, apply as apply_plan

SEED = dict(source_ref="proposal:accepted:longform:" + "a" * 64, reviewer="test_author", rationale="Synthetic reviewed chronology")


@pytest.fixture
def longform_setup(tmp_path):
    return longform_tests.setup.__wrapped__(tmp_path)


@pytest.mark.parametrize("text,known", [
    ("第一日11:33—11:50", True), ("第六十三日09:10至第六十五日09:10", True),
    ("Day 2 10:00:00 to 11:00:00", True),
    ("2026-10-27T10:00:00Z—2026-10-27T11:00:00Z", True),
    ("2026-01-03T10:00Z—2026-01-01T11:00Z", False),
    ("2026-01-01T10:00—2026-01-01T11:00 CST", False),
    ("2026-01-03T10:00Z—2026-01-03T11:00Z；2026-01-01T10:00Z—2026-01-01T11:00Z", True),
    ("第63日，11:33—11:50", True), ("Day 63, 11:33–11:50", True),
    ("第63日，，11:33—11:50", False), ("第63日，上午11:33—11:50", False),
    ("第1日11:00开始", False), ("第1日11:00，记录于11:30", False),
    ("第1日11:00—11:30；第2日", False),
    ("第1日11:00—11:30；第2日12:00—13:00", True),
    ("第1日23:00—01:00", False), ("第一卷第一日", False),
    ("第一日11:35—11:40；11:45尚未发生", False),
    ("第六三日11:00—11:30", False), ("第十十日11:00—11:30", False),
    ("第一百零一日11:00—11:30", True),
    ("第二百三日11:00—11:30", False), ("第一千二百三日11:00—11:30", False),
    ("第二百零三日11:00—11:30", True), ("第一千二百零三日11:00—11:30", True),
    ("第二百三十日11:00—11:30", True),
    ("Day 1 7:00–8:00 PM", False), ("Day 1 7:00–8:00 p.m.", False),
    ("Day 1 7:00–8:00 a.m.", False), ("第1日07:00—08:00（下午）", False),
    ("第1日07:00—08:00（上午）", False),
    ("Day 1 07:00–08:00 UTC", False), ("Day 1 07:00–08:00 GMT+8", False),
    ("Day 1 07:00–08:00 CST", False), ("Day 1 07:00–08:00 JST", False),
    ("Day 1 07:00–08:00", True),
    ("第一日开始，调查持续数日", False), ("第一日—第三日", True),
    ("稍后", False),
])
def test_explicit_complete_interval_grammar(text, known):
    assert (parse_scene_interval(text) is not None) is known


def graph_pair(a_time, b_time, *, old=False, manual=False):
    g = InMemoryGraphStore()
    g.seed_canon_node(node_id="p", node_type="Project", properties={"language": "zh-CN"})
    g.seed_canon_node(node_id="hero", node_type="Character", properties={"project_id": "p", "initial_state": {"physical_state": "healthy"}})
    g.seed_canon_node(node_id="place", node_type="Location", properties={"project_id": "p"})
    ids = [graph_plan_id("bp", "scene", local) for local in ("a", "b")]
    for ref, local, timeline in zip(ids, ("a", "b"), (a_time, b_time)):
        g.seed_canon_node(node_id=ref, node_type="Scene", properties={"project_id": "p", "longform_blueprint_id": "bp", "longform_scene_id": local,
            "timeline_position": timeline, "pov_character_id": "hero", "required_characters": ["hero"], "location_id": "place", "goal": "核对记录", "conflict": "记录模糊"}, **SEED)
    scene_props = {ref: g.nodes[ref].properties for ref in ids}
    links = [(ids[0], ids[1], None)] if old or manual else automatic_scene_links(scene_props)
    for a, b, proof in links:
        ref = "manual" if manual else "rel_lp_" + hashlib.sha256(f"{a}:NEXT_SCENE:{b}".encode()).hexdigest()[:32]
        g.seed_canon_relation(relation_id=ref, relation_type="NEXT_SCENE", source_id=a, target_id=b,
            properties={"project_id": "p", **({PROOF_KEY: proof} if proof else {})}, **(dict(source_ref="manual:author", reviewer="author", rationale="Explicit order") if manual else SEED))
    return g, ids


def injury(g, scene, subject="hero"):
    drafts, candidates = SQLiteDraftStore(), InMemoryCandidateStore()
    data = (g, drafts, candidates)
    accept(data, candidate(data, scene=scene, subject=subject, ref="injury_" + subject + scene, field="physical_state", value="injured"))
    drafts.close()


def entry(g, scene):
    return resolve_temporal_state(g, project_id="p", subject_id="hero", scene_id=scene, fields=["physical_state"], at_scene_start=True).states[0]


@pytest.mark.parametrize("old", [False, True])
def test_parallel_apply_and_legacy_auto_do_not_project_future_injury(old):
    g, (a, b) = graph_pair("第一日11:33—11:50", "第一日11:35—11:40", old=old)
    injury(g, a)
    assert entry(g, b).status == "ambiguous"
    assert entry(g, b).value is None
    # Entry projection is conservative in both the author pack and critic view.
    pack = ContextPackBuilder(g).build(project_id="p", scene_id=b, target_tokens=16000)
    assert next(p for p in pack.temporal_states if p.subject_id == "hero").states[0].status == "ambiguous"
    if old:
        raw_next = next(r for r in g.relationships.values() if r.type == "NEXT_SCENE")
        scene_view = build_canon_snapshot(g, project_id="p", scene_id=b)
        assert raw_next.id not in {fact.id for fact in scene_view.facts}
        assert raw_next.id in g.relationships  # unchanged history/audit
        project_view = build_canon_snapshot(g, project_id="p")
        assert raw_next.id not in {fact.id for fact in project_view.facts}
        assert project_view.fingerprint == scene_view.fingerprint


def test_actual_plan_payload_and_review_inputs_filter_unsafe_default_project_evidence(monkeypatch):
    import storygraph.services.planning_run as module
    from types import SimpleNamespace
    from storygraph.models.planning_run import PlanningRunRequest, PlanningStep
    from storygraph.models.generation_review import CanonFact, GenerationReviewTarget
    from storygraph.services.semantic_review import SemanticReviewService, review_is_current
    g, _ = graph_pair("第一日11:33—11:50", "第一日11:35—11:40", old=True)
    rel = next(iter(g.relationships.values()))
    def forbidden(*args):
        pytest.fail("Evidence projection must never construct a provider")
    service = module.PlanningRunService(graph=g, proposals=None, runs=None, provider_factory=forbidden)
    run = SimpleNamespace(project_id="p", request=PlanningRunRequest(instruction="仅检查模型证据投影。", target_length=10000,
        volume_count=1, chapters_per_volume=2, scenes_per_chapter=2), steps=[SimpleNamespace(proposal_ref=None)])
    payload, _ = service._payload(run, PlanningStep(index=0, phase="blueprint"))
    assert payload["canon"]["scope"] == "project"
    assert rel.id not in {fact["id"] for fact in payload["canon"]["facts"]}
    monkeypatch.setattr(module, "branch_from_ref", lambda *args: SimpleNamespace(blueprint=SimpleNamespace(style_brief=SimpleNamespace(rubric=[], banned_patterns=[]))))
    canon, _ = service._review_inputs(run)
    assert canon.scope == "plan" and rel.id not in {fact.id for fact in canon.facts}
    # An old report with the previously advertised bad fact cannot be reused.
    legacy_fact = CanonFact(id=rel.id, kind="relation", text=canonical_json({"id": rel.id, "type": rel.type, "status": rel.status,
        "source_id": rel.source_id, "target_id": rel.target_id, "properties": rel.properties}))
    legacy = canon.model_copy(update={"facts": (*canon.facts, legacy_fact)})
    target = GenerationReviewTarget(project_id="p", target_type="proposal", target_id="plan", target_version=1,
        text="这是一份固定版本的合成规划。", output_language="zh-CN", purpose="plan")
    old_report = SemanticReviewService().review(target=target, canon=legacy).model_copy(update={"status": "pass"})
    assert not review_is_current(old_report, target=target, canon=canon)
    assert legacy.fingerprint == canon.fingerprint and rel.id in g.relationships


def test_flashback_sorts_world_proof_not_narrative_and_keeps_future_baseline():
    g, (late, early) = graph_pair("第一日12:00—12:30", "第一日10:00—10:30")
    assert early in reliable_scene_edges(g, "p") and late in reliable_scene_edges(g, "p")[early]
    injury(g, late)
    assert entry(g, early).value == "healthy"


@pytest.mark.parametrize("source_time", ["Day 1 7:00–8:00 PM", "Day 1 7:00–8:00 p.m.", "第1日07:00—08:00（下午）", "Day 1 07:00–08:00 JST"])
def test_unsupported_qualifier_never_projects_source_state_into_noon(source_time):
    g, (source, noon) = graph_pair(source_time, "Day 1 12:00–13:00", old=True)
    injury(g, source)
    state = entry(g, noon)
    assert state.status == "ambiguous" and state.value is None
    assert not reliable_scene_order(g, "p").before(source, noon)


@pytest.mark.parametrize("old", [False, True])
def test_linear_auto_restart_and_time_edit_stales_proof(tmp_path, old):
    g, (a, b) = graph_pair("第一日10:00—10:30", "第一日11:00—11:30", old=old)
    injury(g, a)
    assert entry(g, b).value == "injured"
    save_json_graph(g, tmp_path / "graph.json")
    restored = load_json_graph(tmp_path / "graph.json")
    assert entry(restored, b).value == "injured"
    restored.update_node(b, {"timeline_position": "第一日10:10—10:20"}, source_ref="manual:edit", reviewer="author", rationale="Correct time")
    assert entry(restored, b).status == "ambiguous"
    assert len(restored.relationships) == len(g.relationships)  # read filter, no migration
    restored.update_node(b, {"timeline_position": "第一日12:00—12:30"}, source_ref="manual:approved_time", reviewer="author", rationale="Confirm corrected interval")
    restored.update_node(b, {"title": "Corrected scene"}, source_ref="manual:approved_title", reviewer="author", rationale="Change title only")
    assert entry(restored, b).value == "injured"  # authorized time edit restores proof
    assert b not in reliable_scene_edges(restored, "p")[a]  # old stored proof remains stale
    node = restored.nodes[b]
    restored.nodes[b] = node.model_copy(update={"properties": {**node.properties, "timeline_position": "第一日13:00—13:30"}})
    assert entry(restored, b).status == "ambiguous"  # direct mutation has no approved event


def test_manual_order_retains_authority_even_with_overlap():
    g, (a, b) = graph_pair("第一日11:33—11:50", "第一日11:35—11:40", manual=True)
    injury(g, a)
    assert entry(g, b).value == "injured"


def test_touching_intervals_and_incomplete_receipts_are_unknown():
    g, (a, b) = graph_pair("第一日10:00—11:00", "第一日11:00—12:00", old=True)
    injury(g, a)
    assert entry(g, b).status == "ambiguous"
    g, (a, b) = graph_pair("第一日10:00—10:30", "第一日11:00—12:00", old=True)
    g.event_log._events = [e for e in g.event_log.list() if not (e.operation == "create_node" and e.target == a)]
    injury(g, a)
    assert entry(g, b).status == "ambiguous"


def test_fork_join_preserves_both_roles_and_knowledge_without_dense_canon():
    g, (a, b) = graph_pair("第一日11:33—11:50", "第一日11:35—11:40")
    c = graph_plan_id("bp", "scene", "c")
    g.seed_canon_node(node_id=c, node_type="Scene", properties={"project_id": "p", "longform_blueprint_id": "bp", "longform_scene_id": "c", "timeline_position": "第一日12:00—12:30"}, **SEED)
    g.seed_canon_node(node_id="other", node_type="Character", properties={"project_id": "p", "initial_state": {"physical_state": "healthy"}})
    injury(g, a)
    injury(g, b, "other")
    for character, boundary in (("hero", a), ("other", b)):
        secret = "secret_" + character
        g.seed_canon_node(node_id=secret, node_type="Secret", properties={"project_id": "p"})
        g.seed_canon_relation(relation_id="knows_" + character, relation_type="KNOWS_SECRET", source_id=character, target_id=secret,
            properties={"project_id": "p", "valid_from_scene": boundary, "known": True})
        state = resolve_temporal_state(g, project_id="p", subject_id=character, scene_id=c, fields=["physical_state"], at_scene_start=True).states[0]
        assert state.status == "resolved" and state.value == "injured"
        assert secret in g.get_character_knowledge(character, scene_id=c, at_scene_start=True).knows
    assert entry(g, b).status == "ambiguous"  # A's late injury stays unknown at B.
    assert "secret_hero" not in g.get_character_knowledge("hero", scene_id=b, at_scene_start=True).knows
    assert not [r for r in g.relationships.values() if r.type == "NEXT_SCENE"]
    assert reliable_scene_order(g, "p").before(a, c) and reliable_scene_order(g, "p").before(b, c)


@pytest.mark.parametrize("custom_display_indices", [False, True])
def test_legacy_structure_custom_source_is_not_manual_chronology(custom_display_indices):
    g = InMemoryGraphStore()
    g.seed_canon_node(node_id="p", node_type="Project", properties={"language": "zh-CN"})
    provenance = dict(source_ref="custom:imported_outline", reviewer="author", rationale="Reviewed structure")
    props = {"project_id": "p", "source_structure_proposal_id": "outline_one", "source_structure_proposal_version": 1}
    chapter = "chapter_structure"
    g.seed_canon_node(node_id=chapter, node_type="Chapter", properties={**props, "chapter_index": 77 if custom_display_indices else 1}, **provenance)
    ids = []
    for i, (title, timeline) in enumerate((("A", "第一日11:33—11:50"), ("B", "第一日11:35—11:40")), 1):
        ref = slug_id("scene", f"p_1_{i}_{title}")
        ids.append(ref)
        g.seed_canon_node(node_id=ref, node_type="Scene", properties={**props, "chapter_id": chapter, "scene_index": i+10 if custom_display_indices else i, "title": title, "timeline_position": timeline}, **provenance)
    a, b = ids
    g.seed_canon_relation(relation_id=slug_id("rel", f"{a}_NEXT_SCENE_{b}"), relation_type="NEXT_SCENE", source_id=a, target_id=b, properties={"project_id": "p"}, **provenance)
    assert b not in reliable_scene_edges(g, "p")[a]
    assert not reliable_scene_order(g, "p").before(a, b)
    g.update_node(b, {"timeline_position": "第一日12:00—12:30"}, **provenance)
    assert reliable_scene_order(g, "p").before(a, b)
    g.nodes[a].properties["source_structure_proposal_id"] = "corrupted"
    assert b not in reliable_scene_edges(g, "p")[a]
    assert not reliable_scene_order(g, "p").before(a, b)


@pytest.mark.parametrize("field", ["longform_scene_id", "longform_blueprint_id", "project_id"])
def test_corrupt_legacy_auto_identity_never_falls_back_to_manual(field):
    g, (a, b) = graph_pair("第一日11:33—11:50", "第一日11:35—11:40", old=True)
    injury(g, a)
    g.nodes[a].properties[field] = "corrupted"
    state = entry(g, b)
    assert state.status == "ambiguous" and state.value is None


def test_corrupt_legacy_relation_source_keeps_automatic_classification():
    g, (a, b) = graph_pair("第一日11:33—11:50", "第一日11:35—11:40", old=True)
    injury(g, a)
    rel = next(iter(g.relationships.values()))
    g.relationships[rel.id] = rel.model_copy(update={"source_ref": "manual:forged_without_event"})
    assert entry(g, b).status == "ambiguous"


@pytest.mark.parametrize("count", [200, 500])
def test_sparse_scale_and_cross_batch_earlier_scene(count):
    props = {f"scene{i:04}": {"timeline_position": f"第{i+1}日"} for i in range(count)}
    start = time.monotonic()
    links = automatic_scene_links(props)
    assert len(links) == count - 1
    assert time.monotonic() - start < 3
    # Full internal order is still bounded at 500 scenes and never materialized.
    g = InMemoryGraphStore()
    for i in range(count):
        ref = graph_plan_id("bp", "scene", str(i))
        g.seed_canon_node(node_id=ref, node_type="Scene", properties={"project_id": "p", "longform_blueprint_id": "bp", "longform_scene_id": str(i), **props[f"scene{i:04}"]}, **SEED)
    start = time.monotonic()
    order = reliable_scene_order(g, "p")
    assert order.before(graph_plan_id("bp", "scene", "0"), graph_plan_id("bp", "scene", str(count-1)))
    assert time.monotonic() - start < 3
    assert not g.relationships
    # A newly accepted earlier scene can point into an already existing later one.
    assert automatic_scene_links({"new": {"timeline_position": "第一日10:00—11:00"}, "existing": {"timeline_position": "第一日12:00—13:00"}}, target_ids={"new"})[0][:2] == ("new", "existing")


def test_actual_longform_application_parallel_and_replay(longform_setup):
    g, _, provider, _ = longform_setup
    provider.mutate = lambda value: value["entities"][0].update(initial_state={"physical_state": "healthy"}) if "entities" in value else None
    parent = apply_plan(longform_setup, accept_plan(longform_setup, blueprint(longform_setup, target_length=10000, volume_count=1, chapters_per_volume=2, scenes_per_chapter=2)))["proposal"]
    def mutate(value):
        scenes = [s for c in value["chapters"] for s in c["scenes"]]
        for s, text in zip(scenes, ["第一日11:33—11:50", "第一日11:35—11:40", "第一日12:00—12:30", "第一日13:00—13:30"]):
            s["timeline_position"] = text
    provider.mutate = mutate
    proposal = accept_plan(longform_setup, expansion(longform_setup, parent, volume_index=1, chapter_start=1, chapter_count=2))
    assert not apply_plan(longform_setup, proposal)["already_applied"]
    assert apply_plan(longform_setup, proposal)["already_applied"]
    a, b = [graph_plan_id(parent["id"], "scene", name) for name in ("v01_c001_s01", "v01_c001_s02")]
    assert b not in reliable_scene_edges(g, "project_test")[a]
    assert g.nodes[b].properties["previous_scene_id"] == a
    assert not any(r.type == "NEXT_SCENE" and r.source_id == a and r.target_id == b for r in g.relationships.values())
    # The independent critic does not demand that narrative previous == world predecessor.
    assert "missing_scene_reference" not in build_canon_snapshot(g, project_id="project_test", scene_id=b).missing_context
    subject = graph_plan_id(parent["id"], "character", "courier")
    ds, candidates = SQLiteDraftStore(), InMemoryCandidateStore()
    text = "第一日11:45，林舟在现场摔伤手臂。"
    draft = ds.create_draft(project_id="project_test", scene_id=a, content_language="zh-CN", text=text)
    patch = TemporalStatePatch(field="physical_state", value="injured", valid_from_scene=a,
        source_text_sha256=content_hash(text), expected_slot_fingerprint=temporal_slot_fingerprint(g, project_id="project_test", subject_id=subject, field="physical_state"))
    fact = CandidateFact(id="reviewed_parallel_injury", project_id="project_test", fact_type="CharacterState", subject_id=subject,
        relation="physical_state", source_scene_id=a, source_draft_id=draft.id, source_span=SourceSpan(start_offset=0, end_offset=len(text), quote=text),
        confidence=1, rationale="Synthetic reviewed state, not an actual novel decision.", created_at="test",
        evidence=[EvidenceItem(kind="draft_text", ref=draft.id, quote=text, note=canonical_json({"method": "natural_state_extraction_v1", "draft_version": draft.version,
            "text_sha256": content_hash(text), "temporal_scope": {"scene_id": a}}))],
        proposed_graph_patch=ProposedGraphPatch(operation="append_state", target=subject, properties=patch.model_dump(), source_ref=draft.id))
    review = ReviewService(candidates, g, draft_store=ds)
    review.submit([fact])
    review.accept(fact.id, reviewer="synthetic_author")
    state = resolve_temporal_state(g, project_id="project_test", subject_id=subject, scene_id=b, fields=["physical_state"], at_scene_start=True).states[0]
    assert state.status == "ambiguous" and state.value is None
    pack = ContextPackBuilder(g, ds).build(project_id="project_test", scene_id=b, target_tokens=16000)
    projected = next(p for p in pack.temporal_states if p.subject_id == subject)
    assert projected.states[0].status == "ambiguous"
    class NoCall:
        def generate(self, request):
            pytest.fail("Required ambiguous state must block before a provider call")
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=NoCall(), model="offline").draft(pack)
    ds.close()


@pytest.mark.parametrize("legacy_receipts", [False, True])
def test_whole_book_parallel_application_and_immutable_retry(tmp_path, legacy_receipts):
    from storygraph.services.book_bundle import apply_book_bundle
    from storygraph.models.longform import LongformApplyRequest
    setup = planning_tests.setup.__wrapped__(tmp_path)
    graph, proposals, runs, provider, _, service, _ = setup
    def mutate(value):
        if "chapters" not in value:
            return
        for chapter in value["chapters"]:
            day = (value["volume_index"] - 1) * 2 + chapter["index"]
            for i, scene in enumerate(chapter["scenes"]):
                scene["timeline_position"] = (["第一日11:33—11:50", "第一日11:35—11:40"][i]
                    if day == 1 else f"第{day}日{10+i}:00—{10+i}:30")
    provider.mutate = mutate
    finished = service.execute(planning_tests.create(setup).id)
    assert finished.status == "awaiting_review"
    bundle = proposals.get(finished.bundle_proposal_id)
    accepted = proposals.review(bundle.id, decision="accepted", reviewer="author", expected_version=bundle.version)
    args = dict(graph=graph, proposals=proposals, runs=runs, project_id="book", proposal_id=accepted.id,
        request=LongformApplyRequest(expected_version=accepted.version, reviewer="author"),
        persist_snapshot=lambda staged: save_json_graph(staged, tmp_path / "bundle-graph.json"))
    assert not apply_book_bundle(**args)["already_applied"]
    assert any(r.type == "NEXT_SCENE" for r in graph.relationships.values())
    if legacy_receipts:
        # Emulate the historical receipt shape, without altering source plans.
        # Current retries must validate saved evidence rather than recertify it.
        for rel in graph.relationships.values():
            if rel.type == "NEXT_SCENE":
                rel.properties.pop(PROOF_KEY, None)
                for event in graph.event_log.list():
                    if event.operation == "create_relation" and event.target == rel.id:
                        event.payload["properties"].pop(PROOF_KEY, None)
    blueprint_id = finished.steps[0].proposal_ref.id
    a, b = [graph_plan_id(blueprint_id, "scene", x) for x in ("v01_c001_s01", "v01_c001_s02")]
    assert not reliable_scene_order(graph, "book").before(a, b)
    assert graph.nodes[b].properties["previous_scene_id"] == a
    save_json_graph(graph, tmp_path / "bundle-restart.json")
    restored = load_json_graph(tmp_path / "bundle-restart.json")
    before = len(restored.event_log.list())
    assert apply_book_bundle(**{**args, "graph": restored})["already_applied"]
    assert len(restored.event_log.list()) == before
