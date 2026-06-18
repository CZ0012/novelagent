import json

import pytest

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
    assert "context_pack_v1" in provider.requests[0].messages[1].content
    assert "must_not_violate" in provider.requests[0].messages[1].content


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
