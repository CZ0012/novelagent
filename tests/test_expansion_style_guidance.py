"""Captures prove style guidance is delivered, never that a live model obeys it."""
import copy
import json
import pytest
from storygraph.models.longform import BlueprintRequest, ExpansionRequest, LongformRevisionRequest
from storygraph.models.planning_run import PlanningRunRequest, PlanningRunResume
from storygraph.services.longform_planning import generate_blueprint, generate_expansion, revise_longform, parse_longform, _generation_rules
from test_planning_run import setup as setup
from test_longform_planning import setup as _manual_fixture
from test_longform_planning import accept, apply

manual_setup = _manual_fixture
RULE_MARKER = "Before assigning scene POVs"
STRICT_BRIEF = "第三人称有限视角，每章各场必须同一POV；冷静具体，不进入其他人物内心。"
MULTI_BRIEF = "第三人称有限视角，允许每章跨场切换不同人物POV；每场只写该视角能取得的信息。"


def configure_style(provider, *, multi=False):
    def mutate(result):
        if "entities" in result:
            result["style_brief"]["pov"] = MULTI_BRIEF if multi else STRICT_BRIEF
            result["style_brief"]["rubric"].append("对白使用职业措辞，选择与代价须具体。")
            if multi:
                result["entities"].append({"id": "watcher", "kind": "Character", "name": "守塔人", "description": "维护时钟的守塔人。"})
                arc = copy.deepcopy(result["character_arcs"][0])
                arc["character_id"] = "watcher"
                result["character_arcs"].append(arc)
        elif multi:
            for chapter in result["chapters"]:
                for index, scene in enumerate(chapter["scenes"]):
                    scene["pov_character_id"] = "courier" if index % 2 == 0 else "watcher"
                    scene["required_characters"] = [scene["pov_character_id"]]
    provider.mutate = mutate


def assert_delivery(request, brief, style):
    sent = json.loads(request.messages[-1].content)
    assert sent["phase"] == "expansion"
    assert sent["author_brief"] == brief
    assert sent["blueprint"]["style_brief"] == style
    rule = next(rule for rule in sent["validation_rules"] if RULE_MARKER in rule)
    assert "explicitly require" in rule
    assert "If the supplied style permits multiple POVs" in rule
    assert "do not impose a universal single-POV rule" in rule
    assert "actually observes, receives as evidence or can infer" in rule
    assert "add no self-check fields" in rule
    return sent


def test_actual_run_generation_and_explicit_full_revision_receive_frozen_style(setup):
    provider, service = setup[3], setup[5]
    configure_style(provider)
    run = service.create("book", PlanningRunRequest(instruction=STRICT_BRIEF, volume_count=1,
        chapters_per_volume=2, scenes_per_chapter=2, batch_size=1))
    done = service.execute(run.id)
    assert done.status == "awaiting_review"
    generated = [request for request in provider.calls if json.loads(request.messages[-1].content)["phase"] == "expansion"]
    style = json.loads(generated[0].messages[-1].content)["blueprint"]["style_brief"]
    for request in generated:
        assert_delivery(request, STRICT_BRIEF, style)
    resumed = service.resume("book", run.id, PlanningRunResume(expected_version=done.version,
        restart_from_step=1, revision_mode="full", revision_instruction="保持原情节，按已冻结文风完整修订本批。", preserve_later_outputs=True))
    revised = service.execute(resumed.id)
    assert revised.status == "awaiting_review"
    full = next(request for request in provider.calls if json.loads(request.messages[-1].content).get("revision_mode") == "full")
    assert_delivery(full, STRICT_BRIEF, style)
    assert "source_plan" in json.loads(full.messages[-1].content)
    assert not any(RULE_MARKER in rule for rule in _generation_rules("blueprint"))


@pytest.mark.parametrize("multi", [False, True], ids=["same_pov_required", "multi_pov_permitted"])
def test_actual_manual_generation_and_full_revision_preserve_project_permission(manual_setup, multi):
    graph, store, provider, _ = manual_setup
    provider.chapters_per_volume, provider.scenes_per_chapter = 1, 2
    configure_style(provider, multi=multi)
    brief = MULTI_BRIEF if multi else STRICT_BRIEF
    parent = generate_blueprint(graph=graph, store=store, project_id="project_test",
        request=BlueprintRequest(instruction=brief, volume_count=1, chapters_per_volume=1,
            scenes_per_chapter=2, target_length=10000), provider=provider, model="offline-fixture")["proposal"]
    parent = apply(manual_setup, accept(manual_setup, parent))["proposal"]
    child = generate_expansion(graph=graph, store=store, project_id="project_test",
        request=ExpansionRequest(parent_proposal_id=parent["id"], parent_version=parent["version"],
            volume_index=1, chapter_start=1, chapter_count=1), provider=provider, model="offline-fixture")["proposal"]
    revised = revise_longform(graph=graph, store=store, project_id="project_test", proposal_id=child["id"],
        request=LongformRevisionRequest(expected_version=child["version"], mode="full", instruction="按原文风修订，不改变原许可范围。"),
        provider=provider, model="offline-fixture")["proposal"]
    requests = [request for request in provider.calls if json.loads(request.messages[-1].content)["phase"] == "expansion"]
    assert len(requests) == 2
    style = parse_longform(parent["body"]).blueprint.style_brief.model_dump()
    for request in requests:
        sent = assert_delivery(request, brief, style)
        if multi:
            enum = sent["output_schema"]["$defs"]["ExpansionSceneContent"]["properties"]["pov_character_id"]["enum"]
            assert set(enum) == {"courier", "watcher"}
    assert "source_plan" in json.loads(requests[-1].messages[-1].content)
    expansion = parse_longform(revised["body"]).expansion
    povs = [s.pov_character_id for s in expansion.chapters[0].scenes]
    assert povs == (["courier", "watcher"] if multi else ["courier", "courier"])
