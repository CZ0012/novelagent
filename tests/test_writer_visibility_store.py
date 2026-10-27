"""Disclosure settings preserve local CAS history without touching canon stores."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from storygraph.core.errors import ContractError
from storygraph.stores.proposal_store import SQLiteProposalStore
from storygraph.stores.writer_visibility_store import SQLiteWriterVisibilityStore


def save(store, project="p", scene=None, expected=0, spec=None):
    return store.save(project_id=project, scene_id=scene, expected_version=expected,
        spec=spec if spec is not None else {"access_mode": "surface"},
        source_context_sha256="a"*64 if scene else None)


def test_local_policy_cas_persistence_scopes_and_clear_preserve_history(tmp_path):
    path = tmp_path/"proposals.sqlite"
    proposals = SQLiteProposalStore(path)
    store = SQLiteWriterVisibilityStore(proposals)
    first = save(store)
    assert first["version"] == 1 and store.effective("p", "s") == first
    override = save(store, scene="s")
    assert store.effective("p", "s")["scene_id"] == "s"
    assert store.effective("q", "s") is None
    with pytest.raises(ContractError, match="stale_version"):
        save(store, scene="s", expected=0)
    tombstone = store.save(project_id="p", scene_id="s", expected_version=override["version"],
        spec=None, source_context_sha256=None)
    assert tombstone["version"] == 2 and store.effective("p", "s") == first
    assert len(store.history("p", "s")) == 2
    assert proposals.list() == []
    proposals.close()
    reopened = SQLiteProposalStore(path)
    assert SQLiteWriterVisibilityStore(reopened).history("p", "s")[-1] == tombstone
    reopened.close()


def test_competing_same_version_policy_write_has_one_winner():
    proposals = SQLiteProposalStore()
    store = SQLiteWriterVisibilityStore(proposals)
    def write(_):
        try:
            return save(store)
        except ContractError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(write, range(2)))
    assert sum(value is not None for value in values) == 1
    assert len(store.history("p")) == 1
    proposals.close()
