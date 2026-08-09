import json
import sqlite3

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


def test_proposal_content_language_is_frozen_per_version_not_per_proposal(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite")
    created = store.create(_proposal("proposal_language_versions"))

    revised = store.revise(
        created.id,
        actor="agent",
        created_via="llm",
        content_language="en-US",
        title="English revision",
        body="A new English revision.",
        status="agent_revised",
    )

    history = store.history(created.id)
    assert history[0].content_language == "zh-CN"
    assert revised.content_language == "en-US"
    assert history[1].content_language == "en-US"
    with pytest.raises(ContractError, match="must preserve content_language"):
        store.mark_ready(
            created.id,
            actor="author",
            content_language="zh-CN",
        )


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


@pytest.mark.parametrize("transition", ["revise", "ready", "review", "derived"])
def test_legacy_proposal_requires_complete_content_revision_before_freezing_language(
    tmp_path,
    transition,
):
    path = tmp_path / f"legacy-{transition}.sqlite"
    proposal_id = f"proposal_legacy_{transition}"
    _seed_legacy_proposal(path, proposal_id)
    store = SQLiteProposalStore(path)
    legacy = store.get(proposal_id)

    assert legacy.content_language is None
    assert legacy.language_inferred is True

    def apply_transition(content_language=None, *, complete=False):
        common = {"content_language": content_language}
        if transition == "revise":
            return store.revise(
                proposal_id,
                actor="author",
                title="Complete English title" if complete else None,
                body="Complete English body." if complete else "Partial body.",
                **common,
            )
        if transition == "ready":
            return store.mark_ready(proposal_id, actor="author", **common)
        if transition == "review":
            return store.review(
                proposal_id,
                decision="accepted",
                reviewer="author",
                **common,
            )
        return store.record_derived_ref(
            proposal_id,
            derived_ref=ProposalRef(kind="draft", ref="draft_legacy"),
            actor="author",
            **common,
        )

    with pytest.raises(ContractError, match="legacy ProposalArtifact"):
        apply_transition()

    if transition != "revise":
        with pytest.raises(ContractError, match="complete title and body revision"):
            apply_transition("en-US")
        assert len(store.history(proposal_id)) == 1
        return

    with pytest.raises(ContractError, match="complete title and body revision"):
        apply_transition("en-US")
    frozen = apply_transition("en-US", complete=True)
    assert frozen.content_language == "en-US"
    assert frozen.language_inferred is False
    history = store.history(proposal_id)
    assert history[0].content_language is None
    assert history[1].content_language == "en-US"


def test_store_language_change_requires_complete_title_and_body_revision(tmp_path):
    store = SQLiteProposalStore(tmp_path / "proposal-language-change.sqlite")
    created = store.create(_proposal("proposal_language_change"))

    with pytest.raises(ContractError, match="complete title and body revision"):
        store.revise(
            created.id,
            actor="author",
            content_language="en-US",
            body="English body only.",
        )

    revised = store.revise(
        created.id,
        actor="author",
        content_language="en-US",
        title="English title",
        body="English body.",
    )
    assert revised.content_language == "en-US"
    assert store.get(created.id, version=1).content_language == "zh-CN"


def _proposal(proposal_id: str, *, project_id: str = "project_alpha") -> ProposalArtifact:
    now = utc_now()
    return ProposalArtifact(
        id=proposal_id,
        project_id=project_id,
        content_language="zh-CN",
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


def _seed_legacy_proposal(path, proposal_id: str) -> None:
    proposal = _proposal(proposal_id)
    payload = proposal.model_dump(exclude={"content_language", "language_inferred"})
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE proposal_artifacts (
          id TEXT NOT NULL, version INTEGER NOT NULL, project_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY (id, version)
        )
        """
    )
    connection.execute(
        "INSERT INTO proposal_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            proposal.id,
            proposal.version,
            proposal.project_id,
            proposal.artifact_type,
            proposal.status,
            proposal.created_at,
            proposal.updated_at,
            json.dumps(payload),
        ),
    )
    connection.commit()
    connection.close()
