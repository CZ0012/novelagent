"""Visibility API and critic/adoption use local versioned policy, never canon mutation."""
# ruff: noqa: E402 -- main's module-level app requires pre-import workspace/key isolation.
import os
import tempfile
from unittest.mock import patch
# main creates its module-level app during import: never inherit a real workspace/key.
with patch.dict(os.environ):
    os.environ["STORYGRAPH_HOME"] = tempfile.mkdtemp(prefix="storygraph-visibility-import-")
    os.environ["STORYGRAPH_GRAPH_BACKEND"] = "json"
    os.environ["STORYGRAPH_SCENE_WRITER"] = "rule_based"
    for _key in ("STORYGRAPH_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        os.environ.pop(_key, None)
    from apps.api import main
# Restore the complete original environment for other test modules.
import json
import pytest
from fastapi.testclient import TestClient
from storygraph.core.config import StoryGraphSettings
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services.canon_snapshot import build_canon_snapshot, content_hash
from storygraph.services.llm_provider import LLMResponse
from storygraph.stores.json_graph import save_json_graph
from storygraph.models.generation_review import REVIEW_DIMENSIONS


@pytest.fixture
def environment(tmp_path, monkeypatch):
    graph = build_fantasy_demo_graph("zh-CN")
    graph.nodes[PROJECT_ID].properties["require_semantic_review"] = True
    settings = StoryGraphSettings(tmp_path)
    settings.llm_base_url, settings.llm_api_key, settings.llm_model = "https://synthetic.invalid", "synthetic-only", "fixture"
    settings.scene_writer = "llm"
    save_json_graph(graph, settings.graph_path)
    class Provider:
        def __init__(self): self.requests = []
        def generate(self, request):
            self.requests.append(request)
            sent = json.loads(request.messages[-1].content)
            if "required_dimensions" in sent:
                return LLMResponse(json.dumps({"status":"pass","summary":"合成离线审查。","issues":[],"dimensions_checked":list(REVIEW_DIMENSIONS),"evidence_registry_id":sent["evidence_registry_id"]}, ensure_ascii=False))
            if (sent.get("action") or sent.get("mode")) in {"create_scene", "continue_scene", "revise_scene", "revise_selection"}:
                return LLMResponse(json.dumps({"reply":"已按批准范围写作。","proposal_title":"门前的封蜡","proposal_body":"林烬站在门前，仔细看着封蜡。","continuation_text":"林烬核对封蜡。","replacement_text":"他仔细核对。"},ensure_ascii=False))
            # Synthetic text satisfies the explicitly approved scene literal requirements.
            body = "林烬站在门前，仔细看着封蜡。" + "；".join(graph.nodes[SCENE_ID].properties.get("must_include", []))
            return LLMResponse(json.dumps({"text":body,"summary":"他核对封蜡。","self_check":["保持边界。"]},ensure_ascii=False))
    provider = Provider()
    monkeypatch.setattr(main, "create_llm_provider", lambda _: provider)
    monkeypatch.setattr("storygraph.services.scene_writer_factory.create_llm_provider", lambda _: provider)
    app = main.create_app(settings)
    app.state.synthetic_settings = settings
    return TestClient(app), app, provider


def spec(pack):
    return {"access_mode":"pov", "surface_plan":{"kind":"literal","text":"主角只在门前观察封蜡，不揭露其它事实。"},"writer_style":{"pov":"第三人称有限视角","tone":"克制"},"characters":[{"character_id":pack["pov_character_id"],"public_name":"林烬"}],"visible_claims":[{"text":"主角相信自己应先核对封蜡。","presentation":"belief","phase":"entry","character_id":pack["pov_character_id"]}, *[{"text":text,"presentation":"observation","phase":"during_scene"} for text in pack.get("must_include", [])]],"reader_presented":[],"expected_reader_inference":"AUTHOR_PRIVATE_INFERENCE_SENTINEL"}


def info(client):
    return client.get(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/writer-visibility").json()


def save_policy(client, value, expected=0):
    data=info(client)
    return client.put(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/writer-visibility",json={"expected_version":expected,"spec":value,"expected_source_context_sha256":data["source_context_sha256"]})


def test_policy_cas_preview_blocks_missing_and_preserves_plan_canon(environment):
    client, app, provider = environment
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack", json={}).json()
    before = build_canon_snapshot(app.state.writer_visibility_context_builder.graph_store, project_id=PROJECT_ID, purpose="plan").model_dump()
    assert client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/writer-visibility/preview",json={}).status_code == 409
    policy=spec(pack)
    saved=save_policy(client,policy)
    assert saved.status_code==200,saved.text
    assert save_policy(client,policy).status_code==409
    preview=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/writer-visibility/preview",json={})
    assert preview.status_code==200,preview.text
    messages=json.dumps(preview.json()["messages"],ensure_ascii=False)
    assert "AUTHOR_PRIVATE_INFERENCE_SENTINEL" not in messages
    assert pack["pov_character_id"] not in messages
    assert "主角相信自己应先核对封蜡" in messages
    assert build_canon_snapshot(app.state.writer_visibility_context_builder.graph_store,project_id=PROJECT_ID,purpose="plan").model_dump()==before
    assert provider.requests==[]


def test_stale_scene_source_and_foreign_reader_are_rejected_before_provider(environment):
    client, app, provider = environment
    pack=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack",json={}).json()
    policy=spec(pack)
    assert save_policy(client,policy).status_code==200
    graph=app.state.writer_visibility_context_builder.graph_store
    graph.nodes[SCENE_ID].properties["goal"] += "当前来源已变。"
    assert client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/writer-visibility/preview",json={}).status_code==409
    assert client.post(f"/projects/{PROJECT_ID}/proposals/none/revise",json={}).status_code in {404,409,422}
    # Reader source version/hash/UTF16 is checked, never arbitrary file/URL fields.
    draft=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft",json={"text":"甲😀乙"}).json()
    bad=spec(pack)
    bad["reader_presented"]=[{"draft_id":draft["id"],"version":draft["version"],"text_sha256":content_hash("甲😀乙"),"start":1,"end":2,"expected_text":"😀","presentation":"clue"}]
    assert save_policy(client,bad,expected=1).status_code==409
    bad["reader_presented"][0].update(start=1,end=3)
    assert save_policy(client,bad,expected=1).status_code==200
    assert provider.requests==[]


def test_scene_review_policy_freshness_and_adoption_gate(environment):
    client, app, provider=environment
    pack=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack",json={}).json()
    policy=spec(pack)
    assert save_policy(client,policy).status_code==200
    proposal=client.post(f"/projects/{PROJECT_ID}/proposals",json={"artifact_type":"scene_draft","title":"合成正文","body":"林烬站在门前，核对封蜡。","target_refs":[{"kind":"scene","ref":SCENE_ID}]}).json()
    reviewed=client.post(f"/projects/{PROJECT_ID}/generation-reviews",json={"target_type":"proposal","target_id":proposal["id"],"expected_version":proposal["version"]})
    assert reviewed.status_code==200,reviewed.text
    assert reviewed.json()["current"]
    sent=json.loads(provider.requests[-1].messages[-1].content)
    assert "narrative_disclosure_policy" in sent["style_sources"]
    assert "AUTHOR_PRIVATE_INFERENCE_SENTINEL" in sent["style_sources"]["narrative_disclosure_policy"]
    changed=spec(pack)
    changed["expected_reader_inference"]="另一项私有预期"
    assert save_policy(client,changed,expected=1).status_code==200
    history=client.get(f"/projects/{PROJECT_ID}/generation-reviews",params={"target_type":"proposal","target_id":proposal["id"]}).json()["reports"]
    assert next(x for x in history if x["report"]["id"]==reviewed.json()["report"]["id"])["current"] is False
    with pytest.raises(Exception):
        app.state.require_generation_review(PROJECT_ID,proposal["id"],reviewed.json()["report"]["id"])


def test_protected_actual_prose_entrypoints_block_or_share_projected_view(environment):
    client, app, provider = environment
    created = client.post(f"/projects/{PROJECT_ID}/proposals", json={"artifact_type":"scene_draft","title":"待改合成正文","body":"主角停在门前。","target_refs":[{"kind":"scene","ref":SCENE_ID}]}).json()
    assert client.post(f"/projects/{PROJECT_ID}/proposals/{created['id']}/revise",json={"expected_version":created["version"]}).status_code==409
    assert client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation",json={}).status_code==409
    assert provider.requests==[]
    pack=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack",json={}).json()
    policy=spec(pack)
    assert save_policy(client,policy).status_code==200
    response=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion",json={"mode":"create_scene","instruction":policy["surface_plan"]["text"],"include_context_pack":True,"include_latest_draft":False})
    assert response.status_code==200,response.text
    wire=json.dumps([m.content for m in provider.requests[-1].messages],ensure_ascii=False)
    assert "AUTHOR_PRIVATE_INFERENCE_SENTINEL" not in wire and pack["pov_character_id"] not in wire
    draft = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft", json={"text":"待续的作者原稿。"}).json()
    before=len(provider.requests)
    blocked=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion",json={"mode":"continue_scene","instruction":"不要透露AUTHOR_PRIVATE_TRUTH","include_context_pack":True,"include_latest_draft":True,"included_draft_id":draft["id"]})
    assert blocked.status_code==409 and len(provider.requests)==before


def test_reader_refs_are_project_scoped_and_no_external_source_shape(environment):
    client, app, provider=environment
    pack=client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack",json={}).json()
    graph=app.state.writer_visibility_context_builder.graph_store
    other=client.post("/projects",json={"title":"其他合成项目"}).json()["project_id"]
    # Resolve a foreign Draft only from this isolated app's same workspace, never external data.
    drafts=app.state.writer_visibility_context_builder.draft_store
    foreign=drafts.create_draft(project_id=other,scene_id="other-scene",content_language="zh-CN",text="外项目文本")
    policy=spec(pack)
    policy["reader_presented"]=[{"draft_id":foreign.id,"version":foreign.version,"text_sha256":content_hash(foreign.text),"start":0,"end":len(foreign.text),"expected_text":foreign.text,"presentation":"narration"}]
    assert save_policy(client,policy).status_code==409
    policy=spec(pack)
    policy["reader_presented"]=[{"url":"https://invalid.example/private"}]
    assert save_policy(client,policy).status_code==422
    assert provider.requests==[] and graph.nodes[PROJECT_ID].properties.get("require_semantic_review")


def test_explicit_edit_grants_preview_equal_actual_and_reject_stale_or_extra_sources(environment):
    client, app, provider = environment
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack", json={}).json()
    text = "AUTHOR_ONLY_PREFIX😀目标选区AUTHOR_ONLY_SUFFIX"
    draft = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft", json={"text": text}).json()
    assert save_policy(client, spec(pack)).status_code == 200
    endpoint = f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion"
    instruction = "只调整已授权文字的动作节奏。"
    grant = {"instruction": True, "instruction_sha256": content_hash(instruction),
             "target": "draft", "draft_id": draft["id"], "version": draft["version"], "text_sha256": content_hash(text)}
    for mode in ("continue_scene", "revise_scene", "revise_selection"):
        current = dict(grant)
        payload = {"mode": mode, "instruction": instruction, "include_latest_draft": True,
                   "included_draft_id": draft["id"], "include_context_pack": True, "prose_input_grants": current}
        if mode == "revise_selection":
            start = len("AUTHOR_ONLY_PREFIX😀".encode("utf-16-le")) // 2
            current.update(target="selection", start=start, end=start+4, expected_text="目标选区", offset_unit="utf16")
            payload.update(selected_start=start, selected_end=start+4, selected_text="目标选区")
        before = len(provider.requests)
        preview = client.post(endpoint+"/preview", json=payload)
        assert preview.status_code == 200, preview.text
        assert len(provider.requests) == before
        result = client.post(endpoint, json=payload)
        assert result.status_code == 200, result.text
        wire = [{"role": m.role, "content": m.content} for m in provider.requests[-1].messages]
        assert preview.json()["messages"] == wire
        encoded = json.dumps(wire, ensure_ascii=False)
        assert instruction in encoded and "AUTHOR_PRIVATE_INFERENCE_SENTINEL" not in encoded
        if mode == "revise_selection":
            assert "目标选区" in encoded and "AUTHOR_ONLY_PREFIX" not in encoded and "AUTHOR_ONLY_SUFFIX" not in encoded
        bad = {**payload, "prose_input_grants": {**current, "version": draft["version"]+1}}
        before = len(provider.requests)
        assert client.post(endpoint, json=bad).status_code == 409
        assert client.post(endpoint+"/preview", json=bad).status_code == 409
        assert client.post(endpoint, json={**payload, "allow_web_search": True}).status_code == 409
        assert len(provider.requests) == before

def test_legacy_unprotected_discussion_prose_keeps_optional_context_and_old_draft_input(environment):
    client, app, provider = environment
    graph = app.state.writer_visibility_context_builder.graph_store
    graph.nodes[PROJECT_ID].properties["require_semantic_review"] = False
    draft = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft", json={"text":"LEGACY_AUTHOR_DRAFT_KEEP"}).json()
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion", json={
        "mode":"continue_scene", "instruction":"延续既有动作。", "include_context_pack":False,
        "include_latest_draft":True,"included_draft_id":draft["id"]})
    assert response.status_code == 200, response.text
    wire = json.dumps([m.content for m in provider.requests[-1].messages], ensure_ascii=False)
    assert "LEGACY_AUTHOR_DRAFT_KEEP" in wire


def test_workflow_preflights_before_writer_factory_for_missing_stale_and_configured_policy(environment, monkeypatch):
    client, app, provider = environment
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Writer factory must not run before visibility preflight.")
    monkeypatch.setattr(main, "create_scene_writer", forbidden)
    endpoint = f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation"
    assert client.post(endpoint, json={"output_target":"proposal_workspace"}).status_code == 409
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack", json={}).json()
    graph = app.state.writer_visibility_context_builder.graph_store
    graph.nodes[PROJECT_ID].properties["require_semantic_review"] = False
    assert save_policy(client, spec(pack)).status_code == 200
    # A local policy itself requires strict checks even without protection flags.
    assert info(client)["required"] is True
    graph.nodes[SCENE_ID].properties["goal"] += "source revision"
    assert client.post(endpoint, json={"output_target":"proposal_workspace"}).status_code == 409
    assert save_policy(client, spec(pack), expected=1).status_code == 200
    app.state.synthetic_settings.scene_writer = "rule_based"
    response = client.post(endpoint, json={"output_target":"proposal_workspace"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["category"] == "writer_visibility_rule_based_unsupported"
    assert response.json()["detail"]["next_action"] == "configure_llm_writer_and_preview_scene_visibility"
    assert calls == [] and provider.requests == []
    assert client.get(f"/projects/{PROJECT_ID}/runs").json()["runs"] == []


def test_resume_review_only_finishes_review_and_never_constructs_writer(environment, monkeypatch):
    from storygraph.core.time import utc_now
    from storygraph.models.workflow import WorkflowRun
    from storygraph.stores.workflow_store import SQLiteWorkflowStore
    client, app, provider = environment
    def forbidden(*args, **kwargs):
        raise AssertionError("Review completion must not construct a prose writer.")
    monkeypatch.setattr(main, "create_scene_writer", forbidden)
    now = utc_now()
    store = SQLiteWorkflowStore(app.state.synthetic_settings.workflow_store_path)
    store.save(WorkflowRun(id="synthetic-review-only", workflow_name="scene_generation", project_id=PROJECT_ID,
        scene_id=SCENE_ID, output_language="zh-CN", status="awaiting_review", current_step="human_review",
        created_at=now, updated_at=now))
    response = client.post("/runs/synthetic-review-only/resume-review")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert provider.requests == []
    store.close()

def test_workflow_with_current_policy_uses_isolated_messages_and_reviewable_proposal(environment):
    client, app, provider = environment
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack", json={}).json()
    assert save_policy(client, spec(pack)).status_code == 200
    response = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/runs/scene-generation", json={"output_target":"proposal_workspace"})
    assert response.status_code == 200, response.text
    assert response.json()["proposal"]["artifact_type"] == "scene_draft"
    assert response.json()["draft"] is None
    assert len(provider.requests) == 1
    wire = json.dumps([m.content for m in provider.requests[0].messages], ensure_ascii=False)
    assert "writer_visible_context_v1" in wire
    assert "AUTHOR_PRIVATE_INFERENCE_SENTINEL" not in wire
    assert pack["pov_character_id"] not in wire


def test_strict_api_provenance_marks_configured_preset_untransmitted_and_legacy_keeps_it(environment, monkeypatch):
    from storygraph.core.agent_config import AgentPreset
    client, app, provider = environment
    original = main.settings_for_task
    configured = AgentPreset(id="custom_fixture_private_style", name="离线配置预设", system_prompt="PRIVATE_CONFIGURED_PRESET_NOT_WRITER_INPUT")
    def runtime_with_preset(*args, **kwargs):
        runtime = original(*args, **kwargs)
        runtime.agent_preset = configured
        return runtime
    monkeypatch.setattr(main, "settings_for_task", runtime_with_preset)
    pack = client.post(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/context-pack", json={}).json()
    policy = spec(pack)
    assert save_policy(client, policy).status_code == 200
    endpoint = f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/agent-discussion"
    response = client.post(endpoint, json={"mode":"create_scene", "instruction":policy["surface_plan"]["text"], "include_latest_draft":False})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["agent_preset"]["id"] == configured.id
    assert payload["agent_preset_role"] == "configured_only" and payload["agent_preset_transmitted"] is False
    note = payload["proposal"]["provenance"]["note"]
    assert "configured_agent_preset="+configured.id in note
    assert "agent_preset_transmitted=false" in note and "author_discussion_history_transmitted=false" in note
    wire = json.dumps([m.content for m in provider.requests[-1].messages], ensure_ascii=False)
    assert configured.system_prompt not in wire
    ref = next(ref for ref in payload["proposal"]["source_refs"] if ref["kind"] == "writer_visibility_policy")
    assert ref["source_span"]["agent_preset_transmitted"] is False
    assert ref["source_span"]["policy_fingerprint"] in note
    # The separate automatic Proposal rewrite also records its actual isolated source.
    proposal = payload["proposal"]
    revised = client.post(f"/projects/{PROJECT_ID}/proposals/{proposal['id']}/revise", json={"expected_version":proposal["version"]})
    assert revised.status_code == 200, revised.text
    revision = revised.json()
    assert "agent_preset_transmitted=false" in revision["provenance"]["note"]
    assert any(ref["kind"] == "writer_visibility_policy" for ref in revision["source_refs"])
    assert configured.system_prompt not in json.dumps([m.content for m in provider.requests[-1].messages])
    # Legacy still sends and records its configured preset through the old path.
    graph = app.state.writer_visibility_context_builder.graph_store
    graph.nodes[PROJECT_ID].properties["require_semantic_review"] = False
    assert save_policy(client, None, expected=1).status_code == 200
    legacy = client.post(endpoint, json={"mode":"create_scene", "instruction":"离线新写。", "include_latest_draft":False})
    assert legacy.status_code == 200, legacy.text
    value = legacy.json()
    assert value["agent_preset_role"] == "transmitted" and value["agent_preset_transmitted"] is True
    assert "agent_preset="+configured.id in value["proposal"]["provenance"]["note"]
    assert configured.system_prompt in json.dumps([m.content for m in provider.requests[-1].messages])
