"""Service/CLI regression coverage for opt-in review-first generation."""

import json

import pytest

from apps.cli.main import run_scene_command, write_scene_command
from storygraph.core.errors import GraphStoreError
from storygraph.core.time import utc_now
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.models.proposal import ProposalArtifact, ProposalProvenance, ProposalRef
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.continuity_checker import RuleBasedContinuityChecker
from storygraph.services.manuscript_composition import CompositionApplyRequest, apply_composition
from storygraph.services.scene_writer import RuleBasedSceneWriter
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.json_graph import save_json_graph
from storygraph.stores.proposal_store import SQLiteProposalStore
from storygraph.workflows import SceneGenerationWorkflow


SEED = {"reviewer": "author", "rationale": "Synthetic quality policy test.", "source_ref": "test:quality"}


def opt_in(graph):
    graph.update_node(PROJECT_ID, {"require_semantic_review": True}, **SEED)


@pytest.mark.parametrize("kind", ["local", "langgraph"])
def test_workflow_blocks_direct_draft_before_writer_but_allows_isolated_proposal(kind):
    if kind == "langgraph":
        pytest.importorskip("langgraph")
    graph = build_fantasy_demo_graph()
    opt_in(graph)
    drafts, proposals = SQLiteDraftStore(), SQLiteProposalStore()
    class Writer(RuleBasedSceneWriter):
        calls = 0
        def draft(self, context):
            self.calls += 1
            return super().draft(context)
    writer = Writer(drafts)
    workflow = SceneGenerationWorkflow(context_builder=ContextPackBuilder(graph, drafts), writer=writer,
        checker=RuleBasedContinuityChecker(), extractor=RuleBasedStateExtractor(),
        proposal_store=proposals, runtime_kind=kind)
    try:
        events = list(graph.event_log.list())
        with pytest.raises(GraphStoreError) as error:
            workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID)
        assert error.value.category == "generation_review_required" and writer.calls == 0
        assert drafts.latest_for_scene(PROJECT_ID, SCENE_ID) is None
        assert proposals.list() == []
        result = workflow.run(project_id=PROJECT_ID, scene_id=SCENE_ID, output_target="proposal_workspace")
        assert result.proposal is not None and result.draft is None
        assert result.continuity_report is None and result.candidates == []
        assert drafts.latest_for_scene(PROJECT_ID, SCENE_ID) is None
        assert len(proposals.list()) == 1 and writer.calls == 1
        assert graph.event_log.list() == events
    finally:
        workflow.close()


def composition_fixture():
    graph = build_fantasy_demo_graph("zh-CN")
    drafts, proposals = SQLiteDraftStore(), SQLiteProposalStore()
    now = utc_now()
    body = {"schema": "manuscript_composition_v1", "project_id": PROJECT_ID, "output_language": "zh-CN",
        "scope": "chapter", "volume_index": 1, "base_chapter_index": 100, "volume_title": None,
        "chapters": [{"title": "合成新章", "summary": "林烬来到港口。", "purpose": "推动调查。", "scenes": [
            {"title": "港口来信", "summary": "林烬收到来信。", "goal": "找到信使。", "conflict": "信使拒绝见面。",
             "prose": "林烬收起信，沿着石阶走向港口。"}]}]}
    proposal = proposals.create(ProposalArtifact(id="proposal_composition_quality", project_id=PROJECT_ID,
        content_language="zh-CN", artifact_type="outline_draft", title="合成章节提案",
        body=json.dumps(body, ensure_ascii=False), body_format="structured_json",
        target_refs=[ProposalRef(kind="project", ref=PROJECT_ID)],
        provenance=ProposalProvenance(created_by="agent", created_via="llm"), version=1,
        created_at=now, updated_at=now))
    accepted = proposals.review(proposal.id, decision="accepted", reviewer="author", expected_version=1)
    return graph, drafts, proposals, accepted


def apply_fixture(graph, drafts, proposals, accepted):
    return apply_composition(graph=graph, draft_store=drafts, proposal_store=proposals,
        project_id=PROJECT_ID, proposal_id=accepted.id,
        request=CompositionApplyRequest(expected_version=accepted.version, reviewer="author"),
        persist_snapshot=lambda _: None)


def test_opted_in_composition_apply_never_creates_graph_or_initial_prose():
    graph, drafts, proposals, accepted = composition_fixture()
    opt_in(graph)
    before = dict(graph.nodes), dict(graph.relationships), list(graph.event_log.list())
    with pytest.raises(GraphStoreError) as error:
        apply_fixture(graph, drafts, proposals, accepted)
    assert error.value.category == "generation_review_required"
    assert (graph.nodes, graph.relationships, graph.event_log.list()) == before
    assert proposals.get(accepted.id).derived_refs == []


def test_completed_legacy_composition_retry_preserved_after_project_opts_in():
    graph, drafts, proposals, accepted = composition_fixture()
    first = apply_fixture(graph, drafts, proposals, accepted)
    opt_in(graph)
    before = list(graph.event_log.list())
    retry = apply_fixture(graph, drafts, proposals, accepted)
    assert retry["already_applied"]
    assert [d["id"] for d in retry["drafts"]] == [d["id"] for d in first["drafts"]]
    assert graph.event_log.list() == before


def test_cli_direct_generation_and_workflow_cannot_bypass_but_manual_save_works(tmp_path, monkeypatch):
    graph = build_fantasy_demo_graph("zh-CN")
    opt_in(graph)
    save_json_graph(graph, tmp_path / "graph.json")
    called = []
    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError("A blocked generation must not construct a provider.")
    monkeypatch.setattr("apps.cli.main.create_scene_writer", forbidden)
    with pytest.raises(GraphStoreError) as error:
        write_scene_command(workspace=tmp_path, project_id=PROJECT_ID, scene_id=SCENE_ID)
    assert error.value.category == "generation_review_required" and not called
    # Workflow guard is in the shared runtime; its constructor may create a
    # writer, but .run rejects before that writer generates any prose.
    monkeypatch.undo()
    with pytest.raises(GraphStoreError) as error:
        run_scene_command(workspace=tmp_path, project_id=PROJECT_ID, scene_id=SCENE_ID)
    assert error.value.category == "generation_review_required"
    manual = write_scene_command(workspace=tmp_path, project_id=PROJECT_ID, scene_id=SCENE_ID, text="作者保存的文字。")
    assert manual["text"] == "作者保存的文字。"
