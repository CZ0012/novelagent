"""Phase prompts describe actual validated projections, not measured model accuracy."""
import json
from storygraph.services.semantic_review import _system_prompt, decoded_plan_content
from storygraph.services.canon_snapshot import content_hash
from test_planning_run import setup as setup
from test_planning_run import create
from test_longform_planning import setup as _manual_fixture
from test_longform_planning import blueprint, accept, apply, expansion
from apps.api.authoring_routes import manual_longform_review_text
from storygraph.services.longform_planning import parse_longform
from storygraph.models.generation_review import GenerationReviewTarget


manual_setup = _manual_fixture

def test_phase_prompt_is_plan_only_and_preserves_semantic_requirements():
    prompt = _system_prompt("zh-CN", "plan")
    for value in ("current_plan.phase", "top-level phase", "review_scope=whole_book_blueprint_and_scene_outcome_ledger",
                  "phase=blueprint", "NOT required inside a blueprint", "phase=expansion",
                  "missing future batches/chapters/scenes are not a required_gap", "all exact_refs",
                  "overall workflow goal", "real upstream contradictions", "proof sufficiency", "citation grounding"):
        assert value in prompt
    assert "PHASE SCOPE" not in _system_prompt("zh-CN", "scene")
    assert "PHASE SCOPE" not in _system_prompt("zh-CN", "unknown")
    # Scene instructions are unaffected by the plan-only clarification.
    assert content_hash(_system_prompt("zh-CN", "scene")) == "6e3b22b6d6c1727ba07ba99ce6fadb6eae4647115b8c5669a5d20c6db0716a7d"
    assert "Never downgrade a real incompatible fact to advice" in prompt
    assert "For every CENTRAL CLAIMED RESOLUTION" in prompt


def test_actual_run_blueprint_expansion_and_final_have_distinct_existing_metadata(setup):
    run = create(setup)
    finished = setup[5].execute(run.id)
    assert finished.status == "awaiting_review"
    payloads = [json.loads(request.messages[-1].content) for request in setup[4].requests]
    assert payloads[0]["plan_content"]["current_plan"]["phase"] == "blueprint"
    assert payloads[0]["plan_content"]["current_plan"]["expansion"] is None
    assert all(p["plan_content"]["current_plan"]["phase"] == "expansion" for p in payloads[1:-1])
    final = payloads[-1]["plan_content"]
    assert final["review_scope"] == "whole_book_blueprint_and_scene_outcome_ledger"
    assert len(final["exact_refs"]) == len(finished.steps)
    assert sum(len(volume["chapters"]) for volume in final["volumes"]) == 4
    assert sum(len(chapter["scenes"]) for volume in final["volumes"] for chapter in volume["chapters"]) == 8
    assert all("PHASE SCOPE" in request.messages[0].content for request in setup[4].requests)


def test_actual_manual_blueprint_and_expansion_resolve_phase_without_new_fields(manual_setup):
    graph, store = manual_setup[:2]
    original = blueprint(manual_setup)
    def projected(proposal):
        stored = store.get(proposal["id"])
        text = manual_longform_review_text(graph=graph, store=store, project_id="project_test",
            proposal=stored, plan=parse_longform(stored.body))
        target = GenerationReviewTarget(project_id="project_test", target_type="proposal", target_id=stored.id,
            target_version=stored.version, purpose="plan", output_language="zh-CN", text=text)
        return decoded_plan_content(target)
    first = projected(original)
    assert first["schema"] == "longform_plan_v1" and first["phase"] == "blueprint"
    assert first["expansion"] is None
    parent = apply(manual_setup, accept(manual_setup, original))["proposal"]
    child = expansion(manual_setup, parent, volume_index=1, chapter_start=1, chapter_count=1)
    second = projected(child)
    assert second["current_plan"]["phase"] == "expansion"
    assert second["volume_progress"]["remaining_chapter_indices"]
