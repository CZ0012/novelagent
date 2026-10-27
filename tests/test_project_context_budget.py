"""Rich protected projects fit their default; explicit limits stay hard."""

import json
import sys

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from apps.cli import main as cli
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError
from storygraph.models.context import ContextPack
from storygraph.models.writer_visibility import WriterVisibilityPolicy, WriterVisibilityRecord
from storygraph.services.writer_visibility import resolve_writer_visibility
from storygraph.stores.proposal_store import SQLiteProposalStore
from storygraph.stores.writer_visibility_store import SQLiteWriterVisibilityStore
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.stores.json_graph import save_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore


SEED = {"reviewer": "fixture_author", "rationale": "Synthetic protected-context fixture.", "source_ref": "test:context-budget"}


def rich_graph():
    graph = InMemoryGraphStore()
    guidelines = [
        "动作必须具体到工具、手势与观察对象，先写人物做了什么，再呈现能够核对的结果。每次发现都明确来源、持有人和获得权限，避免凭直觉直接跳到幕后答案。",
        "对白承担交换信息、提出条件与拒绝请求的功能，同一证据在不同人物手中应产生不同压力。不能用长篇设定讲解替代冲突，不能让所有角色说同一种标准答案。",
        "技术数据保持同一计量口径，容量、功率、流量和时间必须分别说明。记录预测值与实测值的区别，把误差写成可以追查的线索，不能把凭证当成真实能量。",
        "人物只使用此前真实获得的知识，能够推测但不能把推测写成确认。已批准场景结局是写作意图，不证明事件已经发生；后续计划也不能成为开场时的人物记忆。",
        "节奏由目标、阻碍、选择和后果推进，每场至少改变一项真实处境。避免不断重复查同一张表，必须说明新的材料如何迫使角色调整行动及承担新的代价。",
        "情绪通过停顿、动作和对话中的取舍呈现，少用抽象感叹与状语堆叠。句子长短随任务变化，观察段允许精确复句，危险操作采用清楚的短句而非华丽形容。",
        "证据交接区分工作副本、原始导出与正式封存。展示材料不等于移交所有权，听到口头命令也不等于取得完整授权，所有关键结论应保留来源及不确定性。",
        "伏笔埋设只呈现人物此刻能够观察到的异常，不提前解释隐藏含义。部分验证与最终回收是不同阶段，卷初推进调查，卷末承担结果，不能提前消费所有高潮。",
    ]
    # A detailed author style sheet is realistic protected data, not a giant
    # arbitrary character blob. Repeated columns stand for concrete reminders
    # across observation, dialogue and revision checks in a synthetic profile.
    rubric = [text+"观察时遵守以上要求。"+text+"对话时核对来源。"+text+"行动时明确代价。"+text+
              "证据交接保持边界。"+text+"修订时同样核对上述来源与边界。"+text for text in guidelines]
    nodes = [
        ("p", "Project", {"language": "zh-CN", "title": "合成测试作品", "require_semantic_review": True, "style_profile_id": "style"}),
        ("hero", "Character", {"project_id": "p", "name": "测试检修员", "description": "他使用校验仪核对阀门读数，只依据可追溯记录作出判断。", "initial_state": {"life_status": "alive", "physical_state": "healthy", "location_id": "room"}}),
        ("room", "Location", {"project_id": "p", "name": "检修室", "description": "独立仪表和封存柜所在的工作间。"}),
        ("secret", "Secret", {"project_id": "p", "name": "校验误差", "content": "主表的校验常数被错误录入。"}),
        ("chapter", "Chapter", {"project_id": "p", "title": "合成章节", "chapter_index": 1}),
        ("scene", "Scene", {"project_id": "p", "chapter_id": "chapter", "title": "读数核验", "pov_character_id": "hero", "required_characters": ["hero"], "location_id": "room", "timeline_position": "第一日上午", "goal": "确认阀门读数差异。", "conflict": "原表不能直接修改。", "outcome": "取得一份独立测量记录。", "emotional_turn": "从怀疑转为谨慎核验。", "target_length": 2500}),
        ("style", "StyleProfile", {"project_id": "p", "name": "详细检修悬疑文风", "pov": "第三人称有限视角", "tone": "克制具体", "diction": "使用精确工具和计量名词。", "sentence_rhythm": "用动作推进节奏。", "dialogue_style": "对白承担选择与代价。", "rubric": rubric, "banned_patterns": ["缓缓地", "不由得"]}),
    ]
    for ref, kind, props in nodes:
        graph.seed_canon_node(node_id=ref, node_type=kind, properties=props, **SEED)
    graph.seed_canon_relation(relation_id="knows", relation_type="KNOWS_SECRET", source_id="hero", target_id="secret", properties={"project_id": "p", "initial_knowledge": True, "known": True}, **SEED)
    for index, text in enumerate(guidelines[:3]):
        graph.seed_canon_node(node_id=f"rule_{index}", node_type="WorldRule", properties={"project_id": "p", "rule": text}, **SEED)
    return graph


def approved_policy():
    return WriterVisibilityPolicy(access_mode="surface", surface_plan={"kind":"literal", "text":"检修员记下表盘读数。"},
        writer_style={"tone":"克制具体"}, characters=[{"character_id":"hero", "public_name":"检修员"}],
        visible_claims=[{"text":"检修员记下表盘读数。", "presentation":"observation", "phase":"during_scene"}])


def authorize_writer(pack):
    proposals = SQLiteProposalStore()
    store = SQLiteWriterVisibilityStore(proposals)
    value = store.save(project_id=pack.project_id, scene_id=None, expected_version=0,
        spec=approved_policy().model_dump(mode="json"), source_context_sha256=None,
        configured_by="fixture_author")
    pack.writer_visibility = resolve_writer_visibility(pack, WriterVisibilityRecord.model_validate(value))
    proposals.close()
    return pack


class Capture:
    def __init__(self):
        self.requests = []
    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(json.dumps({"text": "诊断占位：检修员记下表盘读数。", "summary": "仅作离线载荷诊断。", "self_check": []}, ensure_ascii=False))


def test_project_default_preserves_rich_protected_context_and_explicit_4000_blocks():
    graph = rich_graph()
    default = ContextPackBuilder(graph).build(project_id="p", scene_id="scene")
    explicit = ContextPackBuilder(graph).build(project_id="p", scene_id="scene", target_tokens=4000)
    assert 4000 < default.budget.estimated_tokens < 8000
    assert default.budget.target_tokens == 8000 and not any(g.severity == "critical" for g in default.missing_context)
    assert explicit.budget.target_tokens == 4000 and any(g.kind == "context_budget_exceeded" for g in explicit.missing_context)
    for field in ("scene_plan", "style_constraints", "canon_entities", "temporal_states", "knowledge_boundaries", "relevant_world_rules"):
        assert getattr(default, field) == getattr(explicit, field)
    capture = Capture()
    writer = LLMSceneWriter(provider=capture, model="offline-capture")
    writer.draft(authorize_writer(default))
    assert len(capture.requests) == 1
    sent = json.loads(capture.requests[0].messages[-1].content)
    assert "context_pack" not in sent and sent["writer_view"]["isolated"]
    assert sent["writer_view"]["claims"][0]["text"] == approved_policy().visible_claims[0].text
    assert "校验常数被错误录入" not in json.dumps(sent, ensure_ascii=False)
    with pytest.raises(ContractError, match="critical missing context"):
        writer.draft(explicit)
    assert len(capture.requests) == 1


def test_api_omitted_empty_null_and_explicit_context_budgets_and_default_workflow(tmp_path, monkeypatch):
    graph = rich_graph()
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend, settings.graph_backend_explicit = "json", True
    settings.scene_writer = "llm"
    save_json_graph(graph, settings.graph_path)
    capture = Capture()
    monkeypatch.setattr(main, "create_scene_writer", lambda _settings, drafts: LLMSceneWriter(provider=capture, model="offline-capture", draft_store=drafts))
    client = TestClient(main.create_app(settings))
    path = "/projects/p/scenes/scene/context-pack"
    for response in (client.post(path), client.post(path, json={}), client.post(path, json={"target_tokens": None})):
        assert response.status_code == 200, response.text
        assert response.json()["budget"]["target_tokens"] == 8000
    explicit = client.post(path, json={"target_tokens": 4000})
    assert explicit.status_code == 200 and explicit.json()["budget"]["target_tokens"] == 4000
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=capture, model="offline-capture").draft(ContextPack.model_validate(explicit.json()))
    assert not capture.requests
    for value in (True, False, 0, -1, 4000.5):
        assert client.post(path, json={"target_tokens": value}).status_code == 422
    saved = client.put("/projects/p/writer-visibility", json={"expected_version":0,
        "spec":approved_policy().model_dump(mode="json")})
    assert saved.status_code == 200, saved.text
    response = client.post("/projects/p/scenes/scene/runs/scene-generation", json={"output_target": "proposal_workspace"})
    assert response.status_code == 200, response.text
    assert len(capture.requests) == 1 and response.json()["draft"] is None
    author_pack = response.json()["context_pack"]
    assert author_pack["budget"]["target_tokens"] == 8000 and author_pack["scene_plan"]["target_length"] == 2500
    assert len(author_pack["style_constraints"]["rubric"]) == 8 and author_pack["knowledge_boundaries"][0]["knows"] == ["secret"]
    sent = json.loads(capture.requests[0].messages[-1].content)
    assert "context_pack" not in sent and sent["writer_view"]["target_length"] == 2500
    assert sent["writer_view"]["claims"][0]["text"] == approved_policy().visible_claims[0].text
    assert "校验常数被错误录入" not in json.dumps(sent, ensure_ascii=False)


def test_legacy_default_and_cli_explicit_budget_remain_distinct(tmp_path, monkeypatch, capsys):
    graph = rich_graph()
    graph.nodes["p"].properties.pop("require_semantic_review")
    assert ContextPackBuilder(graph).build(project_id="p", scene_id="scene").budget.target_tokens == 4000
    graph.nodes["p"].properties["longform_blueprint_id"] = "approved_fixture"
    save_json_graph(graph, tmp_path/"graph.json")
    assert cli.build_context_command(project_id="p", scene_id="scene", workspace=tmp_path)["budget"]["target_tokens"] == 8000
    assert cli.build_context_command(project_id="p", scene_id="scene", workspace=tmp_path, target_tokens=4000)["budget"]["target_tokens"] == 4000
    monkeypatch.setattr(sys, "argv", ["storygraph", "build-context", "--project", "p", "--scene", "scene", "--workspace", str(tmp_path), "--target-tokens", "4000"])
    cli._main_argparse()
    assert json.loads(capsys.readouterr().out)["budget"]["target_tokens"] == 4000


def test_typer_omitted_budget_uses_project_default(tmp_path, monkeypatch, capsys):
    pytest.importorskip("typer")
    graph = rich_graph()
    save_json_graph(graph, tmp_path/"graph.json")
    monkeypatch.setattr(sys, "argv", ["storygraph", "build-context", "--project", "p", "--scene", "scene", "--workspace", str(tmp_path)])
    with pytest.raises(SystemExit) as finished:
        cli.main()
    assert finished.value.code == 0
    assert json.loads(capsys.readouterr().out)["budget"]["target_tokens"] == 8000


def expanded_graph():
    graph = rich_graph()
    topics = ["计量复核", "权限授权", "潮窗调度", "独立封存", "异常通报", "设备校准"]
    for index, topic in enumerate(topics):
        rule = (f"{topic}必须明确负责人、起止时间、原始记录和复核路径。"
                "更正值不能覆盖原始值，派生报告必须注明计算方法。"
                "任何物理操作先确认安全条件，再保存现场独立读数。"*10)
        graph.seed_canon_node(node_id=f"expanded_rule_{index}", node_type="WorldRule",
            properties={"project_id": "p", "rule": rule}, **SEED)
    return graph


def test_omitted_protected_budget_grows_in_bounded_steps_without_changing_fields_or_provenance(monkeypatch):
    graph = expanded_graph()
    monkeypatch.setattr("storygraph.services.context_pack_builder.utc_now", lambda: "2026-10-25T00:00:00Z")
    builder = ContextPackBuilder(graph)
    auto = builder.build(project_id="p", scene_id="scene")
    assert 8000 < auto.budget.target_tokens <= 16000 and auto.budget.target_tokens % 2000 == 0
    assert not any(g.kind == "context_budget_exceeded" for g in auto.missing_context)
    explicit_same = builder.build(project_id="p", scene_id="scene", target_tokens=auto.budget.target_tokens)
    assert auto.model_dump() == explicit_same.model_dump()
    explicit_8k = builder.build(project_id="p", scene_id="scene", target_tokens=8000)
    assert explicit_8k.budget.target_tokens == 8000 and any(g.kind == "context_budget_exceeded" for g in explicit_8k.missing_context)
    explicit_4k = builder.build(project_id="p", scene_id="scene", target_tokens=4000)
    assert explicit_4k.budget.target_tokens == 4000 and any(g.kind == "context_budget_exceeded" for g in explicit_4k.missing_context)
    for field in ("scene_plan", "style_constraints", "canon_entities", "temporal_states", "knowledge_boundaries", "relevant_world_rules", "provenance"):
        assert getattr(auto, field) == getattr(explicit_8k, field)
    capture = Capture()
    writer = LLMSceneWriter(provider=capture, model="offline-capture")
    writer.draft(authorize_writer(auto))
    with pytest.raises(ContractError):
        writer.draft(explicit_8k)
    assert len(capture.requests) == 1


def test_auto_budget_cap_keeps_oversized_hard_context_and_blocks_without_provider():
    graph = rich_graph()
    text = "合成超限规则：原始证据不可覆盖，任何更正保留完整来源。"*800
    graph.seed_canon_node(node_id="oversized_rule", node_type="WorldRule", properties={"project_id": "p", "rule": text}, **SEED)
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="scene")
    assert pack.budget.target_tokens == 16000 and pack.budget.estimated_tokens > 16000
    assert any(text in rule for rule in pack.relevant_world_rules)
    assert any(g.kind == "context_budget_exceeded" for g in pack.missing_context)
    capture = Capture()
    with pytest.raises(ContractError):
        LLMSceneWriter(provider=capture, model="offline-capture").draft(pack)
    assert not capture.requests
    graph.nodes["p"].properties.pop("require_semantic_review")
    assert ContextPackBuilder(graph).build(project_id="p", scene_id="scene").budget.target_tokens == 4000


def test_api_null_auto_reports_grown_target_and_explicit8000_remains_strict(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend, settings.graph_backend_explicit = "json", True
    save_json_graph(expanded_graph(), settings.graph_path)
    client = TestClient(main.create_app(settings))
    path = "/projects/p/scenes/scene/context-pack"
    for response in (client.post(path), client.post(path, json={"target_tokens": None})):
        assert response.status_code == 200
        assert 8000 < response.json()["budget"]["target_tokens"] <= 16000
        assert not any(g["kind"] == "context_budget_exceeded" for g in response.json()["missing_context"])
    explicit = client.post(path, json={"target_tokens": 8000}).json()
    assert explicit["budget"]["target_tokens"] == 8000
    assert any(g["kind"] == "context_budget_exceeded" for g in explicit["missing_context"])
