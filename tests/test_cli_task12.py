from apps.cli.main import (
    add_character_command,
    add_location_command,
    add_relation_command,
    build_context_command,
    check_continuity_command,
    extract_state_command,
    get_node_command,
    init_workspace,
    query_graph_command,
    review_facts_command,
    run_scene_command,
    write_scene_command,
)
from storygraph.core.errors import GraphStoreError
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


def test_cli_graph_query_commands_read_canon_neighbors(tmp_path):
    workspace = tmp_path / "storygraph"
    init_workspace(workspace=workspace, force=True)

    project = get_node_command(
        workspace=workspace,
        project_id=PROJECT_ID,
        node_id=PROJECT_ID,
    )
    query = query_graph_command(
        workspace=workspace,
        project_id=PROJECT_ID,
        source_id="character_linj",
        edge_labels="KNOWS",
    )

    assert project["id"] == PROJECT_ID
    assert query["source"]["id"] == "character_linj"
    assert query["filters"]["statuses"] == ["CANON"]
    assert [node["id"] for node in query["nodes"]] == ["character_helianya"]
    assert [relation["id"] for relation in query["relationships"]] == [
        "rel_linj_knows_helianya"
    ]


def test_cli_init_force_resets_local_state_files(tmp_path):
    workspace = tmp_path / "storygraph"

    init_workspace(workspace=workspace, force=True)
    first = write_scene_command(workspace=workspace)
    assert first["version"] == 1

    init_workspace(workspace=workspace, force=True)
    second = write_scene_command(workspace=workspace)
    assert second["version"] == 1


def test_cli_author_seed_commands_persist_canon_with_provenance(tmp_path):
    workspace = tmp_path / "storygraph"
    init_result = init_workspace(workspace=workspace, force=True, empty=True, title="Manual Seed")
    project_id = init_result["project_id"]

    character = add_character_command(
        workspace=workspace,
        project_id=project_id,
        node_id="character_mara",
        name="Mara",
        properties_json='{"role":"scout"}',
        reviewer="editor",
        rationale="Seeded from story bible.",
        source_ref="author_seed:story_bible_v1",
    )
    location = add_location_command(
        workspace=workspace,
        project_id=project_id,
        node_id="location_harbor",
        name="Harbor",
        properties_json='{"type":"port"}',
        reviewer="editor",
        rationale="Seeded from story bible.",
        source_ref="author_seed:story_bible_v1",
    )
    relation = add_relation_command(
        workspace=workspace,
        project_id=project_id,
        relation_id="rel_mara_located_at_harbor",
        relation_type="LOCATED_AT",
        source_id="character_mara",
        target_id="location_harbor",
        properties_json='{"scene_id":"scene_seed"}',
        reviewer="editor",
        rationale="Author placed Mara at the harbor.",
        source_ref="author_seed:story_bible_v1",
    )

    assert character["status"] == "CANON"
    assert character["reviewer"] == "editor"
    assert character["rationale"] == "Seeded from story bible."
    assert character["source_ref"] == "author_seed:story_bible_v1"
    assert character["event_id"]
    assert character["properties"]["project_id"] == project_id
    assert location["type"] == "Location"
    assert relation["status"] == "CANON"
    assert relation["properties"]["project_id"] == project_id

    graph = load_json_graph(workspace / "graph.json")
    assert graph.get_node("character_mara").properties["role"] == "scout"
    assert graph.event_log.list()
    assert review_facts_command(workspace=workspace, project_id=project_id)["facts"] == []


def test_cli_author_seed_relation_requires_existing_canon_endpoints(tmp_path):
    workspace = tmp_path / "storygraph"
    init_result = init_workspace(workspace=workspace, force=True, empty=True, title="Manual Seed")

    try:
        add_relation_command(
            workspace=workspace,
            project_id=init_result["project_id"],
            relation_id="rel_missing",
            relation_type="KNOWS",
            source_id="character_missing_a",
            target_id="character_missing_b",
            reviewer="editor",
            rationale="Should fail.",
            source_ref="author_seed:story_bible_v1",
        )
    except GraphStoreError as exc:
        assert exc.category == "not_found"
        assert "Node not found" in str(exc)
    else:
        raise AssertionError("Expected missing relation endpoints to fail")


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
