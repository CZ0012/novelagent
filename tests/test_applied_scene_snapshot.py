"""Real apply storage metadata remains local; scene evidence resolves reviewed graph edges."""

import copy
import pytest
from storygraph.services.canon_snapshot import build_canon_snapshot
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.longform_planning import graph_plan_id
from storygraph.services.semantic_review import SemanticReviewService
from storygraph.services.natural_state_extraction import extract_natural_draft_state
from storygraph.models.generation_review import GenerationReviewTarget, REVIEW_DIMENSIONS
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.services.llm_provider import LLMResponse
from test_longform_planning import setup as setup, blueprint, accept, apply, expansion
from test_planning_run import setup as _run_setup, create

run_setup = _run_setup


def applied(setup):
    parent = apply(
        setup,
        accept(
            setup,
            blueprint(
                setup,
                volume_count=1,
                chapters_per_volume=1,
                scenes_per_chapter=2,
                target_length=10000,
            ),
        ),
    )["proposal"]
    child = expansion(setup, parent, volume_index=1, chapter_start=1, chapter_count=1)
    apply(setup, accept(setup, child))
    return [graph_plan_id(parent["id"], "scene", f"v01_c001_s{i:02}") for i in (1, 2)]


def test_real_applied_local_metadata_reaches_scene_review_and_extraction_without_remap(setup):
    import json

    graph = setup[0]
    ids = applied(setup)
    original = copy.deepcopy(graph.nodes[ids[0]].properties)
    assert original["longform_scene_id"] == "v01_c001_s01"
    assert original["foreshadowing_seed_ids"] == ["brass_key"]
    assert graph.nodes[ids[1]].properties["causal_dependencies"] == ["v01_c001_s01"]
    drafts = SQLiteDraftStore()
    builder = ContextPackBuilder(graph, draft_store=drafts)
    pack = builder.build(project_id="project_test", scene_id=ids[0])
    assert not any(g.severity == "critical" for g in pack.missing_context)
    for sid in ids:
        snap = build_canon_snapshot(graph, project_id="project_test", scene_id=sid)
        assert snap.complete, snap.missing_context
        assert not snap.missing_context

    class Provider:
        def __init__(self):
            self.calls = 0

        def generate(self, request):
            self.calls += 1
            sent = json.loads(request.messages[-1].content)
            assert sent["canon"]["complete"]
            if "required_dimensions" in sent:
                return LLMResponse(
                    json.dumps(
                        {
                            "status": "pass",
                            "summary": "离线合成管线判断。",
                            "dimensions_checked": list(REVIEW_DIMENSIONS),
                            "issues": [],
                            "evidence_registry_id": sent["evidence_registry_id"],
                        },
                        ensure_ascii=False,
                    )
                )
            assert sent["source_draft_id"] and sent["source_draft_version"] == 1
            return LLMResponse('{"facts":[]}')

    provider = Provider()
    draft = drafts.create_draft(
        project_id="project_test",
        scene_id=ids[0],
        content_language="zh-CN",
        text="林舟停在门前，认真核对铜钥匙。",
        summary="他核对钥匙。",
    )
    snapshot = build_canon_snapshot(
        graph, project_id="project_test", scene_id=ids[0], target_text=draft.text
    )
    report = SemanticReviewService(provider, "offline-fixture").review(
        target=GenerationReviewTarget(
            project_id="project_test",
            scene_id=ids[0],
            target_type="draft",
            target_id=draft.id,
            target_version=draft.version,
            text=draft.text,
            output_language="zh-CN",
        ),
        canon=snapshot,
    )
    assert report.status == "pass" and provider.calls == 1
    assert (
        extract_natural_draft_state(
            graph=graph,
            project_id="project_test",
            source_draft=drafts.get_draft(draft.id),
            provider=provider,
            model="offline-fixture",
            output_language="zh-CN",
        )
        == []
    )
    assert provider.calls == 2 and graph.nodes[ids[0]].properties == original


@pytest.mark.parametrize(
    "field",
    [
        "chapter_id",
        "pov_character_id",
        "location_id",
        "previous_scene_id",
        "style_profile_id",
        "custom_id",
        "custom_ids",
        "required_characters",
    ],
)
def test_applied_scene_real_missing_references_stay_incomplete(setup, field):
    graph = setup[0]
    sid = applied(setup)[1]
    graph.nodes[sid].properties[field] = (
        ["missing"] if field in {"custom_ids", "required_characters"} else "missing"
    )
    snap = build_canon_snapshot(graph, project_id="project_test", scene_id=sid)
    assert not snap.complete and "missing_scene_reference" in snap.missing_context


@pytest.mark.parametrize("edge", ["CAUSES", "SEEDED_IN", "PAID_OFF_IN"])
def test_applied_scene_missing_planning_edge_is_not_hidden_by_metadata_exemption(setup, edge):
    graph = setup[0]
    applied(setup)
    relation = next(r for r in graph.relationships.values() if r.type == edge)
    sid = relation.target_id
    graph.relationships.pop(relation.id)
    pack = ContextPackBuilder(graph).build(project_id="project_test", scene_id=sid)
    assert any(g.kind == "missing_scene_plan_relation" for g in pack.missing_context)
    snap = build_canon_snapshot(graph, project_id="project_test", scene_id=sid)
    assert not snap.complete and "missing_scene_plan_relation" in snap.missing_context


def test_metadata_exemption_requires_bound_applied_identity_and_local_edge_match(setup):
    graph = setup[0]
    ids = applied(setup)
    graph.nodes[ids[0]].properties["longform_scene_id"] = "invented_metadata_id"
    assert not build_canon_snapshot(graph, project_id="project_test", scene_id=ids[0]).complete
    graph.nodes[ids[1]].properties["causal_dependencies"] = ["v01_c001_s99"]
    assert (
        "missing_scene_plan_relation"
        in build_canon_snapshot(graph, project_id="project_test", scene_id=ids[1]).missing_context
    )


def test_scene_metadata_handling_never_changes_project_plan_snapshot(setup):
    graph = setup[0]
    ids = applied(setup)
    before = build_canon_snapshot(graph, project_id="project_test", purpose="plan")
    build_canon_snapshot(graph, project_id="project_test", scene_id=ids[0])
    after = build_canon_snapshot(graph, project_id="project_test", purpose="plan")
    assert before.model_dump() == after.model_dump()


def test_metadata_recognition_uses_frozen_project_after_guard(setup, monkeypatch):
    from storygraph.services import canon_snapshot

    graph = setup[0]
    sid = applied(setup)[0]
    expected = build_canon_snapshot(graph, project_id="project_test", scene_id=sid)
    original = canon_snapshot._longform_scene_metadata
    seen = []

    def mutate_live_project(scene, project):
        assert project is not graph.nodes["project_test"]
        graph.nodes["project_test"].properties["longform_blueprint_id"] = "changed_after_read"
        seen.append(project.properties["longform_blueprint_id"])
        return original(scene, project)

    monkeypatch.setattr(canon_snapshot, "_longform_scene_metadata", mutate_live_project)
    captured = build_canon_snapshot(graph, project_id="project_test", scene_id=sid)
    assert len(seen) == 2 and len(set(seen)) == 1
    assert captured.model_dump() == expected.model_dump()


def test_metadata_value_collisions_do_not_select_unrelated_nodes(setup):
    graph = setup[0]
    sid = applied(setup)[0]
    properties = graph.nodes[sid].properties
    opaque_values = [properties["longform_blueprint_id"], properties["longform_scene_id"], "brass_key"]
    for ref in opaque_values:
        graph.seed_canon_node(node_id=ref, node_type="Item", properties={
            "project_id": "project_test", "name": "无关测试物品"})
    snapshot = build_canon_snapshot(graph, project_id="project_test", scene_id=sid)
    assert snapshot.complete
    assert not set(opaque_values).intersection(f.id for f in snapshot.facts)


def test_real_book_bundle_apply_preserves_local_metadata_and_has_complete_scene_scope(run_setup):
    from storygraph.models.longform import LongformApplyRequest
    from storygraph.services.book_bundle import apply_book_bundle
    from storygraph.stores.json_graph import save_json_graph

    graph, proposals, runs, _, _, service, path = run_setup
    done = service.execute(create(run_setup).id)
    accepted = proposals.review(
        done.bundle_proposal_id,
        decision="accepted",
        reviewer="author",
        expected_version=proposals.get(done.bundle_proposal_id).version,
    )
    apply_book_bundle(
        graph=graph,
        proposals=proposals,
        runs=runs,
        project_id="book",
        proposal_id=accepted.id,
        request=LongformApplyRequest(expected_version=accepted.version, reviewer="author"),
        persist_snapshot=lambda staged: save_json_graph(staged, path / "graph.json"),
    )
    scenes = [n for n in graph.nodes.values() if n.type == "Scene"]
    assert len(scenes) == 8
    for scene in scenes:
        assert scene.properties["longform_scene_id"].startswith("v")
        assert scene.properties["longform_blueprint_id"] not in graph.nodes
        snapshot = build_canon_snapshot(graph, project_id="book", scene_id=scene.id)
        assert snapshot.complete, snapshot.missing_context
