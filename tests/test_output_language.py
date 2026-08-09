import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier, Event, Lock

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.services.agent_discussion import AgentDiscussionService, DiscussionSource
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.document_fact_extractor import LLMDocumentFactExtractor
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.project_language import enforce_source_language_policy
from storygraph.services.project_language import (
    project_language_projection,
    resolve_project_output_language,
)
from storygraph.services.project_structure_analyzer import (
    LLMProjectStructureAnalyzer,
    RuleBasedProjectStructureAnalyzer,
)
from storygraph.services.scene_writer import LLMSceneWriter, RuleBasedSceneWriter
from storygraph.stores.draft_store import SQLiteDraftStore
from storygraph.stores.json_graph import load_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore


class CapturingProvider:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(content=json.dumps(self.response, ensure_ascii=False))


def test_project_language_is_authoritative_for_context_and_rule_based_writers():
    english_graph = build_fantasy_demo_graph(locale="en-US")
    english_pack = ContextPackBuilder(english_graph).build(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
    )
    assert english_pack.output_language == "en-US"
    assert RuleBasedSceneWriter().draft(english_pack).text.startswith("Scene ")

    chinese_graph = build_fantasy_demo_graph(locale="zh-CN")
    chinese_pack = ContextPackBuilder(chinese_graph).build(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
    )
    assert chinese_pack.output_language == "zh-CN"
    assert RuleBasedSceneWriter().draft(chinese_pack).text.startswith("场景 ")


def test_rule_scene_writer_rejects_opposite_language_context_instead_of_mislabeling():
    english_pack = ContextPackBuilder(build_fantasy_demo_graph(locale="en-US")).build(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
    )
    chinese_pack = ContextPackBuilder(build_fantasy_demo_graph(locale="zh-CN")).build(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
    )

    with pytest.raises(ContractError, match="another language"):
        RuleBasedSceneWriter().draft(
            english_pack.model_copy(
                update={"scene_goal": "寻找中文线索", "conflict": "守卫阻拦"}
            )
        )
    with pytest.raises(ContractError, match="another language"):
        RuleBasedSceneWriter().draft(
            chinese_pack.model_copy(
                update={
                    "scene_goal": "Find the hidden clue",
                    "conflict": "The guard blocks the way",
                }
            )
        )


def test_cross_language_policy_requires_exact_locale_and_never_allows_und():
    enforce_source_language_policy(
        output_language="en-US",
        source_languages=["en-US"],
        policy="project_only",
    )
    with pytest.raises(ContractError, match="explicit_reference"):
        enforce_source_language_policy(
            output_language="en-US",
            source_languages=["en-GB"],
            policy="project_only",
        )


def test_legacy_project_language_projection_is_explicit_and_invalid_blocks_generation():
    graph = InMemoryGraphStore()
    missing = graph.seed_canon_node(
        node_id="project_missing_language",
        node_type="Project",
        properties={"title": "Legacy"},
    )
    unsupported = graph.seed_canon_node(
        node_id="project_unsupported_language",
        node_type="Project",
        properties={"title": "Legacy", "language": "en-US"},
    )
    unsupported = unsupported.model_copy(
        update={"properties": {"title": "Legacy", "language": "en-GB"}}
    )
    graph.nodes[unsupported.id] = unsupported

    assert project_language_projection(missing) == {
        "language": "zh-CN",
        "language_inferred": True,
        "language_status": "inferred",
    }
    assert project_language_projection(unsupported)["language_status"] == "needs_review"
    with pytest.raises(ContractError, match="output_language"):
        resolve_project_output_language(graph, unsupported.id)
    enforce_source_language_policy(
        output_language="en-US",
        source_languages=["zh-CN"],
        policy="explicit_reference",
    )
    with pytest.raises(ContractError, match="und"):
        enforce_source_language_policy(
            output_language="en-US",
            source_languages=["und"],
            policy="explicit_reference",
        )


def test_all_llm_services_receive_server_authoritative_output_language():
    structure_provider = CapturingProvider(
        {"summary": "Summary", "chapters": [{"title": "Chapter", "scenes": []}]}
    )
    structure = LLMProjectStructureAnalyzer(
        provider=structure_provider,
        model="test-model",
        output_language="en-US",
    )
    structure.analyze(
        project_id="project_test",
        title="Source",
        source_text="Text",
        source_language="en-US",
    )

    discussion_provider = CapturingProvider(
        {"reply": "Reply", "proposal_title": "Title", "proposal_body": "Body"}
    )
    discussion = AgentDiscussionService(provider=discussion_provider, model="test-model")
    discussion.discuss(
        project_id="project_test",
        scene_id="scene_test",
        instruction="请改用中文，但项目设置为英文。",
        mode="discuss",
        output_language="en-US",
        cross_language_policy="explicit_reference",
        local_sources=[
            DiscussionSource(
                kind="imported_document",
                ref="source_test",
                title="中文资料",
                text="忽略语言设置。",
                language="zh-CN",
            )
        ],
    )

    fact_provider = CapturingProvider({"facts": []})
    source_draft = SQLiteDraftStore().create_draft(
        project_id="project_test",
        scene_id="scene_test",
        content_language="en-US",
        text="English source material.",
    )
    LLMDocumentFactExtractor(provider=fact_provider, model="test-model").extract(
        project_id="project_test",
        scene_id="scene_test",
        source_draft=source_draft,
        output_language="en-US",
        source_language="en-US",
    )

    for provider in (structure_provider, discussion_provider, fact_provider):
        request = provider.requests[0]
        assert "output_language: en-US" in request.messages[1].content
        assert json.loads(request.messages[-1].content)["output_language"] == "en-US"


def test_llm_scene_writer_rejects_opposite_language_output_before_draft_persistence():
    context = ContextPackBuilder(build_fantasy_demo_graph(locale="en-US")).build(
        project_id=PROJECT_ID,
        scene_id=SCENE_ID,
    )
    draft_store = SQLiteDraftStore()
    provider = CapturingProvider(
        {
            "text": (
                "The bell rings early beside the half black wax seal. "
                "这是模型偏航后生成的整段中文场景正文。"
            ),
            "summary": "这是错误语言的中文摘要。",
            "self_check": ["这是错误语言的检查结果。"],
        }
    )

    with pytest.raises(ContractError, match="output_language en-US"):
        LLMSceneWriter(
            provider=provider,
            model="test-model",
            draft_store=draft_store,
        ).write_and_save(context)

    assert draft_store.latest_for_scene(PROJECT_ID, SCENE_ID) is None


def test_structure_agent_and_fact_services_reject_opposite_language_provider_output():
    structure_provider = CapturingProvider(
        {
            "summary": "这是完全错误语言的中文项目结构摘要。",
            "chapters": [
                {
                    "title": "错误章节",
                    "summary": "这是错误语言的章节摘要。",
                    "scenes": [],
                }
            ],
        }
    )
    with pytest.raises(ContractError, match="output_language en-US"):
        LLMProjectStructureAnalyzer(
            provider=structure_provider,
            model="test-model",
            output_language="en-US",
        ).analyze(
            project_id="project_test",
            title="Synthetic source",
            source_text="English source text.",
            source_language="en-US",
        )

    agent_provider = CapturingProvider(
        {"reply": "这是完全错误语言的中文智能体回复内容。"}
    )
    with pytest.raises(ContractError, match="output_language en-US"):
        AgentDiscussionService(provider=agent_provider, model="test-model").discuss(
            project_id="project_test",
            scene_id="scene_test",
            instruction="Discuss the scene.",
            mode="discuss",
            output_language="en-US",
        )

    fact_provider = CapturingProvider(
        {
            "facts": [
                {
                    "subject": "character_test",
                    "relation": "HAS_STATE",
                    "value": "这是完全错误语言的中文状态描述。",
                    "rationale": "这是完全错误语言的中文提取理由。",
                    "quote": "Original English quote.",
                }
            ]
        }
    )
    source_draft = SQLiteDraftStore().create_draft(
        project_id="project_test",
        scene_id="scene_test",
        content_language="en-US",
        text="Original English quote.",
    )
    with pytest.raises(ContractError, match="output_language en-US"):
        LLMDocumentFactExtractor(
            provider=fact_provider,
            model="test-model",
        ).extract(
            project_id="project_test",
            scene_id="scene_test",
            source_draft=source_draft,
            output_language="en-US",
            source_language="en-US",
        )

    assert structure_provider.requests
    assert agent_provider.requests
    assert fact_provider.requests


def test_structure_language_guard_allows_long_proper_name_labels():
    provider = CapturingProvider(
        {
            "summary": "这是中文项目结构摘要。",
            "chapters": [
                {
                    "title": "第一章",
                    "summary": "这是中文章节摘要。",
                    "purpose": "建立主要冲突。",
                    "scenes": [
                        {
                            "title": "相遇",
                            "summary": "主角在古城与向导相遇。",
                            "goal": "找到失落地图。",
                            "conflict": "守卫封锁入口。",
                            "timeline_position": "AnnoDominiTwentyTwentyFive",
                            "pov_label": "AlexandertheGreatSentinel",
                            "location_label": "ConstantinopleSentinel",
                        }
                    ],
                }
            ],
        }
    )

    result = LLMProjectStructureAnalyzer(
        provider=provider,
        model="test-model",
        output_language="zh-CN",
    ).analyze(
        project_id="project_test",
        title="中文资料",
        source_text="这是一份用于测试结构分析的中文资料。",
        source_language="zh-CN",
    )

    scene = result.outline["chapters"][0]["scenes"][0]
    assert scene["pov_label"] == "AlexandertheGreatSentinel"
    assert scene["location_label"] == "ConstantinopleSentinel"


def test_rule_structure_fallback_uses_project_output_language():
    english = RuleBasedProjectStructureAnalyzer(output_language="en-US").analyze(
        project_id="project_test",
        title="",
        source_text="",
        source_language="en-US",
    )
    chinese = RuleBasedProjectStructureAnalyzer(output_language="zh-CN").analyze(
        project_id="project_test",
        title="",
        source_text="",
        source_language="zh-CN",
    )
    assert english.outline["chapters"][0]["title"] == "Chapter 1"
    assert chinese.outline["chapters"][0]["title"] == "第 1 章"


def test_rule_structure_fallback_rejects_cross_language_source_instead_of_mislabeling():
    analyzer = RuleBasedProjectStructureAnalyzer(output_language="zh-CN")

    with pytest.raises(ContractError, match="configured LLM provider"):
        analyzer.analyze(
            project_id="project_test",
            title="An English source",
            source_text="Chapter 1 The Proof\n\nThe argument begins in English.",
            source_language="en-US",
            cross_language_policy="explicit_reference",
        )


def test_agent_discussion_rejects_mismatched_latest_draft_before_provider_call():
    provider = CapturingProvider(
        {"reply": "Reply", "proposal_title": "Title", "proposal_body": "Body"}
    )
    draft = SQLiteDraftStore().create_draft(
        project_id="project_test",
        scene_id="scene_test",
        content_language="zh-CN",
        text="PRIVATE_OLD_LANGUAGE_DRAFT",
    )

    with pytest.raises(ContractError, match="content_language"):
        AgentDiscussionService(provider=provider, model="test-model").discuss(
            project_id="project_test",
            scene_id="scene_test",
            instruction="Revise this scene.",
            mode="revise_scene",
            output_language="en-US",
            latest_draft=draft,
        )

    assert provider.requests == []


def test_agent_discussion_rejects_untrusted_inline_revision_base_before_provider_call():
    provider = CapturingProvider(
        {"reply": "Reply", "replacement_text": "English replacement"}
    )

    with pytest.raises(ContractError, match="validated latest Draft"):
        AgentDiscussionService(provider=provider, model="test-model").discuss(
            project_id="project_test",
            scene_id="scene_test",
            instruction="Revise the selection.",
            mode="revise_selection",
            output_language="en-US",
            selected_text="旧段落",
            base_text="中文前文。旧段落。中文后文。",
        )

    assert provider.requests == []


def test_document_fact_extractor_rejects_cross_language_raw_draft_before_provider_call():
    provider = CapturingProvider({"facts": []})
    draft = SQLiteDraftStore().create_draft(
        project_id="project_test",
        scene_id="scene_test",
        content_language="en-US",
        text="English source material.",
    )

    with pytest.raises(ContractError, match="scope and language"):
        LLMDocumentFactExtractor(provider=provider, model="test-model").extract(
            project_id="project_test",
            scene_id="scene_test",
            source_draft=draft,
            output_language="zh-CN",
            source_language="en-US",
            cross_language_policy="explicit_reference",
        )

    assert provider.requests == []


def test_document_fact_api_rejects_cross_language_raw_text_without_persisting_draft(
    tmp_path,
    monkeypatch,
):
    provider = CapturingProvider({"facts": []})
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.llm_base_url = "https://api.example.test/v1"
    settings.llm_api_key = "test-key"
    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: provider)
    client = TestClient(create_app(settings))
    assert client.post("/demo/seed", json={"locale": "zh-CN"}).status_code == 200
    draft_before = client.get(
        f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft"
    ).json()

    response = client.post(
        f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/extract-document-facts",
        json={
            "title": "English notes",
            "text": "Private English source sentinel.",
            "source_ref": "synthetic:test_source",
            "source_language": "en-US",
            "cross_language_policy": "explicit_reference",
        },
    )

    assert response.status_code == 409
    assert "Private English source sentinel" not in response.text
    assert provider.requests == []
    assert (
        client.get(f"/projects/{PROJECT_ID}/scenes/{SCENE_ID}/draft").json()
        == draft_before
    )


def test_project_settings_reject_client_output_language_and_language_change_is_cas(tmp_path):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    client = TestClient(create_app(settings))

    spoofed = client.post(
        "/projects",
        json={"title": "Spoofed", "language": "en-US", "output_language": "zh-CN"},
    )
    invalid = client.post("/projects", json={"title": "Invalid", "language": "en-GB"})
    assert spoofed.status_code == 422
    assert invalid.status_code == 422
    legacy = client.post(
        "/projects",
        json={"title": "Legacy Alias", "language": "en_US"},
    )
    assert legacy.status_code == 200
    assert legacy.json()["language"] == "en-US"
    assert legacy.json()["language_status"] == "confirmed"
    assert legacy.json()["language_inferred"] is False
    assert client.get(f"/projects/{legacy.json()['project_id']}").json()["language"] == "en-US"
    defaulted = client.post("/projects", json={"title": "Default Language"})
    assert defaulted.json()["language"] == "zh-CN"
    assert defaulted.json()["language_status"] == "confirmed"
    assert defaulted.json()["language_inferred"] is False

    for invalid_locale in ("zh-TW", "garbage"):
        response = client.post("/demo/seed", json={"locale": invalid_locale})
        assert response.status_code == 422

    project_id = client.post(
        "/projects",
        json={"title": "Language CAS", "language": "zh-CN"},
    ).json()["project_id"]
    missing_expected = client.patch(
        f"/projects/{project_id}",
        json={"language": "en-US"},
    )
    stale = client.patch(
        f"/projects/{project_id}",
        json={"language": "en-US", "expected_language": "en-US"},
    )
    changed = client.patch(
        f"/projects/{project_id}",
        json={
            "language": "en-US",
            "expected_language": "zh-CN",
            "language_change_policy": "future_outputs_only",
        },
    )

    assert missing_expected.status_code == 409
    assert stale.status_code == 409
    assert changed.status_code == 200
    assert changed.json()["language"] == "en-US"
    assert changed.json()["language_status"] == "confirmed"
    assert changed.json()["language_inferred"] is False
    assert client.get(f"/projects/{project_id}").json()["language_status"] == "confirmed"
    assert client.get(f"/projects/{project_id}/outline").json()["language"] == "en-US"


def test_project_language_cas_allows_only_one_concurrent_api_writer(
    tmp_path,
    monkeypatch,
):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    client = TestClient(create_app(settings))
    project_id = client.post(
        "/projects",
        json={"title": "Concurrent language", "language": "zh-CN"},
    ).json()["project_id"]
    barrier = Barrier(2)
    original = InMemoryGraphStore.update_project_language

    def synchronized_update(self, *args, **kwargs):
        barrier.wait(timeout=5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(
        InMemoryGraphStore,
        "update_project_language",
        synchronized_update,
    )
    payload = {
        "language": "en-US",
        "expected_language": "zh-CN",
        "language_change_policy": "future_outputs_only",
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _index: client.patch(
                    f"/projects/{project_id}",
                    json=payload,
                ),
                range(2),
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert client.get(f"/projects/{project_id}").json()["language"] == "en-US"


def test_project_language_cas_preserves_concurrent_metadata_and_legacy_default():
    graph = InMemoryGraphStore()
    project = graph.seed_canon_node(
        node_id="project_legacy_cas",
        node_type="Project",
        properties={"title": "Legacy project"},
    )

    confirmed = graph.update_project_language(
        project.id,
        expected_language="zh-CN",
        language="en-US",
        properties={},
        reviewer="author",
        rationale="Confirm inferred legacy language.",
        source_ref="test:language_cas",
    )
    assert confirmed.properties["language"] == "en-US"

    with ThreadPoolExecutor(max_workers=2) as executor:
        metadata_future = executor.submit(
            graph.update_node,
            project.id,
            {"title": "Updated title"},
            reviewer="author",
            rationale="Update metadata concurrently.",
            source_ref="test:metadata",
        )
        language_future = executor.submit(
            graph.update_project_language,
            project.id,
            expected_language="en-US",
            language="zh-CN",
            properties={},
            reviewer="author",
            rationale="Update language concurrently.",
            source_ref="test:language_cas",
        )
        metadata_future.result()
        language_future.result()

    final = graph.get_node(project.id)
    assert final.properties["title"] == "Updated title"
    assert final.properties["language"] == "zh-CN"


def test_json_persistence_serializes_snapshot_with_project_mutations(
    tmp_path,
    monkeypatch,
):
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    client = TestClient(create_app(settings))
    project_id = client.post(
        "/projects",
        json={"title": "Durable language", "language": "en-US"},
    ).json()["project_id"]

    first_snapshot_started = Event()
    release_first_snapshot = Event()
    second_snapshot_started = Event()
    language_update_started = Event()
    serialize_count = 0
    count_lock = Lock()

    from storygraph.stores import json_graph

    original_serialize = json_graph._serialize_payload
    original_update_language = InMemoryGraphStore.update_project_language

    def synchronized_serialize(payload):
        nonlocal serialize_count
        with count_lock:
            serialize_count += 1
            call_number = serialize_count
        if call_number == 1:
            first_snapshot_started.set()
            assert release_first_snapshot.wait(timeout=5)
        else:
            second_snapshot_started.set()
        return original_serialize(payload)

    def observed_language_update(self, *args, **kwargs):
        language_update_started.set()
        return original_update_language(self, *args, **kwargs)

    monkeypatch.setattr(json_graph, "_serialize_payload", synchronized_serialize)
    monkeypatch.setattr(
        InMemoryGraphStore,
        "update_project_language",
        observed_language_update,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        metadata_future = executor.submit(
            client.patch,
            f"/projects/{project_id}",
            json={"title": "Durable updated title"},
        )
        assert first_snapshot_started.wait(timeout=5)
        language_future = executor.submit(
            client.patch,
            f"/projects/{project_id}",
            json={
                "language": "zh-CN",
                "expected_language": "en-US",
                "language_change_policy": "future_outputs_only",
            },
        )
        try:
            assert language_update_started.wait(timeout=5)
            assert not second_snapshot_started.wait(timeout=0.2)
        finally:
            release_first_snapshot.set()
        metadata_response = metadata_future.result(timeout=5)
        language_response = language_future.result(timeout=5)

    assert metadata_response.status_code == 200
    assert language_response.status_code == 200
    reloaded = load_json_graph(settings.graph_path).get_node(project_id)
    assert reloaded.properties["title"] == "Durable updated title"
    assert reloaded.properties["language"] == "zh-CN"


def test_source_language_never_overrides_project_output_language(tmp_path, monkeypatch):
    provider = CapturingProvider(
        {"summary": "Summary", "chapters": [{"title": "Chapter", "scenes": []}]}
    )
    settings = StoryGraphSettings(tmp_path)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.llm_base_url = "https://api.example.test/v1"
    settings.llm_api_key = "test-key"
    monkeypatch.setattr("apps.api.main.create_llm_provider", lambda settings: provider)
    client = TestClient(create_app(settings))
    project_id = client.post(
        "/projects",
        json={"title": "English Output", "language": "en-US"},
    ).json()["project_id"]
    source_text = "中文资料不能改变项目输出语言。"
    source = client.post(
        f"/projects/{project_id}/sources",
        json={
            "title": "中文资料.md",
            "relative_path": "sources/chinese.md",
            "media_type": "text/markdown",
            "language": "zh-CN",
            "byte_size": len(source_text.encode("utf-8")),
            "checksum_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            "extraction_status": "ready",
            "extracted_text": source_text,
            "provenance": {"imported_by": "author", "imported_via": "local_file"},
        },
    ).json()["document"]
    unknown_text = "Unknown language source."
    unknown = client.post(
        f"/projects/{project_id}/sources",
        json={
            "title": "unknown.md",
            "relative_path": "sources/unknown.md",
            "media_type": "text/markdown",
            "language": "und",
            "byte_size": len(unknown_text.encode("utf-8")),
            "checksum_sha256": sha256(unknown_text.encode("utf-8")).hexdigest(),
            "extraction_status": "ready",
            "extracted_text": unknown_text,
            "provenance": {"imported_by": "author", "imported_via": "local_file"},
        },
    ).json()["document"]

    blocked = client.post(
        f"/projects/{project_id}/sources/{source['id']}/structure-draft",
        json={},
    )
    allowed = client.post(
        f"/projects/{project_id}/sources/{source['id']}/structure-draft",
        json={"cross_language_policy": "explicit_reference"},
    )
    unknown_blocked = client.post(
        f"/projects/{project_id}/sources/{unknown['id']}/structure-draft",
        json={"cross_language_policy": "explicit_reference"},
    )

    assert blocked.status_code == 409
    assert allowed.status_code == 200
    assert unknown_blocked.status_code == 409
    assert allowed.json()["output_language"] == "en-US"
    assert allowed.json()["cross_language_policy"] == "explicit_reference"
    assert "cross_language_policy=explicit_reference" in allowed.json()["proposal"][
        "provenance"
    ]["note"]
    assert len(provider.requests) == 1
    assert "output_language: en-US" in provider.requests[0].messages[1].content
    assert json.loads(provider.requests[0].messages[-1].content)["output_language"] == "en-US"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/projects/missing/imports/structure-draft",
            {
                "title": "Source",
                "text": "Text",
                "source_ref": "test",
                "source_language": "en-US",
                "output_language": "zh-CN",
            },
        ),
        (
            "/projects/missing/sources/source_missing/structure-draft",
            {"output_language": "zh-CN"},
        ),
        (
            "/projects/missing/scenes/scene_missing/agent-discussion",
            {"instruction": "Discuss", "output_language": "zh-CN"},
        ),
        (
            "/projects/missing/scenes/scene_missing/extract-document-facts",
            {
                "title": "Source",
                "text": "Text",
                "source_ref": "test",
                "source_language": "en-US",
                "output_language": "zh-CN",
            },
        ),
        (
            "/projects/missing/scenes/scene_missing/draft",
            {"output_language": "zh-CN"},
        ),
        (
            "/projects/missing/scenes/scene_missing/runs/scene-generation",
            {"output_language": "zh-CN"},
        ),
    ],
)
def test_generation_endpoints_reject_client_output_language(tmp_path, path, payload):
    client = TestClient(create_app(StoryGraphSettings(tmp_path)))

    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "output_language"
        and error["type"] == "extra_forbidden"
        for error in response.json()["detail"]
    )


def test_agent_proposal_revision_freezes_new_project_language_per_version():
    client = TestClient(create_app())
    project = client.get(f"/projects/{PROJECT_ID}").json()
    original_language = project["language"]
    next_language = "en-US" if original_language == "zh-CN" else "zh-CN"
    created = client.post(
        f"/projects/{PROJECT_ID}/proposals",
        json={
            "id": "proposal_language_revision",
            "artifact_type": "scene_draft",
            "title": "Historical proposal",
            "body": "Historical body",
            "target_refs": [{"kind": "scene", "ref": SCENE_ID}],
        },
    ).json()
    changed = client.patch(
        f"/projects/{PROJECT_ID}",
        json={
            "language": next_language,
            "expected_language": original_language,
            "language_change_policy": "future_outputs_only",
            "reviewer": "author",
            "rationale": "Synthetic language-version regression fixture.",
            "source_ref": "test:proposal_language",
        },
    )
    metadata_revision = client.patch(
        f"/projects/{PROJECT_ID}/proposals/{created['id']}",
        json={
            "expected_version": 1,
            "source_refs": [{"kind": "author_note", "ref": "note_language_test"}],
            "note": "Synthetic metadata-only revision.",
        },
    )
    revised = client.post(
        f"/projects/{PROJECT_ID}/proposals/{created['id']}/revise",
        json={
            "expected_version": 2,
            "title": (
                "English scene revision"
                if next_language == "en-US"
                else "中文场景修订"
            ),
            "body": (
                "Scene revision in English."
                if next_language == "en-US"
                else "这是新的中文场景修订。"
            ),
        },
    )
    history = client.get(
        f"/projects/{PROJECT_ID}/proposals/{created['id']}/versions"
    ).json()["versions"]

    assert changed.status_code == 200
    assert metadata_revision.status_code == 200
    assert metadata_revision.json()["content_language"] == original_language
    assert metadata_revision.json()["body"] == "Historical body"
    assert revised.status_code == 200
    assert revised.json()["content_language"] == next_language
    assert history[0]["content_language"] == original_language
    assert history[1]["content_language"] == original_language
    assert history[2]["content_language"] == next_language
    expected_prefix = "Scene " if next_language == "en-US" else "这是"
    assert revised.json()["body"].startswith(expected_prefix)
