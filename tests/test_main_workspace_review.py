"""Independent SG-034 navigation review reproductions; no provider or network."""
from storygraph.models.authoring import AuthoringToolAction
from tests.test_authoring_service import make_service


def test_explicit_chapter_destination_does_not_inherit_another_chapters_scene():
    # Current scene belongs to chapter A; Main intentionally opens chapter B.
    service, session = make_service(navigation_validator=lambda *_: None)
    result = service._tool(session,
        AuthoringToolAction(tool="open_workflow", args={"target": "manuscript", "chapter_id": "chapter_b"}),
        navigation_context={"chapter_id": "chapter_a", "scene_id": "scene_a"})
    assert result["navigation"] == {"target": "manuscript", "chapter_id": "chapter_b"}


def test_explicit_scene_destination_does_not_inherit_another_scenes_chapter():
    service, session = make_service(navigation_validator=lambda *_: None)
    result = service._tool(session,
        AuthoringToolAction(tool="open_workflow", args={"target": "writer", "scene_id": "scene_b"}),
        navigation_context={"chapter_id": "chapter_a", "scene_id": "scene_a"})
    assert result["navigation"] == {"target": "writer", "scene_id": "scene_b"}
