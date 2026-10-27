"""LangGraph persists permission fingerprints, never live resolver functions."""

import importlib.util
import json
import pytest
from storygraph.core.errors import ContractError
from storygraph.core.agent_config import AgentPreset
from storygraph.models.writer_visibility import WriterVisibilityRecord
from storygraph.services.writer_visibility import resolve_writer_visibility
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.services.continuity_checker import RuleBasedContinuityChecker
from storygraph.services.state_extraction import RuleBasedStateExtractor
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.workflows.scene_generation_runtime import (
    LangGraphSceneGenerationRuntime,
    SceneGenerationServices,
)
from test_knowledge_entry import graph as graph
from test_writer_visibility import Capture, spec

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("langgraph") is None,
    reason="Optional LangGraph dependency unavailable",
)


def configured(graph, tmp_path):
    live = {"enabled": True, "version": 1}

    def resolver(pack):
        if not live["enabled"]:
            return None
        record = WriterVisibilityRecord(
            project_id="p",
            scene_id=None,
            version=live["version"],
            spec=spec(),
            source_context_sha256=None,
            configured_by="synthetic_fixture",
            configured_at="now",
        )
        return resolve_writer_visibility(pack, record)

    drafts = SQLiteDraftStore()
    provider = Capture()
    builder = ContextPackBuilder(graph, drafts, writer_visibility_resolver=resolver)
    services = SceneGenerationServices(
        builder,
        LLMSceneWriter(provider=provider, model="fixture", draft_store=drafts),
        RuleBasedContinuityChecker(),
        RuleBasedStateExtractor(),
        workflow_store=SQLiteWorkflowStore(),
    )
    runtime = LangGraphSceneGenerationRuntime(
        services, checkpoint_path=tmp_path / "checkpoint.sqlite"
    )
    return live, provider, runtime, services


def build_state(runtime):
    run = runtime._start_run(project_id="p", scene_id="s1")
    state = {"project_id": "p", "scene_id": "s1", "run": run.model_dump(), "candidates": []}
    state.update(runtime._lg_build_context(state))
    return state


def test_same_policy_real_checkpoint_reopens_and_writes_with_fresh_sidecar(graph, tmp_path):
    live, provider, first, services = configured(graph, tmp_path)
    services.writer.agent_preset = AgentPreset(
        id="custom_workflow_hidden",
        name="配置但不发送",
        system_prompt="WORKFLOW_PRESET_NOT_TRANSMITTED",
    )
    run = first._start_run(project_id="p", scene_id="s1")
    config = {"configurable": {"thread_id": run.id}}
    state = first._app.invoke(
        {"project_id": "p", "scene_id": "s1", "run": run.model_dump(), "candidates": []},
        config=config,
        interrupt_before=["write_draft"],
    )
    encoded = json.dumps(state)
    assert state["context_pack"]["writer_visibility_required"] is True
    assert state["writer_visibility_checkpoint"]["required"] is True
    assert "reader_source_resolver" not in encoded and "configured_by" not in encoded
    assert not provider.requests
    first.close()
    second = LangGraphSceneGenerationRuntime(
        services, checkpoint_path=tmp_path / "checkpoint.sqlite"
    )
    try:
        done = second._app.invoke(None, config=config)
    finally:
        second.close()
    assert len(provider.requests) == 1 and done["draft"]["text"] == "林烬核对门上的刻痕。"
    payload = json.loads(provider.requests[0].messages[-1].content)
    assert payload["writer_view"]["isolated"] is True and "context_pack" not in payload
    assert "WORKFLOW_PRESET_NOT_TRANSMITTED" not in "".join(
        m.content for m in provider.requests[0].messages
    )
    assert done["draft"]["provenance"]["writer_visibility"]["preset_transmitted"] is False
    write_step = next(step for step in done["run"]["steps"] if step["name"] == "write_draft")
    assert write_step["artifact_refs"]["agent_preset_transmitted"] is False
    assert "agent_preset_id" not in write_step["artifact_refs"]


@pytest.mark.parametrize(
    "change",
    ["source", "policy", "revoked", "marker", "required_marker", "both_markers_and_revoke"],
)
def test_checkpoint_changes_fail_closed_without_provider(graph, tmp_path, change):
    live, provider, runtime, _ = configured(graph, tmp_path)
    state = build_state(runtime)
    if change == "source":
        graph.nodes["s1"].properties["goal"] += "来源改变。"
    elif change == "policy":
        live["version"] = 2
    elif change == "revoked":
        live["enabled"] = False
    elif change == "marker":
        state.pop("writer_visibility_checkpoint")
    elif change == "required_marker":
        state["context_pack"].pop("writer_visibility_required")
    else:
        state.pop("writer_visibility_checkpoint")
        state["context_pack"].pop("writer_visibility_required")
        live["enabled"] = False
    try:
        with pytest.raises(ContractError, match="writer_visibility_"):
            runtime._lg_write_draft(state)
    finally:
        runtime.close()
    assert provider.requests == []


@pytest.mark.parametrize("new_policy", [False, True])
def test_historical_legacy_checkpoint_only_stays_legacy_when_still_unconfigured(
    graph, tmp_path, new_policy
):
    live, provider, runtime, _ = configured(graph, tmp_path)
    live["enabled"] = False
    state = build_state(runtime)
    state.pop("writer_visibility_checkpoint")
    state["context_pack"].pop("writer_visibility_required")
    live["enabled"] = new_policy
    try:
        if new_policy:
            with pytest.raises(ContractError, match="marker_missing"):
                runtime._lg_write_draft(state)
            assert not provider.requests
        else:
            runtime._lg_write_draft(state)
            payload = json.loads(provider.requests[0].messages[-1].content)
            assert payload["writer_mode"] == "legacy_unisolated" and "context_pack" in payload
    finally:
        runtime.close()
