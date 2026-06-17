import pytest

from storygraph.core.errors import ContractError
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.candidate_store import SQLiteCandidateStore
from storygraph.stores.draft_store import SQLiteDraftStore


def test_sqlite_candidate_store_persists_candidates(tmp_path):
    store_path = tmp_path / "candidates.sqlite"
    draft = SQLiteDraftStore().create_draft(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
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
