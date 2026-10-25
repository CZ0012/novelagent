import json

import pytest

from storygraph.core.agent_config import AgentPreset
from storygraph.core.errors import ContractError
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.llm_provider import LLMRequest, LLMResponse
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.stores.draft_store import SQLiteDraftStore


def test_llm_scene_writer_saves_draft_without_graph_mutation():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    before_events = len(graph.event_log.list())
    before_relations = set(graph.relationships)
    provider = FakeProvider(
        {
            "text": "bell rings early. Lin Jin finds the half black wax seal and keeps silent.",
            "summary": "Lin Jin finds a tower clue without changing canon.",
            "self_check": ["included required beats", "did not mutate canon"],
        }
    )
    writer = LLMSceneWriter(provider=provider, model="deepseek-chat", draft_store=draft_store)

    draft = writer.write_and_save(pack)

    assert draft.version == 1
    assert draft.text.startswith("bell rings early")
    assert draft.summary == "Lin Jin finds a tower clue without changing canon."
    assert len(graph.event_log.list()) == before_events
    assert set(graph.relationships) == before_relations
    assert provider.requests[0].model == "deepseek-chat"
    assert any(message.role == "system" and "output_language: en-US" in message.content
               for message in provider.requests[0].messages)
    assert "context_pack_v1" in provider.requests[0].messages[-1].content
    assert "must_not_violate" in provider.requests[0].messages[-1].content


def test_llm_scene_writer_rejects_critical_missing_context_before_provider_call():
    graph = build_fantasy_demo_graph()
    del graph.nodes["character_helianya"]
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    provider = FakeProvider(
        {
            "text": "bell rings early. half black wax seal.",
            "summary": "Should not be used.",
            "self_check": [],
        }
    )
    writer = LLMSceneWriter(provider=provider, model="deepseek-chat", draft_store=draft_store)

    with pytest.raises(ContractError, match="critical missing context"):
        writer.draft(pack)

    assert provider.requests == []


def test_llm_scene_writer_rejects_must_not_violate_output():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    provider = FakeProvider(
        {
            "text": "bell rings early. half black wax seal. Lin Jin learns secret_lineage.",
            "summary": "The draft violates a hard constraint.",
            "self_check": ["missed hard constraint"],
        }
    )
    writer = LLMSceneWriter(provider=provider, model="deepseek-chat", draft_store=draft_store)

    with pytest.raises(ContractError, match="must_not_violate"):
        writer.draft(pack)


def test_llm_scene_writer_rejects_non_json_response():
    graph = build_fantasy_demo_graph()
    draft_store = SQLiteDraftStore()
    pack = ContextPackBuilder(graph, draft_store).build(project_id=PROJECT_ID, scene_id=SCENE_ID)
    writer = LLMSceneWriter(
        provider=RawProvider("not json"),
        model="deepseek-chat",
        draft_store=draft_store,
    )

    with pytest.raises(ContractError, match="must be JSON"):
        writer.draft(pack)


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=json.dumps(self.payload), raw={"fake": True})


class RawProvider:
    def __init__(self, content: str):
        self.content = content

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(content=self.content, raw={"fake": True})


def _response_shape(messages):
    examples = [message.content.split("```json\n", 1)[1].split("\n```", 1)[0]
                for message in messages if message.role == "system" and "```json\n" in message.content]
    return json.loads(examples[-1])


@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_scene_writer_response_example_uses_authoritative_output_language(locale):
    graph = build_fantasy_demo_graph(locale)
    pack = ContextPackBuilder(graph, SQLiteDraftStore()).build(
        project_id=PROJECT_ID, scene_id=SCENE_ID
    )
    provider = CopyExampleChecksProvider()
    result = LLMSceneWriter(provider=provider, model="configured-model").draft(pack)
    request = provider.requests[0]
    example = _response_shape(request.messages)

    assert set(example) == {"text", "summary", "self_check"}
    assert result.self_check == example["self_check"]
    assert all("{{scene_writer_response_example}}" not in message.content
               for message in request.messages)
    if locale == "zh-CN":
        assert example["text"] == "仅填写本场景正文。"
        assert example["summary"] == "一句简短的场景摘要。"
        assert result.self_check == ["已检查视角与知识边界。", "已检查正典安全。"]
        assert "checked POV boundary" not in request.messages[0].content
    else:
        assert example["text"] == "Scene prose only."
        assert example["summary"] == "One short scene summary."
        assert result.self_check == ["Checked the POV and knowledge boundary.", "Checked canon safety."]
    assert json.loads(request.messages[-1].content)["output_language"] == locale


@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_custom_scene_prompt_without_placeholder_stays_verbatim_with_localized_example(tmp_path, locale):
    original = 'Custom literal {keep_this}: {"schema": "author_contract"}\nNo template marker.\n'
    prompt = tmp_path / "custom-scene.md"
    prompt.write_text(original, encoding="utf-8")
    pack = ContextPackBuilder(build_fantasy_demo_graph(locale), SQLiteDraftStore()).build(
        project_id=PROJECT_ID, scene_id=SCENE_ID
    )
    messages = LLMSceneWriter(provider=FakeProvider({}), model="configured-model",
                              prompt_path=prompt)._messages(pack)

    assert messages[0].content == original
    example = _response_shape(messages)
    assert example["self_check"][0] == (
        "已检查视角与知识边界。" if locale == "zh-CN" else "Checked the POV and knowledge boundary."
    )
    assert any(message.content.startswith(f"Authoritative output_language: {locale}")
               or f"output_language: {locale}" in message.content for message in messages)


def test_custom_scene_prompt_replaces_only_the_explicit_example_marker(tmp_path):
    original = 'Keep {literal} and {{unrelated}} unchanged.\n```json\n{{scene_writer_response_example}}\n```'
    prompt = tmp_path / "custom-scene.md"
    prompt.write_text(original, encoding="utf-8")
    pack = ContextPackBuilder(build_fantasy_demo_graph("zh-CN"), SQLiteDraftStore()).build(
        project_id=PROJECT_ID, scene_id=SCENE_ID
    )
    messages = LLMSceneWriter(provider=FakeProvider({}), model="configured-model",
                              prompt_path=prompt)._messages(pack)

    assert "Keep {literal} and {{unrelated}} unchanged." in messages[0].content
    assert _response_shape(messages)["self_check"] == ["已检查视角与知识边界。", "已检查正典安全。"]
    assert prompt.read_text(encoding="utf-8") == original


def test_chinese_scene_output_still_rejects_copied_english_self_checks():
    pack = ContextPackBuilder(build_fantasy_demo_graph("zh-CN"), SQLiteDraftStore()).build(
        project_id=PROJECT_ID, scene_id=SCENE_ID
    )
    provider = FakeProvider({
        "text": "林谨站在塔中，收起信封。\n" + "\n".join(pack.must_include),
        "summary": "林谨发现线索，暂时保留判断。",
        "self_check": ["Checked the POV and knowledge boundary.",
                       "Checked that the scene preserves canon facts."],
    })

    with pytest.raises(ContractError, match=r"self_check\["):
        LLMSceneWriter(provider=provider, model="configured-model").draft(pack)
    assert len(provider.requests) == 1


class CopyExampleChecksProvider:
    """Captures the request and simulates copying only its self-check example."""

    def __init__(self):
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        payload = json.loads(request.messages[-1].content)
        chinese = payload["output_language"] == "zh-CN"
        text = ("林谨站在塔中，收起信封。" if chinese else "Lin Jin pockets the letter.")
        result = {
            "text": text + "\n" + "\n".join(payload["context_pack"]["must_include"]),
            "summary": "林谨发现线索，暂时保留判断。" if chinese else "Lin Jin preserves a clue.",
            "self_check": _response_shape(request.messages)["self_check"],
        }
        return LLMResponse(content=json.dumps(result, ensure_ascii=False), raw={"fake": True})


def test_localized_default_shape_keeps_creative_preset_and_language_authority_messages():
    pack = ContextPackBuilder(build_fantasy_demo_graph("zh-CN"), SQLiteDraftStore()).build(
        project_id=PROJECT_ID, scene_id=SCENE_ID
    )
    preset = AgentPreset(id="custom_capture", name="测试预设", system_prompt="独立预设标记。")
    messages = LLMSceneWriter(provider=FakeProvider({}), model="configured-model",
                              agent_preset=preset)._messages(pack)

    assert "独立预设标记。" in messages[1].content
    assert _response_shape(messages)["self_check"] == ["已检查视角与知识边界。", "已检查正典安全。"]
    assert "output_language: zh-CN" in messages[-2].content
