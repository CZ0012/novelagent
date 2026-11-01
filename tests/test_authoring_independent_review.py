"""Independent acceptance checks for author collaboration safety boundaries."""
import pytest
from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringWorkspace, AuthoringPatch
from storygraph.services.authoring import AuthoringService
from storygraph.services.canon_snapshot import content_hash
from storygraph.stores.authoring_store import SQLiteAuthoringStore
from storygraph.stores.proposal_store import SQLiteProposalStore


def setup_session(**kwargs):
    service = AuthoringService(store=SQLiteAuthoringStore(SQLiteProposalStore()), **kwargs)
    return service, service.create(project_id="p", content_language="en-US", title="Design", idea="A clock stops.")


def card(**extra):
    return {"id": "card", "title": "Clock", "scene_id": "scene", "pov_character_id": "actor", "status": "approved",
            "writer_policy": {"access_mode": "surface", "surface_plan": {"kind": "literal", "text": "The actor searches the clock."}, "writer_style": {}}, **extra}


def test_adoption_rechecks_selected_source_freshness():
    source = ["Original source."]
    service = AuthoringService(store=SQLiteAuthoringStore(SQLiteProposalStore()), source_resolver=lambda p, pin: source[0])
    session = service.create(project_id="p", content_language="en-US", title="Design", idea="A clock stops.",
        source_pins=[{"kind": "source_document", "id": "source", "sha256": content_hash(source[0])}])
    service._propose(session, AuthoringPatch(upsert_items=[{"id":"clock", "kind":"world_fact", "text":"The clock stops."}]), "Design the clock.")
    session = service._save(session)
    source[0] = "Replaced source."
    with pytest.raises(ContractError):
        service.review(project_id="p", session_id=session.id, expected_version=session.version, proposal_id=session.proposals[0].id, decision="adopted")


def test_removed_item_cannot_leave_dangling_card_knowledge_reference():
    service, session = setup_session()
    session.workspace = AuthoringWorkspace(items=[{"id":"clue", "kind":"world_fact", "text":"A red mark."}],
        scene_cards=[card(entry_knowledge=[{"character_id":"actor", "item_id":"clue", "text":"A red mark."}])])
    with pytest.raises(ContractError):
        service._propose(session, AuthoringPatch(remove_item_ids=["clue"]), "Remove the clue.")


def test_changed_character_goal_invalidates_approved_actor_card():
    service, session = setup_session()
    session.workspace = AuthoringWorkspace(character_plans=[{"character_id":"actor", "goal":"Find the missing clock."}], scene_cards=[card()])
    result = service._propose(session, AuthoringPatch(upsert_character_plans=[{"character_id":"actor", "goal":"Destroy the clock."}]), "Change the actor goal.")
    session = service._save(session)
    adopted = service.review(project_id="p", session_id=session.id, expected_version=session.version,
        proposal_id=result["proposal_id"], decision="adopted")
    assert adopted.workspace.scene_cards[0].status == "proposed"


def test_changed_upstream_card_invalidates_explicit_dependent_card():
    service, session = setup_session()
    session.workspace = AuthoringWorkspace(scene_cards=[card(), card(id="dependent", depends_on=["card"])])
    result = service._propose(session, AuthoringPatch(upsert_scene_cards=[card(status="proposed", title="Changed clock")]), "Change the upstream card.")
    session = service._save(session)
    adopted = service.review(project_id="p", session_id=session.id, expected_version=session.version,
        proposal_id=result["proposal_id"], decision="adopted")
    assert adopted.workspace.scene_cards[1].status == "proposed"
