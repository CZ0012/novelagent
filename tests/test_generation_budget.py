from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.models.context import ApprovedScenePlan
from storygraph.services.context_pack_builder import ContextPackBuilder
from storygraph.services.generation_budget import planned_completion_budget
from storygraph.services.scene_writer import LLMSceneWriter


def pack(target=None):
    context = ContextPackBuilder(build_fantasy_demo_graph()).build(
        project_id=PROJECT_ID, scene_id=SCENE_ID,
    )
    if target is not None:
        context.scene_plan = ApprovedScenePlan(target_length=target)
    return context


def test_legacy_and_unplanned_calls_keep_existing_completion_ceiling():
    assert planned_completion_budget(None, baseline=4096) == 4096
    assert planned_completion_budget(pack(), baseline=2048) == 2048


def test_planned_chinese_scene_has_bounded_room_for_prose_and_json_overhead():
    assert planned_completion_budget(pack(2500), baseline=2048) == 6024
    assert planned_completion_budget(pack(200000), baseline=2048) == 16000


def test_scene_writer_uses_target_budget_in_actual_request_without_extra_calls():
    requests = []
    class Provider:
        def generate(self, request):
            requests.append(request)
            raise RuntimeError("synthetic stop after request capture")
    writer = LLMSceneWriter(provider=Provider(), model="fixture")
    import pytest
    with pytest.raises(RuntimeError, match="synthetic stop"):
        writer.draft(pack(2500))
    assert len(requests) == 1
    assert requests[0].max_tokens == 6024
