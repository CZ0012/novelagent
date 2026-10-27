"""No paid calls: strict prose inputs contain only an approved visible capsule."""

import json
import pytest
from storygraph.core.agent_config import AgentPreset
from storygraph.core.errors import ContractError
from storygraph.models.context import ContextPack
from storygraph.models.writer_visibility import WriterVisibilityPolicy, WriterVisibilityRecord
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.scene_writer import LLMSceneWriter, RuleBasedSceneWriter
from storygraph.services.agent_discussion import AgentDiscussionService
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.writer_visibility import (
    writer_source_context_sha256,
    resolve_writer_visibility,
    preflight_writer_context,
    preflight_agent_prose,
    scene_review_constraint,
)
from storygraph.stores.draft_store import SQLiteDraftStore
from test_knowledge_entry import graph as graph


class Capture:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(
            json.dumps(
                {
                    "text": "林烬核对门上的刻痕。",
                    "summary": "他核对刻痕。",
                    "self_check": ["仅用批准可见材料。"],
                },
                ensure_ascii=False,
            )
        )


def pack_with_hidden(graph):
    graph.nodes["p"].properties["require_semantic_review"] = True
    graph.nodes["secret"].properties["description"] = "HIDDEN_TRUTH_SENTINEL"
    graph.nodes["baseline"].properties["description"] = "POV_KNOWN_READER_WITHHELD"
    graph.nodes["place"].properties["description"] = "HIDDEN_LOCATION_SENTINEL"
    graph.nodes["hero"].properties["desire"] = "HIDDEN_ACTOR_DESIRE"
    pack = ContextPackBuilder(graph).build(project_id="p", scene_id="s1", target_tokens=12000)
    pack.unresolved_foreshadowing = ["HIDDEN_FUTURE_CLUE"]
    return pack


def spec(mode="pov", claims=()):
    return WriterVisibilityPolicy(
        access_mode=mode,
        surface_plan={"kind": "literal", "text": "本场只核对门上可见刻痕，不推定原因。"},
        writer_style={"pov": "有限视角", "tone": "冷静具体"},
        characters=[{"character_id": "hero", "public_name": "林烬"}],
        visible_claims=claims,
        expected_reader_inference="PRIVATE_READER_INFERENCE",
    )


def attach(pack, policy=None, reader_resolver=None, scene=True):
    record = WriterVisibilityRecord(
        project_id=pack.project_id,
        scene_id=pack.scene_id if scene else None,
        version=1,
        spec=policy or spec(),
        source_context_sha256=writer_source_context_sha256(pack) if scene else None,
        configured_by="synthetic_fixture_not_human_acceptance",
        configured_at="2026-10-26T00:00:00Z",
    )
    pack.writer_visibility = resolve_writer_visibility(
        pack, record, reader_source_resolver=reader_resolver
    )
    return pack


def test_every_writer_message_withholds_unknown_known_private_ids_and_all_bypasses(graph):
    pack = attach(pack_with_hidden(graph))
    before = pack.model_dump_json()
    preset = AgentPreset(id="custom_hidden", name="合成", system_prompt="PRESET_HIDDEN_SENTINEL")
    provider = Capture()
    LLMSceneWriter(provider=provider, model="fixture", agent_preset=preset).draft(pack)
    wire = "\n".join(m.content for m in provider.requests[0].messages)
    for hidden in (
        "HIDDEN_TRUTH_SENTINEL",
        "POV_KNOWN_READER_WITHHELD",
        "HIDDEN_LOCATION_SENTINEL",
        "HIDDEN_ACTOR_DESIRE",
        "HIDDEN_FUTURE_CLUE",
        "PRIVATE_READER_INFERENCE",
        "PRESET_HIDDEN_SENTINEL",
        "does_not_know",
        "falsely_believes",
    ):
        assert hidden not in wire
    payload = json.loads(provider.requests[0].messages[-1].content)
    assert "context_pack" not in payload
    assert payload["writer_view"]["pov"] == "C1"
    assert payload["writer_view"]["characters"] == [{"handle": "C1", "public_name": "林烬"}]
    assert pack.model_dump_json() == before and "HIDDEN_TRUTH_SENTINEL" in before


def test_belief_claim_retained_without_false_label_and_during_reveal_not_entry(graph):
    claims = [
        {
            "text": "钟表一定坏了。",
            "presentation": "belief",
            "phase": "entry",
            "character_id": "hero",
        },
        {
            "text": "他打开信，读到新的证言。",
            "presentation": "observation",
            "phase": "during_scene",
        },
    ]
    pack = attach(pack_with_hidden(graph), spec(claims=claims))
    view = preflight_writer_context(pack)
    assert view["claims"][0]["text"] == "钟表一定坏了。" and view["claims"][0]["phase"] == "entry"
    assert view["claims"][1]["phase"] == "during_scene"
    assert "HIDDEN_TRUTH_SENTINEL" not in canonical_json(view)


@pytest.mark.parametrize(
    "mode,presentation,allowed",
    [
        ("surface", "belief", False),
        ("pov", "narrator_fact", False),
        ("omniscient", "narrator_fact", True),
    ],
)
def test_explicit_modes_do_not_infer_permissions_from_free_style(
    graph, mode, presentation, allowed
):
    pack = pack_with_hidden(graph)
    policy = spec(
        mode,
        [{"text": "明确批准的叙述材料。", "presentation": presentation, "character_id": "hero"}],
    )
    if allowed:
        assert attach(pack, policy).writer_visibility
    else:
        with pytest.raises(ContractError):
            attach(pack, policy)


def test_serialized_protected_pack_without_sidecar_cannot_downgrade(graph):
    pack = attach(pack_with_hidden(graph))
    saved = pack.model_dump_json()
    assert "writer_visibility_required" in saved and "policy_fingerprint" not in saved
    reloaded = ContextPack.model_validate_json(saved)
    provider = Capture()
    with pytest.raises(ContractError, match="missing_policy"):
        LLMSceneWriter(provider=provider, model="fixture").draft(reloaded)
    assert not provider.requests


def test_omniscient_pov_belief_rejected_before_provider_call(graph):
    pack = attach(pack_with_hidden(graph), spec(claims=[{
        "text": "钟表一定坏了。", "presentation": "belief", "character_id": "hero",
    }]))
    # A policy that was valid for limited POV cannot gain omniscient access
    # while retaining the private-belief presentation.
    record = pack.writer_visibility.record
    changed = record.model_copy(update={"spec": record.spec.model_copy(update={"access_mode": "omniscient"})})
    pack.writer_visibility = pack.writer_visibility.model_copy(update={
        "record": changed,
        "policy_fingerprint": content_hash(canonical_json({
            "record": changed.model_dump(mode="json"),
            "source_context_sha256": writer_source_context_sha256(pack),
        })),
    })
    provider = Capture()
    with pytest.raises(ContractError, match="belief_not_pov"):
        LLMSceneWriter(provider=provider, model="fixture").draft(pack)
    assert provider.requests == []


def test_source_hash_stale_and_crossscope_reject_before_provider(graph):
    pack = attach(pack_with_hidden(graph))
    pack.scene_goal += "改变了当前来源。"
    with pytest.raises(ContractError, match="source_stale"):
        preflight_writer_context(pack)
    pack = pack_with_hidden(graph)
    record = WriterVisibilityRecord(
        project_id="foreign",
        scene_id="s1",
        version=1,
        spec=spec(),
        source_context_sha256=writer_source_context_sha256(pack),
        configured_by="fixture",
        configured_at="now",
    )
    with pytest.raises(ContractError, match="scope_mismatch"):
        resolve_writer_visibility(pack, record)


def test_reader_pins_are_private_exact_and_rechecked(graph):
    store = SQLiteDraftStore()
    draft = store.create_draft(
        project_id="p",
        scene_id="s1",
        content_language="zh-CN",
        text="见到😀线索。",
        summary="只作来源",
    )
    policy = spec().model_copy(
        update={
            "reader_presented": WriterVisibilityPolicy.model_validate(
                {
                    **spec().model_dump(),
                    "reader_presented": [
                        {
                            "draft_id": draft.id,
                            "version": 1,
                            "text_sha256": content_hash(draft.text),
                            "start": 2,
                            "end": 4,
                            "expected_text": "😀",
                            "presentation": "clue",
                        }
                    ],
                }
            ).reader_presented
        }
    )
    pack = attach(pack_with_hidden(graph), policy, store.get_draft)
    assert "😀" not in canonical_json(preflight_writer_context(pack))
    assert draft.id not in canonical_json(preflight_writer_context(pack))
    bad = policy.model_copy(
        update={"reader_presented": (policy.reader_presented[0].model_copy(update={"start": 3}),)}
    )
    with pytest.raises(ContractError):
        attach(pack_with_hidden(graph), bad, store.get_draft)
    with pytest.raises(ContractError):
        attach(pack_with_hidden(graph), policy, lambda _: draft.model_copy(update={"version": 2}))


def test_policy_private_intent_and_style_are_reviewable_not_canon(graph):
    pack = attach(pack_with_hidden(graph))
    constraint = scene_review_constraint(pack)
    assert "PRIVATE_READER_INFERENCE" in constraint
    assert "author_narrative_visibility_not_canon" in constraint
    assert "HIDDEN_TRUTH_SENTINEL" not in canonical_json(preflight_writer_context(pack))
    assert (
        scene_review_constraint(
            pack.model_copy(update={"writer_visibility": None, "writer_visibility_required": False})
        )
        is None
    )


def test_current_summary_needs_explicit_choice_and_existing_plan(graph):
    pack = pack_with_hidden(graph)
    policy = spec().model_copy(
        update={
            "surface_plan": spec().surface_plan.model_copy(
                update={"kind": "current_scene_summary", "text": None}
            )
        }
    )
    with pytest.raises(ContractError, match="current_plan_unavailable"):
        attach(pack, policy)


def test_overbudget_visible_policy_blocks_without_trimming(graph):
    pack = pack_with_hidden(graph)
    pack.budget = pack.budget.model_copy(update={"target_tokens": 20})
    with pytest.raises(ContractError):
        attach(pack)


def test_agent_prose_uses_same_view_and_blocks_unapproved_free_sources(graph):
    pack = attach(pack_with_hidden(graph))
    surface = preflight_writer_context(pack)["surface_plan"]
    assert preflight_agent_prose(pack, mode="create_scene", instruction=surface)["isolated"]
    for options in (
        {"instruction": "不要泄漏HIDDEN_TRUTH_SENTINEL"},
        {"instruction": surface, "has_additional_sources": True},
        {"instruction": surface, "allow_web_search": True},
        {"instruction": surface, "mode": "continue_scene"},
    ):
        args = {"mode": "create_scene", "instruction": surface, **options}
        with pytest.raises(ContractError):
            preflight_agent_prose(pack, **args)
    assert preflight_agent_prose(pack, mode="discuss", instruction="作者讨论可全知") is None

    class Prose(Capture):
        def generate(self, request):
            self.requests.append(request)
            return LLMResponse(
                json.dumps(
                    {
                        "reply": "已按可见计划起草。",
                        "proposal_title": "合成正文",
                        "proposal_body": "林烬核对门上的刻痕。",
                    },
                    ensure_ascii=False,
                )
            )

    provider = Prose()
    service = AgentDiscussionService(
        provider=provider, model="fixture", project_style={"rubric": ["RAW_STYLE_HIDDEN"]}
    )
    service.discuss(
        project_id="p",
        scene_id="s1",
        instruction=surface,
        mode="create_scene",
        output_language="zh-CN",
        context_pack=pack,
    )
    all_messages = "".join(m.content for m in provider.requests[0].messages)
    assert "RAW_STYLE_HIDDEN" not in all_messages and "HIDDEN_TRUTH_SENTINEL" not in all_messages


def test_hidden_changes_leave_project_template_writer_messages_identical(graph):
    first = attach(pack_with_hidden(graph), scene=False)
    second = pack_with_hidden(graph)
    for entity in second.canon_entities:
        if entity.get("type") == "Secret":
            entity["properties"]["description"] = "CHANGED_PRIVATE_AUTHOR_TRUTH"
    second = attach(second, scene=False)
    a = LLMSceneWriter(provider=None, model="fixture")._messages(first)
    b = LLMSceneWriter(provider=None, model="fixture")._messages(second)
    assert [(m.role, m.content) for m in a] == [(m.role, m.content) for m in b]


def test_project_cast_omits_other_scenes_but_cannot_use_their_claims(graph):
    pack = pack_with_hidden(graph)
    policy = WriterVisibilityPolicy.model_validate(
        {
            **spec().model_dump(),
            "characters": [
                {"character_id": "hero", "public_name": "林烬"},
                {"character_id": "other_scene_actor", "public_name": "另一场的人"},
            ],
        }
    )
    view = preflight_writer_context(attach(pack, policy, scene=False))
    assert view["characters"] == [{"handle": "C1", "public_name": "林烬"}]
    bad = policy.model_copy(
        update={
            "visible_claims": WriterVisibilityPolicy.model_validate(
                {
                    **policy.model_dump(),
                    "visible_claims": [
                        {
                            "text": "另一场角色声称的事。",
                            "presentation": "character_statement",
                            "character_id": "other_scene_actor",
                        }
                    ],
                }
            ).visible_claims
        }
    )
    with pytest.raises(ContractError, match="claim_character_scope"):
        attach(pack_with_hidden(graph), bad, scene=False)


def test_explicit_profile_projection_binding_and_custom_prompt_guard(graph, tmp_path):
    pack = pack_with_hidden(graph)
    policy = WriterVisibilityPolicy.model_validate(
        {
            **spec().model_dump(),
            "writer_style_origin": "profile_projection",
            "writer_style_source_profile_id": "missing_profile",
            "writer_style_source_profile_sha256": "a" * 64,
        }
    )
    with pytest.raises(ContractError, match="style_source_stale"):
        attach(pack, policy)
    pack = attach(pack)
    custom = tmp_path / "private-prompt.md"
    custom.write_text("CUSTOM_PROMPT_PRIVATE", encoding="utf-8")
    provider = Capture()
    with pytest.raises(ContractError, match="custom_prompt"):
        LLMSceneWriter(provider=provider, model="fixture", prompt_path=custom).draft(pack)
    assert not provider.requests


def test_reader_source_is_revalidated_after_resolution(graph):
    store = SQLiteDraftStore()
    draft = store.create_draft(
        project_id="p", scene_id="s1", content_language="zh-CN", text="已呈现文字。"
    )
    policy = WriterVisibilityPolicy.model_validate(
        {
            **spec().model_dump(),
            "reader_presented": [
                {
                    "draft_id": draft.id,
                    "version": 1,
                    "text_sha256": content_hash(draft.text),
                    "start": 0,
                    "end": 2,
                    "expected_text": "已呈",
                    "presentation": "narration",
                }
            ],
        }
    )
    current = [draft]
    pack = attach(pack_with_hidden(graph), policy, lambda _: current[0])
    current[0] = draft.model_copy(update={"text": "已改变原文。"})
    with pytest.raises(ContractError, match="reader_source_stale"):
        preflight_writer_context(pack)


@pytest.mark.parametrize("mode", ["continue_scene", "revise_scene", "revise_selection"])
def test_explicit_edit_grants_send_only_exact_target_and_instruction(graph, mode):
    pack = attach(pack_with_hidden(graph))
    store = SQLiteDraftStore()
    text = "不可发送的前文😀可改片段不可发送的后文"
    draft = store.create_draft(project_id="p", scene_id="s1", content_language="zh-CN", text=text)
    instruction = "只按本次指令写具体。"
    start = len("不可发送的前文😀".encode("utf-16-le")) // 2
    end = start + len("可改片段")
    grant = {
        "instruction": True,
        "instruction_sha256": content_hash(instruction),
        "target": "selection" if mode == "revise_selection" else "draft",
        "draft_id": draft.id,
        "version": draft.version,
        "text_sha256": content_hash(text),
    }
    options = {}
    if mode == "revise_selection":
        grant.update(start=start, end=end, expected_text="可改片段")
        options = {"selected_start": start, "selected_end": end, "selected_text": "可改片段"}

    class Prose(Capture):
        def generate(self, request):
            self.requests.append(request)
            field = {
                "continue_scene": "continuation_text",
                "revise_scene": "proposal_body",
                "revise_selection": "replacement_text",
            }[mode]
            return LLMResponse(
                json.dumps(
                    {
                        "reply": "仅按授权材料写作。",
                        "proposal_title": "合成修订",
                        field: "林烬仔细核对刻痕。",
                    },
                    ensure_ascii=False,
                )
            )

    provider = Prose()
    service = AgentDiscussionService(provider=provider, model="fixture", max_source_chars=3)
    result = service.discuss(
        project_id="p",
        scene_id="s1",
        instruction=instruction,
        mode=mode,
        output_language="zh-CN",
        context_pack=pack,
        latest_draft=draft,
        base_text=text,
        prose_input_grants=grant,
        **options,
    )
    payload = json.loads(provider.requests[0].messages[-1].content)
    task = payload["writer_view"]["writing_task"]
    assert task["instruction"] == instruction
    assert task["target_text"] == ("可改片段" if mode == "revise_selection" else text)
    if mode == "revise_selection":
        assert "不可发送的前文" not in "".join(m.content for m in provider.requests[0].messages)
        assert "不可发送的后文" not in "".join(m.content for m in provider.requests[0].messages)
        assert result.proposal_body == "不可发送的前文😀林烬仔细核对刻痕。不可发送的后文"
    assert draft.id not in provider.requests[0].messages[-1].content
    assert not result.truncated_sources


def test_edit_grants_stale_and_huge_targets_fail_without_provider(graph):
    pack = attach(pack_with_hidden(graph))
    store = SQLiteDraftStore()
    draft = store.create_draft(
        project_id="p", scene_id="s1", content_language="zh-CN", text="当前正文。"
    )
    grant = {
        "instruction": True,
        "instruction_sha256": content_hash("修改。"),
        "target": "draft",
        "draft_id": draft.id,
        "version": draft.version,
        "text_sha256": content_hash(draft.text),
    }
    for changed in ({"version": 2}, {"text_sha256": "0" * 64}, {"instruction_sha256": "1" * 64}):
        with pytest.raises(ContractError):
            preflight_agent_prose(
                pack,
                mode="revise_scene",
                instruction="修改。",
                latest_draft=draft,
                base_text=draft.text,
                prose_input_grants={**grant, **changed},
            )
    huge = draft.model_copy(update={"text": "很长正文。" * 20000})
    with pytest.raises(ContractError, match="budget_exceeded"):
        preflight_agent_prose(
            pack,
            mode="revise_scene",
            instruction="修改。",
            latest_draft=huge,
            base_text=huge.text,
            prose_input_grants={**grant, "text_sha256": content_hash(huge.text)},
        )


def test_legacy_preserves_full_old_input_and_none_context_discussion(graph):
    pack = pack_with_hidden(graph)
    pack.writer_visibility_required = False
    provider = Capture()
    LLMSceneWriter(provider=provider, model="fixture").draft(pack)
    payload = json.loads(provider.requests[0].messages[-1].content)
    assert payload["writer_mode"] == "legacy_unisolated"
    assert payload["context_pack"] == json.loads(pack.model_dump_json())
    assert "HIDDEN_TRUTH_SENTINEL" in provider.requests[0].messages[-1].content
    assert preflight_agent_prose(None, mode="continue_scene", instruction="旧请求") == {
        "isolated": False,
        "access_mode": "legacy_unisolated",
    }


def test_indirectly_relevant_cast_not_current_without_single_explicit_grant(graph):
    graph.seed_canon_node(
        node_id="offstage_actor",
        node_type="Character",
        properties={"project_id": "p", "description": "PRIVATE_OTHER_ACTOR"},
    )
    pack = pack_with_hidden(graph)
    pack.canon_entities.append(
        {
            "id": "offstage_actor",
            "type": "Character",
            "properties": {"description": "PRIVATE_OTHER_ACTOR"},
        }
    )
    policy = WriterVisibilityPolicy.model_validate(
        {
            **spec().model_dump(),
            "characters": [
                {"character_id": "hero", "public_name": "林烬"},
                {"character_id": "offstage_actor", "public_name": "另一人"},
            ],
        }
    )
    with pytest.raises(ContractError, match="character_scope_invalid"):
        attach(pack, policy)
    policy = WriterVisibilityPolicy.model_validate(
        {
            **policy.model_dump(),
            "characters": [
                {"character_id": "hero", "public_name": "林烬"},
                {
                    "character_id": "offstage_actor",
                    "public_name": "另一人",
                    "allow_offstage_name": True,
                },
            ],
        }
    )
    record = WriterVisibilityRecord(
        project_id="p",
        scene_id="s1",
        version=1,
        spec=policy,
        source_context_sha256=writer_source_context_sha256(pack),
        configured_by="fixture",
        configured_at="now",
    )
    pack.writer_visibility = resolve_writer_visibility(
        pack, record, character_scope_resolver=graph.get_node
    )
    view = preflight_writer_context(pack)
    assert view["characters"][1] == {"handle": "C2", "public_name": "另一人"}
    assert "PRIVATE_OTHER_ACTOR" not in canonical_json(view)


def test_protected_rule_based_generator_cannot_write_full_author_context(graph):
    pack = attach(pack_with_hidden(graph))
    with pytest.raises(ContractError, match="rule_based_unsupported"):
        RuleBasedSceneWriter().draft(pack)
    with pytest.raises(ContractError, match="missing_policy"):
        RuleBasedSceneWriter().draft(pack.model_copy(update={"writer_visibility": None}))


def test_profile_projection_cannot_label_changed_style_as_source_projection(graph):
    pack = pack_with_hidden(graph)
    pack.style_constraints = pack.style_constraints.model_copy(
        update={"profile_id": "profile_source", "profile_sha256": "a" * 64}
    )
    value = {
        **spec().model_dump(),
        "writer_style_origin": "profile_projection",
        "writer_style_source_profile_id": "profile_source",
        "writer_style_source_profile_sha256": "a" * 64,
        "writer_style": {"tone": pack.style_constraints.tone},
    }
    assert attach(pack, WriterVisibilityPolicy.model_validate(value)).writer_visibility
    value["writer_style"] = {"tone": "与原来源不同的文风"}
    with pytest.raises(ContractError, match="style_projection_mismatch"):
        attach(
            pack_with_hidden(graph).model_copy(
                update={"style_constraints": pack.style_constraints}
            ),
            WriterVisibilityPolicy.model_validate(value),
        )


def test_factory_preflight_happens_before_provider_construction(graph, monkeypatch):
    from types import SimpleNamespace
    from storygraph.services import scene_writer_factory

    calls = []
    monkeypatch.setattr(scene_writer_factory, "create_llm_provider", lambda _: calls.append(True))
    with pytest.raises(ContractError, match="missing_policy"):
        scene_writer_factory.create_scene_writer(
            SimpleNamespace(resolved_task="writing", scene_writer="llm"),
            None,
            context_pack=pack_with_hidden(graph),
        )
    assert calls == []


def test_canonical_literal_requires_explicit_visible_authorization_before_provider(graph):
    pack = pack_with_hidden(graph)
    pack.must_include = ["必须出现的封蜡线索"]
    with pytest.raises(ContractError, match="required_constraint_not_authorized"):
        attach(pack)
    policy = spec(
        claims=[
            {"text": "必须出现的封蜡线索", "presentation": "observation", "phase": "during_scene"}
        ]
    )
    pack = attach(pack, policy)
    assert preflight_writer_context(pack)["required_literals"] == pack.must_include
    # The original local postcheck is intentionally still present.
    with pytest.raises(ContractError, match="omitted must_include"):
        LLMSceneWriter(provider=Capture(), model="fixture").draft(pack)
