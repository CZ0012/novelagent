import pytest

from storygraph.core.errors import ContractError
from storygraph.core.time import utc_now
from storygraph.models.proposal import ProposalArtifact, ProposalProvenance, ProposalRef
from storygraph.stores.proposal_store import SQLiteProposalStore


def test_sqlite_proposal_store_tracks_version_history(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    created = store.create(_proposal("proposal_plan"))

    author_revision = store.revise(
        created.id,
        actor="author",
        title="作者修订",
        body="作者调整后的提案。",
        expected_version=1,
    )
    agent_revision = store.revise(
        created.id,
        actor="agent",
        created_via="llm",
        body="Agent 根据作者要求继续修订。",
        expected_version=2,
        status="agent_revised",
    )
    ready = store.mark_ready(created.id, actor="author", expected_version=3)
    accepted = store.review(
        created.id,
        decision="accepted",
        reviewer="author",
        note="可以作为非正典提案继续使用。",
        expected_version=4,
    )

    assert author_revision.version == 2
    assert author_revision.status == "author_revised"
    assert agent_revision.version == 3
    assert agent_revision.status == "agent_revised"
    assert ready.status == "ready_for_review"
    assert accepted.version == 5
    assert accepted.status == "accepted"
    assert accepted.review_decision.status == "accepted"
    assert accepted.review_decision.reviewer == "author"

    history = store.history(created.id)
    assert [proposal.version for proposal in history] == [1, 2, 3, 4, 5]
    assert store.get(created.id).version == 5


def test_sqlite_proposal_store_rejects_duplicate_and_stale_versions(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    proposal = store.create(_proposal("proposal_unique"))

    with pytest.raises(ContractError, match="Duplicate ProposalArtifact"):
        store.create(_proposal("proposal_unique"))

    store.revise(proposal.id, actor="author", body="新版提案。", expected_version=1)

    with pytest.raises(ContractError, match="Stale ProposalArtifact version"):
        store.revise(proposal.id, actor="author", body="过期编辑。", expected_version=1)


def test_sqlite_proposal_store_lists_latest_versions_by_project(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    first = store.create(_proposal("proposal_first", project_id="project_alpha"))
    second = store.create(_proposal("proposal_second", project_id="project_beta"))
    store.revise(first.id, actor="agent", body="Agent 新版本。", status="agent_revised")

    alpha = store.list(project_id="project_alpha")
    beta = store.list(project_id="project_beta")
    agent_revised = store.list(project_id="project_alpha", status="agent_revised")

    assert [proposal.id for proposal in alpha] == [first.id]
    assert alpha[0].version == 2
    assert [proposal.id for proposal in beta] == [second.id]
    assert [proposal.id for proposal in agent_revised] == [first.id]


def test_sqlite_proposal_store_terminal_reviews_block_later_edits(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    proposal = store.create(_proposal("proposal_terminal"))

    rejected = store.review(proposal.id, decision="rejected", reviewer="author")

    assert rejected.status == "rejected"
    with pytest.raises(ContractError, match="already rejected"):
        store.revise(proposal.id, actor="author", body="不能再改。")


def test_sqlite_proposal_store_records_derived_refs_after_acceptance(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    proposal = store.create(_proposal("proposal_derived"))
    accepted = store.review(proposal.id, decision="accepted", reviewer="author")

    updated = store.record_derived_ref(
        proposal.id,
        derived_ref=ProposalRef(kind="draft", ref="draft_from_proposal"),
        actor="author",
        expected_version=accepted.version,
    )

    assert updated.version == accepted.version + 1
    assert updated.status == "accepted"
    assert updated.review_decision.status == "accepted"
    assert updated.derived_refs[-1].ref == "draft_from_proposal"


def test_sqlite_proposal_store_rejected_proposals_cannot_record_derived_refs(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    proposal = store.create(_proposal("proposal_rejected_derived"))
    rejected = store.review(proposal.id, decision="rejected", reviewer="author")

    with pytest.raises(ContractError, match="Rejected ProposalArtifact"):
        store.record_derived_ref(
            proposal.id,
            derived_ref=ProposalRef(kind="draft", ref="draft_blocked"),
            actor="author",
            expected_version=rejected.version,
        )


def _proposal(proposal_id: str, *, project_id: str = "project_alpha") -> ProposalArtifact:
    now = utc_now()
    return ProposalArtifact(
        id=proposal_id,
        project_id=project_id,
        artifact_type="scene_draft",
        status="drafting",
        title="协作草稿",
        body="非正典提案内容。",
        target_refs=[ProposalRef(kind="scene", ref="scene_opening")],
        source_refs=[ProposalRef(kind="author_instruction", ref="prompt:local")],
        provenance=ProposalProvenance(created_by="author", created_via="manual"),
        version=1,
        created_at=now,
        updated_at=now,
    )
