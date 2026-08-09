import pytest

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.candidate_store import SQLiteCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore


def test_sqlite_candidate_store_persists_candidates(tmp_path):
    store_path = tmp_path / "candidates.sqlite"
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "A fact marker. "
            f"[[fact:id=fact_persisted;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Persistence test.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]

    first_store = SQLiteCandidateStore(store_path)
    first_store.add(candidate)
    second_store = SQLiteCandidateStore(store_path)

    loaded = second_store.get(candidate.id)
    assert loaded == candidate
    assert second_store.list(project_id=PROJECT_ID, pending_only=True)[0].id == candidate.id


def test_sqlite_candidate_store_rejects_duplicate_ids(tmp_path):
    store = SQLiteCandidateStore(tmp_path / "candidates.sqlite")
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            "A fact marker. "
            f"[[fact:id=fact_duplicate_sqlite;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Duplicate test.",
    )
    candidate = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    store.add(candidate)

    with pytest.raises(ContractError, match="Duplicate CandidateFact id"):
        store.add(candidate)


def test_sqlite_candidate_store_add_many_is_atomic_on_existing_id(tmp_path):
    store = SQLiteCandidateStore(tmp_path / "candidates.sqlite")
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_batch_new;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]\n"
            f"[[fact:id=fact_batch_existing;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Atomic batch test.",
    )
    candidates = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)
    store.add(candidates[1])

    with pytest.raises(ContractError, match="Duplicate CandidateFact id"):
        store.add_many(candidates)

    assert [candidate.id for candidate in store.list(project_id=PROJECT_ID)] == [
        "fact_batch_existing"
    ]


def test_sqlite_candidate_review_transition_is_compare_and_set(tmp_path):
    store_path = tmp_path / "candidates.sqlite"
    first = SQLiteCandidateStore(store_path)
    second = SQLiteCandidateStore(store_path)
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
        content_language="en-US",
        text=(
            f"[[fact:id=fact_review_cas;fact_type=ItemState;subject={ITEM_ID};"
            f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
        ),
        summary="Review CAS test.",
    )
    pending = RuleBasedStateExtractor().extract(project_id=PROJECT_ID, draft=draft)[0]
    reviewed = pending.model_copy(
        update={
            "status": "ACCEPTED_FOR_CANON",
            "review": pending.review.model_copy(
                update={
                    "status": "accepted",
                    "reviewer": "first",
                    "reviewed_at": utc_now(),
                }
            ),
        }
    )
    first.add(pending)

    first.update_if_pending(reviewed)
    with pytest.raises(ContractError, match="already reviewed"):
        second.update_if_pending(reviewed.model_copy())

    wrong_expected = reviewed.model_copy(
        update={"review": reviewed.review.model_copy(update={"reviewer": "other"})}
    )
    assert not second.replace_if_current(pending, expected=wrong_expected)
    assert second.get(pending.id) == reviewed
    assert second.replace_if_current(pending, expected=reviewed)
    assert first.get(pending.id) == pending
