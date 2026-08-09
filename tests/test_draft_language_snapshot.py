import sqlite3

from storygraph.stores.draft_store import SQLiteDraftStore


def test_legacy_draft_is_readable_without_relabeling(tmp_path):
    path = tmp_path / "legacy-drafts.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE drafts (
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL, scene_id TEXT NOT NULL,
          version INTEGER NOT NULL, text TEXT NOT NULL, summary TEXT,
          discarded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "draft_legacy",
            "project_001",
            "scene_001",
            1,
            "Legacy text.",
            None,
            0,
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
    )
    connection.commit()
    connection.close()

    store = SQLiteDraftStore(path)
    legacy = store.get_draft("draft_legacy")
    assert legacy.content_language is None
    assert legacy.language_inferred is True

    updated = store.update_draft("draft_legacy", text="Updated legacy text.")
    assert updated.content_language is None
    assert updated.language_inferred is True

    new_version = store.create_draft(
        project_id="project_001",
        scene_id="scene_001",
        content_language="en-US",
        text="New version.",
    )
    assert new_version.version == 2
    assert new_version.content_language == "en-US"
    assert store.list_versions("project_001", "scene_001")[0].content_language is None
