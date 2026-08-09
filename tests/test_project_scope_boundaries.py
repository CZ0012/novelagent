import pytest

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.candidate import CandidateFact, ProposedGraphPatch, SourceSpan
from storygraph.services.canon_seed import AuthorCanonSeedService
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.graph_query import GraphQueryService
from storygraph.services.review_service import ReviewService
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.memory_graph import InMemoryGraphStore


PROJECT_A = "project_scope_a"
PROJECT_B = "project_scope_b"


def _scope_graph() -> InMemoryGraphStore:
    graph = InMemoryGraphStore()
    graph.seed_canon_node(
        node_id=PROJECT_A,
        node_type="Project",
        properties={"title": "Project A", "language": "en-US"},
    )
    graph.seed_canon_node(
        node_id=PROJECT_B,
        node_type="Project",
        properties={"title": "Project B", "language": "zh-CN"},
    )
    graph.seed_canon_node(
        node_id="chapter_scope_a",
        node_type="Chapter",
        properties={"project_id": PROJECT_A, "title": "Chapter A", "chapter_index": 1},
    )
    graph.seed_canon_node(
        node_id="chapter_scope_b",
        node_type="Chapter",
        properties={
            "project_id": PROJECT_B,
            "title": "B_PRIVATE_CHAPTER_SENTINEL",
            "chapter_index": 1,
        },
    )
    graph.seed_canon_node(
        node_id="location_scope_b",
        node_type="Location",
        properties={
            "project_id": PROJECT_B,
            "name": "B_PRIVATE_LOCATION_SENTINEL",
        },
    )
    return graph


def test_author_seed_rejects_cross_project_scene_reference_and_relation():
    graph = _scope_graph()
    service = AuthorCanonSeedService(graph)

    with pytest.raises(ContractError, match="does not belong"):
        service.add_scene(
            project_id=PROJECT_A,
            chapter_id="chapter_scope_a",
            node_id="scene_scope_a",
            title="Scene A",
            properties={"location_id": "location_scope_b"},
            reviewer="author",
            rationale="Synthetic project-scope regression fixture.",
            source_ref="test:project_scope",
        )

    with pytest.raises(ContractError, match="does not belong"):
        service.add_relation(
            project_id=PROJECT_A,
            relation_type="HAS_CHAPTER",
            source_id=PROJECT_A,
            target_id="chapter_scope_b",
            reviewer="author",
            rationale="Synthetic project-scope regression fixture.",
            source_ref="test:project_scope",
        )

    character = service.add_character(
        project_id=PROJECT_A,
        node_id="character_reserved_scope",
        name="Authoritative Name",
        properties={"project_id": PROJECT_B, "name": "B_PRIVATE_OVERRIDE_SENTINEL"},
        reviewer="author",
        rationale="Synthetic reserved-field regression fixture.",
        source_ref="test:project_scope",
    )
    assert character.properties["project_id"] == PROJECT_A
    assert character.properties["name"] == "Authoritative Name"
    assert "B_PRIVATE_OVERRIDE_SENTINEL" not in character.model_dump_json()


def test_outline_preview_and_context_fail_closed_for_corrupt_cross_project_refs():
    graph = _scope_graph()
    graph.seed_canon_node(
        node_id="scene_scope_corrupt",
        node_type="Scene",
        properties={
            "project_id": PROJECT_A,
            "chapter_id": "chapter_scope_a",
            "title": "Scene A",
            "scene_index": 1,
            "location_id": "location_scope_b",
            "required_characters": [],
        },
    )
    graph.seed_canon_relation(
        relation_id="rel_scope_a_chapter",
        relation_type="HAS_CHAPTER",
        source_id=PROJECT_A,
        target_id="chapter_scope_a",
        properties={"project_id": PROJECT_A},
    )
    graph.seed_canon_relation(
        relation_id="rel_scope_a_scene",
        relation_type="HAS_SCENE",
        source_id="chapter_scope_a",
        target_id="scene_scope_corrupt",
        properties={"project_id": PROJECT_A},
    )
    graph.seed_canon_relation(
        relation_id="rel_scope_corrupt_chapter",
        relation_type="HAS_CHAPTER",
        source_id=PROJECT_A,
        target_id="chapter_scope_b",
        properties={"project_id": PROJECT_A},
    )

    query = GraphQueryService(graph)
    outline = query.project_outline(project_id=PROJECT_A)
    preview = query.project_graph_preview(project_id=PROJECT_A)

    assert [chapter["id"] for chapter in outline["chapters"]] == ["chapter_scope_a"]
    assert "B_PRIVATE_CHAPTER_SENTINEL" not in str(outline)
    assert "B_PRIVATE_LOCATION_SENTINEL" not in str(preview)
    assert "location_scope_b" not in {node["id"] for node in preview["nodes"]}
    with pytest.raises(ContractError, match="does not belong"):
        ContextPackBuilder(graph).build(
            project_id=PROJECT_A,
            scene_id="scene_scope_corrupt",
        )


def test_character_knowledge_excludes_secrets_from_other_projects():
    graph = _scope_graph()
    graph.seed_canon_node(
        node_id="character_scope_a",
        node_type="Character",
        properties={"project_id": PROJECT_A, "name": "Character A"},
    )
    graph.seed_canon_node(
        node_id="secret_scope_a",
        node_type="Secret",
        properties={"project_id": PROJECT_A, "content": "Secret A"},
    )
    graph.seed_canon_node(
        node_id="secret_scope_b",
        node_type="Secret",
        properties={"project_id": PROJECT_B, "content": "B_PRIVATE_SECRET_SENTINEL"},
    )

    boundary = graph.get_character_knowledge("character_scope_a")

    assert boundary.does_not_know == ["secret_scope_a"]
    assert "secret_scope_b" not in boundary.model_dump_json()


@pytest.mark.parametrize("action", ["accept", "edit_and_accept"])
def test_candidate_review_cannot_modify_project_configuration(action):
    graph = _scope_graph()
    graph.seed_canon_node(
        node_id="scene_scope_a",
        node_type="Scene",
        properties={"project_id": PROJECT_A, "chapter_id": "chapter_scope_a"},
    )
    candidate = CandidateFact(
        id=f"fact_project_language_{action}",
        project_id=PROJECT_A,
        fact_type="ProjectState",
        subject_id=PROJECT_A,
        relation="HAS_STATE",
        value="zh-CN",
        source_scene_id="scene_scope_a",
        source_draft_id="draft_scope_a",
        source_span=SourceSpan(start_offset=0, end_offset=1, quote="x"),
        confidence=1.0,
        rationale="Synthetic project configuration bypass regression.",
        proposed_graph_patch=ProposedGraphPatch(
            operation="update_node",
            target=PROJECT_A,
            properties={"language": "zh-CN"} if action == "accept" else {},
            source_ref="draft_scope_a",
        ),
        created_at=utc_now(),
    )
    candidate_store = InMemoryCandidateStore()
    candidate_store.add_many([candidate])
    review = ReviewService(candidate_store, graph)
    events_before = list(graph.event_log.list())

    with pytest.raises(ContractError, match="cannot update Project"):
        if action == "accept":
            review.accept(candidate.id, reviewer="author")
        else:
            review.edit_and_accept(
                candidate.id,
                reviewer="author",
                patch_properties={"language": "zh-CN"},
            )

    assert graph.get_node(PROJECT_A).properties["language"] == "en-US"
    assert candidate_store.get(candidate.id).review.status == "pending"
    assert graph.event_log.list() == events_before


def test_candidate_scene_patch_rejects_cross_project_structural_reference():
    graph = _scope_graph()
    graph.seed_canon_node(
        node_id="scene_scope_a",
        node_type="Scene",
        properties={"project_id": PROJECT_A, "chapter_id": "chapter_scope_a"},
    )
    candidate = CandidateFact(
        id="fact_scene_cross_project_location",
        project_id=PROJECT_A,
        fact_type="SceneState",
        subject_id="scene_scope_a",
        relation="HAS_STATE",
        value="location_scope_b",
        source_scene_id="scene_scope_a",
        source_draft_id="draft_scope_a",
        source_span=SourceSpan(start_offset=0, end_offset=1, quote="x"),
        confidence=1.0,
        rationale="Synthetic cross-project Scene reference regression.",
        proposed_graph_patch=ProposedGraphPatch(
            operation="update_node",
            target="scene_scope_a",
            properties={"location_id": "location_scope_b"},
            source_ref="draft_scope_a",
        ),
        created_at=utc_now(),
    )

    with pytest.raises(ContractError, match="belongs to another project"):
        ReviewService(InMemoryCandidateStore(), graph).submit([candidate])

    assert "location_id" not in graph.get_node("scene_scope_a").properties
