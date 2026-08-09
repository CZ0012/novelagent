from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.time import utc_now
from storygraph.demo import (
    ITEM_ID,
    LOCATION_ID,
    PROJECT_ID,
    SCENE_ID,
    build_fantasy_demo_graph,
)
from storygraph.services.review_service import ReviewService
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.candidate_store import InMemoryCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore


class FailingGraphStore:
    def __init__(self):
        self.graph = build_fantasy_demo_graph()

    def validate_candidate_scope(self, candidate, *, expected_project_id=None):
        return self.graph.validate_candidate_scope(
            candidate,
            expected_project_id=expected_project_id,
        )

    def commit_candidate_fact(self, *args, **kwargs):
        raise RuntimeError("graph commit failed")


class FailingCandidateUpdateStore(InMemoryCandidateStore):
    def update_if_pending(self, candidate):
        raise RuntimeError("candidate update failed")


def test_candidate_fact_requires_review_before_canon_commit():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "Lin Jin finds the clue. "
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=LOCATED_AT;"
            f"object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Item found.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    review = ReviewService(InMemoryCandidateStore(), graph)
    review.submit(candidates)

    assert len(review.pending(project_id=PROJECT_ID)) == 1
    assert not any(
        relation.type == "LOCATED_AT" and relation.source_id == ITEM_ID
        for relation in graph.relationships.values()
    )

    accepted = review.accept(candidates[0].id, reviewer="author", note="Seen in draft.")

    assert accepted.status == "ACCEPTED_FOR_CANON"
    assert accepted.review.status == "accepted"
    assert accepted.proposed_graph_patch.properties["project_id"] == PROJECT_ID
    assert any(
        relation.type == "LOCATED_AT"
        and relation.source_id == ITEM_ID
        and relation.target_id == LOCATION_ID
        and relation.properties["project_id"] == PROJECT_ID
        for relation in graph.relationships.values()
    )
    assert graph.event_log.list()


def test_duplicate_candidate_id_is_rejected():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "A clue appears. "
            f"[[fact:id=fact_duplicate;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Duplicate candidate.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    review = ReviewService(InMemoryCandidateStore(), graph)
    review.submit(candidates)

    with pytest.raises(ContractError, match="Duplicate CandidateFact id"):
        review.submit(candidates)


def test_reviewed_candidate_cannot_be_accepted_again():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "The clue moves. "
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=LOCATED_AT;"
            f"object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Item found.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    review = ReviewService(InMemoryCandidateStore(), graph)
    review.submit(candidates)

    review.accept(candidates[0].id, reviewer="author", note="Approved once.")
    event_count = len(graph.event_log.list())

    with pytest.raises(ContractError, match="already reviewed"):
        review.accept(candidates[0].id, reviewer="author", note="Approved twice.")

    assert len(graph.event_log.list()) == event_count


def test_rejected_candidate_cannot_later_be_accepted():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "The clue is uncertain. "
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=LOCATED_AT;"
            f"object={LOCATION_ID};confidence=0.5]]"
        ),
        summary="Uncertain item.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    review = ReviewService(InMemoryCandidateStore(), graph)
    review.submit(candidates)

    review.reject(candidates[0].id, reviewer="author", note="Not canon.")

    with pytest.raises(ContractError, match="already reviewed"):
        review.accept(candidates[0].id, reviewer="author", note="Changed mind.")


@pytest.mark.parametrize("action", ["accept", "edit_and_accept"])
def test_accept_does_not_persist_review_if_graph_commit_fails(action):
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "The clue fails to commit. "
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=LOCATED_AT;"
            f"object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Commit failure.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    candidate_store = InMemoryCandidateStore()
    failing_graph = FailingGraphStore()
    review = ReviewService(candidate_store, failing_graph)
    review.submit(candidates)
    nodes_before = dict(failing_graph.graph.nodes)
    relationships_before = dict(failing_graph.graph.relationships)
    events_before = failing_graph.graph.event_log.list()

    with pytest.raises(RuntimeError, match="graph commit failed"):
        if action == "accept":
            review.accept(candidates[0].id, reviewer="author", note="Should not persist.")
        else:
            review.edit_and_accept(
                candidates[0].id,
                reviewer="author",
                patch_properties={"state": "edited"},
                note="Should not persist.",
            )

    stored = candidate_store.get(candidates[0].id)
    assert stored.status == "DRAFT_FACT"
    assert stored.review.status == "pending"
    assert failing_graph.graph.nodes == nodes_before
    assert failing_graph.graph.relationships == relationships_before
    assert failing_graph.graph.event_log.list() == events_before


@pytest.mark.parametrize("action", ["accept", "edit_and_accept"])
def test_failed_review_persistence_never_reaches_graph(action):
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "The clue cannot be reviewed. "
            f"[[fact:fact_type=ItemState;subject={ITEM_ID};relation=HAS_STATE;"
            "operation=update_node;current_status=blocked;confidence=0.95]]"
        ),
        summary="Review write failure.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate_store = FailingCandidateUpdateStore()
    review = ReviewService(candidate_store, graph)
    review.submit([candidate])
    nodes_before = dict(graph.nodes)
    relationships_before = dict(graph.relationships)
    events_before = graph.event_log.list()

    with pytest.raises(RuntimeError, match="candidate update failed"):
        if action == "accept":
            review.accept(candidate.id, reviewer="author")
        else:
            review.edit_and_accept(
                candidate.id,
                reviewer="author",
                patch_properties={"current_status": "still blocked"},
            )

    stored = candidate_store.get(candidate.id)
    assert stored.status == "DRAFT_FACT"
    assert stored.review.status == "pending"
    assert graph.nodes == nodes_before
    assert graph.relationships == relationships_before
    assert graph.event_log.list() == events_before


def test_concurrent_accept_commits_canon_once_and_never_restores_pending():
    graph = build_fantasy_demo_graph()
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_concurrent_accept;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Concurrent accept.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate_store = InMemoryCandidateStore()
    reviews = [ReviewService(candidate_store, graph), ReviewService(candidate_store, graph)]
    reviews[0].submit([candidate])
    events_before = len(graph.event_log.list())
    barrier = Barrier(3)

    def accept_once(index, reviewer):
        barrier.wait()
        try:
            return reviews[index].accept(candidate.id, reviewer=reviewer)
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(accept_once, index, reviewer)
            for index, reviewer in enumerate(("one", "two"))
        ]
        barrier.wait()
        results = [future.result() for future in futures]

    assert sum(not isinstance(result, Exception) for result in results) == 1
    failure = next(result for result in results if isinstance(result, Exception))
    assert isinstance(failure, ContractError)
    assert "already reviewed" in str(failure)
    stored = candidate_store.get(candidate.id)
    assert stored.review.status == "accepted"
    assert stored.status == "ACCEPTED_FOR_CANON"
    assert len(graph.event_log.list()) == events_before + 1
    assert sum(
        relation.type == "LOCATED_AT"
        and relation.source_id == ITEM_ID
        and relation.target_id == LOCATION_ID
        for relation in graph.relationships.values()
    ) == 1


def test_concurrent_accept_and_reject_have_one_consistent_winner():
    graph = build_fantasy_demo_graph()
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_concurrent_mixed;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Concurrent mixed review.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate_store = InMemoryCandidateStore()
    reviews = [ReviewService(candidate_store, graph), ReviewService(candidate_store, graph)]
    reviews[0].submit([candidate])
    events_before = len(graph.event_log.list())
    barrier = Barrier(3)

    def run(index, action):
        barrier.wait()
        try:
            if action == "accept":
                return reviews[index].accept(candidate.id, reviewer="acceptor")
            return reviews[index].reject(candidate.id, reviewer="rejector")
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(run, index, action)
            for index, action in enumerate(("accept", "reject"))
        ]
        barrier.wait()
        results = [future.result() for future in futures]

    assert sum(not isinstance(result, Exception) for result in results) == 1
    failure = next(result for result in results if isinstance(result, Exception))
    assert isinstance(failure, ContractError)
    assert "already reviewed" in str(failure)
    stored = candidate_store.get(candidate.id)
    assert stored.review.status in {"accepted", "rejected"}
    relation_count = sum(
        relation.type == "LOCATED_AT"
        and relation.source_id == ITEM_ID
        and relation.target_id == LOCATION_ID
        for relation in graph.relationships.values()
    )
    if stored.review.status == "accepted":
        assert relation_count == 1
        assert len(graph.event_log.list()) == events_before + 1
    else:
        assert relation_count == 0
        assert len(graph.event_log.list()) == events_before


def test_submit_rejects_cross_project_batch_before_any_candidate_write():
    graph = build_fantasy_demo_graph()
    other_project_id = "project_other"
    graph.seed_canon_node(
        node_id=other_project_id,
        node_type="Project",
        properties={"project_id": other_project_id, "title": "Other"},
    )
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_valid_first;fact_type=ItemState;subject={ITEM_ID};"
            "relation=HAS_STATE;value=ready;confidence=0.9]]\n"
            f"[[fact:id=fact_cross_project;fact_type=ProjectState;subject={other_project_id};"
            "relation=HAS_STATE;value=mutated;confidence=0.9]]"
        ),
        summary="Mixed project candidates.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    candidate_store = InMemoryCandidateStore()
    review = ReviewService(candidate_store, graph)
    events_before = graph.event_log.list()

    with pytest.raises(ContractError, match="project scope violation"):
        review.submit(candidates)

    assert candidate_store.list() == []
    assert graph.get_node(other_project_id).properties["title"] == "Other"
    assert graph.event_log.list() == events_before


def test_accept_and_edit_accept_recheck_direct_pending_candidate_scope():
    graph = build_fantasy_demo_graph()
    other_project_id = "project_other"
    graph.seed_canon_node(
        node_id=other_project_id,
        node_type="Project",
        properties={"project_id": other_project_id, "title": "Other"},
    )
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_cross_accept;fact_type=ProjectState;subject={other_project_id};"
            "relation=HAS_STATE;value=accept;confidence=0.9]]\n"
            f"[[fact:id=fact_cross_edit;fact_type=ProjectState;subject={other_project_id};"
            "relation=HAS_STATE;value=edit;confidence=0.9]]"
        ),
        summary="Direct pending candidates.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    candidate_store = InMemoryCandidateStore()
    candidate_store.add_many(candidates)
    review = ReviewService(candidate_store, graph)
    events_before = graph.event_log.list()

    with pytest.raises(ContractError, match="project scope violation"):
        review.accept(candidates[0].id, reviewer="author")
    with pytest.raises(ContractError, match="project scope violation"):
        review.edit_and_accept(
            candidates[1].id,
            reviewer="author",
            patch_properties={"title": "Mutated"},
        )

    assert [candidate.review.status for candidate in candidate_store.list()] == [
        "pending",
        "pending",
    ]
    assert graph.get_node(other_project_id).properties["title"] == "Other"
    assert graph.event_log.list() == events_before


def test_graph_store_commit_rejects_cross_project_candidate_without_review_service():
    graph = build_fantasy_demo_graph()
    other_project_id = "project_other"
    graph.seed_canon_node(
        node_id=other_project_id,
        node_type="Project",
        properties={"project_id": other_project_id, "title": "Other"},
    )
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_direct_commit;fact_type=ProjectState;subject={other_project_id};"
            "relation=HAS_STATE;value=mutated;confidence=0.9]]"
        ),
        summary="Direct graph commit attempt.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    reviewed = candidate.model_copy(
        update={
            "status": "ACCEPTED_FOR_CANON",
            "review": candidate.review.model_copy(
                update={
                    "status": "accepted",
                    "reviewer": "author",
                    "reviewed_at": utc_now(),
                }
            ),
        }
    )
    events_before = graph.event_log.list()

    with pytest.raises(GraphStoreError, match="project scope violation"):
        graph.commit_candidate_fact(reviewed, reviewer="author", rationale="Unsafe")

    assert graph.get_node(other_project_id).properties["title"] == "Other"
    assert graph.event_log.list() == events_before


def test_update_relation_scope_checks_relationship_owner_and_endpoints():
    graph = build_fantasy_demo_graph()
    other_project_id = "project_other"
    other_character_id = "character_other"
    graph.seed_canon_node(
        node_id=other_project_id,
        node_type="Project",
        properties={"project_id": other_project_id, "title": "Other"},
    )
    graph.seed_canon_node(
        node_id=other_character_id,
        node_type="Character",
        properties={"project_id": other_project_id, "name": "Other"},
    )
    relation = graph.seed_canon_relation(
        relation_id="rel_cross_project_owner",
        relation_type="KNOWS",
        source_id=ITEM_ID,
        target_id=other_character_id,
        properties={"project_id": other_project_id},
    )
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_update_relation;fact_type=RelationshipState;subject={ITEM_ID};"
            f"relation=KNOWS;object={other_character_id};value=changed;confidence=0.9]]"
        ),
        summary="Cross-project relationship update.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate = candidate.model_copy(
        update={
            "proposed_graph_patch": candidate.proposed_graph_patch.model_copy(
                update={"operation": "update_relation", "target": relation.id}
            )
        }
    )
    review = ReviewService(InMemoryCandidateStore(), graph)

    with pytest.raises(ContractError, match="relationship belongs to another project"):
        review.submit([candidate])

    assert graph.get_relationship(relation.id) == relation

    mixed_relation = graph.seed_canon_relation(
        relation_id="rel_cross_project_endpoint",
        relation_type="KNOWS",
        source_id=ITEM_ID,
        target_id=other_character_id,
        properties={"project_id": PROJECT_ID},
    )
    endpoint_candidate = candidate.model_copy(
        update={
            "id": "fact_update_relation_endpoint",
            "proposed_graph_patch": candidate.proposed_graph_patch.model_copy(
                update={"target": mixed_relation.id}
            ),
        }
    )

    with pytest.raises(ContractError, match="relationship target node belongs"):
        review.submit([endpoint_candidate])


def test_update_relation_scope_requires_candidate_endpoint_semantics():
    graph = build_fantasy_demo_graph()
    relation = graph.get_relationship("rel_linj_knows_helianya")
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_wrong_relation_subject;fact_type=RelationshipState;"
            f"subject={ITEM_ID};relation=KNOWS;object={relation.target_id};"
            "value=changed;confidence=0.9]]"
        ),
        summary="Mismatched relationship subject.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate = candidate.model_copy(
        update={
            "proposed_graph_patch": candidate.proposed_graph_patch.model_copy(
                update={"operation": "update_relation", "target": relation.id}
            )
        }
    )

    with pytest.raises(ContractError, match="subject does not match"):
        ReviewService(InMemoryCandidateStore(), graph).submit([candidate])


def test_submit_requires_source_scene_to_be_same_project_scene():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_bad_source_scene;fact_type=ItemState;subject={ITEM_ID};"
            "relation=HAS_STATE;value=ready;confidence=0.9]]"
        ),
        summary="Invalid source scene.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate = candidate.model_copy(update={"source_scene_id": ITEM_ID})

    with pytest.raises(ContractError, match="source_scene_id is not a Scene"):
        ReviewService(InMemoryCandidateStore(), graph).submit([candidate])


def test_create_relation_id_collision_never_accepts_or_mutates_existing_canon():
    graph = build_fantasy_demo_graph()
    relation = graph.seed_canon_relation(
        relation_id="rel_fact_relation_collision",
        relation_type="OWNED_BY",
        source_id=ITEM_ID,
        target_id=LOCATION_ID,
        properties={"project_id": PROJECT_ID, "state": "original"},
    )
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_relation_collision;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};state=replacement;confidence=0.9]]"
        ),
        summary="Relationship id collision.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate_store = InMemoryCandidateStore()
    review = ReviewService(candidate_store, graph)
    events_before = graph.event_log.list()

    with pytest.raises(ContractError, match="relationship id already exists"):
        review.submit([candidate])
    assert candidate_store.list() == []

    candidate_store.add_many([candidate])
    with pytest.raises(ContractError, match="relationship id already exists"):
        review.accept(candidate.id, reviewer="author", note="Must conflict")

    stored = candidate_store.get(candidate.id)
    assert stored.status == "DRAFT_FACT"
    assert stored.review.status == "pending"
    assert graph.get_relationship(relation.id) == relation
    assert graph.event_log.list() == events_before

    reviewed = candidate.model_copy(
        update={
            "status": "ACCEPTED_FOR_CANON",
            "review": candidate.review.model_copy(
                update={
                    "status": "accepted",
                    "reviewer": "author",
                    "reviewed_at": utc_now(),
                }
            ),
        }
    )
    with pytest.raises(GraphStoreError, match="relationship id already exists"):
        graph.commit_candidate_fact(reviewed, reviewer="author", rationale="Must conflict")

    assert graph.get_relationship(relation.id) == relation
    assert graph.event_log.list() == events_before


def test_patch_source_ref_must_match_source_draft_for_every_operation():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_source_ref;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.9]]"
        ),
        summary="Mismatched graph patch source.",
    )
    base_candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    candidate_store = InMemoryCandidateStore()
    review = ReviewService(candidate_store, graph)
    events_before = graph.event_log.list()
    nodes_before = dict(graph.nodes)
    relationships_before = dict(graph.relationships)

    for operation in (
        "create_node",
        "update_node",
        "create_relation",
        "update_relation",
        "none",
    ):
        candidate = base_candidate.model_copy(
            update={
                "id": f"fact_source_ref_{operation}",
                "proposed_graph_patch": base_candidate.proposed_graph_patch.model_copy(
                    update={"operation": operation, "source_ref": "draft_other"}
                ),
            }
        )
        with pytest.raises(ContractError, match="source_ref does not match"):
            review.submit([candidate])

        reviewed = candidate.model_copy(
            update={
                "status": "ACCEPTED_FOR_CANON",
                "review": candidate.review.model_copy(
                    update={
                        "status": "accepted",
                        "reviewer": "author",
                        "reviewed_at": utc_now(),
                    }
                ),
            }
        )
        with pytest.raises(GraphStoreError, match="source_ref does not match"):
            graph.commit_candidate_fact(
                reviewed,
                reviewer="author",
                rationale="Mismatched provenance",
            )

    assert candidate_store.list() == []
    assert graph.nodes == nodes_before
    assert graph.relationships == relationships_before
    assert graph.event_log.list() == events_before


def test_update_node_literal_object_is_not_treated_as_graph_node():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    draft = draft_store.create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_literal_object;fact_type=ItemState;subject={ITEM_ID};"
            "relation=HAS_STATE;object=ordinary literal;operation=update_node;"
            "current_status=found;confidence=0.9]]"
        ),
        summary="Literal object compatibility.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    review = ReviewService(InMemoryCandidateStore(), graph)

    submitted = review.submit([candidate])
    accepted = review.accept(submitted[0].id, reviewer="author")

    assert accepted.review.status == "accepted"
    assert graph.get_node(ITEM_ID).properties["current_status"] == "found"
