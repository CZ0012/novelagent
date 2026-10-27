"""Offline long-form planning acceptance; fixtures contain no author manuscript."""

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.models.longform import BlueprintRequest, ExpansionRequest, LongformApplyRequest, LongformRevisionRequest
from storygraph.services.llm_provider import LLMResponse
from storygraph.services.longform_planning import (
    apply_longform, generate_blueprint, generate_expansion, graph_plan_id, parse_longform,
    scene_plan_id, split_budget, revise_longform,
)
from storygraph.stores.json_graph import load_json_graph, save_json_graph
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.proposal_store import SQLiteProposalStore


SEED = {"source_ref": "test:longform", "reviewer": "author", "rationale": "合成测试设定。"}


class Provider:
    def __init__(self):
        self.calls = []
        self.mutate = None

    def generate(self, request):
        self.calls.append(request)
        payload = json.loads(request.messages[-1].content)
        config = payload["request"]
        if payload["phase"] == "blueprint":
            count = config["volume_count"]
            result = {
                "synopsis": "失去记忆的信使发现城市依靠借来的时间运转，必须在最后的潮汐前偿还代价。",
                "world_rules": [{"id": "time_cost", "domain": "时间", "rule": "每次停止时间都要交出一段真实记忆。"}],
                "entities": [{"id": "courier", "kind": "Character", "name": "林舟", "description": "失去童年记忆的信使。"},
                             {"id": "harbor", "kind": "Location", "name": "旧港", "description": "潮汐控制出入的城市。"}],
                "character_arcs": [{"character_id": "courier", "initial_state": "回避过去。", "desire": "找回姐姐。",
                                    "conflict": "拯救城市需要放弃记忆。", "turning_points": [{"volume_index": 1, "change": "决定追查时钟。"}],
                                    "final_state": "接受失去，选择承担。"}],
                "style_brief": {"name": "简练叙事", "pov": "第三人称有限视角", "tense": "过去时", "tone": "克制",
                                "sentence_rhythm": "短句推动行动，长句留给观察。", "diction": "具体准确。", "dialogue_style": "对话隐藏意图。",
                                "banned_patterns": ["不由得"], "rubric": ["检查动作是否具体，情绪是否通过行为呈现。"]},
                "volumes": [{"index": index, "title": f"第{index}次潮汐", "summary": "信使追查城市的时间来源。",
                             "central_conflict": "记忆与生存的交换。", "climax": "信使开启封存的时钟。", "ending_hook": "时钟指向下一座塔。",
                             "target_length": budget} for index, budget in enumerate(payload["volume_budgets"], 1)],
                "causal_links": [{"id": f"cause_{index}", "from_volume": index, "to_volume": index+1,
                                 "cause": "前一座塔停摆导致潮汐变化。", "effect": "信使必须前往下一座塔。"} for index in range(1, count)],
                "foreshadowing": [{"id": "brass_key", "clue": "没有齿的铜钥匙。", "payoff": "钥匙靠持有者的记忆打开时钟。",
                                   "seed_volume": 1, "payoff_volume": count, "character_ids": ["courier"]}],
            }
        else:
            blueprint = payload["blueprint"]
            volume = config["volume_index"]
            # Blueprint is always a full 1-based chapter grid; fixture can read
            # its stable shape from generated test metadata on this provider.
            cpv, spc = self.chapters_per_volume, self.scenes_per_chapter
            chapters = []
            for chapter in payload["chapter_budgets"]:
                scenes = []
                for index, scene in enumerate(chapter["scenes"], 1):
                    chap = chapter["index"]
                    if index > 1:
                        prev = scene_plan_id(volume, chap, index-1)
                    elif chap > 1:
                        prev = scene_plan_id(volume, chap-1, spc)
                    elif volume > 1:
                        prev = scene_plan_id(volume-1, cpv, spc)
                    else:
                        prev = None
                    scenes.append({"id": scene["id"], "title": "塔中的铜钥匙", "summary": "林舟检查塔中的时钟。",
                                   "goal": "打开封存的门。", "conflict": "开门会失去记忆。", "outcome": "林舟发现门后的线索。",
                                   "emotional_turn": "迟疑转为决心。", "pov_character_id": "courier", "location_id": "harbor",
                                   "required_characters": ["courier"], "timeline_position": f"第{volume}卷第{chap}日",
                                   "target_length": scene["target_length"], "causal_dependencies": [prev] if prev else [],
                                   "foreshadowing_seed_ids": ["brass_key"] if (volume, chap, index) == (1, 1, 1) else [],
                                   "foreshadowing_payoff_ids": ["brass_key"] if (volume, chap, index) == (len(blueprint["volumes"]), cpv, spc) else []})
                chapters.append({"index": chapter["index"], "title": "封存之门", "summary": "林舟在钟塔寻找失踪的人。",
                                 "purpose": "代价推动角色作出选择。", "target_length": chapter["target_length"], "scenes": scenes})
            result = {"volume_index": volume, "chapter_start": config["chapter_start"], "chapters": chapters}
        if self.mutate:
            self.mutate(result)
        return LLMResponse(json.dumps(result, ensure_ascii=False))


@pytest.fixture
def setup(tmp_path):
    graph = InMemoryGraphStore()
    graph.seed_canon_node(node_id="project_test", node_type="Project", properties={"title": "合成小说", "language": "zh-CN"}, **SEED)
    store = SQLiteProposalStore(tmp_path / "proposals.sqlite3")
    provider = Provider()
    provider.chapters_per_volume = 20
    provider.scenes_per_chapter = 2
    return graph, store, provider, tmp_path


def blueprint(setup, **kwargs):
    graph, store, provider, _ = setup
    request = BlueprintRequest(instruction="独立设计一部长篇时间奇幻小说。", **kwargs)
    provider.chapters_per_volume = request.chapters_per_volume
    provider.scenes_per_chapter = request.scenes_per_chapter
    return generate_blueprint(graph=graph, store=store, project_id="project_test", request=request,
                              provider=provider, model="fixture-model")["proposal"]


def accept(setup, proposal):
    return setup[1].review(proposal["id"], decision="accepted", reviewer="author", expected_version=proposal["version"]).model_dump()


def apply(setup, proposal, persist=None):
    graph, store, _, path = setup
    return apply_longform(graph=graph, store=store, project_id="project_test", proposal_id=proposal["id"],
                          request=LongformApplyRequest(expected_version=proposal["version"], reviewer="author"),
                          persist_snapshot=persist or (lambda staged: save_json_graph(staged, path / "graph.json")))


def expansion(setup, parent, **kwargs):
    graph, store, provider, _ = setup
    return generate_expansion(graph=graph, store=store, project_id="project_test", provider=provider, model="fixture-model",
                              request=ExpansionRequest(parent_proposal_id=parent["id"], parent_version=parent["version"], **kwargs))["proposal"]


def creative_expansion(raw):
    return {"chapters": [{key: ([{field: value for field, value in scene.items() if field not in {"id", "target_length"}}
                                for scene in chapter["scenes"]] if key == "scenes" else value)
                          for key, value in chapter.items() if key not in {"index", "target_length"}}
                         for chapter in raw["chapters"]]}


@pytest.mark.parametrize("response_format", ["legacy", "creative"])
def test_500k_plan_recovers_all_batches_without_manuscript_or_unreviewed_canon(setup, response_format):
    graph, store, provider, path = setup
    if response_format == "creative":
        original = provider.generate
        def generate(request):
            response = original(request)
            if json.loads(request.messages[-1].content)["phase"] == "expansion":
                return LLMResponse(json.dumps(creative_expansion(json.loads(response.content)), ensure_ascii=False))
            return response
        provider.generate = generate
    before = len(graph.nodes), len(graph.event_log.list())
    parent = blueprint(setup)
    assert before == (len(graph.nodes), len(graph.event_log.list()))
    body = parse_longform(parent["body"])
    assert sum(v.target_length for v in body.blueprint.volumes) == 500000
    with pytest.raises(GraphStoreError):
        apply(setup, parent)
    parent = apply(setup, accept(setup, parent))["proposal"]
    assert graph.get_node("project_test").properties["style_profile_id"]
    assert any(n.type == "StyleProfile" for n in graph.nodes.values())
    for volume in range(1, 6):
        for start in range(1, 21, 5):
            generated = expansion(setup, parent, volume_index=volume, chapter_start=start)
            assert parse_longform(generated["body"]).expansion.chapters[0].index == start
            saved = accept(setup, generated)
            result = apply(setup, saved)
            assert not result["already_applied"]
            assert apply(setup, saved)["already_applied"]
    scenes = [n for n in graph.nodes.values() if n.type == "Scene"]
    chapters = [n for n in graph.nodes.values() if n.type == "Chapter"]
    assert len(chapters) == 100 and len(scenes) == 200
    assert sum(n.properties["target_length"] for n in scenes) == 500000
    # The synthetic dates reset by volume and provide no strict scene intervals;
    # navigation still has 199 predecessors, but must not become world chronology.
    assert not [r for r in graph.relationships.values() if r.type == "NEXT_SCENE"]
    assert sum(bool(n.properties.get("previous_scene_id")) for n in scenes) == 199
    assert len([r for r in graph.relationships.values() if r.type == "SEEDED_IN"]) == 1
    assert len([r for r in graph.relationships.values() if r.type == "PAID_OFF_IN"]) == 1
    assert len(provider.calls) == 21
    assert len(load_json_graph(path / "graph.json").nodes) == len(graph.nodes)
    assert len(store.list(project_id="project_test")) == 21
    assert not any("prose" in n.properties for n in graph.nodes.values())


@pytest.mark.parametrize("damage", ["mixed_top", "mixed_scene", "wrong_legacy_id", "chapter_count", "scene_count", "missing", "foreign_character", "foreign_location"])
def test_expansion_skeleton_does_not_renumber_or_guess_malformed_model_content(setup, damage):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    graph, store, provider, _ = setup
    original = provider.generate
    def generate(request):
        response = original(request)
        raw = json.loads(response.content)
        if damage == "wrong_legacy_id":
            raw["chapters"][1]["scenes"][0]["id"] = "v01_c001_s01"
        else:
            raw = creative_expansion(raw)
            if damage == "mixed_top":
                raw["volume_index"] = 1
            elif damage == "mixed_scene":
                raw["chapters"][0]["scenes"][0]["id"] = "v01_c001_s01"
            elif damage == "chapter_count":
                raw["chapters"].pop()
            elif damage == "scene_count":
                raw["chapters"][0]["scenes"].pop()
            elif damage == "missing":
                raw["chapters"][0]["scenes"][0].pop("goal")
            elif damage == "foreign_character":
                raw["chapters"][0]["scenes"][0]["pov_character_id"] = "foreign_project_character"
            elif damage == "foreign_location":
                raw["chapters"][0]["scenes"][0]["location_id"] = "courier"
        return LLMResponse(json.dumps(raw, ensure_ascii=False))
    provider.generate = generate
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    with pytest.raises(GraphStoreError):
        expansion(setup, parent, volume_index=1)
    assert (graph.nodes, graph.event_log.list()) == before and len(store.list()) == 1


def test_advertised_creative_schema_has_exact_counts_enums_and_no_model_owned_ids_or_budgets(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    expansion(setup, parent, volume_index=1, chapter_count=3)
    sent = json.loads(setup[2].calls[-1].messages[-1].content)
    schema = sent["output_schema"]
    assert set(schema["properties"]) == {"chapters"}
    assert schema["properties"]["chapters"]["minItems"] == schema["properties"]["chapters"]["maxItems"] == 3
    chapter = schema["$defs"]["ExpansionChapterContent"]["properties"]
    scene = schema["$defs"]["ExpansionSceneContent"]["properties"]
    assert "index" not in chapter and "target_length" not in chapter
    assert "id" not in scene and "target_length" not in scene
    assert chapter["scenes"]["minItems"] == chapter["scenes"]["maxItems"] == 2
    assert scene["pov_character_id"].get("const") == "courier"
    assert scene["location_id"].get("const") == "harbor"
    assert scene["foreshadowing_payoff_ids"]["maxItems"] == 0
    assert "CREATIVE FORMAT ONLY" in " ".join(sent["validation_rules"])
    assert sent["volume_progress"]["chapters_per_volume"] == 20
    assert sent["volume_progress"]["batch_chapter_indices"] == [1, 2, 3]
    assert sent["volume_progress"]["remaining_chapter_indices"] == list(range(4, 21))
    assert sent["volume_progress"]["batch_role"] == "opening"
    assert not sent["volume_progress"]["is_final_batch"]
    assert sent["author_brief"] == parse_longform(parent["body"]).request.instruction


@pytest.mark.parametrize("mutation", [
    lambda b: b["volumes"][0].update(target_length=1),
    lambda b: b["volumes"][0].update(index=2),
    lambda b: b["entities"][1].update(id="courier"),
    lambda b: b["character_arcs"][0].update(character_id="missing"),
    lambda b: b["causal_links"][0].update(from_volume=2, to_volume=1),
    lambda b: b["foreshadowing"][0].update(seed_volume=5, payoff_volume=1),
    lambda b: b["foreshadowing"][0].update(character_ids=["harbor"]),
    lambda b: b["style_brief"].update(tone="This is an obviously English description of the narrative tone."),
    lambda b: b["world_rules"][0].update(rule="   "),
])
def test_invalid_blueprint_never_persists_or_mutates_canon(setup, mutation):
    graph, store, provider, _ = setup
    provider.mutate = mutation
    before = copy.deepcopy(graph.nodes)
    with pytest.raises((ContractError, GraphStoreError, ValueError)):
        blueprint(setup)
    assert graph.nodes == before and store.list() == []


def test_expansion_requires_accepted_applied_exact_parent_and_sequential_batches(setup):
    parent = blueprint(setup)
    provider = setup[2]
    for candidate in (parent, accept(setup, parent)):
        with pytest.raises(GraphStoreError):
            expansion(setup, candidate, volume_index=1)
    parent = apply(setup, setup[1].get(parent["id"]).model_dump())["proposal"]
    for values in ({"volume_index": 2}, {"volume_index": 1, "chapter_start": 6}, {"volume_index": 6}):
        with pytest.raises(GraphStoreError):
            expansion(setup, parent, **values)
    with pytest.raises(GraphStoreError):
        expansion(setup, {**parent, "version": parent["version"]-1}, volume_index=1)
    assert len(provider.calls) == 1


@pytest.mark.parametrize("mutation", [
    lambda b: b["chapters"][0]["scenes"][0].update(pov_character_id="missing"),
    lambda b: b["chapters"][0]["scenes"][0].update(location_id="courier"),
    lambda b: b["chapters"][0]["scenes"][0].update(id="v01_c002_s01"),
    lambda b: b["chapters"][0]["scenes"][0].update(target_length=1),
    lambda b: b["chapters"][0]["scenes"][1].update(causal_dependencies=["v05_c020_s02"]),
    lambda b: b["chapters"][0]["scenes"][1].update(causal_dependencies=[]),
    lambda b: b["chapters"][0]["scenes"][0].update(foreshadowing_payoff_ids=["brass_key"]),
])
def test_invalid_expansion_has_no_partial_output(setup, mutation):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    graph, store, provider, _ = setup
    before = copy.deepcopy(graph.nodes)
    provider.mutate = mutation
    with pytest.raises(GraphStoreError):
        expansion(setup, parent, volume_index=1)
    assert graph.nodes == before and len(store.list()) == 1


def test_first_apply_checks_snapshot_and_immutable_envelope(setup):
    proposal = accept(setup, blueprint(setup))
    graph = setup[0]
    graph.update_node("project_test", {"genre": "悬疑"}, **SEED)
    before = copy.deepcopy(graph.nodes)
    with pytest.raises(GraphStoreError, match="Canon or"):
        apply(setup, proposal)
    assert graph.nodes == before


def test_graph_persistence_failure_publishes_nothing(setup):
    proposal = accept(setup, blueprint(setup))
    graph = setup[0]
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    def fail(_):
        raise OSError("synthetic persistence failure")
    with pytest.raises(OSError):
        apply(setup, proposal, fail)
    assert (graph.nodes, graph.event_log.list()) == before
    assert setup[1].get(proposal["id"]).derived_refs == []


def test_receipt_failure_recovers_after_restart_and_preserves_author_edits(setup, monkeypatch):
    proposal = accept(setup, blueprint(setup))
    graph, store, provider, path = setup
    original = store.record_derived_refs
    monkeypatch.setattr(store, "record_derived_refs", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fixture")))
    with pytest.raises(OSError):
        apply(setup, proposal)
    monkeypatch.setattr(store, "record_derived_refs", original)
    recovered = load_json_graph(path / "graph.json")
    character_id = graph_plan_id(proposal["id"], "character", "courier")
    recovered.update_node(character_id, {"name": "作者新名"}, **SEED)
    event_count = len(recovered.event_log.list())
    result = apply((recovered, store, provider, path), proposal)
    assert result["already_applied"]
    assert recovered.get_node(character_id).properties["name"] == "作者新名"
    assert len(recovered.event_log.list()) == event_count


def test_concurrent_apply_creates_once_and_corrupt_evidence_fails_closed(setup):
    proposal = accept(setup, blueprint(setup))
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(lambda _: apply(setup, proposal), range(2)))
    assert sorted(x["already_applied"] for x in outputs) == [False, True]
    graph = setup[0]
    ref = graph_plan_id(proposal["id"], "character", "courier")
    del graph.nodes[ref]
    with pytest.raises(GraphStoreError):
        apply(setup, proposal)


def test_ending_volume_must_place_clue_targets(setup):
    parent = apply(setup, accept(setup, blueprint(setup, volume_count=1, chapters_per_volume=1, scenes_per_chapter=2)))["proposal"]
    setup[2].mutate = lambda b: b["chapters"][0]["scenes"][1].update(foreshadowing_payoff_ids=[])
    with pytest.raises(GraphStoreError):
        expansion(setup, parent, volume_index=1, chapter_count=1)


def test_budget_remainders_are_exact():
    assert split_budget(500003, 5) == [100001, 100001, 100001, 100000, 100000]


@pytest.mark.parametrize("field,value", [
    ("graph_snapshot", "0"*64), ("project_id", "project_foreign"),
    ("request", {"instruction": "篡改冻结指令。", "target_length": 500000,
                 "volume_count": 5, "chapters_per_volume": 20, "scenes_per_chapter": 2}),
])
def test_revised_envelope_cannot_replace_server_snapshot(setup, field, value):
    proposal = blueprint(setup)
    graph, store, _, _ = setup
    body = json.loads(proposal["body"])
    body[field] = value
    revised = store.revise(proposal["id"], actor="author", body=json.dumps(body, ensure_ascii=False),
                           expected_version=proposal["version"]).model_dump()
    accepted = accept(setup, revised)
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    with pytest.raises(GraphStoreError):
        apply(setup, accepted)
    assert (graph.nodes, graph.event_log.list()) == before


def test_reviewed_authored_changes_are_applied_with_initial_character_state(setup):
    proposal = blueprint(setup)
    body = json.loads(proposal["body"])
    body["blueprint"]["entities"][0]["name"] = "林澄"
    revised = setup[1].revise(proposal["id"], actor="author", body=json.dumps(body, ensure_ascii=False),
                              expected_version=proposal["version"]).model_dump()
    result = apply(setup, accept(setup, revised))
    character = next(n for n in result["nodes"] if n["type"] == "Character")
    assert character["properties"]["name"] == "林澄"
    assert character["properties"]["current_status"] == "回避过去。"
    assert character["properties"]["current_status"] != character["properties"]["character_arc"]["final_state"]
    project = setup[0].get_node("project_test")
    assert project.properties["require_semantic_review"] is True


def test_expansion_chapter_collision_rejected_before_provider(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    graph, _, provider, _ = setup
    graph.seed_canon_node(node_id="chapter_existing", node_type="Chapter",
                          properties={"project_id": "project_test", "chapter_index": 1, "title": "作者旧章"}, **SEED)
    with pytest.raises(GraphStoreError):
        expansion(setup, parent, volume_index=1)
    assert len(provider.calls) == 1


@pytest.mark.parametrize("damage", ["marker_count", "creation_properties", "missing_creation", "missing_marker"])
def test_retry_rejects_corrupt_receipts_even_when_current_objects_exist(setup, damage):
    proposal = accept(setup, blueprint(setup))
    apply(setup, proposal)
    graph = setup[0]
    events = graph.event_log._events
    marker_index = next(i for i, e in enumerate(events) if e.operation == "update_node")
    created_index = next(i for i, e in enumerate(events) if e.operation == "create_node" and e.target != "project_test")
    if damage == "marker_count":
        event = events[marker_index]
        events[marker_index] = event.model_copy(update={"payload": {**event.payload, "longform_application_count": 1}})
    elif damage == "creation_properties":
        event = events[created_index]
        events[created_index] = event.model_copy(update={"payload": {**event.payload, "properties": {"project_id": "project_test"}}})
    else:
        events.pop(created_index if damage == "missing_creation" else marker_index)
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    with pytest.raises(GraphStoreError):
        apply(setup, proposal)
    assert (graph.nodes, graph.event_log.list()) == before


def test_duplicate_canonical_name_not_silently_recreated(setup):
    graph, store, _, _ = setup
    graph.seed_canon_node(node_id="character_author", node_type="Character",
                          properties={"project_id": "project_test", "name": "林舟"}, **SEED)
    proposal = accept(setup, blueprint(setup))
    before = copy.deepcopy(graph.nodes)
    with pytest.raises(GraphStoreError):
        apply(setup, proposal)
    assert graph.nodes == before and store.get(proposal["id"]).derived_refs == []


def test_expansion_apply_stale_after_author_edit_but_proposal_survives_restart(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    proposal = accept(setup, expansion(setup, parent, volume_index=1))
    graph, store, _, path = setup
    graph.update_node("project_test", {"genre": "作者补充设定"}, **SEED)
    before = copy.deepcopy(graph.nodes)
    with pytest.raises(GraphStoreError):
        apply(setup, proposal)
    assert graph.nodes == before
    reopened = SQLiteProposalStore(path / "proposals.sqlite3")
    assert reopened.get(proposal["id"]).body == proposal["body"]


def test_expansion_receipt_recovery_keeps_later_batches(setup, monkeypatch):
    parent = apply(setup, accept(setup, blueprint(setup, volume_count=1, chapters_per_volume=2)))["proposal"]
    first = accept(setup, expansion(setup, parent, volume_index=1, chapter_count=1))
    apply(setup, first)
    second = accept(setup, expansion(setup, parent, volume_index=1, chapter_start=2, chapter_count=1))
    apply(setup, second)
    count = len(setup[0].event_log.list())
    assert apply(setup, first)["already_applied"]
    assert len(setup[0].event_log.list()) == count


def test_provider_receives_cross_field_invariants_not_only_json_schema(setup):
    parent = apply(setup, accept(setup, blueprint(setup, volume_count=1, chapters_per_volume=2)))["proposal"]
    initial = json.loads(setup[2].calls[0].messages[-1].content)
    rules = " ".join(initial["validation_rules"])
    for expected in ("ONE namespace", "EXACTLY ONE arc for EVERY", "strictly ascending", "incoming link",
                     "volume_budgets[i-1] exactly", "JSON array of 1..20 strings",
                     "CausalLink.cause must actually occur within its declared from_volume",
                     "CausalLink.effect summarizes consequences WITHIN to_volume"):
        assert expected in rules
    causal_schema = initial["output_schema"]["$defs"]["CausalLink"]["properties"]
    assert "within from_volume" in causal_schema["cause"]["description"]
    assert "not necessarily immediate" in causal_schema["effect"]["description"]
    first = expansion(setup, parent, volume_index=1, chapter_count=1)
    apply(setup, accept(setup, first))
    expansion(setup, parent, volume_index=1, chapter_start=2, chapter_count=1)
    last = json.loads(setup[2].calls[-1].messages[-1].content)
    assert last["prior_clue_placements"] == [{"scene_id": "v01_c001_s01", "seed_ids": ["brass_key"], "payoff_ids": []}]
    assert "EVERY clue allocated" in " ".join(last["validation_rules"])


def test_generation_proof_controls_apply_to_blueprints_and_expansions_without_new_fields():
    from storygraph.services.longform_planning import _generation_rules
    for phase in ("blueprint", "expansion"):
        rules = " ".join(_generation_rules(phase))
        for expected in ("evidence-to-inference bridge", "EXISTING summary/climax/cause/effect/outcome fields",
                         "custody/authenticity", "original-versus-derived data identity",
                         "not independent corroboration", "not acquired character knowledge"):
            assert expected in rules


def test_known_validation_failure_exposes_only_static_diagnostic_code(setup):
    setup[2].mutate = lambda result: result["character_arcs"].clear()
    # Empty arcs fail schema first. This code contains no provider field values.
    with pytest.raises(GraphStoreError) as invalid:
        blueprint(setup)
    assert invalid.value.reason_code == "output_schema_invalid"
    setup[2].mutate = lambda result: result["entities"].append({"id": "minor", "kind": "Character",
                                                              "name": "私密测试名字", "description": "没有对应弧线。"})
    with pytest.raises(GraphStoreError) as invalid:
        blueprint(setup)
    assert invalid.value.reason_code == "character_arc_coverage"
    assert "私密" not in invalid.value.reason_code and "私密" not in str(invalid.value)


def revise(setup, proposal, **kwargs):
    graph, store, provider, _ = setup
    return revise_longform(graph=graph, store=store, project_id="project_test", proposal_id=proposal["id"],
        request=LongformRevisionRequest(expected_version=proposal["version"], instruction="统一人物线索交付时间，补足可追溯的案件答案。", **kwargs),
        provider=provider, model="fixture-model")["proposal"]


def test_revision_creates_alternative_preserves_source_and_current_canon(setup):
    source = blueprint(setup)
    graph, store, provider, _ = setup
    # Explicit current-canon revalidation permits a new alternative after an
    # author updates context, while the old proposal keeps its stale fingerprint.
    graph.update_node("project_test", {"genre": "悬疑"}, **SEED)
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    provider.mutate = lambda output: output.update(synopsis="信使追查时钟债务，以证据而非巧合锁定责任人。")
    revised = revise(setup, source)
    assert revised["id"] != source["id"] and revised["status"] == "agent_revised" and revised["version"] == 1
    assert store.get(source["id"]).model_dump() == source
    old, new = parse_longform(source["body"]), parse_longform(revised["body"])
    assert new.request == old.request and new.graph_snapshot != old.graph_snapshot
    assert new.blueprint.synopsis != old.blueprint.synopsis
    assert (graph.nodes, graph.event_log.list()) == before
    assert any(ref["kind"] == "proposal_artifact" and ref["ref"] == source["id"]
               and ref["source_span"] == {"version": 1} for ref in revised["source_refs"])
    payload = json.loads(provider.calls[-1].messages[-1].content)
    assert payload["revision_instruction"] and payload["source_plan"] == old.blueprint.model_dump()


def test_revision_stale_version_and_applied_source_rejected_before_call(setup):
    source = blueprint(setup)
    graph, store, provider, _ = setup
    accepted = accept(setup, source)
    with pytest.raises(GraphStoreError):
        revise(setup, source)
    assert len(provider.calls) == 1
    applied = apply(setup, accepted)["proposal"]
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    with pytest.raises(GraphStoreError):
        revise(setup, applied)
    assert len(provider.calls) == 1 and (graph.nodes, graph.event_log.list()) == before


def test_revision_partial_application_without_refs_is_also_rejected(setup, monkeypatch):
    source = accept(setup, blueprint(setup))
    _, store, provider, _ = setup
    monkeypatch.setattr(store, "record_derived_refs", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fixture")))
    with pytest.raises(OSError):
        apply(setup, source)
    with pytest.raises(GraphStoreError):
        revise(setup, source)
    assert len(provider.calls) == 1


def test_revision_revalidates_output_and_detects_graph_change_during_call(setup):
    source = blueprint(setup)
    graph, store, provider, _ = setup
    provider.mutate = lambda output: output["volumes"][0].update(target_length=1)
    with pytest.raises(GraphStoreError):
        revise(setup, source)
    assert len(store.list()) == 1
    provider.mutate = lambda _: graph.update_node("project_test", {"genre": "调用期间修改"}, **SEED)
    with pytest.raises(GraphStoreError):
        revise(setup, source)
    assert len(store.list()) == 1 and store.get(source["id"]).body == source["body"]


def test_expansion_revision_preserves_accepted_parent_and_batch(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    source = expansion(setup, parent, volume_index=1)
    revised = revise(setup, source)
    old, new = parse_longform(source["body"]), parse_longform(revised["body"])
    assert new.phase == "expansion" and new.request == old.request
    assert new.parent_proposal_id == parent["id"] and new.parent_version == parent["version"]
    assert new.expansion == old.expansion
    assert {r["ref"] for r in revised["source_refs"] if r["kind"] == "proposal_artifact"} == {source["id"], parent["id"]}


def test_full_expansion_revision_accepts_creative_only_response_with_same_server_slots(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    source = expansion(setup, parent, volume_index=1)
    original = setup[2].generate
    def creative(request):
        response = original(request)
        return LLMResponse(json.dumps(creative_expansion(json.loads(response.content)), ensure_ascii=False))
    setup[2].generate = creative
    before = copy.deepcopy(setup[0].nodes), list(setup[0].event_log.list())
    alternative = revise(setup, source)
    assert alternative["id"] != source["id"]
    assert parse_longform(alternative["body"]).expansion == parse_longform(source["body"]).expansion
    assert (setup[0].nodes, setup[0].event_log.list()) == before
    assert "服务端骨架" in alternative["provenance"]["note"]
    sent = json.loads(setup[2].calls[-1].messages[-1].content)
    assert sent["volume_progress"]["chapters_per_volume"] == 20
    assert sent["volume_progress"]["remaining_chapter_indices"] == list(range(6, 21))
    assert sent["author_brief"] == parse_longform(parent["body"]).request.instruction


def test_manual_expansion_and_revision_keep_exact_prior_timeline_anchors(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    first = expansion(setup, parent, volume_index=1)
    apply(setup, accept(setup, first))
    graph = setup[0]
    prior_id = graph_plan_id(parent["id"], "scene", "v01_c005_s02")
    anchor = "事件第5日22:30；记录次日09:20上传；允许明确标注的回溯。"
    graph.update_node(prior_id, {"timeline_position": anchor}, **SEED)
    next_batch = expansion(setup, parent, volume_index=1, chapter_start=6)
    generated = json.loads(setup[2].calls[-1].messages[-1].content)
    assert generated["recent_scene_outcomes"][-1]["id"] == "v01_c005_s02"
    assert generated["recent_scene_outcomes"][-1]["timeline_position"] == anchor
    ledger = generated["prior_scene_outcome_ledger"]
    assert len(ledger["scenes"]) == 10 and ledger["scenes"][-1]["timeline_position"] == anchor
    assert ledger["scenes"][-1]["pov_character_id"] == "courier" and ledger["scenes"][-1]["location_id"] == "harbor"
    revise(setup, next_batch)
    revised = json.loads(setup[2].calls[-1].messages[-1].content)
    assert revised["recent_scene_outcomes"][-1]["timeline_position"] == anchor
    assert revised["prior_scene_outcome_ledger"] == ledger
    rules = " ".join(revised["validation_rules"])
    assert "a new batch does not restart the incident day count" in rules
    assert "Explicit nonlinear narration/flashback is permitted" in rules


def test_first_application_hook_is_atomic_and_completed_retry_skips_it(setup):
    source = accept(setup, blueprint(setup))
    graph, store, _, _ = setup
    before = copy.deepcopy(graph.nodes), list(graph.event_log.list())
    def blocked():
        raise GraphStoreError("generation_review_required", "A passing review is required.")
    args = dict(graph=graph, store=store, project_id="project_test", proposal_id=source["id"],
        request=LongformApplyRequest(expected_version=source["version"], reviewer="author", review_id="review_fixture"),
        persist_snapshot=lambda _: None)
    with pytest.raises(GraphStoreError):
        apply_longform(**args, before_apply=blocked)
    assert (graph.nodes, graph.event_log.list()) == before and store.get(source["id"]).derived_refs == []
    calls = []
    result = apply_longform(**args, before_apply=lambda: calls.append(True))
    assert calls == [True] and not result["already_applied"]
    assert apply_longform(**args, before_apply=blocked)["already_applied"]


def baseline_entities(output):
    output["entities"][0]["initial_state"] = {"life_status": "alive", "physical_state": "injured", "location_id": "harbor"}
    output["entities"].append({"id": "watch", "kind": "Item", "name": "旧怀表", "description": "刻有编号的怀表。",
                               "initial_state": {"location_id": "harbor", "owner_id": "courier"}})


def test_explicit_initial_states_map_local_references_to_reviewed_graph_baselines(setup):
    setup[2].mutate = baseline_entities
    source = blueprint(setup)
    graph = setup[0]
    assert not any(n.type == "Character" for n in graph.nodes.values())
    result = apply(setup, accept(setup, source))
    properties = {node["type"]: node["properties"] for node in result["nodes"]}
    assert properties["Character"]["initial_state"] == {"life_status": "alive", "physical_state": "injured",
        "location_id": graph_plan_id(source["id"], "location", "harbor")}
    assert properties["Item"]["initial_state"] == {"location_id": graph_plan_id(source["id"], "location", "harbor"),
                                                  "owner_id": graph_plan_id(source["id"], "character", "courier")}


@pytest.mark.parametrize("kind,state", [
    ("Character", {"owner_id": None}), ("Location", {"life_status": "alive"}),
    ("Item", {"physical_state": "healthy"}), ("Character", {"life_status": "immortal"}),
    ("Character", {"life_status": None}), ("Character", {"location_id": None}),
    ("Character", {"location_id": "foreign_location"}), ("Character", {"location_id": "courier"}),
    ("Character", {"life_status": "alive", "freeform_status": "hidden"}),
    ("Item", {"owner_id": "harbor"}),
])
def test_invalid_initial_states_never_persist_or_guess_foreign_scope(setup, kind, state):
    def mutate(output):
        if kind == "Item":
            output["entities"].append({"id": "watch", "kind": kind, "name": "旧怀表", "description": "合成物品。", "initial_state": state})
        else:
            target = output["entities"][0 if kind == "Character" else 1]
            target["initial_state"] = state
    setup[2].mutate = mutate
    with pytest.raises(GraphStoreError):
        blueprint(setup)
    assert setup[1].list() == [] and len(setup[0].nodes) == 1


def test_explicit_unowned_is_preserved_while_absent_life_and_location_stay_unknown(setup):
    setup[2].mutate = lambda output: output["entities"].append({"id": "watch", "kind": "Item", "name": "旧怀表",
        "description": "无人持有的怀表。", "initial_state": {"owner_id": None}})
    source = blueprint(setup)
    result = apply(setup, accept(setup, source))
    item = next(n for n in result["nodes"] if n["type"] == "Item")
    character = next(n for n in result["nodes"] if n["type"] == "Character")
    assert item["properties"]["initial_state"] == {"owner_id": None}
    assert "initial_state" not in character["properties"]


def test_legacy_omitted_baseline_keeps_receipt_hash_and_retry_after_reload(setup):
    source = blueprint(setup)
    body = json.loads(source["body"])
    assert all("initial_state" not in e for e in body["blueprint"]["entities"])
    # This is the canonical hash produced before EntityPlan gained the optional
    # field. New parsing must serialize identically, not add null/default slots.
    old_hash = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert parse_longform(source["body"]).model_dump(by_alias=True) == body
    accepted = accept(setup, source)
    result = apply(setup, accepted)
    graph, store, provider, path = setup
    expected_source = f"proposal:{source['id']}:longform:{old_hash}"
    assert any(e.source_ref == expected_source for e in graph.event_log.list())
    assert all("initial_state" not in n["properties"] for n in result["nodes"])
    reloaded = load_json_graph(path / "graph.json")
    before = list(reloaded.event_log.list())
    retry = apply((reloaded, store, provider, path), accepted)
    assert retry["already_applied"] and reloaded.event_log.list() == before


def targeted_output(provider, changes, side_effect=None):
    def mutate(output):
        if side_effect:
            side_effect()
        output.clear()
        output.update(changes=changes)
    provider.mutate = mutate


def test_targeted_revision_only_replaces_explicit_authored_leaves(setup):
    source = blueprint(setup)
    original = json.loads(source["body"])
    after = "信使先核对时钟记录，再凭可追溯的证据揭开城市的债务。"
    targeted_output(setup[2], [{"path": "/blueprint/synopsis", "before": original["blueprint"]["synopsis"], "after": after}])
    revised = revise(setup, source, mode="targeted")
    expected = copy.deepcopy(original)
    expected["blueprint"]["synopsis"] = after
    assert json.loads(revised["body"]) == expected
    assert setup[1].get(source["id"]).model_dump() == source
    payload = json.loads(setup[2].calls[-1].messages[-1].content)
    assert "/blueprint/synopsis" in payload["allowed_paths"]
    assert "/blueprint/style_brief/rubric/0" in payload["allowed_paths"]
    assert all(not p.endswith(("/id", "/kind", "/target_length", "/character_id", "/life_status")) for p in payload["allowed_paths"])
    assert "smallest set of edits" in " ".join(payload["validation_rules"])


@pytest.mark.parametrize("path,before", [
    ("/blueprint/entities/0/id", "courier"), ("/blueprint/entities/0/kind", "Character"),
    ("/blueprint/volumes/0/target_length", "100000"),
    ("/blueprint/entities/0/initial_state/life_status", "alive"),
    ("/blueprint/foreshadowing/0/character_ids/0", "courier"),
    ("/request/instruction", "explicit instruction"),
    ("/blueprint/../request/instruction", "explicit instruction"),
    ("/blueprint/__proto__/title", "unavailable"),
    ("/blueprint/entities/99/name", "missing"),
    ("/blueprint/volumes/0/title~1id", "invalid"),
])
def test_targeted_revision_rejects_machine_fields_and_path_traversal(setup, path, before):
    source = blueprint(setup)
    targeted_output(setup[2], [{"path": path, "before": before, "after": "不应采用的改动。"}])
    with pytest.raises(GraphStoreError) as invalid:
        revise(setup, source, mode="targeted")
    assert invalid.value.reason_code == "targeted_path"
    assert len(setup[1].list()) == 1


@pytest.mark.parametrize("case", ["stale_before", "duplicate", "unchanged", "too_long", "too_many"])
def test_targeted_revision_rejects_unbounded_or_inexact_changes(setup, case):
    source = blueprint(setup)
    body = json.loads(source["body"])["blueprint"]
    change = {"path": "/blueprint/volumes/0/title", "before": body["volumes"][0]["title"], "after": "新的卷名"}
    changes = [change]
    if case == "stale_before":
        change["before"] += " "
    elif case == "duplicate":
        changes.append(copy.deepcopy(change))
    elif case == "unchanged":
        change["after"] = change["before"]
    elif case == "too_long":
        change["after"] = "新"*121
    else:
        changes *= 41
    targeted_output(setup[2], changes)
    with pytest.raises(GraphStoreError):
        revise(setup, source, mode="targeted")
    assert len(setup[1].list()) == 1 and setup[1].get(source["id"]).model_dump() == source


def test_targeted_revision_still_rejects_source_race_after_explicit_call(setup):
    source = blueprint(setup)
    before = json.loads(source["body"])["blueprint"]["synopsis"]
    targeted_output(setup[2], [{"path": "/blueprint/synopsis", "before": before, "after": "新的因果链规划。"}],
        side_effect=lambda: setup[1].mark_ready(source["id"], actor="author", expected_version=source["version"]))
    with pytest.raises(GraphStoreError):
        revise(setup, source, mode="targeted")
    assert len(setup[1].list()) == 1


def test_targeted_expansion_revision_keeps_budget_refs_and_parent(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    source = expansion(setup, parent, volume_index=1)
    body = json.loads(source["body"])
    path = "/expansion/chapters/0/scenes/0/outcome"
    targeted_output(setup[2], [{"path": path, "before": body["expansion"]["chapters"][0]["scenes"][0]["outcome"],
                               "after": "林舟核对编号，排除了一条伪造线索。"}])
    revised = revise(setup, source, mode="targeted")
    expected = copy.deepcopy(body)
    expected["expansion"]["chapters"][0]["scenes"][0]["outcome"] = "林舟核对编号，排除了一条伪造线索。"
    assert json.loads(revised["body"]) == expected


def test_targeted_exact_noop_is_reported_and_skipped_when_real_change_exists(setup):
    source = blueprint(setup)
    body = json.loads(source["body"])
    synopsis = body["blueprint"]["synopsis"]
    title = body["blueprint"]["volumes"][0]["title"]
    targeted_output(setup[2], [{"path": "/blueprint/synopsis", "before": synopsis, "after": synopsis},
        {"path": "/blueprint/volumes/0/title", "before": title, "after": "修订卷名"}])
    result = revise_longform(graph=setup[0], store=setup[1], project_id="project_test", proposal_id=source["id"],
        request=LongformRevisionRequest(expected_version=source["version"], instruction="只改卷名。", mode="targeted"),
        provider=setup[2], model="fixture-model")
    assert result["skipped_noop_paths"] == ["/blueprint/synopsis"]
    expected = copy.deepcopy(body)
    expected["blueprint"]["volumes"][0]["title"] = "修订卷名"
    assert json.loads(result["proposal"]["body"]) == expected


def test_targeted_unique_subspan_preserves_surrounding_text_with_full_field_edit(setup):
    source = blueprint(setup)
    body = json.loads(source["body"])
    synopsis = body["blueprint"]["synopsis"]
    snippet = "必须在最后的潮汐前偿还代价。"
    assert synopsis.count(snippet) == 1
    title = body["blueprint"]["volumes"][0]["title"]
    targeted_output(setup[2], [{"path": "/blueprint/synopsis", "before": snippet, "after": "必须先查清债务来源再偿还代价。"},
        {"path": "/blueprint/volumes/0/title", "before": title, "after": "核对记录"}])
    revised = revise(setup, source, mode="targeted")
    expected = copy.deepcopy(body)
    expected["blueprint"]["synopsis"] = synopsis.replace(snippet, "必须先查清债务来源再偿还代价。")
    expected["blueprint"]["volumes"][0]["title"] = "核对记录"
    assert json.loads(revised["body"]) == expected


def test_targeted_repeated_and_overlapping_subspan_never_guesses_occurrence(setup):
    for text, span in (("重复段落。重复段落。", "重复段落。"), ("哈哈哈", "哈哈")):
        setup[2].mutate = lambda output: output.update(synopsis=text)
        source = blueprint(setup)
        targeted_output(setup[2], [{"path": "/blueprint/synopsis", "before": span, "after": "替换文字。"}])
        count = len(setup[1].list())
        with pytest.raises(GraphStoreError):
            revise(setup, source, mode="targeted")
        assert len(setup[1].list()) == count


def explicit_knowledge(output):
    output["entities"].append({"id": "secret_clock_origin", "kind": "Secret", "name": "时钟来历",
        "description": "时钟靠交换记忆维持运转。"})
    output["entities"][0]["initial_knowledge"] = ["secret_clock_origin"]


def test_reviewed_explicit_initial_knowledge_becomes_same_project_secret_edge(setup):
    setup[2].mutate = explicit_knowledge
    source = blueprint(setup)
    graph = setup[0]
    assert not graph.relationships
    result = apply(setup, accept(setup, source))
    edges = [r for r in result["relationships"] if r["type"] == "KNOWS_SECRET"]
    assert len(edges) == 1
    character_id = graph_plan_id(source["id"], "character", "courier")
    secret_id = graph_plan_id(source["id"], "secret", "secret_clock_origin")
    assert edges[0]["source_id"] == character_id and edges[0]["target_id"] == secret_id
    assert edges[0]["properties"] == {"project_id": "project_test", "known": True,
        "initial_knowledge": True, "longform_blueprint_id": source["id"]}
    assert secret_id in graph.get_character_knowledge(character_id).knows
    assert edges[0]["reviewer"] == "author" and edges[0]["source_ref"].startswith(f"proposal:{source['id']}:longform:")
    assert any(event.target == edges[0]["id"] and event.operation == "create_relation" for event in graph.event_log.list())
    count = len(graph.event_log.list())
    assert apply(setup, accept_existing := setup[1].get(source["id"]).model_dump())["already_applied"]
    assert len(graph.event_log.list()) == count and accept_existing["status"] == "accepted"


@pytest.mark.parametrize("kind,refs", [("Location", []), ("Secret", []), ("Character", ["missing_secret"]),
    ("Character", ["harbor"]), ("Character", ["courier"]),
    ("Character", ["secret_clock_origin", "secret_clock_origin"])])
def test_initial_knowledge_rejects_wrong_kind_unknown_scope_and_duplicate_ids(setup, kind, refs):
    def mutate(output):
        explicit_knowledge(output)
        target = output["entities"][0] if kind == "Character" else next(e for e in output["entities"] if e["kind"] == kind)
        target["initial_knowledge"] = refs
    setup[2].mutate = mutate
    with pytest.raises(GraphStoreError):
        blueprint(setup)
    assert len(setup[0].nodes) == 1 and not setup[0].relationships and setup[1].list() == []


def test_missing_or_empty_initial_knowledge_never_infers_from_author_dossier(setup):
    def mutate(output):
        explicit_knowledge(output)
        output["entities"][0].pop("initial_knowledge")
        output["entities"][0]["description"] = "角色描述中说他知道时钟来历，但没有结构化初始知识声明。"
    setup[2].mutate = mutate
    source = blueprint(setup)
    assert "initial_knowledge" not in json.loads(source["body"])["blueprint"]["entities"][0]
    result = apply(setup, accept(setup, source))
    assert not any(r["type"] == "KNOWS_SECRET" for r in result["relationships"])
    setup[2].mutate = lambda output: (explicit_knowledge(output), output["entities"][0].update(initial_knowledge=[]))
    second = blueprint(setup)
    assert json.loads(second["body"])["blueprint"]["entities"][0]["initial_knowledge"] == []


def test_old_receipt_serialization_omits_added_initial_knowledge_and_reloads(setup):
    source = blueprint(setup)
    body = json.loads(source["body"])
    assert all("initial_knowledge" not in e for e in body["blueprint"]["entities"])
    assert parse_longform(source["body"]).model_dump(by_alias=True) == body
    accepted = accept(setup, source)
    apply(setup, accepted)
    graph, store, provider, path = setup
    reloaded = load_json_graph(path/"graph.json")
    count = len(reloaded.event_log.list())
    assert apply((reloaded, store, provider, path), accepted)["already_applied"]
    assert len(reloaded.event_log.list()) == count


def source_with_known_secrets(setup, known):
    def mutate(output):
        explicit_knowledge(output)
        output["entities"].append({"id": "secret_second", "kind": "Secret", "name": "第二项秘密", "description": "时钟的编号来自旧港。"})
        output["entities"][0]["initial_knowledge"] = known
    setup[2].mutate = mutate
    return blueprint(setup)


@pytest.mark.parametrize("before,after", [
    (["secret_clock_origin"], ["secret_clock_origin", "secret_second"]),
    (["secret_clock_origin", "secret_second"], ["secret_clock_origin"]),
    (None, []), (None, ["secret_clock_origin"]), ([], None),
])
def test_targeted_initial_knowledge_changes_only_exact_character_list(setup, before, after):
    source = source_with_known_secrets(setup, before)
    old = json.loads(source["body"])
    targeted_output(setup[2], [{"path": "/blueprint/entities/0/initial_knowledge", "before": before, "after": after}])
    revised = revise(setup, source, mode="targeted")
    expected = copy.deepcopy(old)
    if after is None:
        expected["blueprint"]["entities"][0].pop("initial_knowledge", None)
    else:
        expected["blueprint"]["entities"][0]["initial_knowledge"] = after
    assert json.loads(revised["body"]) == expected
    assert setup[1].get(source["id"]).model_dump() == source and len(setup[0].nodes) == 1
    sent = json.loads(setup[2].calls[-1].messages[-1].content)
    assert sent["current_values"]["/blueprint/entities/0/initial_knowledge"] == before


@pytest.mark.parametrize("path,before,after", [
    ("/blueprint/entities/0/initial_knowledge", [], ["secret_second"]),
    ("/blueprint/entities/0/initial_knowledge", ["secret_clock_origin"], ["missing_secret"]),
    ("/blueprint/entities/0/initial_knowledge", ["secret_clock_origin"], ["courier"]),
    ("/blueprint/entities/0/initial_knowledge", ["secret_clock_origin"], ["secret_second", "secret_second"]),
    ("/blueprint/entities/0/initial_knowledge", "secret_clock_origin", ["secret_second"]),
    ("/blueprint/entities/0/initial_knowledge", ["secret_clock_origin"], "secret_second"),
    ("/blueprint/entities/1/initial_knowledge", None, ["secret_second"]),
    ("/blueprint/foreshadowing/0/character_ids", ["courier"], []),
    ("/blueprint/style_brief/rubric", ["检查动作是否具体，情绪是否通过行为呈现。"], []),
    ("/blueprint/entities/0/description", ["secret_clock_origin"], None),
])
def test_targeted_knowledge_exception_rejects_wrong_kind_ref_duplicate_before_and_generic_arrays(setup, path, before, after):
    source = source_with_known_secrets(setup, ["secret_clock_origin"])
    targeted_output(setup[2], [{"path": path, "before": before, "after": after}])
    count = len(setup[1].list())
    with pytest.raises(GraphStoreError):
        revise(setup, source, mode="targeted")
    assert len(setup[1].list()) == count and setup[1].get(source["id"]).model_dump() == source


def creative_replacement_output(provider, replacements, side_effect=None):
    def mutate(output):
        if side_effect:
            side_effect()
        output.clear()
        output.update(replacements=replacements)
    provider.mutate = mutate


def test_creative_revision_materializes_before_from_frozen_source_and_changes_only_whole_leaf(setup):
    source = blueprint(setup)
    old = json.loads(source["body"])
    after = old["blueprint"]["synopsis"]+"新证据必须经过独立核验。"
    creative_replacement_output(setup[2], [{"path": "/blueprint/synopsis", "after": after}])
    revised = revise(setup, source, mode="targeted")
    expected = copy.deepcopy(old)
    expected["blueprint"]["synopsis"] = after
    assert json.loads(revised["body"]) == expected and setup[1].get(source["id"]).model_dump() == source
    sent = json.loads(setup[2].calls[-1].messages[-1].content)
    assert set(sent["output_schema"]["properties"]) == {"replacements"}
    replacement = sent["output_schema"]["$defs"]["CreativeRevisionReplacement"]["properties"]
    assert set(replacement) == {"path", "after"} and sent["current_values"]["/blueprint/synopsis"] == old["blueprint"]["synopsis"]


def test_creative_revision_allows_only_declared_typed_knowledge_list(setup):
    source = source_with_known_secrets(setup, None)
    creative_replacement_output(setup[2], [{"path": "/blueprint/entities/0/initial_knowledge", "after": ["secret_second"]}])
    revised = revise(setup, source, mode="targeted")
    assert json.loads(revised["body"])["blueprint"]["entities"][0]["initial_knowledge"] == ["secret_second"]
    assert "initial_knowledge" not in json.loads(source["body"])["blueprint"]["entities"][0]


@pytest.mark.parametrize("case", ["unknown_path", "wrong_type", "unknown_secret", "duplicate_path", "extra_before", "mixed_format"])
def test_creative_revision_rejects_unknown_mixed_or_out_of_scope_replacements(setup, case):
    source = source_with_known_secrets(setup, [])
    replacements = [{"path": "/blueprint/synopsis", "after": "新的调查顺序。"}]
    if case == "unknown_path":
        replacements[0]["path"] = "/blueprint/entities/0/id"
    elif case == "wrong_type":
        replacements[0]["after"] = ["secret_second"]
    elif case == "unknown_secret":
        replacements[0] = {"path": "/blueprint/entities/0/initial_knowledge", "after": ["missing_secret"]}
    elif case == "duplicate_path":
        replacements.append(copy.deepcopy(replacements[0]))
    elif case == "extra_before":
        replacements[0]["before"] = "额外字段不能被悄悄删除。"
    creative_replacement_output(setup[2], replacements)
    if case == "mixed_format":
        setup[2].mutate = lambda output: (output.clear(), output.update(replacements=replacements, changes=[]))
    count = len(setup[1].list())
    with pytest.raises(GraphStoreError):
        revise(setup, source, mode="targeted")
    assert len(setup[1].list()) == count and setup[1].get(source["id"]).model_dump() == source


def test_creative_revision_never_salvages_invented_before_from_complete_legacy_format(setup):
    parent = apply(setup, accept(setup, blueprint(setup)))["proposal"]
    source = expansion(setup, parent, volume_index=1)
    scene_text = json.loads(source["body"])["expansion"]["chapters"][0]["scenes"][0]["summary"]
    chapter_text = json.loads(source["body"])["expansion"]["chapters"][0]["summary"]
    assert scene_text not in chapter_text
    targeted_output(setup[2], [{"path": "/expansion/chapters/0/summary", "before": scene_text, "after": "改写后的整章摘要。"}])
    with pytest.raises(GraphStoreError) as invalid:
        revise(setup, source, mode="targeted")
    assert invalid.value.reason_code == "targeted_before_mismatch"
