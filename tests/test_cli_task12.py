from apps.cli.main import (
    build_context_command,
    check_continuity_command,
    extract_state_command,
    init_workspace,
    review_facts_command,
    run_scene_command,
    write_scene_command,
)
from storygraph.demo import ITEM_ID, LOCATION_ID, PROJECT_ID, SCENE_ID
from storygraph.stores.json_graph import load_json_graph


def test_cli_workspace_scene_commands_round_trip(tmp_path):
    workspace = tmp_path / "storygraph"

    init_result = init_workspace(workspace=workspace, force=True)
    assert init_result["created"] is True
    assert init_result["project_id"] == PROJECT_ID

    context = build_context_command(workspace=workspace)
    assert context["contract_version"] == "context_pack_v1"
    assert context["scene_id"] == SCENE_ID

    draft = write_scene_command(workspace=workspace)
    assert draft["project_id"] == PROJECT_ID
    assert draft["scene_id"] == SCENE_ID
    assert draft["version"] == 1

    report = check_continuity_command(workspace=workspace)
    assert report["contract_version"] == "continuity_report_v1"
    assert report["status"] == "pass"

    run = run_scene_command(workspace=workspace)
    assert run["workflow_run"]["contract_version"] == "workflow_run_v1"
    assert run["workflow_run"]["status"] == "completed"


def test_cli_init_force_resets_local_state_files(tmp_path):
    workspace = tmp_path / "storygraph"

    init_workspace(workspace=workspace, force=True)
    first = write_scene_command(workspace=workspace)
    assert first["version"] == 1

    init_workspace(workspace=workspace, force=True)
    second = write_scene_command(workspace=workspace)
    assert second["version"] == 1


def test_cli_extract_state_and_accept_persists_canon_commit(tmp_path):
    workspace = tmp_path / "storygraph"
    init_workspace(workspace=workspace, force=True)
    marker = (
        f"[[fact:id=fact_cli_task12;fact_type=ItemState;subject={ITEM_ID};"
        f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
    )
    write_scene_command(
        workspace=workspace,
        text=f"Lin Jin finds the half black wax seal. {marker}",
        summary="CLI Task 12 marker draft.",
    )

    extracted = extract_state_command(workspace=workspace)
    assert extracted["candidates"][0]["contract_version"] == "candidate_fact_v1"
    assert extracted["candidates"][0]["review"]["status"] == "pending"

    pending = review_facts_command(workspace=workspace)
    assert [fact["id"] for fact in pending["facts"]] == ["fact_cli_task12"]

    accepted = review_facts_command(
        workspace=workspace,
        action="accept",
        fact_id="fact_cli_task12",
        reviewer="editor",
        note="Approved via CLI.",
    )
    assert accepted["candidate"]["status"] == "ACCEPTED_FOR_CANON"
    assert accepted["pending_count"] == 0
    assert accepted["committed_relations"]

    graph = load_json_graph(workspace / "graph.json")
    assert any(
        relation.properties.get("candidate_fact_id") == "fact_cli_task12"
        for relation in graph.relationships.values()
    )


def test_cli_reject_keeps_candidate_out_of_canon(tmp_path):
    workspace = tmp_path / "storygraph"
    init_workspace(workspace=workspace, force=True)
    marker = (
        f"[[fact:id=fact_cli_reject;fact_type=ItemState;subject={ITEM_ID};"
        f"relation=LOCATED_AT;object={LOCATION_ID};confidence=0.95]]"
    )
    write_scene_command(
        workspace=workspace,
        text=f"Rejected marker draft. {marker}",
        summary="CLI rejection marker draft.",
    )
    extract_state_command(workspace=workspace)

    rejected = review_facts_command(
        workspace=workspace,
        action="reject",
        fact_id="fact_cli_reject",
        reviewer="editor",
        note="Not canon.",
    )

    assert rejected["candidate"]["status"] == "REJECTED"
    assert rejected["committed_relations"] == []
    graph = load_json_graph(workspace / "graph.json")
    assert not any(
        relation.properties.get("candidate_fact_id") == "fact_cli_reject"
        for relation in graph.relationships.values()
    )
